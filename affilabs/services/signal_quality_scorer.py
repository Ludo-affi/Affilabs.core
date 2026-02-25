"""Signal Quality Scorer — Phase 5 of SIGNAL_EVENT_CLASSIFIER_FRS.

Scores each completed acquisition cycle (0–100) and produces a run-level
star rating (1–5) at session end.

Design:
- ``SignalQualityScorer`` is a QObject singleton wired into the app at startup.
- It receives per-frame telemetry via ``record_frame()`` (called from
  SignalTelemetryLogger hook or spectrum_helpers) and cycle lifecycle events
  via ``on_cycle_started()`` / ``on_cycle_completed()``.
- On cycle completion it emits ``cycle_scored(CycleQualityScore)``.
- On session end it emits ``run_scored(RunQualityScore)``.

No network calls. No disk writes. Purely in-memory computation.

See docs/features/SIGNAL_EVENT_CLASSIFIER_FRS.md §7 and §8 for full spec.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from typing import Optional

from PySide6.QtCore import QObject, Signal

# ---------------------------------------------------------------------------
# Thresholds (in RU — 355 RU = 1 nm)
# ---------------------------------------------------------------------------

_NM_TO_RU = 355.0

# Stage 1 readiness thresholds (nm, converted from RU in FRS)
_READY_SLOPE_MAX_NM_S   = 12 / _NM_TO_RU    # 12 RU/s
_READY_P2P_MAX_NM       = 15 / _NM_TO_RU    # 15 RU over 5 frames
_CONTROL_SLOPE_MAX_NM_S = 8  / _NM_TO_RU    # 8 RU/s on control channel

# Stage 2 bubble detection thresholds
_BUBBLE_P2P_THRESHOLD_NM  = 20 / _NM_TO_RU   # 20 RU spike
_BUBBLE_DIP_DEPTH_DROP    = 0.05              # 5% relative drop in dip depth
_BUBBLE_FWHM_BROADEN_NM   = 3.0              # nm broadening

# Scoring thresholds
_CONTACT_NOISE_MAX_NM     = 12 / _NM_TO_RU   # p2p < 12 RU = clean contact
_REGEN_DELTA_MAX_NM       = 18 / _NM_TO_RU   # regen_delta < 18 RU = effective

# Cycle types that should be scored
_SCORED_CYCLE_TYPES = {"binding", "analyte", "sample", "injection"}

# Cycle types that count toward complexity tier
_COMPLEXITY_CYCLE_TYPES = _SCORED_CYCLE_TYPES | {"wash", "regen", "regeneration", "baseline"}


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------

@dataclass
class CycleQualityScore:
    """Quality assessment for a single acquisition cycle."""
    cycle_index: int
    cycle_id: str
    cycle_type: str
    score: int                          # 0–100
    band: str                           # "excellent" / "good" / "marginal" / "poor"
    note: str                           # auto-generated plain English, semicolons between sentences
    components: dict[str, float]        # per-component raw scores (0–1) for debugging
    finished: bool                      # True if cycle reached natural end


@dataclass
class RunQualityScore:
    """Quality roll-up for a complete acquisition session."""
    signal_quality_stars: int           # 0–4 from average cycle scores
    completion_stars: float             # 0, 0.5, or 1.0
    total_stars: int                    # 1–5 (clamped)
    tier: str                           # "easy" / "medium" / "pro"
    cycles_planned: int
    cycles_finished: int
    cycles_scored: int
    avg_score: float                    # 0–100
    note: str
    manual_override: Optional[int] = None   # user-set star count


# ---------------------------------------------------------------------------
# Per-cycle accumulator
# ---------------------------------------------------------------------------

@dataclass
class _CycleAccumulator:
    """Rolling state accumulated while a cycle is running."""
    cycle_index: int
    cycle_id: str
    cycle_type: str

    # Baseline component
    baseline_frames: int = 0
    baseline_ready_frames: int = 0      # frames where slope+p2p met ready criteria

    # Injection detection component
    injection_detected: bool = False    # set externally via notify_injection_detected()

    # Contact SNR component
    contact_frames: int = 0
    contact_clean_frames: int = 0       # frames with p2p < threshold

    # Wash detection component
    wash_detected: bool = False         # set externally via notify_wash_detected()

    # Bubble-free component
    bubble_frames: int = 0             # frames with p2p spike above bubble threshold

    # Regen component
    regen_start_nm: Optional[float] = None
    regen_end_nm: Optional[float] = None
    regen_applicable: bool = False

    # Phase tracking — coarse, derived from cycle_elapsed_frac
    _in_contact: bool = False
    _in_baseline: bool = False

    # Previous frame values for FWHM/dip_depth delta computation
    _prev_dip_depth: Optional[float] = None
    _prev_fwhm: Optional[float] = None

    # First wavelength in regen phase (for delta computation)
    _regen_phase_started: bool = False


# ---------------------------------------------------------------------------
# Scorer
# ---------------------------------------------------------------------------

class SignalQualityScorer(QObject):
    """Per-cycle quality scorer. Singleton, created once at app startup.

    Wiring (in main.py or coordinator):
        scorer = SignalQualityScorer.get_instance()
        # Hook cycle lifecycle:
        # call scorer.on_cycle_started(cycle) when a cycle begins
        # call scorer.on_cycle_completed(cycle, finished=True) when it ends
        # Hook per-frame telemetry:
        # call scorer.record_frame(...) from spectrum_helpers after telemetry logger
        # Hook injection/wash flags:
        # call scorer.notify_injection_detected(channel) from injection coordinator
        # call scorer.notify_wash_detected(channel) from wash monitor
    """

    cycle_scored = Signal(object)   # CycleQualityScore
    run_scored   = Signal(object)   # RunQualityScore

    _instance: Optional["SignalQualityScorer"] = None
    _inst_lock = threading.Lock()

    @classmethod
    def get_instance(cls) -> "SignalQualityScorer":
        if cls._instance is None:
            with cls._inst_lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    def __init__(self, parent: QObject = None) -> None:
        super().__init__(parent)
        self._lock = threading.Lock()
        self._current: Optional[_CycleAccumulator] = None
        self._completed_scores: list[CycleQualityScore] = []
        self._cycles_planned: int = 0
        self._session_active: bool = False

    # ------------------------------------------------------------------
    # Session lifecycle
    # ------------------------------------------------------------------

    def start_session(self, cycles_planned: int = 0) -> None:
        with self._lock:
            self._completed_scores.clear()
            self._cycles_planned = cycles_planned
            self._session_active = True
            self._current = None

    def end_session(self) -> Optional[RunQualityScore]:
        """Finalise current cycle if still open, compute run rating, emit signal."""
        with self._lock:
            if self._current is not None:
                score = self._finalise_cycle(finished=False)
                self._completed_scores.append(score)
                self._current = None

            run = self._compute_run_score()
            self._session_active = False

        self.run_scored.emit(run)
        return run

    # ------------------------------------------------------------------
    # Cycle lifecycle
    # ------------------------------------------------------------------

    def on_cycle_started(self, cycle_index: int, cycle_id: str, cycle_type: str) -> None:
        with self._lock:
            # Finalise previous cycle if scorer missed the completion signal
            if self._current is not None:
                score = self._finalise_cycle(finished=False)
                self._completed_scores.append(score)

            self._current = _CycleAccumulator(
                cycle_index=cycle_index,
                cycle_id=cycle_id,
                cycle_type=(cycle_type or "").lower(),
            )

    def on_cycle_completed(self, cycle_id: str, finished: bool = True) -> None:
        """Called when a cycle ends. Emits cycle_scored."""
        with self._lock:
            if self._current is None or self._current.cycle_id != cycle_id:
                return
            score = self._finalise_cycle(finished=finished)
            self._completed_scores.append(score)
            self._current = None

        self.cycle_scored.emit(score)

    # ------------------------------------------------------------------
    # Per-frame data
    # ------------------------------------------------------------------

    def record_frame(
        self,
        *,
        channel: str,
        elapsed_s: float,
        wavelength_nm: float,
        p2p_5frame_nm: Optional[float],
        slope_5s_nm_s: Optional[float],
        fwhm_nm: Optional[float],
        dip_depth: Optional[float],
        cycle_elapsed_frac: Optional[float],
        cycle_type: str,
    ) -> None:
        """Record one processed frame. Called from spectrum_helpers per channel.

        Must be fast and never raise — runs in processing worker thread.
        """
        if not self._session_active:
            return
        try:
            with self._lock:
                acc = self._current
                if acc is None:
                    return

                frac = cycle_elapsed_frac if cycle_elapsed_frac is not None else 0.0
                ct = (cycle_type or "").lower()

                # --- Phase determination (coarse heuristic from elapsed fraction) ---
                # First 20% of cycle = baseline/pre-inject
                # 20–80% = contact window
                # 80–100% = regen/wash
                in_baseline = frac < 0.20
                in_contact  = 0.20 <= frac <= 0.80
                in_regen    = frac > 0.80

                # --- Baseline component ---
                if in_baseline and p2p_5frame_nm is not None and slope_5s_nm_s is not None:
                    acc.baseline_frames += 1
                    if (abs(slope_5s_nm_s) <= _READY_SLOPE_MAX_NM_S and
                            p2p_5frame_nm <= _READY_P2P_MAX_NM):
                        acc.baseline_ready_frames += 1

                # --- Contact SNR component ---
                if in_contact and p2p_5frame_nm is not None:
                    acc.contact_frames += 1
                    if p2p_5frame_nm <= _CONTACT_NOISE_MAX_NM:
                        acc.contact_clean_frames += 1

                # --- Bubble detection ---
                if in_contact and p2p_5frame_nm is not None:
                    p2p_spike = p2p_5frame_nm >= _BUBBLE_P2P_THRESHOLD_NM
                    depth_drop = False
                    fwhm_broad = False
                    if dip_depth is not None and acc._prev_dip_depth is not None:
                        depth_drop = (acc._prev_dip_depth - dip_depth) >= _BUBBLE_DIP_DEPTH_DROP
                    if fwhm_nm is not None and acc._prev_fwhm is not None:
                        fwhm_broad = (fwhm_nm - acc._prev_fwhm) >= _BUBBLE_FWHM_BROADEN_NM
                    # Two of three criteria
                    hits = sum([p2p_spike, depth_drop, fwhm_broad])
                    if hits >= 2:
                        acc.bubble_frames += 1

                # --- Regen component ---
                if in_regen:
                    if not acc._regen_phase_started:
                        acc.regen_start_nm = wavelength_nm
                        acc._regen_phase_started = True
                        acc.regen_applicable = True
                    acc.regen_end_nm = wavelength_nm

                # Update prev values
                acc._prev_dip_depth = dip_depth
                acc._prev_fwhm = fwhm_nm

        except Exception:
            pass  # never crash acquisition

    # ------------------------------------------------------------------
    # External event hooks
    # ------------------------------------------------------------------

    def notify_injection_detected(self, channel: str) -> None:
        with self._lock:
            if self._current is not None:
                self._current.injection_detected = True

    def notify_wash_detected(self, channel: str) -> None:
        with self._lock:
            if self._current is not None:
                self._current.wash_detected = True

    # ------------------------------------------------------------------
    # Score computation (called with lock held)
    # ------------------------------------------------------------------

    def _finalise_cycle(self, finished: bool) -> CycleQualityScore:
        acc = self._current
        ct = acc.cycle_type
        components: dict[str, float] = {}
        notes: list[str] = []

        # 1. Baseline stability (25%)
        if acc.baseline_frames > 0:
            ratio = acc.baseline_ready_frames / acc.baseline_frames
            components["baseline"] = ratio
            if ratio < 0.5:
                notes.append("Baseline was still drifting when injection was triggered.")
        else:
            components["baseline"] = 0.5   # neutral — no baseline data captured

        # 2. Injection detection (20%)
        if ct in _SCORED_CYCLE_TYPES:
            components["injection"] = 1.0 if acc.injection_detected else 0.0
            if not acc.injection_detected:
                notes.append("Injection start could not be auto-detected — verify in Edits.")
        else:
            components["injection"] = 1.0  # not applicable, full marks

        # 3. Contact SNR (20%)
        if acc.contact_frames > 0:
            ratio = acc.contact_clean_frames / acc.contact_frames
            components["contact_snr"] = ratio
        else:
            components["contact_snr"] = 1.0  # no contact data — neutral

        # 4. Wash detection (15%)
        if ct in _SCORED_CYCLE_TYPES:
            components["wash"] = 1.0 if acc.wash_detected else 0.0
            if not acc.wash_detected:
                notes.append("Wash start not detected. Wash flag may need manual placement.")
        else:
            components["wash"] = 1.0

        # 5. Bubble-free (15%)
        if acc.contact_frames > 0:
            bubble_fraction = acc.bubble_frames / acc.contact_frames
            components["bubble_free"] = max(0.0, 1.0 - bubble_fraction * 4)
            if acc.bubble_frames > 3:
                notes.append("Sustained bubble event. Data quality during contact is uncertain.")
            elif acc.bubble_frames > 0:
                notes.append("Short bubble event during contact window. Check sensorgram.")
        else:
            components["bubble_free"] = 1.0

        # 6. Regen effectiveness (5%)
        if acc.regen_applicable and acc.regen_start_nm is not None and acc.regen_end_nm is not None:
            regen_delta = abs(acc.regen_end_nm - acc.regen_start_nm)
            components["regen"] = 1.0 if regen_delta <= _REGEN_DELTA_MAX_NM else 0.3
            if regen_delta > _REGEN_DELTA_MAX_NM:
                notes.append(
                    "Residual signal from previous cycle. "
                    "Consider longer regen or higher concentration."
                )
        else:
            components["regen"] = 1.0  # first cycle or not applicable

        # Weighted sum
        weights = {
            "baseline":    0.25,
            "injection":   0.20,
            "contact_snr": 0.20,
            "wash":        0.15,
            "bubble_free": 0.15,
            "regen":       0.05,
        }
        raw = sum(components.get(k, 1.0) * w for k, w in weights.items())
        score = int(round(min(100, max(0, raw * 100))))

        # Band + label
        band, label = _score_to_band(score)

        # Auto-note
        if not notes:
            notes.append("Baseline stable, injection and wash clearly detected, no bubble events.")
        note_str = " ".join(notes)

        if not finished:
            note_str = "[Incomplete] " + note_str

        return CycleQualityScore(
            cycle_index=acc.cycle_index,
            cycle_id=acc.cycle_id,
            cycle_type=acc.cycle_type,
            score=score,
            band=band,
            note=note_str,
            components=components,
            finished=finished,
        )

    def _compute_run_score(self) -> RunQualityScore:
        scores = self._completed_scores
        cycles_finished = sum(1 for s in scores if s.finished)
        cycles_scored = len(scores)

        # Signal quality: average score of scored (binding-type) cycles → 4 stars
        binding_scores = [s.score for s in scores if s.cycle_type in _SCORED_CYCLE_TYPES]
        if binding_scores:
            avg = sum(binding_scores) / len(binding_scores)
        else:
            avg = sum(s.score for s in scores) / len(scores) if scores else 50.0

        sig_stars = _avg_to_signal_stars(avg)

        # Completion: were all planned cycles finished?
        planned = self._cycles_planned or cycles_scored
        comp_ratio = cycles_finished / planned if planned > 0 else 1.0
        if comp_ratio >= 0.95:
            comp_stars = 1.0
        elif comp_ratio >= 0.5:
            comp_stars = 0.5
        else:
            comp_stars = 0.0

        total = max(1, min(5, round(sig_stars + comp_stars)))

        # Complexity tier
        tier = _complexity_tier(cycles_scored)

        # Note
        poor_count = sum(1 for s in scores if s.band == "poor")
        note_parts = []
        if poor_count:
            note_parts.append(f"{poor_count} poor cycle{'s' if poor_count > 1 else ''}.")
        if not note_parts:
            note_parts.append("Run completed successfully.")
        if cycles_finished < planned:
            note_parts.append(f"{planned - cycles_finished} cycle(s) not completed.")

        return RunQualityScore(
            signal_quality_stars=sig_stars,
            completion_stars=comp_stars,
            total_stars=total,
            tier=tier,
            cycles_planned=planned,
            cycles_finished=cycles_finished,
            cycles_scored=cycles_scored,
            avg_score=round(avg, 1),
            note=" ".join(note_parts),
        )

    # ------------------------------------------------------------------
    # Query API
    # ------------------------------------------------------------------

    def get_cycle_score(self, cycle_id: str) -> Optional[CycleQualityScore]:
        with self._lock:
            for s in self._completed_scores:
                if s.cycle_id == cycle_id:
                    return s
        return None

    def get_all_cycle_scores(self) -> list[CycleQualityScore]:
        with self._lock:
            return list(self._completed_scores)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _score_to_band(score: int) -> tuple[str, str]:
    if score >= 85:
        return "excellent", "Clean cycle"
    if score >= 65:
        return "good", "Usable"
    if score >= 40:
        return "marginal", "Check in Edits"
    return "poor", "Consider repeating"


def _score_to_dot_color(band: str) -> str:
    """Return a CSS hex colour for the queue dot."""
    return {
        "excellent": "#4CAF50",   # green
        "good":      "#FFC107",   # amber
        "marginal":  "#FF9800",   # orange
        "poor":      "#F44336",   # red
    }.get(band, "#9E9E9E")


def _avg_to_signal_stars(avg: float) -> int:
    """Map average cycle score (0–100) to 0–4 signal quality stars."""
    if avg >= 85:
        return 4
    if avg >= 70:
        return 3
    if avg >= 50:
        return 2
    if avg >= 30:
        return 1
    return 0


def _complexity_tier(cycle_count: int) -> str:
    if cycle_count <= 5:
        return "easy"
    if cycle_count <= 10:
        return "medium"
    return "pro"
