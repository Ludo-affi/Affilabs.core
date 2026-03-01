"""
Spark Pattern Definitions - Single Source of Truth

All pre-defined Q&A patterns for the Spark AI assistant.
Organized by category. Answers are concise and conversational.

To add new patterns:
1. Find the appropriate category or create a new one
2. Add the regex pattern as a key
3. Provide answer text, category, keywords, and priority
4. Test with real user questions

Pattern format:
{
    r"regex_pattern": {
        "answer": "Concise answer text...",
        "category": "category_name",
        "keywords": ["keyword1", "keyword2"],
        "priority": "high|medium|low"
    }
}
"""

PATTERNS = {
    "startup": {
        r"getting.*started.*affilabs|start.*with.*affilabs|begin.*affilabs|how.*use.*affilabs|affilabs.*getting.*started": {
            "answer": "Welcome to Affilabs! Here's the quick setup:\n\n"
            "1. Connect your SPR instrument via USB\n"
            "2. Launch Affilabs — it auto-detects your device\n"
            "3. Complete startup calibration (1-2 min)\n"
            "4. Head to the **Method** tab to build your experiment\n\n"
            "You can also explore the interface without hardware connected.",
            "category": "startup",
            "keywords": ["getting", "started", "affilabs", "begin", "start", "how", "use"],
            "priority": "high"
        },
        r"power.*on|start.*system|startup.*procedure|turn.*on": {
            "answer": "To power on:\n\n"
            "1. Click **Power On** (top right)\n"
            "2. Startup calibration runs automatically (1-2 min)\n"
            "3. Review the QC Report, then click **Start**\n\n"
            "The system begins in Auto-Read mode. Build a method and press **Record** to save data.",
            "category": "startup",
            "keywords": ["power", "on", "start", "system", "startup", "turn"],
            "priority": "high"
        },
        r"calibration.*fail|startup.*calibration|qc.*report": {
            "answer": "Startup calibration takes 1-2 minutes. If it fails, check for flow path obstructions, "
            "verify reagents are loaded, and confirm the detector connection. You can retry or power cycle the device.",
            "category": "startup",
            "keywords": ["calibration", "fail", "startup", "qc", "report"],
            "priority": "high"
        },
        r"auto.*read.*mode|how.*to.*record|save.*data.*live": {
            "answer": "The system starts in **Auto-Read mode** — it shows live data but doesn't save it.\n\n"
            "To record: go to the **Method** tab, build your method, and press **Record**.",
            "category": "startup",
            "keywords": ["auto", "read", "mode", "record", "save", "data"],
            "priority": "medium"
        },
        r"hardware.*not.*found|cannot.*find.*hardware|device.*not.*connected": {
            "answer": "Try these steps:\n\n"
            "1. Check both ends of the USB cable\n"
            "2. Try a different USB port (USB 3.0 preferred)\n"
            "3. Check Windows Device Manager for driver issues\n"
            "4. Restart the software and power cycle the device\n\n"
            "Still not working? Contact support at info@affiniteinstruments.com.",
            "category": "startup",
            "keywords": ["hardware", "not", "found", "device", "connected"],
            "priority": "high"
        },
    },

    "basic": {
        r"how.*(start|begin|run).*(acquisition|test|experiment|run)|begin.*recording|start.*a.*(test|run|experiment)": {
            "answer": "Click the **Live** tab, make sure your detector is connected (check **Device Status**), "
            "and hit the green **Start** button. Data streams in real-time.",
            "category": "basic",
            "keywords": ["start", "acquisition", "begin", "recording", "test", "experiment", "run"],
            "priority": "high"
        },
        r"how.*stop.*acquisition|end.*recording": {
            "answer": "Click the red **Stop** button in the Live tab, or press **Ctrl+S**.",
            "category": "basic",
            "keywords": ["stop", "acquisition", "end", "recording"],
            "priority": "high"
        },
    },

    "export": {
        r"export.*data|save.*data|download.*data": {
            "answer": "Go to the **Export** tab, pick your format (Excel, CSV, or AnIML), "
            "select the cycles you want, and click **Export**.",
            "category": "export",
            "keywords": ["export", "save", "download", "data"],
            "priority": "high"
        },
    },

    "hardware": {
        r"detector.*not.*found|can't.*find.*detector|no.*detector": {
            "answer": "Check that your USB cable is firmly connected, then open **Device Status** and click "
            "**Scan for Devices**. If it's still not showing, try a different USB port (USB 3.0 preferred) "
            "or check Device Manager for driver issues.",
            "category": "hardware",
            "keywords": ["detector", "not", "found", "can't", "find"],
            "priority": "high"
        },
    },

    "calibration": {
        r"what.*calibrations|calibration.*types|how.*many.*calibrations": {
            "answer": "There are 5 calibration types:\n\n"
            "1. **Simple LED** — Quick sensor swap (10-20 sec)\n"
            "2. **Full System** — Complete with QC report (3-5 min)\n"
            "3. **Polarizer** — Servo position optimization (2-5 min)\n"
            "4. **OEM LED** — Factory-level full calibration (10-15 min)\n"
            "5. **LED Model Training** — Rebuild optical model (2-5 min)\n\n"
            "All found in **Settings → Calibration Controls**.",
            "category": "calibration",
            "keywords": ["calibrations", "types", "how", "many"],
            "priority": "high"
        },
        r"simple.*calibration|simple.*led|quick.*calibration": {
            "answer": "**Simple LED Calibration** takes 10-20 seconds — perfect for same-type sensor swaps "
            "when an LED model already exists.\n\n"
            "Run it from **Settings → Run Simple Calibration**. "
            "If you get a 'LED model not found' error, run **OEM Calibration** first.",
            "category": "calibration",
            "keywords": ["simple", "calibration", "led", "quick"],
            "priority": "high"
        },
        r"full.*calibration|complete.*calibration|6.*step": {
            "answer": "**Full System Calibration** takes 3-5 minutes and runs 6 steps: dark reference, "
            "S/P convergence, S/P reference, and QC validation.\n\n"
            "Go to **Settings → Run Full Calibration**, then review the QC Report when done. "
            "Great for sensor swaps, monthly QC, or after maintenance.",
            "category": "calibration",
            "keywords": ["full", "calibration", "complete", "6", "step"],
            "priority": "high"
        },
        r"polarizer.*calibration|servo.*calibration|calibrate.*polarizer": {
            "answer": "**Polarizer Calibration** (2-5 min) finds optimal servo positions for S and P modes "
            "by sweeping across 180°.\n\n"
            "Run from **Settings → Calibrate Polarizer**. Use when signal drops or after replacing a servo.",
            "category": "calibration",
            "keywords": ["polarizer", "calibration", "servo"],
            "priority": "medium"
        },
        r"oem.*calibration|factory.*calibration|complete.*calibration": {
            "answer": "**OEM LED Calibration** is the most thorough option (10-15 min). It runs servo calibration "
            "+ LED model training + full 6-step calibration.\n\n"
            "Go to **Settings → Run OEM Calibration**. Use for first-time setup, missing LED model, or a complete "
            "system reset. For quick sensor swaps, use **Simple LED** instead.",
            "category": "calibration",
            "keywords": ["oem", "calibration", "factory", "complete"],
            "priority": "high"
        },
        r"led.*model.*training|train.*led|optical.*model": {
            "answer": "**LED Model Training** (2-5 min) rebuilds just the optical model without a full calibration.\n\n"
            "Go to **Settings → Train LED Model**. Faster than OEM when you only need the model rebuilt.",
            "category": "calibration",
            "keywords": ["led", "model", "training", "train", "optical"],
            "priority": "medium"
        },
        r"startup.*calibration|daily.*calibration|power.*on.*calibration": {
            "answer": "Startup calibration runs automatically when you click **Power On** (1-2 min). "
            "If it fails, click **Retry** (up to 3 times) or **Continue Anyway** to troubleshoot manually.\n\n"
            "Common causes: air bubbles, cold hardware, or connection issues. "
            "Allow 30-60 min warmup before the first calibration of the day.",
            "category": "calibration",
            "keywords": ["startup", "calibration", "daily", "power", "on"],
            "priority": "high"
        },
        r"calibration.*failed|retry.*calibration|calibration.*fail": {
            "answer": "Click **Retry** (up to 3 attempts) or **Continue Anyway** to troubleshoot.\n\n"
            "Common causes: air bubbles, insufficient warmup, hardware issues, or missing LED model. "
            "You can also run a **Full System Calibration** manually from the Settings tab.",
            "category": "calibration",
            "keywords": ["calibration", "failed", "retry", "fail"],
            "priority": "high"
        },
        r"when.*calibrate|which.*calibration|calibration.*use": {
            "answer": "Quick guide:\n\n"
            "• **Same-type sensor swap** → Simple LED (10-20 sec)\n"
            "• **Different sensor type** → Full System (3-5 min)\n"
            "• **First-time setup** → OEM LED (10-15 min)\n"
            "• **LED model missing** → LED Model Training (2-5 min)\n"
            "• **Servo positions wrong** → Polarizer (2-5 min)\n"
            "• **Daily startup** → Automatic on Power On",
            "category": "calibration",
            "keywords": ["when", "calibrate", "which", "use"],
            "priority": "high"
        },
        r"led.*model.*not.*found|optical.*calibration.*missing": {
            "answer": "This error means `optical_calibration.json` is missing.\n\n"
            "**Quick fix:** Settings → **Train LED Model** (2-5 min)\n"
            "**Complete fix:** Settings → **Run OEM Calibration** (10-15 min)\n\n"
            "First-time setup? Go with OEM.",
            "category": "calibration",
            "keywords": ["led", "model", "not", "found", "missing"],
            "priority": "high"
        },
        r"calibration.*freeze|calibration.*hang|calibration.*stuck": {
            "answer": "Wait 5 minutes first — some steps take time. If still frozen, close and restart the software, "
            "then try again.\n\n"
            "Prevent this by ensuring a stable connection, allowing warmup time, checking for air bubbles, "
            "and not changing settings during calibration.",
            "category": "calibration",
            "keywords": ["calibration", "freeze", "hang", "stuck"],
            "priority": "medium"
        },
        r"qc.*report|quality.*control|calibration.*qc": {
            "answer": "The **QC Report** appears after Full or OEM calibrations and validates signal strength, "
            "LED convergence, baseline stability, and reference quality.\n\n"
            "If you see warnings: check prism/LEDs (low signal), allow more warmup (drift), "
            "or retrain the LED model (slow convergence).",
            "category": "calibration",
            "keywords": ["qc", "report", "quality", "control"],
            "priority": "medium"
        },
        r"sensor.*swap|replace.*sensor|change.*sensor": {
            "answer": "**Same type** (e.g. gold→gold): Install sensor → **Simple Calibration** (10-20 sec)\n"
            "**Different type**: Install sensor → **Full Calibration** (3-5 min)\n"
            "**Major change**: Install sensor → **OEM Calibration** (10-15 min)\n\n"
            "Make sure there are no air bubbles!",
            "category": "calibration",
            "keywords": ["sensor", "swap", "replace", "change"],
            "priority": "high"
        },
        r"calibration.*best.*practice|calibration.*tips": {
            "answer": "**Before:** Clean prism, use fresh bubble-free buffer, allow 30-60 min warmup.\n"
            "**During:** Don't disturb the system or change settings.\n"
            "**After:** Review QC Report, verify sensorgram looks good.\n\n"
            "Schedule: daily startup (auto), weekly Full System, monthly OEM.",
            "category": "calibration",
            "keywords": ["calibration", "best", "practice", "tips"],
            "priority": "medium"
        },
    },

    "pump": {
        r"pump.*types|which.*pump|pump.*configuration|do.*i.*need.*pump": {
            "answer": "**SimplexSPR uses manual syringe injection — no pump required.**\n\n"
            "You inject samples by hand with a pipette or syringe directly into each flow cell.\n\n"
            "An optional **AffiPump** accessory is available for automated flow if needed later.",
            "category": "pump",
            "keywords": ["pump", "types", "which", "configuration", "need"],
            "priority": "high"
        },
        r"how.*pump|use.*pump|pump.*control|start.*pump": {
            "answer": "**SimplexSPR is designed for manual injection — no pump needed.**\n\n"
            "If you have the optional AffiPump accessory:\n"
            "Set flow rate in the **Flow** tab → choose pump → click **Run Buffer** → **Stop** when done.\n\n"
            "Most SimplexSPR users work entirely with manual syringe injection.",
            "category": "pump",
            "keywords": ["how", "pump", "use", "control", "start"],
            "priority": "high"
        },
        r"prime.*pump|pump.*priming|how.*prime": {
            "answer": "**Priming applies only if you have the optional AffiPump accessory.**\n\n"
            "Go to **Flow** tab → click **Prime Pump**. It runs 6 cycles to fill tubing with buffer "
            "and remove air bubbles (~2-3 min).\n\n"
            "For standard SimplexSPR manual injection, no priming is needed.",
            "category": "pump",
            "keywords": ["prime", "pump", "priming"],
            "priority": "medium"
        },
        r"cleanup.*pump|pump.*cleanup|remove.*bubbles": {
            "answer": "**For manual injection (SimplexSPR):** Remove bubbles by gently pushing buffer through "
            "the flow cell with your syringe. Tilt the instrument slightly to help trapped bubbles escape.\n\n"
            "**With optional AffiPump:** Click **Cleanup** in the Flow tab — it runs pulse + prime cycles (~3-4 min).",
            "category": "pump",
            "keywords": ["cleanup", "pump", "remove", "bubbles"],
            "priority": "high"
        },
        r"pump.*flush|flush.*pump|flush.*system": {
            "answer": "**For manual injection:** Flush by pushing 200-500 µL of fresh buffer through each flow cell with your syringe.\n\n"
            "**With optional AffiPump:** Click **Flush** in the Flow tab for a quick 1-minute system rinse.",
            "category": "pump",
            "keywords": ["pump", "flush", "system"],
            "priority": "medium"
        },
        r"pump.*blocked|blockage|pump.*error": {
            "answer": "**For manual injection:** If flow seems blocked:\n\n"
            "1. Check for air bubbles at the flow cell inlet\n"
            "2. Gently push buffer through with steady pressure\n"
            "3. If blocked, carefully disconnect tubing and check for debris\n"
            "4. Re-compress the sensor chip and try again\n\n"
            "**With optional AffiPump:** Click **Home Pumps**, then run **Prime Pump**.",
            "category": "pump",
            "keywords": ["pump", "blocked", "blockage", "error"],
            "priority": "high"
        },
        r"channel.*routing|channel.*a.*b.*c.*d|sensor.*channels": {
            "answer": "SimplexSPR has **4 fully independent channels (A, B, C, D)**.\n\n"
            "Each channel has its own flow cell inlet — you pipette each one separately.\n"
            "Use different analytes per channel, or the same analyte at different concentrations.\n\n"
            "Typical setup: one channel as buffer reference, three for samples.",
            "category": "pump",
            "keywords": ["channel", "routing", "a", "b", "c", "d"],
            "priority": "medium"
        },
        r"flow.*rate|set.*flow|pump.*speed": {
            "answer": "**SimplexSPR uses static injection** — you inject by hand, so flow rate is controlled "
            "by how fast you push the syringe. Push slowly and steadily (~1 drop/sec).\n\n"
            "**With optional AffiPump:** Set flow rate in the Flow tab (typical: 50-200 µL/min for experiments).",
            "category": "pump",
            "keywords": ["flow", "rate", "set", "speed"],
            "priority": "medium"
        },
        r"pump.*emergency.*stop|emergency.*stop|stop.*pump": {
            "answer": "**For manual injection:** Simply stop pushing the syringe.\n\n"
            "**With optional AffiPump:** Click the red **Emergency Stop** button — all pumps halt immediately.",
            "category": "pump",
            "keywords": ["pump", "emergency", "stop"],
            "priority": "high"
        },
        r"pump.*troubleshoot|pump.*not.*working|pump.*issue": {
            "answer": "**SimplexSPR manual injection troubleshooting:**\n\n"
            "**No signal change:** Verify sample is in contact with the sensor — push slowly, check for leaks.\n"
            "**Bubbles in flow cell:** Tilt instrument, push buffer through gently.\n"
            "**Uneven signal across channels:** Inject more evenly — try to pipette all 4 channels within 15 seconds.\n\n"
            "**With optional AffiPump:** Check Device Status for connection, verify COM port, try **Home Pumps**.",
            "category": "pump",
            "keywords": ["pump", "troubleshoot", "not", "working", "issue"],
            "priority": "high"
        },
    },

    "manual_injection": {
        r"manual.*injection.*workflow|how.*manual.*inject|manual.*syringe|perform.*manual.*injection": {
            "answer": "**Manual Injection Workflow:**\n\n"
            "1. Build a Concentration cycle in **Manual** mode\n"
            "2. Start the run — system shows live sensorgram\n"
            "3. Watch for baseline plateau, then **Ctrl+Click** on sensorgram to place injection flag\n"
            "4. Manual injection dialog appears — inject sample via syringe\n"
            "5. Click **Injection Complete** when done\n"
            "6. Contact timer counts down — **wash flags appear automatically** when timer expires\n"
            "7. Perform wash when 'WASH NOW' alert appears\n\n"
            "💡 Pump/semi-automated modes skip the dialog and detect automatically.",
            "category": "manual_injection",
            "keywords": ["manual", "injection", "workflow", "syringe", "perform"],
            "priority": "high"
        },
        r"injection.*flag|place.*injection.*flag|ctrl.*click.*flag": {
            "answer": "**Ctrl+Click** on the live sensorgram to place an injection flag at the current time point. "
            "This marks when you're ready to inject and triggers the manual injection dialog.\n\n"
            "The dialog shows a 60-second detection window with channel LED indicators. "
            "Click 'Injection Complete' after injecting to start the contact timer.",
            "category": "manual_injection",
            "keywords": ["injection", "flag", "place", "ctrl", "click"],
            "priority": "high"
        },
        r"wash.*flag.*automatic|automatic.*wash|when.*wash.*flag|wash.*flag.*placed": {
            "answer": "**Wash flags are now automatic!** They appear when the contact timer expires.\n\n"
            "After you place an injection flag and complete the injection, the contact timer starts counting down. "
            "When it reaches zero, the system:\n"
            "• Shows 'WASH NOW' alert on timer button\n"
            "• Plays alarm sound\n"
            "• **Automatically places wash flags** on all channels\n\n"
            "You no longer need to manually place wash flags — just perform the wash when alerted.",
            "category": "manual_injection",
            "keywords": ["wash", "flag", "automatic", "when", "placed"],
            "priority": "high"
        },
        r"contact.*timer|contact.*time.*countdown|wash.*alert|wash.*now": {
            "answer": "The **contact timer** starts after injection and counts down to zero. "
            "When it expires:\n\n"
            "• Timer button shows **yellow 'WASH NOW' alert**\n"
            "• Alarm sound plays (if enabled)\n"
            "• Wash flags automatically placed\n\n"
            "Click the timer button to stop the alarm. Set contact time in your cycle note (e.g. `contact 180s`).",
            "category": "manual_injection",
            "keywords": ["contact", "timer", "countdown", "wash", "alert", "now"],
            "priority": "high"
        },
        r"manual.*injection.*dialog|60.*second.*window|injection.*detection.*window": {
            "answer": "The **manual injection dialog** appears only for manual syringe injections. It shows:\n\n"
            "• 60-second timeout countdown\n"
            "• Channel LED indicators (turn green when injection detected)\n"
            "• 'Injection Complete' button\n\n"
            "The dialog auto-closes when all channels detect injection or timeout expires. "
            "Pump/semi-automated modes skip this dialog entirely and detect automatically.",
            "category": "manual_injection",
            "keywords": ["manual", "injection", "dialog", "60", "second", "window", "detection"],
            "priority": "medium"
        },
        r"detection.*mode|detection.*priority|sensitivity.*factor|manual.*pump.*detection": {
            "answer": "**Detection modes** control injection detection sensitivity:\n\n"
            "• **Manual** (factor 2.0): Conservative, avoids false positives from syringe noise\n"
            "• **Pump** (factor 0.75): Tight detection for clean pump injections\n"
            "• **Priority** (factor 1.0): Medium sensitivity\n"
            "• **Off** (factor 999): Disables auto-detection\n\n"
            "Detection threshold = 2.5 × baseline_std × sensitivity_factor. "
            "Set in Method Builder → Settings (⚙ cog button).",
            "category": "manual_injection",
            "keywords": ["detection", "mode", "priority", "sensitivity", "factor", "manual", "pump"],
            "priority": "medium"
        },
        r"injection.*not.*detected|detection.*missed|false.*negative": {
            "answer": "If injection isn't detected:\n\n"
            "1. Check **Device Type** in Method Builder Settings (⚙ button) — use 'Manual' for syringes\n"
            "2. Lower **Detection Priority** to Baseline for more sensitive detection\n"
            "3. Verify you clicked 'Injection Complete' in the dialog\n"
            "4. Make sure injection volume is sufficient (>10 µL)\n\n"
            "Manual mode uses factor 2.0 to avoid syringe handling noise.",
            "category": "manual_injection",
            "keywords": ["injection", "not", "detected", "missed", "false", "negative"],
            "priority": "medium"
        },
        r"false.*positive.*detection|noise.*trigger|detection.*too.*sensitive": {
            "answer": "If detection triggers on noise:\n\n"
            "1. Switch **Device Type** to 'Manual' (factor 2.0, more conservative)\n"
            "2. Increase **Detection Priority** to Elevated for stricter detection\n"
            "3. Turn off detection completely with 'Off' mode\n"
            "4. Check for air bubbles causing baseline spikes\n\n"
            "Settings are in Method Builder → ⚙ Settings panel (below table).",
            "category": "manual_injection",
            "keywords": ["false", "positive", "detection", "noise", "trigger", "sensitive"],
            "priority": "medium"
        },
        r"injection.*deadline.*marker|orange.*line|wash.*deadline": {
            "answer": "The **orange deadline marker** appears automatically after injection to show when contact time will expire. "
            "It's a visual guide to help you plan the wash timing.\n\n"
            "Position = injection_time + contact_time. When the live cursor reaches it, the wash alert triggers.",
            "category": "manual_injection",
            "keywords": ["injection", "deadline", "marker", "orange", "line", "wash"],
            "priority": "low"
        },
    },

    "method": {
        r"create.*cycle|new.*cycle|build.*cycle": {
            "answer": "1. Click **+ Build Method** in the sidebar\n"
            "2. Type cycles in the Note field (one per line)\n"
            "3. Click **➕ Add to Method**\n"
            "4. Reorder with ↑/↓ as needed\n"
            "5. Click **📋 Push to Queue** → **▶ Start Run**\n\n"
            "Example: `Binding 8.5min A:100nM contact 300s`",
            "category": "method",
            "keywords": ["create", "cycle", "new", "build", "method", "how"],
            "priority": "high"
        },
        r"how.*build.*method|how.*make.*method|how.*create.*method|method.*builder|build.*method": {
            "answer": "Open **+ Build Method** from the sidebar and type cycles one per line:\n\n"
            "`Baseline 5min`\n"
            "`Binding 8.5min A:100nM contact 300s`\n"
            "`Regeneration 30sec ALL:50mM`\n\n"
            "Click **➕ Add to Method** → **📋 Push to Queue** → **▶ Start Run**.\n\n"
            "Shortcuts: `build 5` for auto-generated series, `@spark amine coupling` for templates.",
            "category": "method",
            "keywords": ["build", "method", "how", "create", "make"],
            "priority": "high"
        },
        r"cycle.*type|what.*types|available.*types|type.*cycle": {
            "answer": "There are 7 cycle types for P4SPR manual injection:\n\n"
            "• **Baseline** — Running buffer, no injection\n"
            "• **Binding** — Manual injection, 5 min contact, 8.5 min total window\n"
            "• **Regeneration** — Strip bound analyte (30s contact)\n"
            "• **Immobilization** — 30 min freestyle window for ligand attachment (no injection prompt)\n"
            "• **Blocking** — Block unreacted surface sites, no injection\n"
            "• **Wash** — Rinse flow path, no injection\n"
            "• **Other** — Custom step (activation, etc.)\n\n"
            "All injections start 20 seconds into the cycle.",
            "category": "method",
            "keywords": ["cycle", "types", "available", "what"],
            "priority": "high"
        },
        r"cycle.*syntax|how.*write.*cycle|note.*syntax|note.*format|how.*type.*cycle": {
            "answer": "Format: `Type Duration Channel:ValueUnits contact Ns`\n\n"
            "Examples:\n"
            "• `Baseline 5min`\n"
            "• `Binding 8.5min A:100nM contact 300s`\n"
            "• `Regeneration 30sec ALL:50mM`\n"
            "• `Binding 8.5min A:100nM contact 300s partial`\n\n"
            "Channels: A, B, C, D, ALL. Units: nM, µM, mM, mg/mL, etc.",
            "category": "method",
            "keywords": ["syntax", "write", "cycle", "note", "format", "type"],
            "priority": "high"
        },
        r"what.*contact.*time|contact.*time|injection.*time": {
            "answer": "**Contact time** is how long sample stays in the flow cell after injection. "
            "Add `contact Ns` to your cycle line (e.g. `contact 180s`).\n\n"
            "Regeneration auto-sets to 30 seconds. Baseline and Other types don't inject.",
            "category": "method",
            "keywords": ["contact", "time", "injection"],
            "priority": "medium"
        },
        r"what.*injection|injection.*method|simple.*inject|partial.*inject|how.*inject": {
            "answer": "**Simple injection** (default): Manual syringe — user pipettes sample at the prompt.\n"
            "**Partial injection**: 30 µL spike — add `partial injection` to the cycle line.\n\n"
            "Binding and Regeneration cycles expect a manual injection. "
            "Baseline, Immobilization, Blocking, Wash, and Other have no injection prompt. "
            "All injections start 20 seconds into the cycle.",
            "category": "method",
            "keywords": ["injection", "simple", "partial", "inject", "method"],
            "priority": "medium"
        },
        r"save.*method|save.*preset|preset|load.*preset|reuse.*method": {
            "answer": "**Save:** Type `!save my_method_name` and click Add to Method.\n"
            "**Load:** Type `@my_method_name` and click ⚡ Spark.\n\n"
            "Saved presets let you reuse protocols without retyping.",
            "category": "method",
            "keywords": ["save", "preset", "load", "reuse", "method"],
            "priority": "medium"
        },
        r"what.*auto.*read|auto.*read|after.*queue|after.*last.*cycle": {
            "answer": "After your last queued cycle finishes, the system starts a **2-hour Auto-Read** "
            "for continuous monitoring. This keeps recording so you don't lose data if you step away.\n\n"
            "You can disable Auto-Read in Settings.",
            "category": "method",
            "keywords": ["auto", "read", "after", "queue", "last", "cycle"],
            "priority": "medium"
        },
        r"next.*cycle|skip.*cycle|advance.*cycle": {
            "answer": "Press **⏭ Next Cycle** to end the current cycle early and start the next one. "
            "Data from the shortened cycle is still saved.\n\n"
            "If no cycles remain, Auto-Read begins automatically.",
            "category": "method",
            "keywords": ["next", "cycle", "skip", "advance"],
            "priority": "medium"
        },
        r"edit.*cycle|modify.*cycle": {
            "answer": "After your run, go to the **Edits** tab, load your saved Excel file, "
            "click on a cycle in the table, and use the **Cycle Details** panel to adjust boundaries and settings.",
            "category": "method",
            "keywords": ["edit", "cycle", "modify"],
            "priority": "medium"
        },
        r"method.*example|example.*method|show.*example|sample.*method": {
            "answer": "**Simple Binding:**\n"
            "`Baseline 5min` → `Binding 8.5min A:100nM contact 300s` → `Regeneration 30sec ALL:50mM`\n\n"
            "**Dose-Response:**\n"
            "`Baseline 5min` → Binding cycles at 10nM, 50nM, 100nM, 500nM (8.5min each) → `Regeneration 30sec`\n\n"
            "💡 Type `build 5` for an auto-generated binding series.",
            "category": "method",
            "keywords": ["example", "method", "sample", "show"],
            "priority": "medium"
        },
        r"cycle.*abbreviation|short.*cycle|abbreviate|cycle.*short.*form|BL|BN|IM|BK|KN|CN|RG|AS|DS|WS|OT": {
            "answer": "**Cycle Type Abbreviations** (use anywhere):\n\n"
            "• **BL** — Baseline\n"
            "• **BN** — Binding\n"
            "• **IM** — Immobilization\n"
            "• **BK** — Blocking\n"
            "• **RG** — Regeneration\n"
            "• **WS** — Wash\n"
            "• **OT** — Other\n\n"
            "Example: `BN 8.5min A:100nM contact 300s` (short for Binding)",
            "category": "method",
            "keywords": ["abbreviation", "short", "form", "BL", "BN", "IM", "BK", "KN", "CN", "RG"],
            "priority": "high"
        },
        r"duration.*shortcut|time.*shortcut|minute|second|hour|overnight|5m|5s|5h|24h": {
            "answer": "**Duration Shortcuts** (all equivalent):\n\n"
            "Seconds: `5s` or `5sec`\n"
            "Minutes: `5m` or `5min`\n"
            "Hours: `2h` or `2hr`\n"
            "Special: `overnight` (= 8h, auto-enables Overnight Mode)\n\n"
            "Examples: `Baseline 30sec`, `Binding 5min`, `Baseline 2h`, `Baseline overnight`",
            "category": "method",
            "keywords": ["duration", "shortcut", "time", "minute", "second", "hour", "overnight"],
            "priority": "high"
        },
        r"flow.*rate|fr|injection.*volume|iv|shorthand.*parameter": {
            "answer": "**Parameter Shorthand** for power users:\n\n"
            "• `flow 50` or `fr 50` — Set flow rate to 50 µL/min\n"
            "• `iv 25` — Set injection volume to 25 µL\n\n"
            "Examples:\n"
            "`Binding 8.5min A:100nM contact 300s` (standard)\n"
            "`Binding 8.5min A:100nM iv 25 contact 300s` (injection volume)\n"
            "`Binding 8.5min A:100nM contact 300s partial` (partial injection)",
            "category": "method",
            "keywords": ["flow", "rate", "injection", "volume", "shorthand", "parameter", "fr", "iv"],
            "priority": "high"
        },
        r"contact.*time.*hour|contact.*hour|contact.*h|contact.*hr|5h|3h": {
            "answer": "**Contact Time with Hours** (auto-converts to seconds):\n\n"
            "`contact 5h` → 18,000 seconds\n"
            "`contact 3h 30min` → 2+ hours shown as contact time\n"
            "⚠️ **Auto-enables Overnight Mode if > 3 hours**\n\n"
            "Examples:\n"
            "`Binding 8.5min A:100nM contact 5h` (extended binding)\n"
            "`Baseline overnight` (long stability run)",
            "category": "method",
            "keywords": ["contact", "time", "hour", "h", "hr", "3h", "5h"],
            "priority": "high"
        },
        r"partial.*injection|simple.*injection|injection.*type": {
            "answer": "**Injection Types** (modifiers):\n\n"
            "• `partial` — 30 µL spike (quick test, less reagent)\n"
            "• No modifier (default) — Full sample loop injection\n\n"
            "Usage: `Binding 8.5min A:100nM contact 300s partial`\n"
            "Also works with: `manual` or `automated` to override injection mode",
            "category": "method",
            "keywords": ["partial", "injection", "simple", "type"],
            "priority": "medium"
        },
        r"detection.*mode|detection.*priority|baseline|priority|elevated|off": {
            "answer": "**Detection Modes** (sensitivity level):\n\n"
            "• `detection baseline` — Low sensitivity (factor 2.0)\n"
            "• `detection priority` — Medium (factor 1.0)\n"
            "• `detection elevated` — High (factor 0.5)\n"
            "• `detection off` — Disabled\n\n"
            "Example: `Binding 5min A:100nM detection priority`\n"
            "Sets injection detection sensitivity for this cycle only.",
            "category": "method",
            "keywords": ["detection", "mode", "priority", "baseline", "elevated", "off", "sensitivity"],
            "priority": "medium"
        },
        r"channel.*selection|channels.*A|channels.*B|channels.*BD|override.*channel|per.*channel": {
            "answer": "**Channel Selection** (override defaults):\n\n"
            "`channels A` — Restrict to channel A only\n"
            "`channels BD` — Run on channels B & D\n"
            "`channels ALL` — All channels (default)\n\n"
            "Per-channel concentration (combo tag):\n"
            "`A:100nM B:50nM` — Different concentrations per channel\n\n"
            "Examples:\n"
            "`Binding 5min A:100nM B:50nM`\n"
            "`Binding 5min channels AC` (restrict to A & C)",
            "category": "method",
            "keywords": ["channel", "selection", "channels", "A", "B", "C", "D", "BD", "ALL", "override"],
            "priority": "medium"
        },
        r"in.*place.*edit|#N|#3|#all|#2-5|modify.*cycle.*line": {
            "answer": "**In-Place Modifiers** — Edit cycles without removing them:\n\n"
            "`#3 contact 120s` — Change cycle 3 contact time\n"
            "`#3 channels BD` — Restrict cycle 3 to B & D\n"
            "`#2-5 detection priority` — Apply to cycles 2-5\n"
            "`#all detection off` — Disable detection on ALL cycles\n"
            "`#3 contact 120s channels BD detection priority` — Multiple mods in one line\n\n"
            "Then click **➕ Add to Method** to apply.",
            "category": "method",
            "keywords": ["in", "place", "edit", "modify", "cycle", "line", "#N", "#3"],
            "priority": "high"
        },
        r"concentration.*unit|nM|µM|mM|pM|mg/mL|µg/mL|ng/mL|unit|tag": {
            "answer": "**Concentration/Unit Tags** (optional documentation):\n\n"
            "Supported units: nM, µM, pM, mM, M, mg/mL, µg/mL, ng/mL\n"
            "Format: `Channel:ValueUnit` or `[Channel:ValueUnit]`\n\n"
            "Examples:\n"
            "`A:100nM` — Channel A at 100 nanoM\n"
            "`B:50µM` — Channel B at 50 microM\n"
            "`ALL:25pM` — All channels at 25 picoM\n"
            "`A:100nM B:50nM` — Multiple per-channel tags\n\n"
            "Tags are for reference; they don't affect injection volume.",
            "category": "method",
            "keywords": ["concentration", "unit", "nM", "µM", "mM", "tag", "mg/mL"],
            "priority": "medium"
        },
        r"preset|save.*preset|load.*preset|!save|@save|reuse": {
            "answer": "**Presets & Templates** for quick reuse:\n\n"
            "**Save a preset:**\n"
            "Type `!save my_protocol_name` and click **➕ Add to Method**\n\n"
            "**Load a preset:**\n"
            "Type `@my_protocol_name` and click **⚡ Spark**\n\n"
            "**Built-in templates:**\n"
            "`@spark titration` — Dose-response series\n"
            "`@spark kinetics` — Association + long dissociation\n"
            "`@spark amine coupling` — Full coupling workflow\n"
            "`@spark binding` — Multi-concentration binding",
            "category": "method",
            "keywords": ["preset", "save", "load", "template", "reuse", "!save", "@"],
            "priority": "high"
        },
        r"build.*quick|build.*5|build.*10|auto.*generate|automate": {
            "answer": "**Build Quick Series** (auto-generates):\n\n"
            "`build 5` → 5 × (Binding 8.5min + Regeneration + Baseline)\n"
            "`build 10` → 10 × (Binding 8.5min + Regeneration + Baseline)\n\n"
            "Perfect for dose-response or replicate binding runs.\n"
            "Click **➕ Add to Method**, adjust concentrations as needed.",
            "category": "method",
            "keywords": ["build", "quick", "series", "5", "10", "auto", "generate"],
            "priority": "medium"
        },
        r"full.*example|dose.*response|titration|amine.*coupling|overnight": {
            "answer": "**Full Method Examples:**\n\n"
            "**Dose-Response Titration:**\n"
            "`Baseline 5min`\n"
            "`Binding 8.5min A:10nM contact 300s`\n"
            "`Regen 30sec ALL:50mM`\n"
            "`Baseline 2min`\n"
            "`Binding 8.5min A:50nM contact 300s`\n"
            "`< repeat at 100nM, 500nM >`\n\n"
            "**Overnight Stability:**\n"
            "`Baseline overnight` (8 hours, auto-enables Overnight Mode)\n"
            "`Baseline 12h` (12 hours)\n\n"
            "**Amine Coupling:**\n"
            "`Baseline 5min`\n"
            "`Other 4min` (EDC/NHS activation)\n"
            "`Immobilization 30min` (30 min freestyle — pipette ligand manually)\n"
            "`Blocking 4min` (ethanolamine)\n"
            "`< Wash + Binding + Regen series >`",
            "category": "method",
            "keywords": ["example", "dose", "response", "titration", "amine", "coupling", "overnight"],
            "priority": "high"
        },
        r"quick.*reference|all.*syntax|cheat.*sheet|shortcut|quick": {
            "answer": "**Quick Syntax Cheat Sheet:**\n\n"
            "**Type Duration Channel Contact Modifiers**\n\n"
            "Examples:\n"
            "`BN 8.5min A:100nM contact 300s` (short for Binding)\n"
            "`IM 30min` (Immobilization — 30 min freestyle, no injection)\n"
            "`RG 30sec ALL:50mM` (Regeneration)\n"
            "`BL 5min` (Baseline)\n\n"
            "**Modifiers:** `partial`, `manual`, `automated`, `detection priority/off`\n"
            "**In-place edit:** `#3 contact 120s` or `#2-5 detection off`\n"
            "**Presets:** `!save myprotocol` or `@myprotocol`\n"
            "Click **?** button in Method Builder for full docs!",
            "category": "method",
            "keywords": ["quick", "reference", "syntax", "cheat", "sheet"],
            "priority": "high"
        },
    },

    "p4spr": {
        r"how.*use.*4.*channel|4.*channel|all.*four.*channel|independent.*channel": {
            "answer": "P4SPR has **4 fully independent optical + fluidic channels (A, B, C, D)**.\n\n"
            "You can inject 4 **different analytes simultaneously** — one per channel!\n\n"
            "In Method Builder, specify channels per cycle:\n"
            "`Binding 8.5min [A:100nM] [B:50nM] [C:25nM] [D:10nM] contact 300s`\n\n"
            "Or use all channels: `Binding 8.5min ALL:100nM contact 300s`",
            "category": "p4spr",
            "keywords": ["4", "channel", "independent", "analyte", "parallel"],
            "priority": "high"
        },
        r"p4spr.*inject|manual.*inject|how.*inject.*p4spr|pipette|syringe": {
            "answer": "P4SPR uses **manual syringe injection**.\n\n"
            "1. Prepare 4 sample aliquots (one per channel)\n"
            "2. When method starts, you have **60 seconds** to pipette each channel\n"
            "3. Inject smoothly into inlet ports — **avoid air bubbles**\n"
            "4. Injections can be **up to 15 seconds apart** — software handles the timing\n\n"
            "Watch the sensorgram in real-time for the blue shift (analyte binding).",
            "category": "p4spr",
            "keywords": ["p4spr", "inject", "manual", "syringe", "pipette", "sample"],
            "priority": "high"
        },
        r"what.*concentration|starting.*concentration|how.*much.*analyte|dose.*p4spr": {
            "answer": "**Typical starting concentrations for P4SPR:**\n\n"
            "• **Proteins:** Start at **100 nM** → 3-fold dilutions → 5–7 concentrations\n"
            "• **Small molecules:** Start at **500 nM** → 3-fold dilutions → 5–7 concentrations\n"
            "• **Antibodies:** Start at **50 nM** → 2–3 fold dilutions → 5–7 concentrations\n\n"
            "**Why?** Affilabs sensors bind ~50–200 nM of ligand. Too dilute = weak signal; too concentrated = saturates instantly.\n\n"
            "Try 100 nM first, then adjust based on signal strength.",
            "category": "p4spr",
            "keywords": ["concentration", "dose", "dilution", "p4spr", "analyte"],
            "priority": "high"
        },
        r"p4spr.*immobiliz|which.*channel.*ligand|how.*immobiliz": {
            "answer": "In P4SPR, you typically immobilize ligand on **channel A only** (or any one channel).\n\n"
            "**Immobilization** is a 30-minute freestyle window — the system runs the timer while you manually "
            "pipette your ligand solution into the flow cell inlet. No injection prompt is shown.\n\n"
            "Example workflow:\n"
            "`Baseline 5min ALL`\n"
            "`Immobilization 30min` (pipette ligand manually into the cell)\n"
            "`Wash 30sec ALL`\n"
            "`Baseline 5min ALL`\n\n"
            "Channels B, C, D remain in buffer as references.",
            "category": "p4spr",
            "keywords": ["p4spr", "immobilize", "ligand", "channel"],
            "priority": "medium"
        },
        r"p4spr.*workflow|complete.*p4spr|end.*to.*end.*p4spr": {
            "answer": "**P4SPR End-to-End Workflow:**\n\n"
            "1. **Prep** (20 min): Prepare buffers, samples, calibrate system\n"
            "2. **Surface** (15–30 min): Immobilize ligand on channel A, baseline other channels\n"
            "3. **Binding** (30–60 min): Add 5–7 concentration cycles with regeneration\n"
            "4. **Analysis:** Fit kinetics, extract Kd, ka, kd\n\n"
            "Total experiment: ~2–3 hours for a complete dose-response.\n\n"
            "Type '!save my_p4spr_protocol' to save your method as a preset.",
            "category": "p4spr",
            "keywords": ["p4spr", "workflow", "protocol", "experiment"],
            "priority": "medium"
        },
        r"p4spr.*regen|regenerat.*p4spr|strip.*analyte": {
            "answer": "**Regeneration removes bound analyte** so you can run the next concentration.\n\n"
            "Standard P4SPR regeneration: `Regeneration 30sec [ALL:50mM]`\n\n"
            "Use a **harsh buffer** (e.g., 50 mM glycine pH 2.5) to strip binding.\n\n"
            "**Important:** After regen, allow 1–2 min baseline stabilization before the next binding cycle.",
            "category": "p4spr",
            "keywords": ["regen", "regeneration", "p4spr", "strip", "surface"],
            "priority": "medium"
        },
        r"p4spr.*missing.*regen|forgot.*regen|need.*regen|without.*regen": {
            "answer": "**Regen is critical between binding cycles!**\n\n"
            "Without regeneration:\n"
            "• The old analyte stays on the sensor\n"
            "• New analyte binds to already-occupied sites → signal is suppressed\n"
            "• Kinetics look wrong (non-linear, weird shapes)\n\n"
            "Always include: `Regeneration 30sec [ALL:50mM]` after each binding or kinetic cycle.",
            "category": "p4spr",
            "keywords": ["p4spr", "regen", "missing", "regeneration"],
            "priority": "high"
        },
        r"p4spr.*baseline|baseline.*p4spr|how.*long.*baseline": {
            "answer": "**P4SPR baseline cycles establish and verify signal stability.**\n\n"
            "Typical baseline duration: **5–10 minutes** before immobilization.\n\n"
            "Use after: regeneration (wait for surface recovery), temperature changes, or maintenance.\n\n"
            "Example: `Baseline 10min ALL` → watch for drift < 0.5 nm/min before proceeding.",
            "category": "p4spr",
            "keywords": ["baseline", "p4spr", "duration", "stability"],
            "priority": "medium"
        },
        r"p4spr.*different.*sample.*channel|two.*channel.*different|channel.*conflict": {
            "answer": "**Yes! P4SPR channels are independent.** Each can have a different analyte.\n\n"
            "Example method:\n"
            "`Baseline 5min ALL`\n"
            "`Binding 8.5min [A:100nM] [B:50nM] [C:25nM] [D:10nM] contact 300s`\n"
            "`Regeneration 30sec ALL:50mM`\n\n"
            "At injection time, you pipette:\n"
            "• Channel A gets 100 nM solution\n"
            "• Channel B gets 50 nM solution\n"
            "• Etc.\n\n"
            "No crosstalk — each channel is isolated.",
            "category": "p4spr",
            "keywords": ["p4spr", "different", "sample", "channel", "analyte"],
            "priority": "high"
        },
        r"chip.*load|insert.*chip|new.*chip|change.*chip|replace.*chip": {
            "answer": "**Loading a new sensor chip:**\n\n"
            "1. Open the compression clamp\n"
            "2. Place the gold-coated chip **gold side down** on the prism\n"
            "3. Align with the flow cell gasket — the chip sits on top of the prism\n"
            "4. Close the clamp gently — use the Compression Assistant if available\n"
            "5. Push buffer through each channel to wet the flow cells and flush air\n"
            "6. **Always recalibrate** after inserting a new chip\n\n"
            "⚠️ Never touch the gold surface — fingerprints destroy sensitivity.",
            "category": "p4spr",
            "keywords": ["chip", "load", "insert", "new", "change", "replace", "gold"],
            "priority": "high"
        },
        r"which.*buffer|what.*buffer|buffer.*recommend|running.*buffer|pbs|hbs": {
            "answer": "**Recommended running buffers for SimplexSPR:**\n\n"
            "• **PBS** (phosphate buffered saline) — most common, good for proteins\n"
            "• **HBS-EP** (HEPES buffered saline + EDTA + P20) — reduces non-specific binding\n"
            "• **TBS** (Tris buffered saline) — when phosphate interferes\n\n"
            "**Tips:**\n"
            "• Filter and degas your buffer before use\n"
            "• Use the same buffer batch for the entire experiment\n"
            "• Keep buffer at room temperature to avoid thermal drift",
            "category": "p4spr",
            "keywords": ["buffer", "PBS", "HBS", "running", "recommend"],
            "priority": "high"
        },
        r"read.*sensorgram|understand.*sensorgram|what.*sensorgram.*show|interpret.*graph": {
            "answer": "**Reading the SimplexSPR sensorgram:**\n\n"
            "• **X-axis:** Time (seconds or minutes)\n"
            "• **Y-axis:** SPR wavelength (nm) — higher = more mass on sensor\n"
            "• **Rising signal:** Analyte is binding (association)\n"
            "• **Falling signal:** Analyte is leaving (dissociation or wash)\n"
            "• **Flat line:** Stable baseline — no net change\n\n"
            "Each colored line is one channel (A, B, C, D). A shift of even 0.5 nm indicates binding.",
            "category": "p4spr",
            "keywords": ["sensorgram", "read", "understand", "interpret", "graph", "signal"],
            "priority": "high"
        },
        r"how.*inject.*properly|injection.*technique|pipett.*technique|inject.*without.*bubble": {
            "answer": "**Manual injection technique for SimplexSPR:**\n\n"
            "1. Pre-fill sample in a 1 mL syringe or pipette tip (no air gaps!)\n"
            "2. Touch the tip to the flow cell inlet and push **slowly, steadily**\n"
            "3. 50-100 µL is typical — enough to fill the flow cell\n"
            "4. Inject all 4 channels within **15 seconds** of each other\n"
            "5. Don't jerk the syringe — a pressure spike creates an artifact\n\n"
            "💡 Pre-wet the syringe tip with buffer to reduce bubble risk.",
            "category": "p4spr",
            "keywords": ["inject", "properly", "technique", "pipette", "bubble", "manual"],
            "priority": "high"
        },
        r"how.*many.*sample|sample.*volume|how.*much.*sample|volume.*per.*channel": {
            "answer": "**Sample volumes for SimplexSPR:**\n\n"
            "• **Per channel:** 50-100 µL typical injection volume\n"
            "• **Per experiment:** Prepare ~200 µL per concentration (4 channels × 50 µL + dead volume)\n"
            "• **Minimum:** ~30 µL fills the flow cell, but 50 µL ensures full contact\n\n"
            "For a 5-concentration dose-response across 4 channels, prepare ~1 mL total per concentration.",
            "category": "p4spr",
            "keywords": ["sample", "volume", "how", "much", "amount", "channel"],
            "priority": "medium"
        },
        r"what.*contact.*time|how.*long.*contact|contact.*time.*recommend": {
            "answer": "**Contact time = how long sample stays on the sensor before washing.**\n\n"
            "• **Fast binders** (antibodies): 60-120 seconds\n"
            "• **Standard proteins:** 180-300 seconds (3-5 min)\n"
            "• **Slow binders** (small molecules): 300-600 seconds (5-10 min)\n"
            "• **Immobilization:** 1800 seconds (30 min)\n\n"
            "Set in Method Builder: `Binding 8.5min A:100nM contact 180s`\n"
            "The system shows a countdown timer and alerts you when it's time to wash.",
            "category": "p4spr",
            "keywords": ["contact", "time", "how", "long", "recommend", "duration"],
            "priority": "high"
        },
        r"signal.*too.*low|no.*signal|weak.*signal|can.*t.*see.*binding": {
            "answer": "**Weak or no signal on SimplexSPR?**\n\n"
            "1. **Check concentration** — try 10× higher (e.g. 1 µM instead of 100 nM)\n"
            "2. **Check the chip** — recalibrate and verify the SPR dip is visible in Spectroscopy tab\n"
            "3. **Check immobilization** — was ligand successfully attached? Look for the shift during immobilization\n"
            "4. **Check for bubbles** — air in the flow cell blocks the optical path\n"
            "5. **Check buffer** — wrong pH or salt can prevent binding\n\n"
            "A good SPR dip should be 20-40 nm wide in the transmission spectrum.",
            "category": "p4spr",
            "keywords": ["signal", "low", "weak", "no", "binding", "can't", "see"],
            "priority": "high"
        },
        r"warmup|warm.*up|how.*long.*before.*experiment|temperature.*stable": {
            "answer": "**Allow 30-60 minutes of warmup** before starting an experiment.\n\n"
            "The LED and optical system need time to reach thermal equilibrium. "
            "During warmup, run buffer through the flow cells and watch the baseline — "
            "when drift is < 0.5 nm/min, you're ready to go.\n\n"
            "💡 Calibrate after warmup, not before.",
            "category": "p4spr",
            "keywords": ["warmup", "warm", "up", "temperature", "stable", "before"],
            "priority": "medium"
        },
    },

    "analysis": {
        r"baseline.*drift|baseline.*unstable|drift.*baseline": {
            "answer": "Allow 30-60 minutes of warmup, check for bubbles in the flow cell, "
            "and verify consistent flow rate and temperature.\n\n"
            "You can capture a new baseline in **Settings** or apply baseline correction in the **Analysis** tab.",
            "category": "analysis",
            "keywords": ["baseline", "drift", "unstable"],
            "priority": "medium"
        },
        r"signal.*noise|noisy.*signal|signal.*quality|signal.*weak|weak.*signal": {
            "answer": "Noisy or weak signal? Try:\n\n"
            "• **Run Full Calibration** — recaptures S/P references with current sensor\n"
            "• **Check sensor chip** — is it dry, scratched, or oxidized?\n"
            "• **Allow warmup** — 30-60 min before first experiment\n"
            "• **Remove air bubbles** — Cleanup → Prime in Flow tab\n"
            "• **Check prism contact** — ensure chip seats flush\n\n"
            "Signal quality shows in the **Signal Quality bar** (channel pills A/B/C/D above the sensorgram).\n"
            "Green = good, yellow = monitor, red = action needed.",
            "category": "analysis",
            "keywords": ["signal", "noise", "noisy", "quality", "weak"],
            "priority": "high"
        },
        r"how.*read.*sensorgram|read.*graph|sensorgram.*mean|what.*sensorgram": {
            "answer": "The **sensorgram** shows resonance wavelength (nm) vs time.\n\n"
            "• **Flat line** = stable baseline\n"
            "• **Downward shift** (blue shift) = analyte binding ✅ (SPR signal goes DOWN on binding)\n"
            "• **Return to baseline** = dissociation\n"
            "• **Partial recovery after regen** = some analyte still bound\n\n"
            "Each colored line = one channel (A, B, C, D). "
            "Watch for correlated drops across channels — that confirms real binding vs noise.",
            "category": "analysis",
            "keywords": ["sensorgram", "read", "graph", "mean", "interpret"],
            "priority": "high"
        },
        r"blue.*shift|signal.*goes.*down|binding.*signal|why.*down|wavelength.*decrease": {
            "answer": "**SPR signal goes DOWN when analyte binds.** This is called a blue shift.\n\n"
            "Why? When the refractive index at the sensor surface increases (from analyte binding), "
            "the plasmon resonance wavelength decreases (shifts to shorter wavelength = blue shift).\n\n"
            "This is the opposite of angular SPR (Biacore). In Affilabs, **a downward dip = binding.**",
            "category": "analysis",
            "keywords": ["blue", "shift", "signal", "down", "binding", "wavelength", "decrease"],
            "priority": "high"
        },
        r"kd|affinity|dissociation.*constant|binding.*affinity|how.*calculate.*kd": {
            "answer": "**Kd (dissociation constant)** tells you binding affinity.\n\n"
            "**Method:**\n"
            "1. Run 5–7 concentrations (dose-response)\n"
            "2. Plot equilibrium signal vs concentration → fit to: Signal = Signal_max × [A] / (Kd + [A])\n"
            "3. Kd = concentration at half-maximum binding\n\n"
            "**Quick estimate:** Kd ≈ concentration where signal is 50% of maximum.\n\n"
            "Export your data to Excel (Export tab) and use the built-in fitting in the Analysis tab.",
            "category": "analysis",
            "keywords": ["kd", "affinity", "dissociation", "constant", "binding", "calculate"],
            "priority": "high"
        },
        r"ka|kon|kd.*off|koff|kinetic.*rate|association.*rate|dissociation.*rate": {
            "answer": "**Kinetic rate constants:**\n\n"
            "• **ka (kon)** = association rate — how fast analyte binds (M⁻¹s⁻¹)\n"
            "• **kd (koff)** = dissociation rate — how fast analyte leaves (s⁻¹)\n"
            "• **Kd** = kd/ka = equilibrium affinity (M)\n\n"
            "**To measure kinetics:**\n"
            "Run a Kinetic cycle with an association phase (injection) + dissociation phase (buffer wash).\n"
            "Fit the association curve to 1:1 Langmuir model to extract ka and kd.\n\n"
            "The Analysis tab provides kinetic fitting tools.",
            "category": "analysis",
            "keywords": ["ka", "kon", "koff", "kinetic", "rate", "association", "dissociation"],
            "priority": "medium"
        },
        r"reference.*channel|blank.*channel|negative.*control|reference.*subtract": {
            "answer": "**Reference channel subtraction** removes bulk refractive index changes (temperature, buffer).\n\n"
            "**Setup:** Immobilize ligand on channel A only. Leave B (or C/D) in buffer — it's your reference.\n\n"
            "**What to subtract:** Signal(reference) from Signal(sample).\n"
            "Result = pure binding signal, corrected for non-specific effects.\n\n"
            "In the Analysis tab, select reference channel(s) for auto-subtraction.",
            "category": "analysis",
            "keywords": ["reference", "channel", "blank", "negative", "control", "subtract"],
            "priority": "high"
        },
        r"non.*specific.*binding|nsp|surface.*blocking|blocking.*step": {
            "answer": "**Non-specific binding (NSB)** is analyte sticking to the chip surface (not the ligand).\n\n"
            "**Reduce NSB:**\n"
            "1. **Blocking step:** `Other 4min [ALL:1mg/mL BSA]` or `[ALL:1% Tween-20]` after immobilization\n"
            "2. **Running buffer:** Add 0.05% Tween-20 to running buffer\n"
            "3. **Sample preparation:** Use same buffer composition for samples\n"
            "4. **Reference subtraction:** Use un-modified reference channel to subtract background\n\n"
            "NSB appears as signal on your reference channel — subtract it out.",
            "category": "analysis",
            "keywords": ["non", "specific", "binding", "nsp", "block", "blocking"],
            "priority": "medium"
        },
        r"regeneration.*condition|regen.*condition|strip.*surface|how.*regen": {
            "answer": "**Common regeneration conditions:**\n\n"
            "| Application | Regeneration solution |\n"
            "| --- | --- |\n"
            "| Antibody-antigen | 10 mM glycine pH 1.5–2.5 (30 sec) |\n"
            "| Protein-protein | 1 M NaCl (60 sec) |\n"
            "| Biotin-streptavidin | Not reversible (use fresh chip) |\n"
            "| DNA hybridization | 0.5% SDS or 8 M urea (30 sec) |\n\n"
            "**Tips:** Start mild (glycine pH 2.5), go harsher only if needed. Check that baseline returns fully.",
            "category": "analysis",
            "keywords": ["regeneration", "condition", "regen", "strip", "surface", "glycine"],
            "priority": "medium"
        },
    },

    "troubleshooting": {
        r"no.*signal|zero.*signal|flat.*line.*always|nothing.*happening": {
            "answer": "No signal at all? Check these in order:\n\n"
            "1. **Device Status** — is the detector connected (green dot)?\n"
            "2. **Power On** — did startup calibration complete successfully?\n"
            "3. **Live tab** → **Start** — is acquisition running?\n"
            "4. **Sensor chip** — is it installed and in contact with the prism?\n"
            "5. **Signal Quality bar** — are channel pills showing red (P2P >8nm = sensor issue)?\n\n"
            "If calibration passed but sensorgram is flat: check sensor chip seating and prism cleanliness.",
            "category": "troubleshooting",
            "keywords": ["no", "signal", "zero", "flat", "nothing", "happening"],
            "priority": "high"
        },
        r"sensor.*dry|dry.*sensor|light.*path.*blocked|sensor.*bad|chip.*bad": {
            "answer": "**Sensor may be dry or light path blocked.**\n\n"
            "Symptoms: P2P noise > 8 nm (red pill in Signal Quality bar), no SPR dip visible.\n\n"
            "**Fix:**\n"
            "1. Check sensor chip is wet — add a drop of buffer if dry\n"
            "2. Verify chip is seated flush on the prism (no tilt, no gap)\n"
            "3. Inspect prism — clean with lens tissue if dirty\n"
            "4. Run **Full Calibration** to recapture references\n\n"
            "If problem persists: try a fresh sensor chip.",
            "category": "troubleshooting",
            "keywords": ["sensor", "dry", "light", "blocked", "chip", "bad"],
            "priority": "high"
        },
        r"bubble.*flow.*cell|bubble.*sensor|air.*in.*flow|air.*bubble": {
            "answer": "Air bubbles cause spikes and noise in the sensorgram.\n\n"
            "**Remove bubbles:**\n"
            "1. Flow tab → **Cleanup** (pulse + prime, ~3-4 min)\n"
            "2. If still noisy: **Prime** again, wait 2-3 min\n"
            "3. Check inlet tubing — no kinks, fully submerged in buffer\n"
            "4. **Degas your buffer** — heat to 37°C and cool, or use vacuum degasser\n\n"
            "Bubbles show as sharp transient spikes, not slow drift.",
            "category": "troubleshooting",
            "keywords": ["bubble", "flow", "cell", "sensor", "air", "spike"],
            "priority": "high"
        },
        r"spike.*sensorgram|sharp.*spike|transient.*spike|spike.*signal": {
            "answer": "**Spikes** are usually:\n\n"
            "• **Air bubbles** → Cleanup/Prime (Flow tab)\n"
            "• **Loose connection** → Check USB and fluidic connections\n"
            "• **Valve switching** → Normal at injection start (brief, < 2 sec)\n"
            "• **Mechanical vibration** → Move instrument away from vibration sources\n\n"
            "If spikes are random and frequent: run **Cleanup** first, then check connections.",
            "category": "troubleshooting",
            "keywords": ["spike", "sharp", "transient", "signal", "glitch"],
            "priority": "medium"
        },
        r"software.*crash|app.*crash|crash|froze|not.*respond": {
            "answer": "App crashed or frozen?\n\n"
            "1. Force close (Task Manager if needed)\n"
            "2. Restart Affilabs\n"
            "3. Hardware auto-reconnects — click **Power On** again\n"
            "4. Your last recorded data is safe (auto-saved)\n\n"
            "If it crashes repeatedly: check logs in `_data/logs/` and send to info@affiniteinstruments.com.",
            "category": "troubleshooting",
            "keywords": ["crash", "freeze", "not", "respond", "software"],
            "priority": "high"
        },
        r"error.*message|what.*error|error.*code|error.*mean": {
            "answer": "**Common error messages:**\n\n"
            "• **'LED model not found'** → Settings → Train LED Model\n"
            "• **'Calibration failed'** → Click Retry; check for bubbles\n"
            "• **'Detector not found'** → Reconnect USB, try different port\n"
            "• **'Pump blocked'** → Check tubing, then Home Pumps\n"
            "• **'Hardware disconnected'** → USB issue; reconnect and Power On\n\n"
            "If the error is not listed, contact support at info@affiniteinstruments.com.",
            "category": "troubleshooting",
            "keywords": ["error", "message", "code", "mean"],
            "priority": "high"
        },
        r"temperature.*control|temp.*stability|temperature.*drift|set.*temperature": {
            "answer": "**Temperature control** helps reduce baseline drift from refractive index changes.\n\n"
            "• SPR signal is sensitive to temperature (refractive index changes with temp)\n"
            "• Allow 30-60 min warmup before experiments\n"
            "• Ideal: 25°C ± 0.1°C for most protein experiments\n"
            "• Keep instrument away from drafts, vents, and sunlight\n\n"
            "Temperature settings (if available) are in **Settings → Advanced**.",
            "category": "troubleshooting",
            "keywords": ["temperature", "control", "stability", "drift", "set"],
            "priority": "medium"
        },
        r"recording.*stop|data.*lost|data.*not.*saved|where.*data": {
            "answer": "Data is **auto-saved** during acquisition. If recording stopped unexpectedly:\n\n"
            "1. Check `_data/` folder — raw data files are saved there automatically\n"
            "2. Open the **Export** tab → **Load from file** to recover a session\n"
            "3. If you see data in the sensorgram, it can still be exported\n\n"
            "For future sessions: always click **Record** before starting cycles to ensure named saving.",
            "category": "troubleshooting",
            "keywords": ["recording", "stop", "data", "lost", "saved", "where"],
            "priority": "high"
        },
    },

    "sensor_chip": {
        r"sensor.*chip|gold.*chip|spr.*chip|chip.*type|which.*chip": {
            "answer": "**Sensor chips** are gold-coated glass slides for SPR measurements.\n\n"
            "**Common types:**\n"
            "• **Bare gold** — For custom surface chemistry\n"
            "• **Carboxymethyl (CM)** — Amine coupling ready; most common\n"
            "• **Streptavidin** — For biotin-tagged ligands\n"
            "• **Neutravidin** — Similar to streptavidin, lower NSB\n"
            "• **NiNTA** — For His-tagged ligands\n\n"
            "Contact Affinité Instruments for chip recommendations: info@affiniteinstruments.com",
            "category": "sensor_chip",
            "keywords": ["sensor", "chip", "gold", "type", "surface"],
            "priority": "medium"
        },
        r"how.*install.*chip|install.*sensor|replace.*chip|chip.*installation": {
            "answer": "**Installing a sensor chip:**\n\n"
            "1. Power down flow (stop pump if running)\n"
            "2. Remove old chip (slide out from prism contact surface)\n"
            "3. Clean prism with lens tissue (isopropanol, wipe dry)\n"
            "4. Place new chip — index-matched contact with prism\n"
            "5. Run **Simple Calibration** (same chip type) or **Full Calibration** (new type)\n\n"
            "⚠️ Never touch the gold side — oils from fingers kill the SPR response.",
            "category": "sensor_chip",
            "keywords": ["install", "chip", "sensor", "replace", "installation"],
            "priority": "high"
        },
        r"chip.*lifetime|how.*long.*chip|reuse.*chip|chip.*reusable": {
            "answer": "**Sensor chip lifetime:**\n\n"
            "• Typically **5–20 cycles** depending on regeneration harshness\n"
            "• Carboxymethyl (CM) chips: up to 50 regeneration cycles with gentle conditions\n"
            "• Replace when: baseline drifts excessively, signal decreases >30%, or surface is scratched\n\n"
            "**Signs it's time to replace:** very low FWHM (<40nm), signal quality bar shows red, "
            "baseline won't stabilize even after warmup.",
            "category": "sensor_chip",
            "keywords": ["chip", "lifetime", "long", "reuse", "reusable"],
            "priority": "medium"
        },
        r"amine.*coupling|NHS.*EDC|EDC.*NHS|immobiliz.*amine|surface.*activation": {
            "answer": "**Amine coupling on CM chip:**\n\n"
            "1. `Other 4min` → inject EDC/NHS (activates -COOH → -NHS ester)\n"
            "2. `Immobilization 30min` → pipette ligand manually (low-pH buffer, pH 4.5–5.5); 30 min freestyle window\n"
            "3. `Blocking 4min` → ethanolamine (blocks unreacted sites)\n"
            "4. `Wash 30sec` → rinse\n"
            "5. `Baseline 10min` → verify stable post-immobilization baseline\n\n"
            "**EDC/NHS prep:** Mix equal volumes, use immediately. Ligand buffer: 10 mM sodium acetate pH 4.5–5.0.\n"
            "**Target:** 100–500 RU immobilized (SPR units equivalent ~1-5nm shift).",
            "category": "sensor_chip",
            "keywords": ["amine", "coupling", "NHS", "EDC", "immobilize", "activation"],
            "priority": "high"
        },
        r"biotinylated|streptavidin.*chip|biotin.*chip|his.*tag|ninta.*chip": {
            "answer": "**Affinity capture approaches:**\n\n"
            "**Biotin-Streptavidin:**\n"
            "`Immobilization 5min [A:100nM_biotinylated_ligand]` on Streptavidin chip\n"
            "(No EDC/NHS needed — biotin binds directly to streptavidin)\n\n"
            "**His-tag NiNTA:**\n"
            "`Immobilization 5min [A:100nM_His-protein]` on NiNTA chip\n"
            "(Reversible — regenerate with imidazole or EDTA)\n\n"
            "Both are non-covalent captures — gentler than amine coupling but ligand may leach.",
            "category": "sensor_chip",
            "keywords": ["biotin", "streptavidin", "his", "tag", "NiNTA", "capture"],
            "priority": "medium"
        },
    },

    "buffer": {
        r"what.*buffer|running.*buffer|buffer.*spr|pbs.*hbs|hepes.*buffer": {
            "answer": "**Standard SPR running buffers:**\n\n"
            "• **PBS-T:** 137 mM NaCl, 2.7 mM KCl, 10 mM phosphate, 0.05% Tween-20 (pH 7.4) — most common\n"
            "• **HBS-EP+:** 10 mM HEPES pH 7.4, 150 mM NaCl, 3 mM EDTA, 0.05% P20 — Biacore-style\n"
            "• **HBS-N:** HBS without EDTA (for metal-ion sensitive experiments)\n\n"
            "**Key rule:** Sample buffer = running buffer (match exactly to avoid bulk shifts).",
            "category": "buffer",
            "keywords": ["buffer", "running", "PBS", "HBS", "HEPES", "saline"],
            "priority": "high"
        },
        r"buffer.*prep|prepare.*buffer|degas.*buffer|filter.*buffer": {
            "answer": "**Buffer preparation for SPR:**\n\n"
            "1. **Filter:** 0.22 µm filter (removes particles that clog tubing)\n"
            "2. **Degas:** Warm to 37°C, cool to room temp — removes dissolved gas\n"
            "3. **Match:** Sample buffer = running buffer composition (critical!)\n"
            "4. **Fresh:** Use within 24h (bacterial growth, pH shift)\n\n"
            "**Degas shortcut:** Heat water to 37°C before dissolving salts. Avoids degassing step.",
            "category": "buffer",
            "keywords": ["buffer", "prepare", "degas", "filter"],
            "priority": "medium"
        },
        r"tween|surfactant|detergent.*buffer|0\.05%|polysorbate": {
            "answer": "**Tween-20 (0.05%) in running buffer:**\n\n"
            "• Reduces **non-specific binding** to tubing and flow cell\n"
            "• Prevents analyte sticking to surfaces before reaching sensor\n"
            "• Standard: 0.05% P20 (Polysorbate-20 = Tween-20)\n"
            "• Too much (> 0.1%): disrupts hydrophobic interactions, may interfere with binding\n\n"
            "Always use same surfactant concentration in running buffer AND sample.",
            "category": "buffer",
            "keywords": ["tween", "surfactant", "detergent", "0.05", "polysorbate"],
            "priority": "medium"
        },
        r"sample.*preparation|dilute.*sample|dissolve.*sample|protein.*buffer": {
            "answer": "**Sample preparation for P4SPR:**\n\n"
            "1. **Dissolve** in running buffer (not water — pH and ionic strength must match)\n"
            "2. **Dilute** to working concentration (start at 100 nM for proteins)\n"
            "3. **Centrifuge** 5 min at 10,000 rpm (removes aggregates)\n"
            "4. **Check volume:** need 100-200 µL per channel\n"
            "5. **Temperature:** equilibrate to room temp before injecting\n\n"
            "**Golden rule:** Sample buffer = running buffer. Any mismatch = bulk refractive index shift.",
            "category": "buffer",
            "keywords": ["sample", "preparation", "dilute", "dissolve", "protein"],
            "priority": "high"
        },
    },

    "data_management": {
        r"export.*excel|excel.*export|save.*excel|how.*export": {
            "answer": "**Export to Excel:**\n\n"
            "1. Go to **Export** tab\n"
            "2. Select data to export (all cycles or specific ones)\n"
            "3. Click **Export to Excel** → choose save location\n\n"
            "The Excel file includes:\n"
            "• Sensorgram data (time + wavelength per channel)\n"
            "• Cycle annotations (type, timestamps, notes)\n"
            "• Signal quality metrics\n"
            "• Built-in charts\n\n"
            "For CSV: **Export to CSV** exports raw wavelength-vs-time data.",
            "category": "data_management",
            "keywords": ["export", "excel", "save", "download"],
            "priority": "high"
        },
        r"csv.*export|export.*csv|raw.*data.*export": {
            "answer": "**CSV export** gives raw sensorgram data (time, wavelength per channel).\n\n"
            "Export tab → **Export to CSV** → choose location.\n\n"
            "Format: timestamp, channel A wavelength, B, C, D — one row per acquisition point.\n\n"
            "Use this for custom analysis in Python, R, MATLAB, or GraphPad.",
            "category": "data_management",
            "keywords": ["csv", "export", "raw", "data"],
            "priority": "medium"
        },
        r"load.*data|open.*data|load.*previous|previous.*session|open.*file": {
            "answer": "**Load previous session data:**\n\n"
            "1. Export tab → **Load from File**\n"
            "2. Select your saved Excel or data file\n"
            "3. Data appears in the Edits tab for review and cycle analysis\n\n"
            "All sessions auto-save to the `_data/` folder with timestamps.",
            "category": "data_management",
            "keywords": ["load", "data", "open", "previous", "session", "file"],
            "priority": "medium"
        },
        r"recording.*start|start.*recording|record.*data|how.*record": {
            "answer": "**Start Recording:**\n\n"
            "1. Build your method in **Method Builder** (sidebar)\n"
            "2. Click **📋 Push to Queue**\n"
            "3. Click **▶ Start Run** — acquisition + recording begins\n\n"
            "Recording saves all data to a file automatically.\n\n"
            "**Auto-Read mode** (without a method) shows live data but doesn't save named cycles. "
            "Use Record for experiments you want to keep.",
            "category": "data_management",
            "keywords": ["record", "start", "recording", "data", "save"],
            "priority": "high"
        },
        r"animl.*format|animl.*export|xml.*export|data.*format": {
            "answer": "**AnIML export** (Analytical Information Markup Language):\n\n"
            "AnIML is a standardized XML format for analytical instrument data, enabling:\n"
            "• Lab data management system (LIMS) integration\n"
            "• Long-term archival\n"
            "• Cross-instrument comparison\n\n"
            "Export tab → **Export to AnIML** → choose location.\n\n"
            "For most users, Excel export is simpler and includes charts.",
            "category": "data_management",
            "keywords": ["animl", "format", "export", "xml"],
            "priority": "low"
        },
    },

    "edits_tab": {
        r"edits.*tab|analysis.*tab|review.*data|cycle.*review": {
            "answer": "**The Edits tab** lets you review and annotate recorded data:\n\n"
            "• Click any cycle in the table to display it on the graph\n"
            "• Drag cycle boundaries to re-align injection markers\n"
            "• Add or edit notes per cycle\n"
            "• View all 4 channels simultaneously\n"
            "• Calculate delta SPR (binding response) between cursors\n\n"
            "Load data with **Load from File** if reviewing a past session.",
            "category": "edits_tab",
            "keywords": ["edits", "tab", "analysis", "review", "cycle"],
            "priority": "medium"
        },
        r"delta.*spr|delta.*signal|binding.*response|how.*measure.*binding": {
            "answer": "**Delta SPR** = binding response (nm shift from baseline to plateau).\n\n"
            "**In Edits tab:**\n"
            "1. Click a cycle to display it\n"
            "2. Place the **left cursor** on the pre-injection baseline\n"
            "3. Place the **right cursor** on the binding plateau\n"
            "4. Delta SPR = right - left (shown in the panel)\n\n"
            "Negative delta = blue shift (binding). More negative = stronger binding.",
            "category": "edits_tab",
            "keywords": ["delta", "spr", "signal", "binding", "response", "measure"],
            "priority": "high"
        },
        r"save.*method.*edits|save.*as.*method|export.*method": {
            "answer": "**Save as Method** lets you turn a recorded experiment into a reusable method template.\n\n"
            "Edits tab → **Save as Method** → name it → the cycle sequence is saved as a preset.\n\n"
            "Load it later with `@method_name` in the Method Builder.",
            "category": "edits_tab",
            "keywords": ["save", "method", "edits", "export"],
            "priority": "low"
        },
    },

    "general": {
        r"keyboard.*shortcuts|hotkeys|ctrl.*shortcut": {
            "answer": "Useful shortcuts:\n\n"
            "• **Ctrl+S** — Stop acquisition\n"
            "• **Ctrl+E** — Export data\n"
            "• **Ctrl+Z** / **Ctrl+Shift+Z** — Undo / Redo (Edits tab)\n"
            "• **F5** — Refresh detector scan\n"
            "• **Ctrl+Click** on sensorgram — Place injection flag (manual injection)\n"
            "• **Space** — Pause/resume acquisition (if supported)\n\n"
            "Full list: **Help → Keyboard Shortcuts**.",
            "category": "general",
            "keywords": ["keyboard", "shortcuts", "hotkeys", "ctrl"],
            "priority": "low"
        },
        r"what.*spark|who.*spark|spark.*ai|what.*can.*you.*do|what.*can.*spark|what.*sparq|who.*sparq|sparq.*ai": {
            "answer": "I'm **Sparq**, your Affilabs AI assistant! 🤖\n\n"
            "I'm specially trained on:\n"
            "• **Method building** — cycle syntax, abbreviations, templates, examples\n"
            "• **Calibration** — which type to use, troubleshooting\n"
            "• **Pump & flow** — priming, cleanup, valve control\n"
            "• **SPR science** — sensorgram reading, binding kinetics, surface prep\n"
            "• **Troubleshooting** — common errors and fixes\n"
            "• **Data export** — Excel, CSV, AnIML\n\n"
            "Just ask a question in plain language — I'll do my best!",
            "category": "general",
            "keywords": ["sparq", "spark", "ai", "what", "can", "do", "assistant"],
            "priority": "high"
        },
        r"why.*q|sparq.*name|name.*sparq|why.*spelled|why.*spelt|pourquoi.*q|d'où.*nom|vient.*nom": {
            "answer": "On vient du Québec, man! 🔵⚪\n\n"
            "The **Q** is a nod to Québec — where Affinité Instruments was founded. "
            "SPR + Q = Sparq. It also sounds like *spark* — the flash of insight when "
            "your binding data clicks into place.",
            "category": "general",
            "keywords": ["sparq", "name", "why", "q", "quebec", "québec", "spelled"],
            "priority": "high"
        },
        r"contact.*support|email.*support|help.*support|technical.*support": {
            "answer": "**Contact Affinité Instruments support:**\n\n"
            "📧 Email: info@affiniteinstruments.com\n"
            "🌐 Website: https://www.affiniteinstruments.com/\n\n"
            "Include:\n"
            "• Your instrument serial number\n"
            "• Description of the problem\n"
            "• Screenshots or log files if available\n\n"
            "Support typically responds within 1 business day.",
            "category": "general",
            "keywords": ["contact", "support", "email", "help", "technical"],
            "priority": "high"
        },
        r"version.*software|software.*version|what.*version|affilabs.*version": {
            "answer": "Check the software version in **Settings → About Affilabs.core** at the bottom of the Settings tab, or in the title bar.\n\n"
            "Current version: **v2.0.5**\n\n"
            "For updates, contact support at info@affiniteinstruments.com.",
            "category": "general",
            "keywords": ["version", "software", "affilabs"],
            "priority": "low"
        },
        r"settings.*tab|where.*settings|advanced.*settings|configure": {
            "answer": "**Settings tab** contains:\n\n"
            "• **Power On / Off** (starts startup calibration)\n"
            "• **Calibration Controls** — Simple, Full, Polarizer, OEM, LED Model Training\n"
            "• **Device Status** — detector + hardware connection info\n"
            "• **Signal processing** settings (baseline mode, pipeline, smoothing)\n"
            "• **Overnight Mode** toggle\n"
            "• **Advanced** — developer/diagnostic settings\n\n"
            "Open from the left sidebar navigation bar.",
            "category": "general",
            "keywords": ["settings", "tab", "where", "advanced", "configure"],
            "priority": "medium"
        },
        r"overnight.*mode|long.*run|8.*hour|12.*hour|unattended": {
            "answer": "**Overnight Mode** keeps acquisition running safely for hours:\n\n"
            "• Auto-enabled when contact time > 3h or you type `Baseline overnight`\n"
            "• Reduces display refresh rate to save resources\n"
            "• Auto-saves data periodically\n"
            "• Alarm sounds if signal drops out of expected range\n\n"
            "**Enable manually:** Settings → Overnight Mode toggle.\n"
            "**In method:** `Baseline overnight` (= 8h), `Baseline 12h`, `Baseline 24hr`",
            "category": "general",
            "keywords": ["overnight", "mode", "long", "run", "hour", "unattended"],
            "priority": "medium"
        },
        r"spr.*basics|what.*spr|surface.*plasmon|how.*spr.*work|spr.*principle": {
            "answer": "**Surface Plasmon Resonance (SPR)** measures biomolecular interactions label-free in real-time.\n\n"
            "**How it works:**\n"
            "1. Light hits a gold-coated sensor at a specific angle\n"
            "2. At the **resonance wavelength**, light couples into surface plasmons (electron oscillations)\n"
            "3. When molecules bind at the gold surface, the refractive index changes\n"
            "4. → resonance wavelength shifts (blue shift on binding)\n"
            "5. We track this wavelength shift over time = the sensorgram\n\n"
            "**What you measure:** binding kinetics (ka, kd), affinity (Kd), thermodynamics.\n"
            "**No labels needed** — measure binding directly, no fluorescent tags required.",
            "category": "general",
            "keywords": ["spr", "basics", "surface", "plasmon", "how", "work", "principle"],
            "priority": "high"
        },
        r"how.*affilabs.*different|affinite.*instruments|what.*instrument|p4spr.*vs.*biacore|compared.*biacore": {
            "answer": "**Affilabs / Affinité Instruments vs conventional SPR (e.g. Biacore):**\n\n"
            "| Feature | Affilabs P4SPR | Biacore/conventional |\n"
            "| --- | --- | --- |\n"
            "| Interrogation | Wavelength (spectral) | Angle |\n"
            "| Signal unit | nm shift | RU (resonance units) |\n"
            "| Optics | Lensless | Lens-based |\n"
            "| Channels | 4 independent | 2-4 (fluidically coupled) |\n"
            "| Size | Compact | Large |\n"
            "| Price | Lower | Higher |\n\n"
            "Both measure the same binding events — just via different optical readout.",
            "category": "general",
            "keywords": ["affilabs", "different", "biacore", "comparison", "instrument"],
            "priority": "medium"
        },
    },

    # -------------------------------------------------------------------------
    # FLAGS (FRS-sourced: FLAGGING_SYSTEM_GUIDE.md)
    # -------------------------------------------------------------------------
    "flags": {
        r"what.*flag|flag.*type|injection.*flag|wash.*flag|spike.*flag|type.*flag": {
            "answer": "Affilabs uses three flag types to annotate events on your sensorgram:\n\n"
            "- **Injection** (red triangle ▲) — marks when analyte is applied to the sensor\n"
            "- **Wash** (blue square ■) — marks a wash or regeneration step\n"
            "- **Spike** (orange star ★) — marks a transient artifact or noise event\n\n"
            "Flags appear as markers on the sensorgram timeline.",
            "category": "flags",
            "keywords": ["flag", "type", "injection", "wash", "spike", "marker"],
            "priority": "high"
        },
        r"how.*add.*flag|add.*flag|place.*flag|create.*flag|mark.*injection": {
            "answer": "To add a flag in the **Edits** tab:\n\n"
            "- **Right-click** on the sensorgram at the point you want to mark\n"
            "- Select the flag type (Injection, Wash, or Spike) from the context menu\n\n"
            "Flags added this way snap to the nearest data point. "
            "You can also use the Flag toolbar buttons above the graph.",
            "category": "flags",
            "keywords": ["add", "flag", "place", "mark", "right-click", "edits"],
            "priority": "high"
        },
        r"remove.*flag|delete.*flag|clear.*flag|ctrl.*right.?click": {
            "answer": "To remove a flag in the **Edits** tab:\n\n"
            "- **Ctrl + right-click** near the flag to remove it\n\n"
            "Flags are removed by proximity — click close to the flag marker and it will be deleted.",
            "category": "flags",
            "keywords": ["remove", "delete", "clear", "flag", "ctrl", "right-click"],
            "priority": "medium"
        },
        r"move.*flag|flag.*position|arrow.*key.*flag|adjust.*flag|nudge.*flag": {
            "answer": "To move a flag in the **Edits** tab:\n\n"
            "1. Click the flag marker to select it\n"
            "2. Use the **← →** arrow keys to shift it left or right\n\n"
            "The flag snaps to adjacent data points with each keypress — it won't land between data points.",
            "category": "flags",
            "keywords": ["move", "flag", "arrow", "key", "position", "adjust", "nudge"],
            "priority": "medium"
        },
        r"injection.*alignment|align.*channel|flag.*align|multi.*channel.*flag": {
            "answer": "In multi-channel experiments, injection flags can be automatically aligned:\n\n"
            "- The **first channel's injection** is used as the reference position\n"
            "- Subsequent channels snap their injection flags to the same relative position\n\n"
            "This corrects for the ~15 second inter-channel delay when injecting P4SPR channels sequentially by hand.",
            "category": "flags",
            "keywords": ["injection", "alignment", "align", "channel", "flag", "multi", "sequential"],
            "priority": "medium"
        },
        r"contact.*time|contact.*timer|timer.*flag|how.*long.*injection": {
            "answer": "The **contact timer** shows how long the analyte has been in contact with the sensor surface.\n\n"
            "It starts when the injection flag is placed and can be displayed as an overlay on the live sensorgram. "
            "Use it to track association phase duration during manual injections.",
            "category": "flags",
            "keywords": ["contact", "time", "timer", "injection", "duration", "overlay"],
            "priority": "low"
        },
        r"live.*flag|flag.*live|auto.*flag|automatic.*flag|software.*flag": {
            "answer": "On the **live sensorgram**, injection flags are placed automatically by the software "
            "when it detects a signal change (injection detection algorithm).\n\n"
            "You cannot manually place flags on the live graph — manual flag editing is done in the **Edits** tab "
            "after the run, where you can add, move, or remove flags freely.",
            "category": "flags",
            "keywords": ["live", "flag", "automatic", "auto", "software", "detection"],
            "priority": "medium"
        },
    },

    # -------------------------------------------------------------------------
    # PRESETS & TEMPLATES (FRS-sourced: METHOD_PRESETS_SYSTEM.md)
    # -------------------------------------------------------------------------
    "presets_templates": {
        r"cycle.*template|template.*cycle|save.*template|preset.*template": {
            "answer": "A **cycle template** saves a single cycle configuration (flow rate, contact time, volumes) "
            "so you can reuse it without re-entering settings.\n\n"
            "Cycle templates appear in the **Template Gallery** in the Method Builder.\n\n"
            "They are separate from **Queue Presets**, which save an entire experiment sequence.",
            "category": "presets_templates",
            "keywords": ["cycle", "template", "save", "preset", "reuse", "method"],
            "priority": "high"
        },
        r"queue.*preset|save.*preset|full.*sequence.*preset|preset.*queue": {
            "answer": "A **queue preset** saves your entire experiment queue (multiple cycles in sequence). "
            "Use it to repeat a full protocol across experiments.\n\n"
            "Queue presets are distinct from single-cycle templates — they capture the complete run order.",
            "category": "presets_templates",
            "keywords": ["queue", "preset", "sequence", "full", "protocol", "experiment"],
            "priority": "high"
        },
        r"how.*save.*preset|save.*method.*preset|!save": {
            "answer": "To save a preset, use the **!save** command in the Method Builder queue:\n\n"
            "```\n!save my_protocol_name\n```\n\n"
            "This saves the current queue as a named preset. "
            "To save a single cycle as a template, use the save button in the cycle editor.",
            "category": "presets_templates",
            "keywords": ["save", "preset", "!save", "command", "queue", "method"],
            "priority": "high"
        },
        r"how.*load.*preset|load.*template|@.*preset|use.*preset|apply.*preset": {
            "answer": "To load a saved preset into the Method Builder:\n\n"
            "- Type **@preset_name** in the queue to load a queue preset\n"
            "- Or click a template card in the **Template Gallery** to load a cycle template\n\n"
            "Loading a queue preset **replaces the current queue** (this action can be undone).",
            "category": "presets_templates",
            "keywords": ["load", "preset", "template", "apply", "@", "queue"],
            "priority": "high"
        },
        r"export.*preset|import.*preset|share.*preset|json.*preset|preset.*file": {
            "answer": "Presets and templates can be exported/imported as **JSON files**:\n\n"
            "- **Export**: Use the export button in the Template Gallery or Presets panel\n"
            "- **Import**: Drag-and-drop a JSON file or use the import button\n\n"
            "This lets you share protocols between instruments or users.",
            "category": "presets_templates",
            "keywords": ["export", "import", "share", "json", "preset", "template", "file"],
            "priority": "medium"
        },
        r"built.?in.*template|default.*template|example.*template|example.*method": {
            "answer": "Affilabs includes built-in templates for common P4SPR experiments:\n\n"
            "- **Binding** — Baseline → Binding 8.5 min → Regen → Baseline\n"
            "- **Amine Coupling** — EDC/NHS activation → 30 min Immobilization → Blocking → Binding series\n"
            "- **Titration** — 4-concentration dose-response series\n"
            "- **Custom** — Start with a blank step list\n\n"
            "Browse them in the **Template Gallery** (Method Builder opens with gallery when list is empty).",
            "category": "presets_templates",
            "keywords": ["built-in", "template", "default", "example", "gallery", "method"],
            "priority": "medium"
        },
    },

    # -------------------------------------------------------------------------
    # RECORDING & DATA SAVING (FRS-sourced: RECORDING_MANAGER_FRS.md)
    # -------------------------------------------------------------------------
    "recording": {
        r"how.*record|start.*recording|record.*data|begin.*recording|recording.*mode": {
            "answer": "To start recording:\n\n"
            "1. Press the **Record** button (red circle) in the top controls\n"
            "2. Choose a filename or accept the auto-generated name\n"
            "3. Data is saved to `~/Documents/Affilabs Data/<your name>/SPR_data/`\n\n"
            "Recording auto-saves every **60 seconds** — no manual save needed.",
            "category": "recording",
            "keywords": ["record", "start", "recording", "data", "save", "begin"],
            "priority": "high"
        },
        r"where.*save|save.*location|data.*folder|file.*location|find.*data.*file": {
            "answer": "Experiment data files are saved to:\n\n"
            "**`~/Documents/Affilabs Data/<username>/SPR_data/`**\n\n"
            "Files are named automatically with a timestamp. "
            "You can also find the current file path shown in the Recording status bar.",
            "category": "recording",
            "keywords": ["save", "location", "folder", "file", "find", "data", "path"],
            "priority": "high"
        },
        r"auto.*save|autosave|auto-save|data.*lost|recording.*crash": {
            "answer": "Affilabs auto-saves your recording every **60 seconds** when in file recording mode.\n\n"
            "If the software closes unexpectedly, you won't lose more than 60 seconds of data. "
            "The file is written incrementally — not just at the end.",
            "category": "recording",
            "keywords": ["auto", "save", "autosave", "crash", "lost", "data", "60"],
            "priority": "high"
        },
        r"memory.*only|no.*file|record.*without.*file|in.*memory.*mode": {
            "answer": "**Memory-only mode** records data in RAM without writing to disk.\n\n"
            "- No file is created until you manually export\n"
            "- The experiment counter does **not** increment\n"
            "- Data is lost if the software closes before you export\n\n"
            "Use this for exploratory runs. Switch to file mode for real experiments.",
            "category": "recording",
            "keywords": ["memory", "only", "no file", "in memory", "mode", "export"],
            "priority": "medium"
        },
        r"excel.*sheet|excel.*tab|what.*excel|excel.*export.*contain|excel.*file": {
            "answer": "The exported Excel file contains **7 sheets**:\n\n"
            "1. **Raw Data** — all raw wavelength values per channel per timepoint\n"
            "2. **Channels XY** — processed X/Y data per channel (time vs wavelength)\n"
            "3. **Cycles** — cycle-by-cycle summary table\n"
            "4. **Events** — timestamped event log (start, stop, injections, etc.)\n"
            "5. **Flags** — all annotation flags with positions\n"
            "6. **Analysis** — reserved for kinetics results (populated by analysis tools)\n"
            "7. **Metadata** — instrument info, user, date, settings",
            "category": "recording",
            "keywords": ["excel", "sheet", "tab", "export", "contain", "file", "data"],
            "priority": "medium"
        },
        r"experiment.*count|run.*number|experiment.*number|session.*count": {
            "answer": "The **experiment counter** increments each time you start a new recording in **file mode**.\n\n"
            "If you use memory-only mode, the counter does not increment. "
            "The counter is per user profile and persists across sessions.",
            "category": "recording",
            "keywords": ["experiment", "count", "number", "run", "session", "counter"],
            "priority": "low"
        },
        r"stop.*recording|end.*recording|finish.*recording|pause.*recording": {
            "answer": "To stop recording:\n\n"
            "- Press the **Stop** button (■) in the top controls\n\n"
            "The file is finalized and closed. You can then export or review data in the Edits tab. "
            "You can start a new recording immediately after stopping.",
            "category": "recording",
            "keywords": ["stop", "end", "finish", "recording", "pause"],
            "priority": "medium"
        },
    },

    # -------------------------------------------------------------------------
    # EDITS TAB & EXPORT (FRS-sourced: EDITS_EXPORT_FRS.md + EDITS_TABLE_FRS.md)
    # -------------------------------------------------------------------------
    "edits_export": {
        r"edits.*tab|edit.*tab|what.*edits.*tab|edits.*panel": {
            "answer": "The **Edits tab** is your post-acquisition analysis workspace:\n\n"
            "- Browse and overlay cycles from your experiment\n"
            "- Add, move, or remove annotation flags\n"
            "- Measure delta SPR (∆λ) between two cursor positions\n"
            "- Export data in multiple formats\n\n"
            "Open it from the tab bar after starting acquisition (or load a saved file).",
            "category": "edits_export",
            "keywords": ["edits", "tab", "panel", "analysis", "browse", "cycle"],
            "priority": "high"
        },
        r"export.*data|how.*export|export.*button|save.*data.*file": {
            "answer": "The Edits tab has **7 export options** in the right sidebar:\n\n"
            "1. **Excel** — full 7-sheet workbook\n"
            "2. **CSV / External Software** — comma-separated for Prism or Origin\n"
            "3. **TraceDrawer** — tab-delimited `.txt` for TraceDrawer software\n"
            "4. **Save as Method** — save cycle parameters as a reusable Method Builder template\n"
            "5. **Copy to Clipboard** — paste data directly into another app\n"
            "6. **Image (PNG)** — high-resolution 2400px graph export\n"
            "7. **AnIML** — open standard XML format for archiving\n\n"
            "Select cycles in the table first to export only those cycles.",
            "category": "edits_export",
            "keywords": ["export", "data", "button", "save", "options", "format"],
            "priority": "high"
        },
        r"tracedrawer|trace.?drawer|tracedrawer.*format|export.*tracedrawer": {
            "answer": "The **TraceDrawer export** produces a tab-delimited `.txt` file compatible with TraceDrawer analysis software.\n\n"
            "**Format:**\n"
            "- Columns: `X_RawDataA`, `Y_RawDataA`, `X_RawDataB`, `Y_RawDataB` ... (one pair per channel)\n"
            "- Y values are in **RU (resonance units)** — converted automatically from nm shift\n"
            "- Conversion factor: 1 nm = 355 RU\n\n"
            "Use this format if your analysis workflow is in TraceDrawer.",
            "category": "edits_export",
            "keywords": ["tracedrawer", "trace", "drawer", "format", "txt", "RU", "export"],
            "priority": "medium"
        },
        r"prism.*export|origin.*export|csv.*export|external.*software.*export": {
            "answer": "The **External Software** export button produces a standard **CSV file** "
            "compatible with GraphPad Prism, OriginPro, or any spreadsheet.\n\n"
            "Columns include time and wavelength shift per channel. "
            "This is different from the TraceDrawer export (which uses a specific column naming convention and RU units).",
            "category": "edits_export",
            "keywords": ["prism", "origin", "csv", "external", "software", "graphpad"],
            "priority": "medium"
        },
        r"save.*as.*method|export.*method|cycle.*to.*method|reuse.*cycle": {
            "answer": "**Save as Method** captures the parameters of selected cycle(s) and saves them as a reusable template in the Method Builder.\n\n"
            "Use it when you've run a good experiment and want to repeat it exactly — flow rates, contact times, volumes, and cycle order are all preserved.\n\n"
            "Find this button in the Edits tab export sidebar.",
            "category": "edits_export",
            "keywords": ["save", "method", "export", "cycle", "template", "reuse", "repeat"],
            "priority": "medium"
        },
        r"delta.*spr|delta.*lambda|∆.*lambda|∆.*spr|measure.*shift|cursor.*measurement": {
            "answer": "The **Delta SPR** tool measures the wavelength shift between two points:\n\n"
            "1. Place **Cursor 1** at your baseline reference point\n"
            "2. Place **Cursor 2** at the measurement point\n"
            "3. The ∆λ value (in nm) and ∆RU are shown in the measurement panel\n\n"
            "Use this to quantify binding responses, regeneration efficiency, or signal drift.",
            "category": "edits_export",
            "keywords": ["delta", "SPR", "lambda", "shift", "cursor", "measure", "nm", "RU"],
            "priority": "high"
        },
        r"image.*export|export.*image|screenshot.*graph|save.*graph.*image|png.*export": {
            "answer": "To export a high-resolution image of the sensorgram:\n\n"
            "- Click **Export Image** in the Edits tab sidebar\n"
            "- A **2400px PNG** is saved to your Documents folder\n\n"
            "The exported image includes all visible traces, flags, and cursor annotations as displayed.",
            "category": "edits_export",
            "keywords": ["image", "export", "screenshot", "graph", "png", "save", "high-resolution"],
            "priority": "low"
        },
        r"clipboard.*copy|copy.*data|paste.*excel|copy.*to.*clipboard": {
            "answer": "The **Copy to Clipboard** button in the Edits tab copies the currently visible data in tabular format.\n\n"
            "You can paste directly into Excel, Google Sheets, or any text editor. "
            "Only data for the cycles selected in the table is copied.",
            "category": "edits_export",
            "keywords": ["clipboard", "copy", "paste", "excel", "sheets", "tabular"],
            "priority": "low"
        },
    },

    # -------------------------------------------------------------------------
    # SIGNAL QUALITY / SENSOR IQ (FRS-sourced: SENSOR_IQ_SYSTEM.md)
    # -------------------------------------------------------------------------
    "signal_quality": {
        r"sensor.*iq|signal.*quality|quality.*score|iq.*level|sensor.*quality": {
            "answer": "**Sensor IQ** is the real-time signal quality rating for each SPR channel:\n\n"
            "- 🌟 **Excellent** — optimal signal (590–690 nm, very tight dip)\n"
            "- ✅ **Good** — normal operation (590–690 nm, ~70 nm dip width)\n"
            "- ⚠️ **Questionable** — edge zone or broadening dip — monitor closely\n"
            "- 🔶 **Poor** — weak coupling or sensor dry — stop and check\n"
            "- ⛔ **Critical** — out of valid range — immediate action required\n\n"
            "The colored pill next to each channel updates in real time.",
            "category": "signal_quality",
            "keywords": ["sensor", "IQ", "quality", "score", "level", "rating", "channel"],
            "priority": "high"
        },
        r"wavelength.*range|valid.*range|out.*of.*range|expected.*wavelength": {
            "answer": "The valid SPR wavelength range for this system is **560–720 nm**:\n\n"
            "| Zone | Range | Status |\n"
            "| --- | --- | --- |\n"
            "| Expected | 590–690 nm | ✅ Normal |\n"
            "| Edge low | 560–590 nm | ⚠️ Monitor |\n"
            "| Edge high | 690–720 nm | ⚠️ Monitor |\n"
            "| Out of bounds | <560 or >720 nm | ⛔ Critical |\n\n"
            "If your wavelength is outside 560–720 nm, stop and check the sensor.",
            "category": "signal_quality",
            "keywords": ["wavelength", "range", "valid", "expected", "out of bounds", "zone"],
            "priority": "high"
        },
        r"fwhm|dip.*width|peak.*width|full.*width|broad.*dip": {
            "answer": "**FWHM (Full Width at Half Maximum)** describes the width of the SPR dip:\n\n"
            "| FWHM | Quality |\n"
            "| --- | --- |\n"
            "| <60 nm | 🌟 Excellent |\n"
            "| 60–80 nm | ✅ Good (target ~70 nm) |\n"
            "| 80–100 nm | ⚠️ Poor — weak coupling |\n"
            "| >100 nm | ⛔ Critical — check sensor |\n\n"
            "A broad dip (>100 nm) usually means an air bubble, dry surface, or contamination.",
            "category": "signal_quality",
            "keywords": ["FWHM", "dip", "width", "full", "half", "maximum", "broad"],
            "priority": "medium"
        },
        r"critical.*signal|red.*signal|signal.*red|signal.*critical|stop.*signal": {
            "answer": "A **Critical** signal means the SPR wavelength is outside the valid range (<560 nm or >720 nm).\n\n"
            "**Stop acquisition immediately and check:**\n"
            "1. Is there water/buffer in the flow cell?\n"
            "2. Are there air bubbles on the sensor?\n"
            "3. Is the sensor chip properly installed?\n"
            "4. Is the optical path clear?\n\n"
            "Replace the sensor chip if the problem persists after priming.",
            "category": "signal_quality",
            "keywords": ["critical", "signal", "red", "stop", "out of range", "check"],
            "priority": "high"
        },
        r"poor.*signal|signal.*poor|orange.*signal|p2p|peak.?to.?peak|noisy.*signal": {
            "answer": "A **Poor** signal (orange indicator) means one or more of:\n\n"
            "- FWHM >100 nm (very broad dip — weak coupling)\n"
            "- Dip depth <30% (low contrast)\n"
            "- Peak-to-peak noise ≥8 nm (sensor dry or light blocked)\n\n"
            "**Action:**\n"
            "1. Prime the flow cell to remove air bubbles\n"
            "2. Check that the sensor surface is wetted\n"
            "3. Verify the optical path is unobstructed",
            "category": "signal_quality",
            "keywords": ["poor", "signal", "orange", "P2P", "peak-to-peak", "noisy", "weak"],
            "priority": "high"
        },
        r"questionable.*signal|yellow.*signal|signal.*yellow|edge.*zone|monitor.*signal": {
            "answer": "A **Questionable** signal (yellow indicator) means the sensor is in an edge condition:\n\n"
            "- Wavelength in 560–590 nm or 690–720 nm (edge zones)\n"
            "- FWHM 80–100 nm (broadening)\n"
            "- Peak-to-peak noise 5–8 nm\n\n"
            "**Action:** Monitor closely. Data is still usable but quality is reduced. "
            "Check temperature stability and flow rate.",
            "category": "signal_quality",
            "keywords": ["questionable", "signal", "yellow", "edge", "zone", "monitor"],
            "priority": "medium"
        },
        r"good.*signal|excellent.*signal|green.*signal|signal.*good|signal.*excellent": {
            "answer": "A **Good** or **Excellent** signal means the sensor is operating normally:\n\n"
            "- ✅ **Good**: wavelength 590–690 nm, FWHM ~60–80 nm, P2P <5 nm\n"
            "- 🌟 **Excellent**: same zone, FWHM <60 nm, dip depth ≥50%\n\n"
            "No action required — proceed with your experiment.",
            "category": "signal_quality",
            "keywords": ["good", "excellent", "signal", "green", "optimal", "normal"],
            "priority": "low"
        },
        r"signal.*drift|wavelength.*drift|baseline.*drift|drift.*over.*time": {
            "answer": "Slow wavelength drift over time can indicate:\n\n"
            "1. **Temperature instability** — check thermostat, allow more equilibration time\n"
            "2. **Buffer refractive index change** — verify buffer composition\n"
            "3. **Real binding** — expected during assay association phase\n"
            "4. **Sensor degradation** — if drift continues without recovery\n\n"
            "Drift toward edge zones (approaching <590 nm or >690 nm) will trigger a Questionable IQ rating.",
            "category": "signal_quality",
            "keywords": ["drift", "wavelength", "baseline", "shift", "time", "instability"],
            "priority": "medium"
        },
    },
}


def get_all_patterns():
    """Get flattened dict of all patterns across categories."""
    all_patterns = {}
    for category, patterns in PATTERNS.items():
        all_patterns.update(patterns)
    return all_patterns


def get_patterns_by_category(category: str):
    """Get all patterns for a specific category."""
    return PATTERNS.get(category, {})


def get_all_categories():
    """Get list of all pattern categories."""


def get_all_patterns():
    """Get flattened dict of all patterns across categories."""
    all_patterns = {}
    for category, patterns in PATTERNS.items():
        all_patterns.update(patterns)
    return all_patterns


def get_patterns_by_category(category: str):
    """Get all patterns for a specific category."""
    return PATTERNS.get(category, {})


def get_all_categories():
    """Get list of all pattern categories."""
    return list(PATTERNS.keys())
