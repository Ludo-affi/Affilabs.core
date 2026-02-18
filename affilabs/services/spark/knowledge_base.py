"""Spark Knowledge Base - Website content storage and retrieval

This module manages a searchable knowledge base of website content
that Spark can use to answer questions. Content can be manually added
or scraped from the Affinité Instruments website.

Features:
- Thread-safe search and retrieval
- Automatic database corruption repair
- Default content population
- Relevance scoring for search results

USAGE:
    kb = SparkKnowledgeBase()

    # Add content manually
    kb.add_article(
        title="How to Calibrate SPR Detector",
        content="Calibration steps...",
        category="calibration",
        url="https://www.affiniteinstruments.com/docs/calibration"
    )

    # Search for relevant content
    results = kb.search("calibration steps")
"""

from datetime import datetime
from pathlib import Path
import re
import threading
from typing import List, Dict
import logging

logger = logging.getLogger(__name__)


class SparkKnowledgeBase:
    """Searchable knowledge base for Spark AI help."""

    def __init__(self, db_path=None):
        """Initialize knowledge base (thread-safe).

        Args:
            db_path: Path to TinyDB database file. If None, uses default location
                    in affilabs/data/spark/knowledge_base.json
        """
        from tinydb import TinyDB
        import json
        from pathlib import Path

        if db_path is None:
            # Default to organized data location
            from affilabs.utils.resource_path import get_resource_path

            db_path = get_resource_path("data/spark/knowledge_base.json")

        # Ensure parent directory exists
        db_file = Path(db_path)
        db_file.parent.mkdir(parents=True, exist_ok=True)

        # Handle corrupted or empty database files
        if db_file.exists():
            try:
                with open(db_file, 'r') as f:
                    content = f.read().strip()
                    if not content:
                        # Empty file - delete it to force reinit
                        db_file.unlink()
                    else:
                        # Try to parse JSON
                        json.loads(content)
            except (json.JSONDecodeError, IOError):
                # Corrupted file - delete it
                logger.warning(f"Corrupted knowledge base file {db_file}, removing")
                db_file.unlink()

        self.db = TinyDB(str(db_path))
        self.articles = self.db.table("articles")
        self.faqs = self.db.table("faqs")
        
        # Thread safety for concurrent searches
        self._search_lock = threading.RLock()

        # Repair corrupt tables (e.g. faqs stored as [] instead of {})
        self._repair_tables()

        # Initialize with default content if empty
        if len(self.articles) == 0:
            self._populate_default_content()

    def _repair_tables(self):
        """Fix corrupt TinyDB tables (e.g. stored as list instead of dict)."""
        try:
            raw = self.db.storage.read()
            if raw is None:
                return
            changed = False
            for table_name in ("articles", "faqs"):
                if table_name in raw and isinstance(raw[table_name], list):
                    logger.warning(f"Repairing corrupt '{table_name}' table (was list, converting to dict)")
                    raw[table_name] = {}
                    changed = True
            if changed:
                self.db.storage.write(raw)
                # Re-open tables after repair
                self.articles = self.db.table("articles")
                self.faqs = self.db.table("faqs")
        except Exception as e:
            logger.warning(f"Table repair check failed: {e}")

    def _populate_default_content(self):
        """Populate with initial default content."""
        logger.info("Initializing Spark knowledge base with default content")

        # Default articles structure - can be expanded later
        default_articles = [
            {
                "title": "Getting Started with Affilabs",
                "content": (
                    "Affilabs is Affinité Instruments' SPR data acquisition software. "
                    "To get started:\n\n"
                    "1. Connect your SPR instrument via USB\n"
                    "2. Launch Affilabs - it will auto-detect your device\n"
                    "3. Run OEM LED Calibration (Settings tab)\n"
                    "4. Start acquiring data using the Start Recording button\n\n"
                    "For detailed tutorials, visit the Support section on our website."
                ),
                "category": "getting-started",
                "keywords": ["start", "begin", "setup", "connect", "installation", "first time"],
                "url": "https://www.affiniteinstruments.com/",
                "last_updated": datetime.now().isoformat(),
            },
            {
                "title": "SPR Technology Overview",
                "content": (
                    "Surface Plasmon Resonance (SPR) is a label-free detection method "
                    "for measuring biomolecular interactions in real-time. "
                    "Affinité Instruments provides compact, user-friendly SPR systems "
                    "suitable for research and quality control applications.\n\n"
                    "Our instruments offer:\n"
                    "• Multi-channel detection (up to 4 channels)\n"
                    "• Real-time kinetic measurements\n"
                    "• Temperature control\n"
                    "• Integrated microfluidics\n\n"
                    "Learn more about SPR technology on our website."
                ),
                "category": "technology",
                "keywords": ["spr", "surface plasmon", "technology", "how it works", "principle"],
                "url": "https://www.affiniteinstruments.com/",
                "last_updated": datetime.now().isoformat(),
            },
            {
                "title": "Contact Support",
                "content": (
                    "For technical support, questions, or assistance:\n\n"
                    "• Email: info@affiniteinstruments.com\n"
                    "• Website: https://www.affiniteinstruments.com/\n"
                    "• Submit questions through our contact form\n\n"
                    "Our support team typically responds within 1 business day."
                ),
                "category": "support",
                "keywords": ["contact", "support", "help", "email", "phone", "assistance"],
                "url": "https://www.affiniteinstruments.com/",
                "last_updated": datetime.now().isoformat(),
            },
            {
                "title": "Method Builder - Complete Syntax Guide",
                "content": (
                    "The Method Builder lets you create automated experiment sequences (methods). "
                    "Each method is a series of timed cycles that run back-to-back.\n\n"
                    "BASIC CYCLE FORMAT:\n"
                    "Type Duration [Channel:Concentration] [Modifiers]\n\n"
                    "CYCLE TYPES:\n"
                    "• Baseline (BL) - Running buffer only\n"
                    "• Binding (BN) - Manual injection with contact time\n"
                    "• Kinetic (KN) - Flow injection (association + dissociation)\n"
                    "• Regeneration (RG) - Strip bound analyte\n"
                    "• Immobilization (IM) - Attach ligand to sensor\n"
                    "• Blocking (BK) - Block unreacted surface\n"
                    "• Wash (WS) - Rinse flow path\n"
                    "• Other (OT) - Custom steps\n\n"
                    "DURATION EXAMPLES:\n"
                    "5s, 30sec, 5min, 5m, 2h, 2hr, overnight (=8h)\n\n"
                    "CONTACT TIME (for injections):\n"
                    "contact 180s, contact 3min, contact 5h (auto-enables Overnight Mode if >3h)\n\n"
                    "PARAMETER SHORTCUTS:\n"
                    "fr 50 (flow rate 50 µL/min) - shorthand for 'flow 50'\n"
                    "iv 25 (injection volume 25 µL)\n\n"
                    "MODIFIERS:\n"
                    "partial - 30 µL spike injection (vs full loop)\n"
                    "manual/automated - override injection mode\n"
                    "detection priority/off - adjust sensitivity\n\n"
                    "CHANNELS:\n"
                    "A, B, C, D, ALL (default)\n"
                    "Per-channel: A:100nM B:50nM (mix concentrations)\n\n"
                    "QUICK EXAMPLES:\n"
                    "Baseline 5min\n"
                    "BN 5min A:100nM contact 180s\n"
                    "KN 5min A:100nM fr 50 contact 3min\n"
                    "RG 30sec ALL:50mM"
                ),
                "category": "method-building",
                "keywords": ["method", "builder", "syntax", "cycle", "format", "type"],
                "url": "https://www.affiniteinstruments.com/",
                "last_updated": datetime.now().isoformat(),
            },
            {
                "title": "Cycle Type Abbreviations",
                "content": (
                    "Use these 2-letter abbreviations anywhere instead of full cycle type names:\n\n"
                    "BL = Baseline - Running buffer only, establishes stable signal\n"
                    "BN = Binding - Manual injection with contact time (5 min default)\n"
                    "IM = Immobilization - Attach ligand to sensor surface\n"
                    "BK = Blocking - Block unreacted surface sites\n"
                    "KN = Kinetic - Flow injection (association + dissociation phases)\n"
                    "CN = Concentration - Alias for Binding (deprecated, use BN)\n"
                    "RG = Regeneration - Strip bound analyte, restore baseline (30s default)\n"
                    "AS = Association - Alias for Kinetic (deprecated, use KN)\n"
                    "DS = Dissociation - Alias for Baseline (deprecated, use BL)\n"
                    "WS = Wash - Rinse flow path between steps\n"
                    "OT = Other - Custom steps (activation, equilibration, etc.)\n\n"
                    "EXAMPLES:\n"
                    "BL 5min (instead of Baseline 5min)\n"
                    "BN 5min A:100nM contact 180s (instead of Binding 5min A:100nM contact 180s)"
                ),
                "category": "method-building",
                "keywords": ["abbreviation", "cycle", "type", "short", "form", "BL", "BN", "IM", "BK"],
                "url": "https://www.affiniteinstruments.com/",
                "last_updated": datetime.now().isoformat(),
            },
            {
                "title": "Duration Shortcuts and Time Units",
                "content": (
                    "Flexible duration format:\n\n"
                    "SECONDS: 5s OR 5sec\n"
                    "MINUTES: 5m OR 5min\n"
                    "HOURS: 2h OR 2hr\n"
                    "SPECIAL: overnight (= 8 hours, auto-enables Overnight Mode)\n\n"
                    "EXAMPLES:\n"
                    "Baseline 30sec - 30 seconds\n"
                    "Binding 5min - 5 minutes\n"
                    "Baseline 2h - 2 hours\n"
                    "Baseline overnight - 8 hours (perfect for stability tests)\n\n"
                    "CONTACT TIME with HOURS:\n"
                    "contact 5h - 5 hours incubation (18,000 seconds)\n"
                    "contact 3m - 3 minutes (180 seconds)\n"
                    "⚠️ IMPORTANT: Contact times > 3 hours AUTO-ENABLE OVERNIGHT MODE"
                ),
                "category": "method-building",
                "keywords": ["duration", "time", "unit", "second", "minute", "hour", "overnight", "contact"],
                "url": "https://www.affiniteinstruments.com/",
                "last_updated": datetime.now().isoformat(),
            },
            {
                "title": "Parameter Shorthand (fr and iv)",
                "content": (
                    "Express flow rate and injection volume concisely:\n\n"
                    "FLOW RATE SHORTHAND:\n"
                    "fr 50 = same as 'flow 50' = 50 µL/min\n"
                    "Add to Kinetic cycles to control pump speed\n\n"
                    "INJECTION VOLUME SHORTHAND:\n"
                    "iv 25 = 25 µL injection volume\n"
                    "Add to any injection cycle\n\n"
                    "EXAMPLES:\n"
                    "Kinetic 5min A:100nM fr 50\n"
                    "Binding 5min A:100nM iv 25\n"
                    "Kinetic 5min A:100nM fr 50 iv 25 contact 3min (both parameters)\n\n"
                    "💡 Use fr for flow-based experiments, iv to customize injection size"
                ),
                "category": "method-building",
                "keywords": ["flow", "rate", "injection", "volume", "fr", "iv", "shorthand", "parameter"],
                "url": "https://www.affiniteinstruments.com/",
                "last_updated": datetime.now().isoformat(),
            },
            {
                "title": "In-Place Cycle Editing (#N Commands)",
                "content": (
                    "Edit cycles in the method table without removing them:\n\n"
                    "SYNTAX:\n"
                    "#N [modifiers] - Edit cycle number N\n"
                    "#2-5 [modifiers] - Edit range (cycles 2 through 5)\n"
                    "#all [modifiers] - Edit ALL cycles\n\n"
                    "EXAMPLES:\n"
                    "#3 contact 120s - Change cycle 3 contact time to 2 minutes\n"
                    "#3 channels BD - Restrict cycle 3 to channels B & D\n"
                    "#2-5 detection priority - Apply detection priority to cycles 2-5\n"
                    "#all detection off - Disable detection on ALL cycles\n"
                    "#3 contact 120s channels BD detection priority - Multiple mods at once\n\n"
                    "WORKFLOW:\n"
                    "1. Method table shows your queued cycles\n"
                    "2. Type an #N command in the Note field\n"
                    "3. Click '➕ Add to Method'\n"
                    "4. Changes apply immediately to the selected cycle(s)"
                ),
                "category": "method-building",
                "keywords": ["in-place", "edit", "modify", "#N", "#3", "cycle", "range", "all"],
                "url": "https://www.affiniteinstruments.com/",
                "last_updated": datetime.now().isoformat(),
            },
            {
                "title": "Channel Selection and Concentration Tags",
                "content": (
                    "CHANNEL FORMATS:\n"
                    "channels A - Single channel\n"
                    "channels BD - Multiple channels (B and D)\n"
                    "channels ALL - All channels (default)\n\n"
                    "CONCENTRATION TAGS:\n"
                    "Format: Channel:ValueUnit or [Channel:ValueUnit] (brackets optional)\n"
                    "Channels: A, B, C, D, ALL\n"
                    "Units: nM, µM, pM, mM, M, mg/mL, µg/mL, ng/mL\n\n"
                    "EXAMPLES:\n"
                    "A:100nM - Channel A at 100 nanoM\n"
                    "B:50µM - Channel B at 50 microM\n"
                    "ALL:25pM - All channels at 25 picoM\n"
                    "A:100nM B:50nM - Different concentrations per channel\n\n"
                    "PURPOSE:\n"
                    "Tags are for documentation and workflow tracking. "
                    "They don't affect injection volume or flow rate calculations."
                ),
                "category": "method-building",
                "keywords": ["channel", "concentration", "tag", "unit", "A", "B", "C", "D", "ALL"],
                "url": "https://www.affiniteinstruments.com/",
                "last_updated": datetime.now().isoformat(),
            },
            {
                "title": "Presets and Templates",
                "content": (
                    "**Where:** Use these commands in the Method Builder dialog (green ⚡ Spark button → type in popup)\n\n"
                    "SAVE A PRESET:\n"
                    "Type: !save my_protocol_name\n"
                    "Click: ➕ Add to Method\n"
                    "Saved in: cycle_templates.json\n\n"
                    "LOAD A PRESET:\n"
                    "Type: @my_protocol_name\n"
                    "Click: ⚡ Spark (opens popup) or press Enter in the Method Builder dialog\n\n"
                    "BUILT-IN TEMPLATES:\n"
                    "@spark titration - Dose-response series (auto-generates 5 concentrations + regen)\n"
                    "@spark kinetics - Association + long dissociation + regeneration\n"
                    "@spark amine coupling - Full amine coupling workflow\n"
                    "@spark binding - Multi-concentration binding template\n"
                    "@spark baseline - Single baseline cycle\n"
                    "@spark regeneration - Single regeneration cycle\n\n"
                    "QUICK GENERATION:\n"
                    "build 5 - Auto-generates 5 × (Binding 15min + Regen + Baseline)\n"
                    "build 10 - Auto-generates 10 × (Binding 15min + Regen + Baseline)"
                ),
                "category": "method-building",
                "keywords": ["preset", "template", "save", "load", "spark", "build", "reuse"],
                "url": "https://www.affiniteinstruments.com/",
                "last_updated": datetime.now().isoformat(),
            },
            {
                "title": "Common Method Examples",
                "content": (
                    "SIMPLE BINDING:\n"
                    "Baseline 5min\n"
                    "Binding 5min A:100nM contact 180s\n"
                    "Regeneration 30sec ALL:50mM\n\n"
                    "DOSE-RESPONSE TITRATION:\n"
                    "Baseline 5min\n"
                    "Binding 5min A:10nM contact 180s\n"
                    "Regeneration 30sec ALL:50mM\n"
                    "Baseline 2min\n"
                    "Binding 5min A:50nM contact 180s\n"
                    "Regeneration 30sec ALL:50mM\n"
                    "(Add more concentrations: 100nM, 500nM)\n\n"
                    "KINETICS (Association + Dissociation):\n"
                    "Baseline 2min\n"
                    "Kinetic 5min A:100nM contact 120s\n"
                    "Baseline 10min (dissociation phase)\n"
                    "Regeneration 30sec ALL:50mM\n\n"
                    "OVERNIGHT STABILITY TEST:\n"
                    "Baseline overnight (8 hours, auto-enables Overnight Mode)\n"
                    "Baseline 12h (12 hours)\n"
                    "Baseline 24hr (24 hours)\n\n"
                    "AMINE COUPLING WITH IMMOBILIZATION:\n"
                    "Baseline 30sec\n"
                    "Other 4min (EDC/NHS activation)\n"
                    "Immobilization 4min A:50µg/mL contact 180s\n"
                    "Wash 30sec\n"
                    "Other 4min (ethanolamine blocking)\n"
                    "Wash 30sec\n"
                    "Baseline 15min\n"
                    "(Add titration cycles)"
                ),
                "category": "method-building",
                "keywords": ["example", "binding", "titration", "kinetics", "amine", "coupling", "overnight"],
                "url": "https://www.affiniteinstruments.com/",
                "last_updated": datetime.now().isoformat(),
            },
            {
                "title": "P4SPR Channel Assignment — 4 Independent Sensors",
                "content": (
                    "The P4SPR has **4 fully independent optical channels (A, B, C, D)** — each with its own:\n"
                    "• Dedicated white-light LED source\n"
                    "• Fiber optic path to sensor\n"
                    "• Spectrometer pixel region\n"
                    "• **Independent fluidic channel** for sample injection\n\n"
                    "KEY POINT: You can inject **4 different analytes simultaneously** — one per channel.\n\n"
                    "CHANNEL USE PATTERNS:\n"
                    "**Option 1: All 4 channels** (most common)\n"
                    "Inject 4 different samples in parallel. Ideal for high-throughput screening or dose-response with different compounds.\n\n"
                    "**Option 2: Subset** (e.g., A + C only)\n"
                    "Inject 2 samples while B and D remain in buffer. Unused channels still acquire data.\n\n"
                    "**Option 3: 1 channel** (single-sample mode)\n"
                    "Use only channel A, ignore the rest. Good for beginner experiments.\n\n"
                    "SETUP:\n"
                    "In Method Builder, set each cycle with channels: `...channels ABCD` or `...channels AC` or just `channels A`.\n"
                    "Concentrations can differ per channel: `A:50nM B:100nM C:200nM D:400nM`."
                ),
                "category": "method-building",
                "keywords": ["p4spr", "channel", "4", "independent", "sensor", "analyte", "parallel", "fluidic"],
                "url": "https://www.affiniteinstruments.com/",
                "last_updated": datetime.now().isoformat(),
            },
            {
                "title": "P4SPR Manual Injection Timing & Technique",
                "content": (
                    "**The P4SPR uses manual syringe injection.** You pipette sample into each channel by hand.\n\n"
                    "TIMING:\n"
                    "When you click **Start Run**, the baseline timer begins. You have **up to 60 seconds** to inject all samples.\n"
                    "Injections are detected automatically when the analyte touches the sensor.\n\n"
                    "Inter-channel injection delay:\n"
                    "• If you pipette A→B→C→D sequentially, there can be **up to 15 seconds between the first and last injection**.\n"
                    "• The software accounts for this: each channel's binding kinetics timeline is referenced from its own injection detection, not the start time.\n\n"
                    "TECHNIQUE:\n"
                    "1. Prepare 4 sample aliquots in separate tubes (one per channel)\n"
                    "2. Pipette **100–200 µL** per channel (standard 1 mL pipette)\n"
                    "3. Inject smoothly into the inlet port for each channel\n"
                    "4. **Avoid air bubbles** — hold the pipette tip fully submerged\n"
                    "5. Use the same sample prep reagent (buffer) for all channels if possible\n\n"
                    "DETECTION:\n"
                    "Watch the sensorgram in real-time. When you inject, you'll see an immediate baseline shift (blue shift in SPR). "
                    "If no shift appears after 1–2 seconds, recheck the channels and try again."
                ),
                "category": "method-building",
                "keywords": ["p4spr", "inject", "injection", "manual", "syringe", "timing", "analyte", "sample"],
                "url": "https://www.affiniteinstruments.com/",
                "last_updated": datetime.now().isoformat(),
            },
            {
                "title": "P4SPR Starting Concentration Recommendations",
                "content": (
                    "**How much analyte should you use?** Here's a practical guide for P4SPR experiments.\n\n"
                    "GENERAL RANGES:\n"
                    "• **Proteins** (MW 10–100 kDa): Start at **100 nM** → 3-fold dilutions → 5–7 concentrations\n"
                    "• **Small molecules** (MW < 500): Start at **500 nM** → 3-fold dilutions → 5–7 concentrations\n"
                    "• **Antibodies** (MW 150 kDa): Start at **50 nM** → 2-fold or 3-fold dilutions → 5–7 concentrations\n\n"
                    "WHY THESE RANGES:\n"
                    "Affilabs sensors have **intermediate binding capacity** (~50–200 nM of ligand immobilized).\n"
                    "• **Too dilute** (< 1 nM): Signal is weak, you'll just see baseline noise.\n"
                    "• **Too concentrated** (> 10 µM): Binding saturates too fast — you lose kinetic detail.\n"
                    "• **Goldilocks zone** (10–500 nM): Kinetics are visible, binding curve is smooth.\n\n"
                    "DOSE-RESPONSE STRATEGY:\n"
                    "1. Start with one concentration (e.g., 100 nM)\n"
                    "2. If signal is weak (< 50 nm dip), use higher concentration\n"
                    "3. If signal saturates in < 20 sec, use lower concentration\n"
                    "4. Once happy with one, run 5–7 concentrations with 2–3× spacing\n\n"
                    "EXAMPLE:\n"
                    "Protein at 100 nM → step down: 100, 33, 11, 3.7, 1.2 nM (3-fold dilutions, 5 points)"
                ),
                "category": "method-building",
                "keywords": ["p4spr", "concentration", "dose", "response", "analyte", "protein", "dilution", "kinetics"],
                "url": "https://www.affiniteinstruments.com/",
                "last_updated": datetime.now().isoformat(),
            },
            {
                "title": "P4SPR Complete Experiment Workflow",
                "content": (
                    "**End-to-end workflow for a typical P4SPR binding kinetics experiment.**\n\n"
                    "PHASE 1: PREPARATION (20 min)\n"
                    "1. **Sensor prep:** Clean sensor, dry, inspect for scratches\n"
                    "2. **Buffer prep:** Make 3 buffers: running buffer, sample buffer, regeneration solution (typically 50 mM glycine pH 2.5)\n"
                    "3. **Analyte prep:** Prepare 4 sample aliquots (one per channel) at different concentrations\n"
                    "4. Open Affilabs, check **Device Status** → confirm detector + hardware connected\n\n"
                    "PHASE 2: CALIBRATION (5–10 min)\n"
                    "1. **Settings tab → Power On** (auto-runs startup calibration) → OK the QC Report\n"
                    "2. **Settings → OEM LED Calibration** (if first time or new sensor)\n\n"
                    "PHASE 3: SURFACE PREPARATION (15–30 min)\n"
                    "1. **Method Builder:**\n"
                    "   Baseline 5min\n"
                    "   Immobilization 10min [A:50µg/mL] [B:50µg/mL] [C:50µg/mL] [D:50µg/mL] contact 300s\n"
                    "   Wash 30sec\n"
                    "   Baseline 10min\n"
                    "2. **Click Run** → Watch baseline establish → When 'Ready for Injection' appears, inject ligand\n\n"
                    "PHASE 4: BINDING KINETICS (30–60 min)\n"
                    "1. **Add to method:**\n"
                    "   Binding 5min [A:100nM] [B:50nM] [C:25nM] [D:10nM] contact 180s\n"
                    "   Regeneration 30sec [ALL:50mM]\n"
                    "2. **Repeat** for remaining concentrations (5–7 total)\n"
                    "3. **Run → Start Recording** → Inject samples sequentially as prompted\n"
                    "4. Watch sensorgram in real-time. When run finishes, system auto-stops.\n\n"
                    "PHASE 5: ANALYSIS (varies)\n"
                    "1. **Live tab:** Review sensorgram, baseline, drift\n"
                    "2. **Analysis tab:** Fit kinetic models, extract Kd, ka, kd\n"
                    "3. **Export tab:** Save data to CSV/Excel\n\n"
                    "TOTAL TIME: ~2–3 hours for a complete 5-concentration dose-response."
                ),
                "category": "method-building",
                "keywords": ["p4spr", "workflow", "experiment", "protocol", "binding", "kinetics", "end-to-end", "complete"],
                "url": "https://www.affiniteinstruments.com/",
                "last_updated": datetime.now().isoformat(),
            },
            {
                "title": "P4SPR vs P4PRO — What's the Difference?",
                "content": (
                    "Confused about which instrument to choose? Here's the breakdown:\n\n"
                    "| Feature | P4SPR | P4PRO |\n"
                    "| --- | --- | --- |\n"
                    "| **Optical channels** | 4 independent | 4 independent |\n"
                    "| **Sample injection** | **Manual syringe** (pipette by hand) | **Automated 6-port valve** + AffiPump |\n"
                    "| **Fluidic channels** | 4 independent | 2 addressable per cycle (AC or BD) |\n"
                    "| **Pump** | None (or optional AffiPump) | AffiPump (external syringe pump, pulseless) |\n"
                    "| **Flow quality** | Manually pipetted | Precision-controlled, no pulsation |\n"
                    "| **Best for** | Manual work, 4-sample parallel | High-throughput, reproducible injections |\n"
                    "| **Price** | Lower | Higher (includes pump + automation) |\n"
                    "| **Method mode** | Manual only | Manual or Semi-Automated |\n\n"
                    "**P4SPR:** You pipette each sample manually into each channel. Great for flexibility, research labs, lower sample throughput.\n\n"
                    "**P4PRO:** Automated injections via programmable syringe pump. Better for QC, production, when you need reproducibility and higher throughput. "
                    "Note: Only 2 fluidic channels active per injection (AC or BD), so to inject 4 different samples, you run 2 cycles."
                ),
                "category": "method-building",
                "keywords": ["p4spr", "p4pro", "difference", "comparison", "manual", "automated", "pump", "automation"],
                "url": "https://www.affiniteinstruments.com/",
                "last_updated": datetime.now().isoformat(),
            },
        ]

        for article in default_articles:
            self.articles.insert(article)

        logger.info(f"Added {len(default_articles)} default articles to knowledge base")

    def add_article(
        self, title: str, content: str, category: str, keywords: List[str] = None, url: str = None
    ) -> int:
        """Add an article to the knowledge base.

        Args:
            title: Article title
            content: Article content (can include markdown)
            category: Category (e.g., 'calibration', 'troubleshooting', 'tutorial')
            keywords: List of keywords for searching
            url: URL to the original content on website

        Returns:
            int: Database ID of inserted article
        """
        article = {
            "title": title,
            "content": content,
            "category": category,
            "keywords": keywords or [],
            "url": url or "https://www.affiniteinstruments.com/",
            "last_updated": datetime.now().isoformat(),
        }

        doc_id = self.articles.insert(article)
        logger.debug(f"Added article: {title} (ID: {doc_id})")
        return doc_id

    def add_faq(
        self, question: str, answer: str, category: str = "general", url: str = None
    ) -> int:
        """Add a FAQ entry.

        Args:
            question: The question text
            answer: The answer text
            category: Category for organization
            url: URL to FAQ page on website

        Returns:
            int: Database ID of inserted FAQ
        """
        faq = {
            "question": question,
            "answer": answer,
            "category": category,
            "url": url or "https://www.affiniteinstruments.com/",
            "last_updated": datetime.now().isoformat(),
        }

        doc_id = self.faqs.insert(faq)
        logger.debug(f"Added FAQ: {question[:50]}... (ID: {doc_id})")
        return doc_id

    def search(self, query: str, max_results: int = 3) -> List[Dict]:
        """Search knowledge base for relevant content (thread-safe).

        Uses keyword matching and content search to find relevant articles.
        Performance: <50ms typical, <100ms with many articles.

        Args:
            query: Search query
            max_results: Maximum number of results to return

        Returns:
            List of matching articles/FAQs with relevance scores
        """
        # Validate input
        if not query or not query.strip():
            return []

        try:
            with self._search_lock:
                query_lower = query.lower()
                query_words = set(re.findall(r"\w+", query_lower))

                results = []

                # Search articles
                try:
                    for article in self.articles.all():
                        try:
                            score = self._calculate_relevance(query_lower, query_words, article)
                            if score > 0:
                                results.append(
                                    {
                                        "type": "article",
                                        "title": article.get("title", ""),
                                        "content": article.get("content", ""),
                                        "category": article.get("category", ""),
                                        "url": article.get("url", "https://www.affiniteinstruments.com/"),
                                        "score": score,
                                    }
                                )
                        except Exception as e:
                            logger.debug(f"Error scoring article: {e}")
                            continue
                except Exception as e:
                    logger.warning(f"Articles search failed (corrupt table?): {e}")

                # Search FAQs
                try:
                    for faq in self.faqs.all():
                        try:
                            # Check if question matches
                            q_score = self._calculate_relevance(
                                query_lower, query_words, {"content": faq.get("question", ""), "keywords": []}
                            )

                            if q_score > 0:
                                results.append(
                                    {
                                        "type": "faq",
                                        "title": faq.get("question", ""),
                                        "content": faq.get("answer", ""),
                                        "category": faq.get("category", ""),
                                        "url": faq.get("url", "https://www.affiniteinstruments.com/"),
                                        "score": q_score + 0.5,  # Boost FAQ scores slightly
                                    }
                                )
                        except Exception as e:
                            logger.debug(f"Error scoring FAQ: {e}")
                            continue
                except Exception as e:
                    logger.warning(f"FAQ search failed (corrupt table?): {e}")

                # Sort by relevance score (limit to prevent large result sets)
                results.sort(key=lambda x: x.get("score", 0), reverse=True)

                return results[:max_results]
        except Exception as e:
            logger.error(f"Search failed: {e}")
            return []

    def _calculate_relevance(self, query_lower: str, query_words: set, item: dict) -> float:
        """Calculate relevance score for an item.

        Args:
            query_lower: Lowercase query string
            query_words: Set of query words
            item: Article or FAQ dict

        Returns:
            float: Relevance score (0.0 - 10.0)
        """
        score = 0.0

        # Check keywords (highest weight)
        keywords = item.get("keywords", [])
        for keyword in keywords:
            if keyword.lower() in query_lower:
                score += 3.0

        # Check content (medium weight)
        content = item.get("content", "").lower()
        for word in query_words:
            if len(word) > 3:  # Ignore short words
                if word in content:
                    score += 1.0

        # Check title if present (high weight)
        title = item.get("title", "").lower()
        for word in query_words:
            if len(word) > 3 and word in title:
                score += 2.0

        return score

    def get_by_category(self, category: str) -> List[Dict]:
        """Get all articles in a category.

        Args:
            category: Category name

        Returns:
            List of articles in that category
        """
        from tinydb import Query

        Article = Query()
        return self.articles.search(Article.category == category)

    def update_article(self, doc_id: int, **fields):
        """Update an article.

        Args:
            doc_id: Database ID
            **fields: Fields to update
        """
        fields["last_updated"] = datetime.now().isoformat()
        self.articles.update(fields, doc_ids=[doc_id])

    def delete_article(self, doc_id: int):
        """Delete an article.

        Args:
            doc_id: Database ID
        """
        self.articles.remove(doc_ids=[doc_id])

    def clear_all(self):
        """Clear all knowledge base content."""
        self.articles.truncate()
        self.faqs.truncate()
        logger.warning("Knowledge base cleared")

    def get_stats(self) -> dict:
        """Get knowledge base statistics.

        Returns:
            dict: Statistics about the knowledge base
        """
        return {
            "total_articles": len(self.articles),
            "total_faqs": len(self.faqs),
            "categories": list(set(a["category"] for a in self.articles.all())),
        }
