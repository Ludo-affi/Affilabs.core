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
        r"pump.*types|which.*pump|pump.*configuration": {
            "answer": "ezControl supports two pump types:\n\n"
            "**AffiPump** — External syringe pumps (2× Tecan Cavro, 1000 µL, 0.001–24,000 µL/min) for precise injections.\n"
            "**P4PROPLUS** — Internal peristaltic pumps (3 pumps, 5–220 RPM) for continuous flow.\n\n"
            "Control both from the **Flow** tab.",
            "category": "pump",
            "keywords": ["pump", "types", "which", "configuration"],
            "priority": "high"
        },
        r"how.*pump|use.*pump|pump.*control|start.*pump": {
            "answer": "In the **Flow** tab:\n\n"
            "**AffiPump:** Set flow rate → choose pump (KC1/KC2/Both) → click **Run Buffer** → **Stop** when done.\n"
            "**P4PROPLUS:** Set RPM (5-220) → choose channel → click **Start**. You can adjust RPM live.\n\n"
            "Red **Emergency Stop** button halts all pumps immediately.",
            "category": "pump",
            "keywords": ["how", "pump", "use", "control", "start"],
            "priority": "high"
        },
        r"prime.*pump|pump.*priming|how.*prime": {
            "answer": "Go to **Flow** tab → click **Prime Pump**. It runs 6 cycles to fill tubing with buffer "
            "and remove air bubbles (~2-3 min).\n\n"
            "Always prime before your first experiment of the day!",
            "category": "pump",
            "keywords": ["prime", "pump", "priming"],
            "priority": "high"
        },
        r"cleanup.*pump|pump.*cleanup|remove.*bubbles": {
            "answer": "Click **Cleanup** in the Flow tab. It runs a pulse phase (10 rapid cycles to dislodge bubbles) "
            "then a prime phase (6 cycles to flush) — takes ~3-4 minutes.\n\n"
            "Use when you see air bubbles, after maintenance, or if the baseline is noisy.",
            "category": "pump",
            "keywords": ["cleanup", "pump", "remove", "bubbles"],
            "priority": "high"
        },
        r"pump.*flush|flush.*pump|flush.*system": {
            "answer": "Click **Flush** in the Flow tab for a quick 1-minute system rinse (2-3 rapid cycles). "
            "Good for switching between samples or buffers.\n\n"
            "For air bubble removal, use **Cleanup** instead.",
            "category": "pump",
            "keywords": ["pump", "flush", "system"],
            "priority": "medium"
        },
        r"pump.*home|home.*pump|initialize.*pump": {
            "answer": "Click **Home Pumps** in the Flow tab to return syringe plungers to zero (~10-20 sec). "
            "Do this after errors, blockages, or before switching samples.\n\n"
            "Pumps also auto-home if a blockage is detected.",
            "category": "pump",
            "keywords": ["pump", "home", "initialize"],
            "priority": "medium"
        },
        r"pump.*blocked|blockage|pump.*error": {
            "answer": "The system auto-detects blockages by comparing pump completion times. If blocked:\n\n"
            "1. Check tubing for kinks or clogs\n"
            "2. Verify valve positions\n"
            "3. Remove the obstruction\n"
            "4. Click **Home Pumps**, then run **Prime Pump** to test",
            "category": "pump",
            "keywords": ["pump", "blocked", "blockage", "error"],
            "priority": "high"
        },
        r"30.*second.*injection|contact.*time|timed.*injection": {
            "answer": "Click **30s Inject** in the Flow tab while pumps are running. The valve opens for "
            "30 seconds of sample contact, then auto-closes.\n\n"
            "Use **Valve Sync** to control whether one or both valves open.",
            "category": "pump",
            "keywords": ["30", "second", "injection", "contact", "time"],
            "priority": "medium"
        },
        r"valve.*control|6.*port.*valve|3.*way.*valve": {
            "answer": "**6-Port Valves** (KC1/KC2): Switch between LOAD (loop isolated) and INJECT (sample to sensor).\n"
            "**3-Way Valves** (KC1/KC2): Route flow between channels A/B (KC1) or C/D (KC2).\n\n"
            "Valves operate automatically during most operations. Manual control is in Advanced mode.",
            "category": "pump",
            "keywords": ["valve", "control", "6", "port", "3", "way"],
            "priority": "medium"
        },
        r"channel.*routing|channel.*a.*b.*c.*d|sensor.*channels": {
            "answer": "KC1 routes to **Channel A** (3-way closed) or **B** (open). "
            "KC2 routes to **Channel C** (closed) or **D** (open).\n\n"
            "Typical setup: A & C for buffer reference, B & D for samples.",
            "category": "pump",
            "keywords": ["channel", "routing", "a", "b", "c", "d"],
            "priority": "medium"
        },
        r"flow.*rate|set.*flow|pump.*speed": {
            "answer": "**AffiPump:** 0.001–24,000 µL/min (typical: 50-200 for experiments). "
            "**P4PROPLUS:** 5–220 RPM with live adjustment. Set both in the **Flow** tab.\n\n"
            "Recommendations: 50-100 µL/min for binding, 200-500 for washing, 1000+ for priming.",
            "category": "pump",
            "keywords": ["flow", "rate", "set", "speed"],
            "priority": "medium"
        },
        r"rpm.*correction|pump.*correction|correction.*factor": {
            "answer": "The correction factor compensates for tubing wear on peristaltic pumps (default: 1.00). "
            "Flow too slow? Increase it (e.g. 1.05). Too fast? Decrease (e.g. 0.95). "
            "Reset to 1.00 after replacing tubing.\n\n"
            "Set in **Flow** tab → Correction spinbox.",
            "category": "pump",
            "keywords": ["rpm", "correction", "factor"],
            "priority": "low"
        },
        r"pump.*emergency.*stop|emergency.*stop|stop.*pump": {
            "answer": "Click the red **Emergency Stop** button — all pumps halt immediately. "
            "Your settings are preserved so you can restart after fixing the issue.",
            "category": "pump",
            "keywords": ["pump", "emergency", "stop"],
            "priority": "high"
        },
        r"pump.*troubleshoot|pump.*not.*working|pump.*issue": {
            "answer": "**Won't start:** Check connection in Device Status, verify COM port, try **Home Pumps**.\n"
            "**No flow:** Check tubing, verify valves, run **Prime Pump**.\n"
            "**Erratic flow:** Run **Cleanup** for air bubbles, check for kinked tubing.\n"
            "**Blockage:** Check tubing/valves, **Home Pumps**, then **Prime Pump**.",
            "category": "pump",
            "keywords": ["pump", "troubleshoot", "not", "working", "issue"],
            "priority": "high"
        },
        r"pump.*best.*practice|pump.*maintenance": {
            "answer": "**Daily:** Prime at startup, check for air bubbles.\n"
            "**After experiments:** Flush with buffer, stop pumps.\n"
            "**Weekly:** Inspect tubing, clean pump heads, test with water.\n"
            "**Storage:** Keep in buffer or 20% ethanol — never leave empty.",
            "category": "pump",
            "keywords": ["pump", "best", "practice", "maintenance"],
            "priority": "medium"
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
            "Example: `Concentration 5min A:100nM contact 180s`",
            "category": "method",
            "keywords": ["create", "cycle", "new", "build", "method", "how"],
            "priority": "high"
        },
        r"how.*build.*method|how.*make.*method|how.*create.*method|method.*builder|build.*method": {
            "answer": "Open **+ Build Method** from the sidebar and type cycles one per line:\n\n"
            "`Baseline 5min`\n"
            "`Concentration 5min A:100nM contact 180s`\n"
            "`Regeneration 30sec ALL:50mM`\n\n"
            "Click **➕ Add to Method** → **📋 Push to Queue** → **▶ Start Run**.\n\n"
            "Shortcuts: `build 5` for auto-generated series, `@spark amine coupling` for templates.",
            "category": "method",
            "keywords": ["build", "method", "how", "create", "make"],
            "priority": "high"
        },
        r"cycle.*type|what.*types|available.*types|type.*cycle": {
            "answer": "There are 6 cycle types:\n\n"
            "• **Baseline** — Running buffer, stable signal\n"
            "• **Concentration** — Inject analyte, measure binding\n"
            "• **Regeneration** — Strip bound analyte (auto 30s contact)\n"
            "• **Immobilization** — Attach ligand to sensor\n"
            "• **Wash** — Rinse flow path\n"
            "• **Other** — Custom (activation, blocking, etc.)\n\n"
            "All injections start 20 seconds into the cycle.",
            "category": "method",
            "keywords": ["cycle", "types", "available", "what"],
            "priority": "high"
        },
        r"cycle.*syntax|how.*write.*cycle|note.*syntax|note.*format|how.*type.*cycle": {
            "answer": "Format: `Type Duration Channel:ValueUnits contact Ns`\n\n"
            "Examples:\n"
            "• `Baseline 5min`\n"
            "• `Concentration 5min A:100nM contact 180s`\n"
            "• `Regeneration 30sec ALL:50mM`\n"
            "• `Concentration 5min A:100nM contact 120s partial injection`\n\n"
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
            "answer": "**Simple injection** (default): Full sample loop injection via valve switching.\n"
            "**Partial injection**: 30 µL spike — add `partial injection` to the cycle line.\n\n"
            "Concentration, Immobilization, Wash, and Regeneration auto-inject. "
            "Baseline and Other don't. All injections start 20 seconds into the cycle.",
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
            "`Baseline 5min` → `Concentration 5min A:100nM contact 180s` → `Regeneration 30sec ALL:50mM`\n\n"
            "**Dose-Response:**\n"
            "`Baseline 5min` → Concentration cycles at 10nM, 50nM, 100nM, 500nM → `Regeneration 30sec`\n\n"
            "💡 Type `build 5` for an auto-generated concentration series.",
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
            "• **KN** — Kinetic\n"
            "• **CN** — Concentration\n"
            "• **RG** — Regeneration\n"
            "• **AS** — Association\n"
            "• **DS** — Dissociation\n"
            "• **WS** — Wash\n"
            "• **OT** — Other\n\n"
            "Example: `BN 5min A:100nM contact 180s` (short for Binding)",
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
            "`Kinetic 5min A:100nM fr 50` (flow rate shorthand)\n"
            "`Binding 5min A:100nM iv 25` (injection volume shorthand)\n"
            "`Kinetic 5min A:100nM fr 50 iv 25 contact 3min` (both)",
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
            "`Binding 5min A:100nM contact 5h` (long overnight binding)\n"
            "`Immobilization 4min contact 2hr` (controlled surface prep)",
            "category": "method",
            "keywords": ["contact", "time", "hour", "h", "hr", "3h", "5h"],
            "priority": "high"
        },
        r"partial.*injection|simple.*injection|injection.*type": {
            "answer": "**Injection Types** (modifiers):\n\n"
            "• `partial` — 30 µL spike (quick test, less reagent)\n"
            "• No modifier (default) — Full sample loop injection\n\n"
            "Usage: `Binding 5min A:100nM contact 180s partial`\n"
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
            "`build 5` → 5 × (Binding 15min + Regeneration + Baseline)\n"
            "`build 10` → 10 × (Binding 15min + Regeneration + Baseline)\n\n"
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
            "`Binding 5min A:10nM contact 180s`\n"
            "`Regen 30sec ALL:50mM`\n"
            "`Baseline 2min`\n"
            "`Binding 5min A:50nM contact 180s`\n"
            "`< repeat at 100nM, 500nM >`\n\n"
            "**Overnight Stability:**\n"
            "`Baseline overnight` (8 hours, auto-enables Overnight Mode)\n"
            "`Baseline 12h` (12 hours)\n\n"
            "**Amine Coupling:**\n"
            "`Baseline 30sec`\n"
            "`Other 4min` (EDC/NHS activation)\n"
            "`Immobilization 4min A:50µg/mL contact 180s`\n"
            "`< blocking & titration >`",
            "category": "method",
            "keywords": ["example", "dose", "response", "titration", "amine", "coupling", "overnight"],
            "priority": "high"
        },
        r"quick.*reference|all.*syntax|cheat.*sheet|shortcut|quick": {
            "answer": "**Quick Syntax Cheat Sheet:**\n\n"
            "**Type Duration Channel Contact Modifiers**\n\n"
            "Examples:\n"
            "`BN 5min A:100nM contact 180s` (short for Binding)\n"
            "`KN 5min A:100nM fr 50 contact 3min` (Kinetic with flow rate)\n"
            "`IM 4min A:50µg/mL contact 2h` (2-hour immobilization)\n"
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
            "`Binding 5min [A:100nM] [B:50nM] [C:25nM] [D:10nM] contact 180s`\n\n"
            "Or use all channels: `Binding 5min ALL:100nM contact 180s`",
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
            "Example workflow:\n"
            "`Baseline 5min ALL`\n"
            "`Immobilization 10min [A:50µg/mL] contact 300s` (only A gets ligand)\n"
            "`Wash 30sec ALL`\n"
            "`Baseline 5min ALL`\n\n"
            "Then channels B, C, D remain in buffer as references while you inject analyte into **all 4 channels**, "
            "and only A shows binding (because A has the ligand).",
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
            "`Binding 5min [A:100nM] [B:50nM] [C:25nM] [D:10nM] contact 180s`\n"
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
    },

    "analysis": {
        r"baseline.*drift|baseline.*unstable": {
            "answer": "Allow 30-60 minutes of warmup, check for bubbles in the flow cell, "
            "and verify consistent flow rate and temperature.\n\n"
            "You can capture a new baseline in **Settings** or apply baseline correction in the **Analysis** tab.",
            "category": "analysis",
            "keywords": ["baseline", "drift", "unstable"],
            "priority": "medium"
        },
    },

    "general": {
        r"keyboard.*shortcuts|hotkeys": {
            "answer": "Useful shortcuts: **Ctrl+S** (stop), **Ctrl+E** (export), "
            "**Ctrl+Z** (undo), **Ctrl+Shift+Z** (redo), **F5** (refresh detector).",
            "category": "general",
            "keywords": ["keyboard", "shortcuts", "hotkeys"],
            "priority": "low"
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
    return list(PATTERNS.keys())
