"""BindingPlotMixin — dose-response and kinetics fitting for Edits tab.

Provides _update_binding_plot(), _binding_show_empty(), and _on_binding_ch_clicked().

Two fit modes:
  - Equilibrium (Linear / 1:1 Langmuir): uses stored delta_ch{n} values vs concentration
  - Kinetics (ka/kd): extracts raw sensorgram per cycle, fits association phase to
    R(t) = Rmax*(1-exp(-kobs*t)), then linear regression of kobs vs C gives
    ka (slope) and kd (intercept), KD = kd/ka.
"""

import numpy as np
import pyqtgraph as pg

from affilabs.utils.logger import logger

try:
    from scipy.optimize import curve_fit as _scipy_curve_fit
    _SCIPY_OK = True
except ImportError:
    _SCIPY_OK = False

_CH_COLORS = ['#1D1D1F', '#FF3B30', '#007AFF', '#34C759']


class BindingPlotMixin:
    """Mixin providing binding plot (dose-response) functionality for EditsTab."""

    # ------------------------------------------------------------------
    # Channel button handler
    # ------------------------------------------------------------------

    def _on_binding_ch_clicked(self, clicked_idx: int):
        """Enforce exclusive channel button selection then refresh plot."""
        for i, btn in enumerate(self.binding_ch_btns):
            btn.setChecked(i == clicked_idx)
        self._update_binding_plot()

    # ------------------------------------------------------------------
    # Main update
    # ------------------------------------------------------------------

    def _update_binding_plot(self):
        """Recompute and redraw the binding dose-response plot."""
        if not hasattr(self, 'bottom_tab_widget'):
            return
        if self.bottom_tab_widget.currentIndex() != 1:
            return

        selected_rows = sorted(set(
            idx.row() for idx in self.cycle_data_table.selectedIndexes()
        ))

        if not selected_rows:
            self._binding_show_empty("Select cycles in the table to generate a binding plot.")
            return

        cycles_data = getattr(self.main_window, '_loaded_cycles_data', [])

        # --- Determine which channels have valid data ---
        valid_channels = set()
        for row in selected_rows:
            if row >= len(cycles_data):
                continue
            cycle = cycles_data[row]
            if not cycle.get('delta_measured'):
                continue
            try:
                float(cycle.get('concentration_value', ''))
            except (ValueError, TypeError):
                continue
            for ch_idx in range(4):
                if cycle.get(f'delta_ch{ch_idx + 1}') is not None:
                    valid_channels.add(ch_idx)

        # Update button enabled state; preserve or auto-select current channel
        current_ch = next((i for i, b in enumerate(self.binding_ch_btns) if b.isChecked()), 0)
        for i, btn in enumerate(self.binding_ch_btns):
            btn.setEnabled(i in valid_channels)
        if current_ch not in valid_channels:
            if valid_channels:
                current_ch = min(valid_channels)
                for i, btn in enumerate(self.binding_ch_btns):
                    btn.setChecked(i == current_ch)
            else:
                self._binding_show_empty("Place the ΔSPR cursors on each cycle first.")
                return

        # --- Build data arrays ---
        conc_list, dspr_list, labels_list, refs_seen = [], [], [], set()
        for row in selected_rows:
            if row >= len(cycles_data):
                continue
            cycle = cycles_data[row]
            if not cycle.get('delta_measured'):
                continue
            try:
                conc = float(cycle.get('concentration_value', ''))
            except (ValueError, TypeError):
                continue
            delta = cycle.get(f'delta_ch{current_ch + 1}')
            if delta is None:
                continue
            conc_list.append(conc)
            dspr_list.append(float(delta))
            labels_list.append(cycle.get('name', f'Cycle {row + 1}'))
            refs_seen.add(cycle.get('delta_ref_ch', 'None'))

        if not conc_list:
            self._binding_show_empty(
                "Set concentration values in the Conc. column to generate a binding plot."
            )
            return
        if len(conc_list) < 2:
            self._binding_show_empty("Need at least 2 data points to fit.")
            return

        conc_arr = np.array(conc_list)
        dspr_arr = np.array(dspr_list)
        ref_label = refs_seen.pop() if len(refs_seen) == 1 else 'mixed ⚠'
        model = self.binding_model_combo.currentText()
        ch_color = _CH_COLORS[current_ch]

        # Unit scaling — concentration values in Excel are assumed to be in nM
        unit_combo = getattr(self, 'binding_conc_unit_combo', None)
        conc_unit = unit_combo.currentText() if unit_combo else 'nM'
        _NM_SCALE = {'nM': 1.0, 'µM': 1e-3, 'pM': 1e3}
        scale = _NM_SCALE.get(conc_unit, 1.0)
        conc_arr_scaled = conc_arr * scale  # display units for plot/Kd
        self.binding_scatter_plot.setLabel('bottom', f'Concentration ({conc_unit})')

        x_min = max(0.0, conc_arr_scaled.min() * 0.8)
        x_max = conc_arr_scaled.max() * 1.15
        x_line = np.linspace(x_min, x_max, 300)

        # --- Fit ---
        kd_text = ""
        fit_ok = False
        # Initialized here so the static analyzer knows they're always bound
        # before use (runtime is guarded by `if not fit_ok: return` below).
        y_fit = np.zeros_like(x_line)
        r2 = 0.0
        formula_text = ""
        params_text = ""

        if model == 'Linear':
            coeffs = np.polyfit(conc_arr_scaled, dspr_arr, 1)
            m, b = coeffs
            y_fit = np.polyval(coeffs, x_line)
            ss_res = np.sum((dspr_arr - np.polyval(coeffs, conc_arr_scaled)) ** 2)
            ss_tot = np.sum((dspr_arr - dspr_arr.mean()) ** 2)
            r2 = float(1.0 - ss_res / ss_tot) if ss_tot > 0 else 0.0
            formula_text = "y = m·x + b"
            params_text = f"m = {m:.3f} RU/{conc_unit}\nb = {b:.2f} RU"
            fit_ok = True

        elif model == '1:1 Langmuir':
            if not _SCIPY_OK:
                self._binding_show_empty(
                    "scipy not available — install scipy to use Langmuir fitting."
                )
                return

            def langmuir(c, Rmax, Kd):
                return Rmax * c / (Kd + c)

            try:
                p0 = [float(dspr_arr.max()), float(np.median(conc_arr_scaled))]
                popt, _ = _scipy_curve_fit(
                    langmuir, conc_arr_scaled, dspr_arr,
                    p0=p0, bounds=([0.0, 0.0], [np.inf, np.inf]),
                    maxfev=5000
                )
                Rmax, Kd = float(popt[0]), float(popt[1])
                y_fit = langmuir(x_line, Rmax, Kd)
                y_pred = langmuir(conc_arr_scaled, Rmax, Kd)
                ss_res = np.sum((dspr_arr - y_pred) ** 2)
                ss_tot = np.sum((dspr_arr - dspr_arr.mean()) ** 2)
                r2 = float(1.0 - ss_res / ss_tot) if ss_tot > 0 else 0.0
                formula_text = "y = Rmax·c / (Kd + c)"
                params_text = f"Rmax = {Rmax:.1f} RU\nKd   = {Kd:.3f} {conc_unit}"
                kd_text = f"Kd = {Kd:.3f} {conc_unit}"
                fit_ok = True
            except RuntimeError:
                self._binding_show_empty(
                    "1:1 fit did not converge.\nTry Linear, or check that concentration range spans Kd."
                )
                return

        elif model == 'Kinetics (ka/kd)':
            if not _SCIPY_OK:
                self._binding_show_empty("scipy not available — required for kinetics fitting.")
                return

            # Extract raw sensorgram per cycle and fit association phase
            raw_rows = []
            dc = getattr(getattr(getattr(self, 'main_window', None), None, None), None, None)
            try:
                dc = self.main_window.app.recording_mgr.data_collector.raw_data_rows
            except AttributeError:
                pass
            if not dc:
                self._binding_show_empty(
                    "No raw sensorgram data available.\nKinetics fitting requires loaded sensorgram data."
                )
                return

            ch_key = 'abcd'[current_ch]
            kobs_list, conc_fit_list = [], []

            for row in selected_rows:
                if row >= len(cycles_data):
                    continue
                cycle = cycles_data[row]
                try:
                    conc = float(cycle.get('concentration_value', ''))
                except (ValueError, TypeError):
                    continue
                t_start = cycle.get('start_time_sensorgram')
                t_end = cycle.get('end_time_sensorgram')
                if t_start is None or t_end is None:
                    continue

                kobs = self._fit_kobs_from_raw(dc, ch_key, float(t_start), float(t_end))
                if kobs is not None:
                    kobs_list.append(kobs)
                    conc_fit_list.append(conc)

            if len(kobs_list) < 2:
                self._binding_show_empty(
                    "Need at least 2 cycles with sensorgram data for kinetics fitting.\n"
                    "Check that raw data was loaded and time windows are set."
                )
                return

            conc_fit_arr = np.array(conc_fit_list) * scale  # display units
            kobs_arr = np.array(kobs_list)

            # Linear regression: kobs = ka * C + kd
            coeffs = np.polyfit(conc_fit_arr, kobs_arr, 1)
            ka, kd_val = float(coeffs[0]), float(coeffs[1])
            kd_val = max(kd_val, 0.0)  # kd must be ≥ 0
            KD = kd_val / ka if ka > 1e-15 else float('inf')

            y_fit = np.polyval(coeffs, x_line)
            ss_res = np.sum((kobs_arr - np.polyval(coeffs, conc_fit_arr)) ** 2)
            ss_tot = np.sum((kobs_arr - kobs_arr.mean()) ** 2)
            r2 = float(1.0 - ss_res / ss_tot) if ss_tot > 0 else 0.0

            # Format ka/kd with appropriate units
            # ka is in 1/(conc_unit·s), kd in 1/s
            ka_str = f"{ka:.3e} {conc_unit}⁻¹s⁻¹"
            kd_str = f"{kd_val:.3e} s⁻¹"
            KD_str = f"{KD:.3f} {conc_unit}"

            formula_text = "kobs = ka·[C] + kd"
            params_text = f"ka  = {ka_str}\nkd  = {kd_str}\nKD  = {KD_str}"
            kd_text = f"KD = {KD_str}  (ka/kd)"

            # Swap axes: plot kobs vs concentration
            self.binding_scatter_plot.setLabel('left', 'kobs (s⁻¹)')
            dspr_arr = kobs_arr   # repurpose y-axis for kobs values
            conc_arr_scaled = conc_fit_arr
            fit_ok = True

        if not fit_ok:
            return

        # Restore y-axis label for equilibrium models
        if model != 'Kinetics (ka/kd)':
            self.binding_scatter_plot.setLabel('left', 'ΔSPR (RU)')

        # --- Update scatter plot ---
        self.binding_scatter_plot.clear()
        scatter = pg.ScatterPlotItem(
            x=conc_arr_scaled, y=dspr_arr,
            size=10, symbol='o',
            brush=pg.mkBrush(ch_color),
            pen=pg.mkPen(None),
        )
        # Hover tooltips
        spots = [
            {'pos': (c, d), 'data': f"{lbl}\n{c:.3g} {conc_unit} → {d:.1f} RU"}
            for c, d, lbl in zip(conc_arr_scaled.tolist(), dspr_list, labels_list)
        ]
        scatter.addPoints(spots)
        self.binding_scatter_plot.addItem(scatter)

        fit_pen = pg.mkPen(color=ch_color, width=2,
                           style=pg.Qt.QtCore.Qt.PenStyle.DashLine)
        self.binding_scatter_plot.plot(x_line, y_fit, pen=fit_pen)

        # --- Update formula panel ---
        r2_color = '#34C759' if r2 >= 0.95 else ('#FF9500' if r2 >= 0.85 else '#FF3B30')
        self.binding_model_lbl.setText(model)
        self.binding_formula_lbl.setText(formula_text)
        self.binding_params_lbl.setText(params_text)
        self.binding_r2_lbl.setText(f"R² = {r2:.3f}")
        self.binding_r2_lbl.setStyleSheet(
            f"font-size:12px; font-weight:700; color:{r2_color};"
        )
        self.binding_ref_lbl.setText(f"ref: {ref_label}")
        self.binding_kd_lbl.setText(kd_text)
        self.binding_kd_lbl.setVisible(bool(kd_text))
        self.binding_warn_frame.setVisible(model == '1:1 Langmuir')

        # --- Cache for export ---
        self._binding_fit_result = {
            'model': model,
            'channel': 'ABCD'[current_ch],
            'r2': r2,
            'ref': ref_label,
            'conc': conc_list,
            'dspr': dspr_list,
            'labels': labels_list,
            'x_fit': x_line.tolist(),
            'y_fit': y_fit.tolist(),
            'params': params_text,
        }
        if model == '1:1 Langmuir':
            self._binding_fit_result['Kd_uM'] = Kd
            self._binding_fit_result['Rmax_RU'] = Rmax

        logger.debug(
            f"[BindingPlot] Ch {self._binding_fit_result['channel']} "
            f"{model} R²={r2:.3f} n={len(conc_list)}"
        )

        # Refresh Rmax calculator (Langmuir Rmax may have updated)
        self._update_rmax_calculator()

    # ------------------------------------------------------------------
    # Rmax calculator
    # ------------------------------------------------------------------

    def _on_rmax_input_changed(self):
        """Slot: either MW spinbox changed — persist and recompute."""
        ligand_val = getattr(self, 'rmax_ligand_spin', None)
        analyte_val = getattr(self, 'rmax_analyte_spin', None)
        if ligand_val is not None and ligand_val.value() > 0:
            self._ligand_mw = float(ligand_val.value())
        else:
            self._ligand_mw = None
        if analyte_val is not None and analyte_val.value() > 0:
            self._analyte_mw = float(analyte_val.value())
        else:
            self._analyte_mw = None
        self._update_rmax_calculator()

    def _update_rmax_calculator(self):
        """Recompute Rmax outputs and refresh labels.

        Called after any binding plot update or MW input change.
        Also auto-fills _immob_delta_spr_ru from _injection_stats.
        """
        if not hasattr(self, 'rmax_immob_lbl'):
            return  # UI not yet built

        # ── Auto-fill Immob ΔSPR from live stats ─────────────────────
        if self._immob_delta_spr_ru is None:
            inj_stats = getattr(self.main_window, '_injection_stats', {})
            for (c, ch), entry in inj_stats.items():
                ctype = entry.get('cycle_type', '')
                if ctype in ('Immobilisation', 'Immobilization'):
                    d = entry.get('delta_spr_ru')
                    if d is not None:
                        self._immob_delta_spr_ru = abs(d)
                        break

        if self._immob_delta_spr_ru is not None:
            self.rmax_immob_lbl.setText(f"{self._immob_delta_spr_ru:.0f} RU")
        else:
            self.rmax_immob_lbl.setText("—")

        # ── Theoretical Rmax ─────────────────────────────────────────
        theoretical = None
        if (self._ligand_mw and self._analyte_mw and self._immob_delta_spr_ru
                and self._ligand_mw > 0):
            theoretical = (self._analyte_mw / self._ligand_mw) * self._immob_delta_spr_ru

        if theoretical is not None:
            self.rmax_theoretical_lbl.setText(f"{theoretical:.0f} RU")
        else:
            self.rmax_theoretical_lbl.setText("—")

        # ── Empirical Rmax (from Langmuir fit) ───────────────────────
        empirical = None
        fit = getattr(self, '_binding_fit_result', None)
        if fit and fit.get('model') == '1:1 Langmuir':
            empirical = fit.get('Rmax_RU')

        if empirical is not None:
            self.rmax_empirical_lbl.setText(f"{empirical:.0f} RU  (from Langmuir fit)")
            self.rmax_empirical_lbl.setStyleSheet("font-size:11px; color:#1D1D1F;")
        else:
            self.rmax_empirical_lbl.setText("—")
            self.rmax_empirical_lbl.setStyleSheet("font-size:11px; color:#86868B; font-style:italic;")

        # ── Surface activity ─────────────────────────────────────────
        if theoretical and theoretical > 0 and empirical is not None:
            pct = (empirical / theoretical) * 100.0
            if pct > 80:
                label, color = f"● High activity  ({pct:.1f}%)", "#34C759"
            elif pct >= 50:
                label, color = f"● Good  ({pct:.1f}%)", "#34C759"
            elif pct >= 20:
                label, color = f"◐ Low activity  ({pct:.1f}%)", "#FF9500"
            else:
                label, color = f"○ Poor — check surface  ({pct:.1f}%)", "#FF3B30"
            self.rmax_activity_lbl.setText(label)
            self.rmax_activity_lbl.setStyleSheet(f"font-size:11px; font-weight:600; color:{color};")
        else:
            self.rmax_activity_lbl.setText("—")
            self.rmax_activity_lbl.setStyleSheet("font-size:11px; color:#86868B;")

    # ------------------------------------------------------------------
    # Kinetics helper
    # ------------------------------------------------------------------

    def _fit_kobs_from_raw(self, raw_rows: list, ch: str,
                           t_start: float, t_end: float) -> float | None:
        """Fit a single-exponential association to extract kobs.

        Slices raw_rows for the given channel between t_start and t_end,
        baseline-subtracts using the first 10% of points, then fits:
            R(t) = Rmax * (1 - exp(-kobs * t))

        Returns kobs (s⁻¹) or None if fit fails / insufficient data.
        """
        if not _SCIPY_OK:
            return None

        pts = sorted(
            (r['time'], r['value']) for r in raw_rows
            if r.get('channel') == ch
            and t_start <= r['time'] <= t_end
        )
        if len(pts) < 10:
            return None

        times = np.array([p[0] for p in pts])
        values = np.array([p[1] for p in pts])

        # Baseline: mean of first 10% of points
        n_base = max(1, len(times) // 10)
        baseline = float(values[:n_base].mean())
        response = values - baseline
        t_rel = times - times[0]

        # Fit R(t) = Rmax * (1 - exp(-kobs * t))
        def assoc(t, Rmax, kobs):
            return Rmax * (1.0 - np.exp(-kobs * t))

        try:
            rmax_guess = float(response.max()) if response.max() > 0 else 1.0
            popt, _ = _scipy_curve_fit(
                assoc, t_rel, response,
                p0=[rmax_guess, 0.01],
                bounds=([0.0, 1e-6], [np.inf, 10.0]),
                maxfev=3000,
            )
            return float(popt[1])  # kobs
        except (RuntimeError, ValueError):
            return None

    # ------------------------------------------------------------------
    # Empty state helper
    # ------------------------------------------------------------------

    def _binding_show_empty(self, msg: str):
        """Clear scatter plot and show an empty-state message."""
        if not hasattr(self, 'binding_scatter_plot'):
            return
        self.binding_scatter_plot.clear()

        text = pg.TextItem(anchor=(0.5, 0.5))
        text.setHtml(
            f'<span style="color:#86868B; font-size:11px; font-style:italic;">{msg}</span>'
        )
        self.binding_scatter_plot.addItem(text)
        vb = self.binding_scatter_plot.getViewBox()
        vb.setRange(xRange=(0, 1), yRange=(0, 1), padding=0)
        text.setPos(0.5, 0.5)

        # Clear formula panel
        for attr in ('binding_model_lbl', 'binding_formula_lbl', 'binding_params_lbl',
                     'binding_r2_lbl', 'binding_ref_lbl', 'binding_kd_lbl'):
            lbl = getattr(self, attr, None)
            if lbl is not None:
                lbl.setText("")
        if hasattr(self, 'binding_warn_frame'):
            self.binding_warn_frame.hide()

        self._binding_fit_result = None
