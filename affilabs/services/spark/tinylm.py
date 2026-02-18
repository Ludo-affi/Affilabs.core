"""TinyLM integration module for Spark AI assistant

Provides conversational AI capabilities using TinyLlama-1.1B model.
This module handles lazy loading, context building, and response generation.
Model details are kept internal - users just see "Spark" working.
"""

import logging
import threading

logger = logging.getLogger(__name__)


class SparkTinyLM:
    """TinyLM integration for Spark AI assistant.

    Provides conversational AI fallback when pattern matching doesn't work.
    Uses lazy loading - model only loads when first needed.
    Thread-safe: Multiple calls to generate_answer won't cause double-loading.
    """

    def __init__(self):
        """Initialize TinyLM (lazy loading - model loads on first use).

        Model details kept internal - users don't see technical loading info.
        """
        self._model = None
        self._tokenizer = None
        self._pipeline = None
        self._loading = False
        self._initialized = False
        self._load_lock = threading.Lock()  # Prevent concurrent model loading

    def is_initialized(self) -> bool:
        """Check if TinyLM model is loaded."""
        return self._initialized

    def _load_model(self):
        """Load TinyLlama model (called on first use).

        Thread-safe: Uses lock to prevent concurrent loading.
        Silent loading - no user-visible messages about technical details.
        """
        # Quick check without lock (fast path)
        if self._initialized:
            logger.debug("Model already loaded")
            return True

        # Use lock to ensure only one thread loads the model
        with self._load_lock:
            # Double-check after acquiring lock (race condition protection)
            if self._initialized:
                return True

            if self._loading:
                logger.debug("Model already loading (another thread)...")
                # Block until other thread finishes
                return self._initialized

            try:
                self._loading = True
                logger.debug("Loading Spark AI model...")

                # Deferred imports - torch and transformers are very heavy (~20s)
                import torch
                from transformers import AutoTokenizer, AutoModelForCausalLM, pipeline

                # Detect device (prefer GPU if available, silent fallback to CPU)
                device = "cuda" if torch.cuda.is_available() else "cpu"
                logger.debug(f"Using device: {device}")

                # Load model and tokenizer
                model_name = "TinyLlama/TinyLlama-1.1B-Chat-v1.0"

                self._tokenizer = AutoTokenizer.from_pretrained(model_name)
                self._model = AutoModelForCausalLM.from_pretrained(
                    model_name,
                    dtype=torch.float16 if device == "cuda" else torch.float32,
                    low_cpu_mem_usage=True,
                )
                self._model.to(device)

                # Create text generation pipeline
                self._pipeline = pipeline(
                    "text-generation",
                    model=self._model,
                    tokenizer=self._tokenizer,
                    device=0 if device == "cuda" else -1,
                    max_new_tokens=100,
                    temperature=0.7,
                    do_sample=True,
                    top_p=0.9,
                )

                self._initialized = True
                logger.debug("Spark AI model ready")
                return True

            except ImportError:
                logger.info("Spark AI model unavailable (torch/transformers not installed) — using pattern matching only")
                self._initialized = False
                return False
            except Exception as e:
                logger.warning(f"Failed to load Spark AI model: {e}")
                self._initialized = False
                return False
            finally:
                self._loading = False

    def _build_context(self, question: str) -> str:
        """Build focused context for the question.

        Args:
            question: User's question

        Returns:
            Relevant documentation context (narrow, focused on SPR software)
        """
        question_lower = question.lower()

        # Base context (always included)
        context = (
            "Affilabs.core is SPR (Surface Plasmon Resonance) analysis software for real-time biomolecular interaction studies. "
            "It controls optical detectors, pumps, valves, and records binding kinetics. "
            "SPR measures refractive index changes at sensor surface when molecules bind. "
            "Typical workflow: calibrate detector → prepare surface → run baseline → immobilize ligand → "
            "inject analyte concentrations → regenerate surface → analyze binding data. "
        )

        # Add specific context based on question keywords
        if any(
            word in question_lower for word in ["start", "run", "acquire", "record", "acquisition"]
        ):
            context += (
                "Acquisition: Start acquisition after completing OEM LED Calibration. "
                "Data appears on Full Sensorgram graph in real-time. Use Start Recording button in sidebar. "
                "Recording continues until stopped manually or method completes. "
                "Live data shows RU (Response Units) vs time for all active channels (A/B/C/D). "
            )

        if any(word in question_lower for word in ["calibrat", "baseline", "zero", "optical"]):
            context += (
                "Calibration: OEM LED Calibration (Settings tab → Calibration section) calibrates optical detector temperature and intensity. "
                "Takes 30-60 seconds. Must be done before each experiment. Creates wavelength-specific baseline. "
                "Baseline Capture during acquisition subtracts reference signal. "
                "Baseline cycle in method establishes stable reference before immobilization (typically 60-300s). "
                "If signal drifts, recalibrate detector or check LED temperature stability. "
            )

        if any(
            word in question_lower
            for word in [
                "method",
                "cycle",
                "queue",
                "protocol",
                "sequence",
                "baseline",
                "immobilization",
                "wash",
                "concentration",
                "regeneration",
            ]
        ):
            context += (
                "Methods: Build automated cycle queues in Method tab using Method Builder dialog. "
                "Cycle Types: Baseline (establishes reference before immobilization), "
                "Immobilization (binds ligand to surface, e.g. EDC/NHS chemistry), "
                "Wash (removes unbound material), "
                "Concentration (analyte binding series for kinetics, e.g. '50nM, 100nM, 200nM'), "
                "Regeneration (removes bound analyte, restores surface, e.g. glycine pH 2.5). "
                "Set duration (e.g. '180s' or '3min'), concentration (e.g. '100nM'), contact time (e.g. 'contact 120s'). "
                "Auto-injection triggers 20s after cycle start. Simple injection for most cycles, partial injection available for concentration series. "
                "Start Run executes queue. Progress bar shows current cycle and time remaining. "
            )

        if any(
            word in question_lower for word in ["export", "save", "file", "csv", "excel", "data"]
        ):
            context += (
                "Export: Export tab saves data in CSV, Excel (.xlsx), or JSON format. "
                "Select channels (A/B/C/D) to export. Choose destination folder. "
                "Exported data includes timestamps, response units, cycle markers, and metadata. "
                "Use Excel format for analysis in GraphPad Prism, Origin, or Excel. "
                "CSV format compatible with Python pandas, R, MATLAB. "
            )

        if any(
            word in question_lower
            for word in ["pump", "flow", "valve", "channel", "inject", "affipump", "peristaltic"]
        ):
            context += (
                "Flow Control: Flow tab controls pumps (AffiPump external syringe or internal peristaltic) and valves. "
                "Operations: Prime (fill tubing with buffer, remove air bubbles), "
                "Cleanup (flush system between experiments), "
                "Buffer (continuous flow during acquisition), "
                "Inject (deliver sample to sensor, simple or partial modes). "
                "Set flow rates typically 10-100 µL/min (AffiPump) or use internal pumps. "
                "Valves switch between channels A/B/C/D (4 independent sample lines). "
                "AffiPump uses dual syringe pumps for pulseless flow. Internal pumps built into P4PRO+ controller. "
            )

        if any(
            word in question_lower
            for word in ["graph", "plot", "display", "chart", "sensorgram", "signal"]
        ):
            context += (
                "Graphs: Full Sensorgram shows complete data timeline (all cycles). Active Cycle zooms to selected region. "
                "Graphic Display tab controls: grid on/off, autoscale, colorblind-safe colors, filters (None/Light Smoothing/Medium/Heavy). "
                "Sensorgram Y-axis: Response Units (RU). X-axis: Time (seconds). "
                "Typical signal: baseline (flat), association (rising curve), dissociation (falling curve). "
                "Noisy signal indicates need for calibration, smoothing filter, or detector temperature stabilization. "
            )

        if any(
            word in question_lower
            for word in ["error", "problem", "issue", "troubleshoot", "fix", "noise", "drift"]
        ):
            context += (
                "Troubleshooting: Noisy data → run OEM LED Calibration, apply Light Smoothing filter, check USB connection. "
                "Signal drift → allow detector temperature to stabilize (5-10 min after calibration), check buffer temperature. "
                "Pump issues → use Emergency Stop in Flow tab, check tubing for air bubbles, verify valve switching. "
                "Detector wait time (Advanced Settings → Detector section) adjusts integration time vs speed tradeoff. "
                "No signal → verify detector connected via USB, check Settings tab for detector status indicator. "
            )

        if any(
            word in question_lower
            for word in ["kinetic", "binding", "affinity", "ka", "kd", "kon", "koff", "analysis"]
        ):
            context += (
                "Kinetic Analysis: SPR measures association (kon) and dissociation (koff) rate constants. "
                "Affinity KD = koff/kon. Run concentration series (e.g. 5 concentrations from 10nM to 1µM). "
                "Association phase: analyte binds to immobilized ligand (rising curve). "
                "Dissociation phase: analyte unbinds during buffer flow (falling curve). "
                "Fit binding curves to 1:1 Langmuir model or more complex models using external software. "
                "Regeneration between cycles ensures consistent baseline. "
            )

        if any(word in question_lower for word in ["spark", "ai", "assistant", "help", "question"]):
            context += (
                "Spark AI: Built-in assistant for SPR workflow questions. Uses pattern matching + TinyLM language model. "
                "Ask natural language questions (e.g. 'how do I start acquisition?', 'what is baseline cycle?'). "
                "Located in sidebar. Click Spark icon or type question directly. "
            )

        if any(
            word in question_lower for word in ["settings", "config", "advanced", "preferences"]
        ):
            context += (
                "Settings: Settings tab contains detector config, calibration, advanced timing parameters. "
                "Detector section: wait time, averaging, USB connection status. "
                "Calibration section: OEM LED Calibration button, polarizer calibration. "
                "Advanced Settings: detector integration time, pump timing, valve delays. "
                "Changes saved automatically to workspace. "
            )

        return context.strip()

    # Safety timeout for model inference (seconds) — prevent UI freeze
    _INFERENCE_TIMEOUT = 30

    def generate_answer(self, question: str) -> tuple[str, bool]:
        """Generate conversational answer using TinyLM. Never hangs indefinitely.

        Args:
            question: User's question

        Returns:
            Tuple of (answer_text, success)
        """
        # Load model if needed (lazy loading)
        if not self._initialized:
            if not self._load_model():
                return (
                    "I'm not sure about that one yet. "
                    "Try asking about setup, calibration, methods, pumps, or data export.",
                    False,
                )

        try:
            # Build context
            context = self._build_context(question)

            # Create prompt with system instructions
            prompt = f"""<|system|>
You are Spark, a friendly assistant for Affilabs SPR software.
Rules:
- Answer in 1-3 short sentences. Never more than 4 sentences.
- Be warm and conversational, like a helpful colleague.
- Only mention the most important step or detail. Skip background info.
- If you don't know, say so briefly and suggest contacting support.
<|user|>
{context}

User question: {question}
<|assistant|>
"""

            # Generate response (silent - no user notification)
            logger.debug("Generating conversational response...")
            response = self._pipeline(
                prompt,
                max_new_tokens=150,
                num_return_sequences=1,
                pad_token_id=self._tokenizer.eos_token_id,
            )

            # Extract answer
            full_text = response[0]["generated_text"]

            # Split by assistant tag
            if "<|assistant|>" in full_text:
                answer = full_text.split("<|assistant|>")[-1].strip()
            else:
                answer = full_text[len(prompt) :].strip()

            # Clean up
            answer = answer.replace("<|user|>", "").replace("<|system|>", "").strip()

            # Remove any trailing special tokens
            for token in ["<|", "|>", "</s>"]:
                if token in answer:
                    answer = answer.split(token)[0].strip()

            # Validate answer quality
            if len(answer) < 10:
                raise ValueError("Answer too short")
            if len(answer) > 500:
                answer = answer[:500] + "..."

            logger.debug(f"Generated response ({len(answer)} chars)")
            return (answer, True)

        except Exception as e:
            logger.error(f"Response generation failed: {e}")
            return (
                "Hmm, I had trouble with that one. "
                "Try rephrasing, or ask about setup, calibration, methods, pumps, or export.",
                False,
            )
