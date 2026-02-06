"""
Spark Pattern Definitions - Single Source of Truth

This module contains all pre-defined Q&A patterns for the Spark AI assistant.
Patterns are organized by category for maintainability.

To add new patterns:
1. Find the appropriate category or create a new one
2. Add the regex pattern as a key
3. Provide answer text, category, keywords, and priority
4. Test with real user questions

Pattern format:
{
    r"regex_pattern": {
        "answer": "Multi-line answer text with formatting...",
        "category": "category_name",
        "keywords": ["keyword1", "keyword2"],
        "priority": "high|medium|low"
    }
}
"""

PATTERNS = {
    "startup": {
        r"power.*on|start.*system|startup.*procedure|turn.*on": {
            "answer": "**Power On Procedure:**\n1. Press the 'Power On' button (top right corner)\n2. System will check for hardware connection\n3. If hardware not found, check USB connections\n4. Click 'Start' in the Startup Calibration popup\n5. Wait 1-2 minutes for calibration to complete\n6. Review the QC Report\n7. Close and press 'Start' to begin live acquisition\n\n💡 The system starts in Auto-Read mode. To record data, build a method and press 'Record'.",
            "category": "startup",
            "keywords": ["power", "on", "start", "system", "startup", "turn"],
            "priority": "high"
        },
        r"calibration.*fail|startup.*calibration|qc.*report": {
            "answer": "**Startup Calibration:**\n• Takes 1-2 minutes to complete\n• Review QC Report for any warnings\n• If calibration fails:\n  - Ensure no flow path obstructions\n  - Check reagents are loaded properly\n  - Verify detector connection\n  - Try power cycling the device\n\nAfter successful calibration, you can start live acquisition.",
            "category": "startup",
            "keywords": ["calibration", "fail", "startup", "qc", "report"],
            "priority": "high"
        },
        r"auto.*read.*mode|how.*to.*record|save.*data.*live": {
            "answer": "**Recording Data:**\nThe system starts in Auto-Read Mode (displays data but doesn't save).\n\nTo record data:\n1. Go to 'Method' tab in sidebar\n2. Build your experimental method\n3. Press 'Record' when ready\n4. Data will be saved according to your method\n\nYou can view live data without recording at any time.",
            "category": "startup",
            "keywords": ["auto", "read", "mode", "record", "save", "data"],
            "priority": "medium"
        },
        r"hardware.*not.*found|cannot.*find.*hardware|device.*not.*connected": {
            "answer": "**Hardware Connection Issues:**\n1. Check USB cable connections (both ends)\n2. Verify device power supply is on\n3. Try a different USB port (USB 3.0 preferred)\n4. Check Windows Device Manager for driver issues\n5. Restart the software\n6. Power cycle the device\n\nIf the problem persists, contact technical support.",
            "category": "startup",
            "keywords": ["hardware", "not", "found", "device", "connected"],
            "priority": "high"
        },
    },

    "basic": {
        r"how.*start.*acquisition|begin.*recording": {
            "answer": "To start acquisition:\n1. Click 'Live' tab in the main area\n2. Ensure detector is connected (check Device Status tab)\n3. Click the green 'Start' button\n4. Data will begin streaming in real-time",
            "category": "basic",
            "keywords": ["start", "acquisition", "begin", "recording"],
            "priority": "high"
        },
        r"how.*stop.*acquisition|end.*recording": {
            "answer": "To stop acquisition, click the red 'Stop' button in the Live tab. You can also use the keyboard shortcut Ctrl+S.",
            "category": "basic",
            "keywords": ["stop", "acquisition", "end", "recording"],
            "priority": "high"
        },
    },

    "export": {
        r"export.*data|save.*data|download.*data": {
            "answer": "To export data:\n1. Go to the 'Export' tab in the sidebar\n2. Select your desired format (Excel, CSV, or AnIML)\n3. Choose cycles to export\n4. Click 'Export' button\n5. Choose save location",
            "category": "export",
            "keywords": ["export", "save", "download", "data"],
            "priority": "high"
        },
    },

    "hardware": {
        r"detector.*not.*found|can't.*find.*detector|no.*detector": {
            "answer": "Detector connection troubleshooting:\n1. Check USB cable is firmly connected\n2. Open 'Device Status' tab to see connection status\n3. Try clicking 'Scan for Devices'\n4. Check Windows Device Manager for driver issues\n5. Try a different USB port (USB 3.0 preferred)",
            "category": "hardware",
            "keywords": ["detector", "not", "found", "can't", "find"],
            "priority": "high"
        },
    },

    "calibration": {
        r"what.*calibrations|calibration.*types|how.*many.*calibrations": {
            "answer": "**ezControl has 5 calibration types:**\n\n"
            "1. **Simple LED** (10-20 sec) - Quick sensor swap\n"
            "2. **Full System** (3-5 min) - Complete calibration with QC\n"
            "3. **Polarizer** (2-5 min) - Servo position optimization\n"
            "4. **OEM LED** (10-15 min) - Factory-level calibration\n"
            "5. **LED Model Training** (2-5 min) - Rebuild optical model\n\n"
            "📍 All found in: Settings Tab → Calibration Controls\n\n"
            "💡 For details, see CALIBRATION_GUIDE.md",
            "category": "calibration",
            "keywords": ["calibrations", "types", "how", "many"],
            "priority": "high"
        },
        r"simple.*calibration|simple.*led|quick.*calibration": {
            "answer": "**Simple LED Calibration** (10-20 seconds)\n\n"
            "**When to use:** Sensor swap (same type), quick LED adjustment\n\n"
            "**Requirements:** LED model must already exist\n\n"
            "**How to run:**\n"
            "1. Settings tab → Calibration Controls\n"
            "2. Click 'Run Simple Calibration'\n"
            "3. Wait 10-20 seconds\n"
            "4. Graphs clear, live data resumes\n\n"
            "⚠️ If 'LED model not found' error → Run OEM Calibration first",
            "category": "calibration",
            "keywords": ["simple", "calibration", "led", "quick"],
            "priority": "high"
        },
        r"full.*calibration|complete.*calibration|6.*step": {
            "answer": "**Full System Calibration** (3-5 minutes)\n\n"
            "**6 Steps:**\n"
            "1. Dark reference\n"
            "2. S-mode convergence\n"
            "3. S-mode reference\n"
            "4. P-mode convergence\n"
            "5. P-mode reference\n"
            "6. QC validation\n\n"
            "**How to run:**\n"
            "1. Settings tab → Calibration Controls\n"
            "2. Click 'Run Full Calibration'\n"
            "3. Click 'Start' in dialog\n"
            "4. Wait 3-5 minutes\n"
            "5. Review QC Report\n"
            "6. Click 'Start' to begin live data\n\n"
            "✅ Use for: sensor swaps, monthly QC, after maintenance",
            "category": "calibration",
            "keywords": ["full", "calibration", "complete", "6", "step"],
            "priority": "high"
        },
        r"polarizer.*calibration|servo.*calibration|calibrate.*polarizer": {
            "answer": "**Polarizer Calibration** (2-5 minutes)\n\n"
            "**Purpose:** Find optimal servo positions for S and P modes\n\n"
            "**Process:**\n"
            "• Sweeps servo across 180° range\n"
            "• Finds positions ~90° apart with best signal\n"
            "• Saves to device_config.json\n\n"
            "**How to run:**\n"
            "1. Settings tab → Calibration Controls\n"
            "2. Click 'Calibrate Polarizer'\n"
            "3. Wait 2-5 minutes\n"
            "4. Positions saved, live data resumes\n\n"
            "✅ Use when: signal drops, servo replaced, positions incorrect",
            "category": "calibration",
            "keywords": ["polarizer", "calibration", "servo"],
            "priority": "medium"
        },
        r"oem.*calibration|factory.*calibration|complete.*calibration": {
            "answer": "**OEM LED Calibration** (10-15 minutes)\n\n"
            "**Most complete calibration - 3 phases:**\n"
            "1. Servo Polarizer Calibration (2-5 min)\n"
            "2. LED Model Training (2-5 min)\n"
            "3. Full 6-Step Calibration (3-5 min)\n\n"
            "**How to run:**\n"
            "1. Settings tab → Calibration Controls\n"
            "2. Click 'Run OEM Calibration'\n"
            "3. Click 'Start' in dialog\n"
            "4. Wait 10-15 minutes (grab coffee ☕)\n"
            "5. Review QC Report\n"
            "6. Click 'Start' to begin live data\n\n"
            "✅ Use for: first-time setup, LED model missing, complete reset\n"
            "❌ Don't use for: quick sensor swaps (use Simple LED instead)",
            "category": "calibration",
            "keywords": ["oem", "calibration", "factory", "complete"],
            "priority": "high"
        },
        r"led.*model.*training|train.*led|optical.*model": {
            "answer": "**LED Model Training** (2-5 minutes)\n\n"
            "**Purpose:** Rebuild optical model only (no full calibration)\n\n"
            "**Process:**\n"
            "• Tests LED response at 10-60ms integration times\n"
            "• Creates 3-stage linear model\n"
            "• Saves optical_calibration.json\n\n"
            "**How to run:**\n"
            "1. Settings tab → Calibration Controls\n"
            "2. Click 'Train LED Model'\n"
            "3. Click 'Start'\n"
            "4. Wait 2-5 minutes\n"
            "5. Model saved, live data resumes\n\n"
            "✅ Use when: LED model missing, model seems incorrect\n"
            "💡 Faster than OEM if you only need model (not servo positions)",
            "category": "calibration",
            "keywords": ["led", "model", "training", "train", "optical"],
            "priority": "medium"
        },
        r"startup.*calibration|daily.*calibration|power.*on.*calibration": {
            "answer": "**Startup Calibration** (1-2 minutes)\n\n"
            "**Runs automatically when you click 'Power On'**\n\n"
            "**Process:**\n"
            "1. Hardware connection check\n"
            "2. Quick LED adjustment\n"
            "3. Signal quality validation\n"
            "4. QC Report shown\n\n"
            "**If it fails:**\n"
            "• Click 'Retry' (up to 3 attempts)\n"
            "• OR click 'Continue Anyway' to troubleshoot manually\n\n"
            "**Common fail causes:**\n"
            "• Air bubbles in flow cell\n"
            "• Hardware not warmed up\n"
            "• Connection issues\n\n"
            "💡 Allow 30-60 min warmup before first calibration of the day",
            "category": "calibration",
            "keywords": ["startup", "calibration", "daily", "power", "on"],
            "priority": "high"
        },
        r"calibration.*failed|retry.*calibration|calibration.*fail": {
            "answer": "**Calibration Failed - Recovery Options:**\n\n"
            "**During Startup Calibration:**\n"
            "• Click **'Retry'** - Try again (up to 3 attempts)\n"
            "• Click **'Continue Anyway'** - Skip and troubleshoot\n\n"
            "**Common Causes:**\n"
            "✅ Air bubbles → Purge system, retry\n"
            "✅ Not warmed up → Wait 30-60 min, retry\n"
            "✅ Hardware issue → Check Device Status tab\n"
            "✅ LED model missing → Run OEM Calibration\n\n"
            "**Manual Fix:**\n"
            "1. Click 'Continue Anyway'\n"
            "2. Go to Settings tab\n"
            "3. Run Full System Calibration manually\n\n"
            "If fails 3+ times → Check logs, contact support",
            "category": "calibration",
            "keywords": ["calibration", "failed", "retry", "fail"],
            "priority": "high"
        },
        r"when.*calibrate|which.*calibration|calibration.*use": {
            "answer": "**Which Calibration to Use:**\n\n"
            "**Sensor swap (same type):**\n→ Simple LED Calibration (10-20 sec)\n\n"
            "**Sensor swap (different type):**\n→ Full System Calibration (3-5 min)\n\n"
            "**First-time setup:**\n→ OEM LED Calibration (10-15 min)\n\n"
            "**LED model missing:**\n→ LED Model Training (2-5 min)\n\n"
            "**Polarizer positions wrong:**\n→ Polarizer Calibration (2-5 min)\n\n"
            "**Daily startup:**\n→ Automatic (runs on Power On)\n\n"
            "**Monthly QC:**\n→ OEM LED Calibration (10-15 min)\n\n"
            "All calibrations: Settings tab → Calibration Controls",
            "category": "calibration",
            "keywords": ["when", "calibrate", "which", "use"],
            "priority": "high"
        },
        r"led.*model.*not.*found|optical.*calibration.*missing": {
            "answer": "**Error: 'LED model not found'**\n\n"
            "**Cause:** optical_calibration.json is missing\n\n"
            "**Solution - Two options:**\n\n"
            "**Option 1: Quick (2-5 min)**\n"
            "• Settings → Calibration Controls\n"
            "• Click 'Train LED Model'\n"
            "• Creates model only\n\n"
            "**Option 2: Complete (10-15 min)**\n"
            "• Settings → Calibration Controls\n"
            "• Click 'Run OEM Calibration'\n"
            "• Creates model + calibrates servo + full calibration\n\n"
            "💡 First-time setup? → Use Option 2 (OEM)\n"
            "💡 Just need model? → Use Option 1 (Training)",
            "category": "calibration",
            "keywords": ["led", "model", "not", "found", "missing"],
            "priority": "high"
        },
        r"calibration.*freeze|calibration.*hang|calibration.*stuck": {
            "answer": "**Calibration Freezing/Hanging:**\n\n"
            "**Immediate action:**\n"
            "• Wait 5 minutes first (some steps take time)\n"
            "• If still frozen → Close software\n"
            "• Restart ezControl\n"
            "• Try calibration again\n\n"
            "**Prevention:**\n"
            "✅ Ensure stable hardware connection\n"
            "✅ Allow 30-60 min warmup\n"
            "✅ Check for air bubbles before starting\n"
            "✅ Don't change settings during calibration\n\n"
            "**If persists:**\n"
            "• Check logs/ folder for errors\n"
            "• Try different calibration type\n"
            "• Contact support with log file",
            "category": "calibration",
            "keywords": ["calibration", "freeze", "hang", "stuck"],
            "priority": "medium"
        },
        r"qc.*report|quality.*control|calibration.*qc": {
            "answer": "**QC Report (Quality Control)**\n\n"
            "**Shown after Full/OEM calibrations**\n\n"
            "**Validates:**\n"
            "✅ Signal strength above minimum\n"
            "✅ LED convergence successful\n"
            "✅ Baseline stability good\n"
            "✅ Reference spectra quality\n"
            "✅ No detector saturation\n\n"
            "**If warnings appear:**\n"
            "⚠️ Signal low → Check prism, LEDs, detector\n"
            "⚠️ Baseline drift → Allow more warmup\n"
            "⚠️ Slow convergence → May need LED retraining\n\n"
            "**Best practice:**\n"
            "• Save QC reports to file\n"
            "• Track trends over time\n"
            "• Document any warnings",
            "category": "calibration",
            "keywords": ["qc", "report", "quality", "control"],
            "priority": "medium"
        },
        r"sensor.*swap|replace.*sensor|change.*sensor": {
            "answer": "**Sensor Swap Calibration Workflow:**\n\n"
            "**Same sensor type (e.g., gold to gold):**\n"
            "1. Install new sensor with buffer\n"
            "2. Settings → 'Run Simple Calibration' (10-20 sec)\n"
            "3. Start acquisition ✅\n\n"
            "**Different sensor type (e.g., gold to graphene):**\n"
            "1. Install new sensor with buffer\n"
            "2. Settings → 'Run Full Calibration' (3-5 min)\n"
            "3. Review QC Report\n"
            "4. Start acquisition ✅\n\n"
            "**Major sensor change:**\n"
            "1. Install new sensor\n"
            "2. Settings → 'Run OEM Calibration' (10-15 min)\n"
            "3. Thoroughly review QC\n"
            "4. Validate with test samples ✅\n\n"
            "⚠️ Critical: No air bubbles!",
            "category": "calibration",
            "keywords": ["sensor", "swap", "replace", "change"],
            "priority": "high"
        },
        r"calibration.*best.*practice|calibration.*tips": {
            "answer": "**Calibration Best Practices:**\n\n"
            "**Before calibration:**\n"
            "✅ Clean prism/sensor\n"
            "✅ Fresh buffer (no bubbles!)\n"
            "✅ Allow warmup (30-60 min ideal)\n"
            "✅ Check Device Status tab\n"
            "✅ Stable baseline\n\n"
            "**During calibration:**\n"
            "❌ Don't disturb system\n"
            "❌ Don't change settings\n"
            "❌ Don't run other operations\n"
            "✅ Monitor progress dialog\n\n"
            "**After calibration:**\n"
            "✅ Review QC Report\n"
            "✅ Verify sensorgram looks good\n"
            "✅ Document any issues\n\n"
            "**Schedule:**\n"
            "• Daily: Startup calibration (auto)\n"
            "• Weekly: Full System Calibration\n"
            "• Monthly: OEM LED Calibration",
            "category": "calibration",
            "keywords": ["calibration", "best", "practice", "tips"],
            "priority": "medium"
        },
    },

    "pump": {
        r"pump.*types|which.*pump|pump.*configuration": {
            "answer": "**ezControl supports 2 pump configurations:**\n\n"
            "**1. AffiPump (External Syringe Pumps)**\n"
            "• Hardware: 2× Tecan Cavro Centris syringe pumps\n"
            "• Volume: 1000 µL per syringe (precision)\n"
            "• Type: Volume-based (aspirate/dispense)\n"
            "• Flow: 0.001 - 24,000 µL/min\n"
            "• Use: Precise volume injections, titrations\n\n"
            "**2. P4PROPLUS (Internal Peristaltic)**\n"
            "• Hardware: 3 peristaltic pumps (integrated)\n"
            "• Type: Continuous flow (RPM-based)\n"
            "• RPM: 5 - 220 RPM\n"
            "• Use: Continuous buffer flow, kinetics\n\n"
            "📍 Location: Flow tab in sidebar",
            "category": "pump",
            "keywords": ["pump", "types", "which", "configuration"],
            "priority": "high"
        },
        r"how.*pump|use.*pump|pump.*control|start.*pump": {
            "answer": "**Pump Control - Flow Tab:**\n\n"
            "**AffiPump (Syringe Pumps):**\n"
            "1. Flow tab → Set flow rate (µL/min)\n"
            "2. Choose pump: KC1, KC2, or Both\n"
            "3. Click 'Run Buffer' for continuous flow\n"
            "4. Click 'Stop' when done\n\n"
            "**P4PROPLUS (Peristaltic):**\n"
            "1. Flow tab → Set RPM (5-220)\n"
            "2. Choose channel: Pump 1, Pump 2, or Both\n"
            "3. Click 'Start' to begin flow\n"
            "4. Adjust RPM while running (live updates)\n"
            "5. Click 'Stop' when done\n\n"
            "⚠️ Emergency Stop: Red button stops all pumps immediately",
            "category": "pump",
            "keywords": ["how", "pump", "use", "control", "start"],
            "priority": "high"
        },
        r"prime.*pump|pump.*priming|how.*prime": {
            "answer": "**Pump Priming (AffiPump):**\n\n"
            "**Purpose:** Fill pumps and tubing with buffer\n\n"
            "**Steps:**\n"
            "1. Flow tab → Click 'Prime Pump'\n"
            "2. Default: 6 cycles × 1000 µL\n"
            "3. Takes ~2-3 minutes\n"
            "4. Valves open progressively:\n"
            "   - Cycles 1-2: Pump priming\n"
            "   - Cycles 3-4: Sample loop priming\n"
            "   - Cycles 5-6: Full path priming\n\n"
            "✅ Removes air bubbles\n"
            "✅ Establishes buffer flow\n"
            "✅ Auto-detects blockages\n\n"
            "⚠️ Always prime before first experiment of the day!",
            "category": "pump",
            "keywords": ["prime", "pump", "priming"],
            "priority": "high"
        },
        r"cleanup.*pump|pump.*cleanup|remove.*bubbles": {
            "answer": "**Pump Cleanup (AffiPump):**\n\n"
            "**Purpose:** Remove air bubbles and contaminants\n\n"
            "**Two-Phase Process:**\n"
            "1. **Pulse Phase:** 10 rapid cycles (200 µL)\n"
            "   - Dislodges stubborn bubbles\n"
            "   - Fast aspirate/dispense\n\n"
            "2. **Prime Phase:** 6 standard cycles (1000 µL)\n"
            "   - Flushes entire system\n"
            "   - Opens all valves progressively\n\n"
            "**How to run:**\n"
            "1. Flow tab → Click 'Cleanup'\n"
            "2. Takes ~3-4 minutes\n"
            "3. Check for bubbles in tubing\n\n"
            "Use when: Air bubbles visible, after maintenance, baseline noisy",
            "category": "pump",
            "keywords": ["cleanup", "pump", "remove", "bubbles"],
            "priority": "high"
        },
        r"pump.*flush|flush.*pump|flush.*system": {
            "answer": "**Pump Flush:**\n\n"
            "**Purpose:** Rapid system flush (faster than prime)\n\n"
            "**Steps:**\n"
            "1. Flow tab → Click 'Flush'\n"
            "2. Homes pumps first (safety)\n"
            "3. Runs 2-3 rapid cycles\n"
            "4. Takes ~1 minute\n\n"
            "**When to use:**\n"
            "✅ Quick flush between samples\n"
            "✅ Change buffer type\n"
            "✅ Remove residual sample\n\n"
            "**Not for:**\n"
            "❌ Removing air bubbles (use Cleanup)\n"
            "❌ First startup (use Prime)",
            "category": "pump",
            "keywords": ["pump", "flush", "system"],
            "priority": "medium"
        },
        r"pump.*home|home.*pump|initialize.*pump": {
            "answer": "**Home Pumps (AffiPump):**\n\n"
            "**Purpose:** Return syringe plungers to zero position\n\n"
            "**Steps:**\n"
            "1. Flow tab → Click 'Home Pumps'\n"
            "2. Both KC1 and KC2 plungers retract\n"
            "3. Takes ~10-20 seconds\n\n"
            "**When to home:**\n"
            "✅ Before pump operations (auto-done)\n"
            "✅ After errors or blockages\n"
            "✅ System initialization\n"
            "✅ Before switching samples\n\n"
            "**Safety:** Pumps auto-home if blockage detected",
            "category": "pump",
            "keywords": ["pump", "home", "initialize"],
            "priority": "medium"
        },
        r"pump.*blocked|blockage|pump.*error": {
            "answer": "**Pump Blockage Detection:**\n\n"
            "**How it works:**\n"
            "• Monitors completion time for KC1 and KC2\n"
            "• If time difference > 1.5 sec → blockage detected\n"
            "• Reports which pump is blocked\n"
            "• Auto-homes plungers and aborts\n\n"
            "**If pump blocked:**\n"
            "1. ⚠️ **Don't force it!**\n"
            "2. Check tubing for kinks/clogs\n"
            "3. Verify valve positions\n"
            "4. Remove blockage source\n"
            "5. Click 'Home Pumps'\n"
            "6. Run 'Prime Pump' to test\n\n"
            "**Common causes:**\n"
            "• Kinked tubing\n"
            "• Clogged filter\n"
            "• Closed valve\n"
            "• Empty reservoir",
            "category": "pump",
            "keywords": ["pump", "blocked", "blockage", "error"],
            "priority": "high"
        },
        r"30.*second.*injection|contact.*time|timed.*injection": {
            "answer": "**30-Second Contact Time Injection:**\n\n"
            "**Purpose:** Precise timed sample delivery\n\n"
            "**Workflow:**\n"
            "1. Start pump at desired flow rate\n"
            "2. Click '30s Inject' button\n"
            "3. Valve opens (sample flows to sensor)\n"
            "4. Wait 30 seconds (contact time)\n"
            "5. Valve auto-closes (buffer continues)\n\n"
            "**Valve Sync:**\n"
            "• Sync OFF: Only KC1 valve opens\n"
            "• Sync ON: Both KC1 & KC2 open\n\n"
            "**Use for:**\n"
            "✅ Kinetic binding measurements\n"
            "✅ Association phase timing\n"
            "✅ Reproducible sample delivery\n\n"
            "📍 Location: Flow tab → Inject section",
            "category": "pump",
            "keywords": ["30", "second", "injection", "contact", "time"],
            "priority": "medium"
        },
        r"valve.*control|6.*port.*valve|3.*way.*valve": {
            "answer": "**Valve System:**\n\n"
            "**1. 6-Port Valves (KC1 & KC2)**\n"
            "• Function: Sample injection control\n"
            "• Positions:\n"
            "  - LOAD (0): Sample loop isolated\n"
            "  - INJECT (1): Sample flows to sensor\n"
            "• Use: Volume-based injections\n\n"
            "**2. 3-Way Valves (KC1 & KC2)**\n"
            "• Function: Channel routing\n"
            "• Positions:\n"
            "  - CLOSED (0): KC1→A, KC2→C\n"
            "  - OPEN (1): KC1→B, KC2→D\n"
            "• Use: Multi-channel experiments\n\n"
            "**Auto-Control:**\n"
            "• Valves open/close automatically during operations\n"
            "• Manual control in Advanced mode\n"
            "• Safety timeout prevents stuck-open valves",
            "category": "pump",
            "keywords": ["valve", "control", "6", "port", "3", "way"],
            "priority": "medium"
        },
        r"channel.*routing|channel.*a.*b.*c.*d|sensor.*channels": {
            "answer": "**Channel Routing with 3-Way Valves:**\n\n"
            "**4 Sensor Channels Available:**\n\n"
            "**KC1 (Pump 1):**\n"
            "• 3-way CLOSED → Channel A (reference)\n"
            "• 3-way OPEN → Channel B (sample)\n\n"
            "**KC2 (Pump 2):**\n"
            "• 3-way CLOSED → Channel C (reference)\n"
            "• 3-way OPEN → Channel D (sample)\n\n"
            "**Typical Setup:**\n"
            "• Channel A: Buffer reference (KC1)\n"
            "• Channel B: Sample 1 (KC1)\n"
            "• Channel C: Buffer reference (KC2)\n"
            "• Channel D: Sample 2 (KC2)\n\n"
            "✅ Enables parallel experiments\n"
            "✅ Reference-corrected measurements",
            "category": "pump",
            "keywords": ["channel", "routing", "a", "b", "c", "d"],
            "priority": "medium"
        },
        r"flow.*rate|set.*flow|pump.*speed": {
            "answer": "**Setting Flow Rate:**\n\n"
            "**AffiPump (Syringe):**\n"
            "• Range: 0.001 - 24,000 µL/min\n"
            "• Typical: 50-200 µL/min for experiments\n"
            "• Set in Flow tab → Flow rate spinbox\n"
            "• Precision: ±1% accuracy\n\n"
            "**P4PROPLUS (Peristaltic):**\n"
            "• Range: 5 - 220 RPM\n"
            "• Set in Flow tab → RPM spinbox\n"
            "• Live updates: Change RPM while running\n"
            "• Correction factor: Compensates for tubing wear\n\n"
            "**Recommendations:**\n"
            "• Binding studies: 50-100 µL/min\n"
            "• Washing: 200-500 µL/min\n"
            "• Priming: 1000-5000 µL/min",
            "category": "pump",
            "keywords": ["flow", "rate", "set", "speed"],
            "priority": "medium"
        },
        r"rpm.*correction|pump.*correction|correction.*factor": {
            "answer": "**RPM Correction Factor (P4PROPLUS):**\n\n"
            "**Purpose:** Compensate for tubing wear/calibration drift\n\n"
            "**How it works:**\n"
            "```\n"
            "Actual RPM = Base RPM × Correction Factor\n"
            "```\n\n"
            "**Example:**\n"
            "• Base RPM: 100\n"
            "• Correction: 1.05\n"
            "• Actual RPM sent: 105\n\n"
            "**When to adjust:**\n"
            "• Flow rate seems too slow → Increase factor (1.05)\n"
            "• Flow rate seems too fast → Decrease factor (0.95)\n"
            "• After tubing replacement → Reset to 1.00\n\n"
            "**Default:** 1.00 (no correction)\n"
            "**Range:** 0.50 - 2.00\n\n"
            "📍 Location: Flow tab → Correction spinbox",
            "category": "pump",
            "keywords": ["rpm", "correction", "factor"],
            "priority": "low"
        },
        r"pump.*emergency.*stop|emergency.*stop|stop.*pump": {
            "answer": "**Emergency Pump Stop:**\n\n"
            "**How to stop:**\n"
            "1. Click red 'Emergency Stop' button\n"
            "2. OR click regular 'Stop' button\n"
            "3. All pumps halt immediately\n\n"
            "**What happens:**\n"
            "✅ All pumps stop\n"
            "✅ Valves remain in current position\n"
            "✅ Flow rate settings preserved\n"
            "✅ Safe to restart after checking system\n\n"
            "**When to use:**\n"
            "• Leak detected\n"
            "• Air bubble entering sensor\n"
            "• Abnormal noise/vibration\n"
            "• System malfunction\n\n"
            "**After emergency stop:**\n"
            "1. Check for issues (leaks, blockages)\n"
            "2. Fix problem\n"
            "3. Run 'Prime Pump' to resume",
            "category": "pump",
            "keywords": ["pump", "emergency", "stop"],
            "priority": "high"
        },
        r"pump.*troubleshoot|pump.*not.*working|pump.*issue": {
            "answer": "**Pump Troubleshooting:**\n\n"
            "**Pump won't start:**\n"
            "• Check hardware connection (Device Status)\n"
            "• Verify COM port (AffiPump: COM8)\n"
            "• Try 'Home Pumps' first\n"
            "• Restart software if needed\n\n"
            "**No flow detected:**\n"
            "• Check tubing connections\n"
            "• Verify valves opening (check LED/status)\n"
            "• Run 'Prime Pump' to establish flow\n"
            "• Check for air bubbles (run 'Cleanup')\n\n"
            "**Erratic flow:**\n"
            "• Air bubbles → Run 'Cleanup'\n"
            "• Kinked tubing → Straighten\n"
            "• Empty reservoir → Refill\n"
            "• Adjust correction factor (peristaltic)\n\n"
            "**Blockage error:**\n"
            "• Check tubing for kinks/clogs\n"
            "• Verify valve positions\n"
            "• Run 'Home Pumps'\n"
            "• Clear blockage, then 'Prime Pump'",
            "category": "pump",
            "keywords": ["pump", "troubleshoot", "not", "working", "issue"],
            "priority": "high"
        },
        r"pump.*best.*practice|pump.*maintenance": {
            "answer": "**Pump Best Practices:**\n\n"
            "**Daily Routine:**\n"
            "✅ Prime pumps at start of day\n"
            "✅ Check for air bubbles in tubing\n"
            "✅ Verify flow is smooth and consistent\n"
            "✅ Run cleanup if bubbles present\n\n"
            "**After Each Experiment:**\n"
            "✅ Flush with buffer (remove sample)\n"
            "✅ Return valves to LOAD position\n"
            "✅ Stop pumps when not in use\n\n"
            "**Weekly Maintenance:**\n"
            "✅ Check tubing for wear/cracks\n"
            "✅ Clean pump heads (peristaltic)\n"
            "✅ Verify valve operation\n"
            "✅ Test with water (no samples)\n\n"
            "**Storage:**\n"
            "✅ Store in buffer or 20% ethanol\n"
            "✅ Never leave empty (cavitation risk)\n"
            "✅ Home pumps before shutdown",
            "category": "pump",
            "keywords": ["pump", "best", "practice", "maintenance"],
            "priority": "medium"
        },
    },

    "method": {
        r"create.*cycle|new.*cycle|build.*cycle": {
            "answer": "**How to Build a Method:**\n\n"
            "1. Click **+ Build Method** in the sidebar\n"
            "2. Type cycle lines in the Note field (one per line)\n"
            "3. Click **➕ Add to Method** — cycles appear in the table\n"
            "4. Reorder with ↑/↓, delete with 🗑, undo/redo as needed\n"
            "5. Click **📋 Push to Queue** — cycles move to the Cycle Queue\n"
            "6. Press **▶ Start Run** — cycles execute automatically in order\n\n"
            "**Cycle syntax:** `Type Duration [Channel:Concentration]`\n"
            "Example: `Concentration 5min [A:100nM] contact 180s`\n\n"
            "**Cycle types:** Baseline, Concentration, Regeneration, Immobilization, Wash, Other\n\n"
            "💡 Type `build 5` for quick 5-concentration series, or `@spark amine coupling` for a full method template.",
            "category": "method",
            "keywords": ["create", "cycle", "new", "build", "method", "how"],
            "priority": "high"
        },
        r"how.*build.*method|how.*make.*method|how.*create.*method|method.*builder|build.*method": {
            "answer": "**Building a Method — Step by Step:**\n\n"
            "1. Click **+ Build Method** in the sidebar to open the Method Builder\n"
            "2. In the **Note** field, type your cycles (one per line):\n"
            "   `Baseline 5min`\n"
            "   `Concentration 5min [A:100nM] contact 180s`\n"
            "   `Regeneration 30sec [ALL:50mM]`\n"
            "3. Click **➕ Add to Method** to add them to the method table\n"
            "4. Use ↑/↓ buttons to reorder, 🗑 to delete\n"
            "5. Click **📋 Push to Queue** to send to the main Cycle Queue\n"
            "6. Press **▶ Start Run** to execute\n\n"
            "**Quick shortcuts:**\n"
            "• `build 5` → generates 5 concentration cycles automatically\n"
            "• `@spark amine coupling` → full coupling + titration method\n"
            "• `!save my_method` → save method as preset for reuse\n"
            "• `@my_method` → load a saved preset\n\n"
            "After the last cycle, the system enters **Auto-Read** mode (2 hours of continuous monitoring).",
            "category": "method",
            "keywords": ["build", "method", "how", "create", "make"],
            "priority": "high"
        },
        r"cycle.*type|what.*types|available.*types|type.*cycle": {
            "answer": "**6 Cycle Types:**\n\n"
            "| Type | Injection | Contact Time | Purpose |\n"
            "|------|-----------|-------------|--------|\n"
            "| **Baseline** | None | — | Running buffer, establish stable signal |\n"
            "| **Concentration** | Simple (or partial) | User-specified | Inject analyte, measure binding |\n"
            "| **Regeneration** | Simple | 30s (auto) | Strip bound analyte, restore baseline |\n"
            "| **Immobilization** | Simple | User-specified | Attach ligand to sensor surface |\n"
            "| **Wash** | Simple | User-specified | Rinse flow path between steps |\n"
            "| **Other** | None | — | Custom (activation, blocking, etc.) |\n\n"
            "All injections start at **20 seconds** into the cycle.\n"
            "Regeneration auto-sets 30s contact time. All others require `contact Ns` if injection is needed.",
            "category": "method",
            "keywords": ["cycle", "types", "available", "what"],
            "priority": "high"
        },
        r"cycle.*syntax|how.*write.*cycle|note.*syntax|note.*format|how.*type.*cycle": {
            "answer": "**Cycle Syntax:**\n"
            "`Type Duration [Channel:ValueUnits] contact Ns partial injection`\n\n"
            "**Parts:**\n"
            "• **Type** (required): Baseline, Concentration, Regeneration, Immobilization, Wash, Other\n"
            "• **Duration** (required): `5min`, `30sec`, `2m`, `30s`\n"
            "• **[Tags]** (optional): `[A]`, `[ALL:100nM]`, `[B:50µM]`\n"
            "• **contact Ns** (optional): injection contact time, e.g. `contact 180s` or `contact 3min`\n"
            "• **partial injection** (optional): use 30µL partial loop injection for Concentration\n\n"
            "**Units:** nM, µM, pM, mM, M, mg/mL, µg/mL, ng/mL\n"
            "**Channels:** A, B, C, D, ALL\n\n"
            "**Examples:**\n"
            "• `Baseline 5min`\n"
            "• `Concentration 5min [A:100nM] contact 180s`\n"
            "• `Regeneration 30sec [ALL:50mM]`\n"
            "• `Immobilization 4min [A:50µg/mL] contact 180s`\n"
            "• `Concentration 5min [A:100nM] contact 120s partial injection`",
            "category": "method",
            "keywords": ["syntax", "write", "cycle", "note", "format", "type"],
            "priority": "high"
        },
        r"what.*contact.*time|contact.*time|injection.*time": {
            "answer": "**Contact Time** is how long the sample stays in the flow cell after injection.\n\n"
            "• Specified with `contact Ns` (e.g. `contact 180s` or `contact 3min`)\n"
            "• **Baseline** and **Other**: No injection, no contact time\n"
            "• **Concentration**: User must specify (e.g. `contact 120s` or `contact 180s`)\n"
            "• **Immobilization**: User must specify (e.g. `contact 180s`)\n"
            "• **Wash**: User must specify (e.g. `contact 30s`)\n"
            "• **Regeneration**: Auto-set to **30 seconds** (no need to specify)\n\n"
            "All injections begin at **20 seconds** into the cycle (fixed delay).\n\n"
            "Example: `Concentration 5min [A:100nM] contact 180s`",
            "category": "method",
            "keywords": ["contact", "time", "injection"],
            "priority": "medium"
        },
        r"what.*injection|injection.*method|simple.*inject|partial.*inject|how.*inject": {
            "answer": "**Injection Methods:**\n\n"
            "• **Simple injection** (default): Full sample loop injection via valve switching\n"
            "• **Partial injection**: 30µL spike — add `partial injection` to the cycle line\n\n"
            "**Which types auto-inject?**\n"
            "• Concentration → simple (or partial if specified)\n"
            "• Immobilization → simple\n"
            "• Wash → simple\n"
            "• Regeneration → simple (30s contact auto-set)\n"
            "• Baseline → no injection\n"
            "• Other → no injection\n\n"
            "All injections start at **20 seconds** into the cycle.\n\n"
            "Example: `Concentration 5min [A:100nM] contact 120s partial injection`",
            "category": "method",
            "keywords": ["injection", "simple", "partial", "inject", "method"],
            "priority": "medium"
        },
        r"save.*method|save.*preset|preset|load.*preset|reuse.*method": {
            "answer": "**Save & Load Method Presets:**\n\n"
            "**Save:** Build your method in the table, then type:\n"
            "`!save my_method_name`\n"
            "and click Add to Method.\n\n"
            "**Load:** Type `@my_method_name` and click ⚡ Spark.\n"
            "The saved cycles will load directly into the method table.\n\n"
            "This lets you reuse common protocols without retyping them.",
            "category": "method",
            "keywords": ["save", "preset", "load", "reuse", "method"],
            "priority": "medium"
        },
        r"what.*auto.*read|auto.*read|after.*queue|after.*last.*cycle": {
            "answer": "**Auto-Read Mode:**\n\n"
            "After the last cycle in your queue finishes, the system automatically starts a **2-hour Auto-Read** cycle.\n\n"
            "This provides continuous monitoring so you don't lose data if you step away. "
            "The sensorgram keeps recording and you can observe dissociation or baseline recovery.\n\n"
            "Auto-Read can be disabled in Settings if not needed.",
            "category": "method",
            "keywords": ["auto", "read", "after", "queue", "last", "cycle"],
            "priority": "medium"
        },
        r"next.*cycle|skip.*cycle|advance.*cycle": {
            "answer": "**Next Cycle / Skip:**\n\n"
            "Press the **⏭ Next Cycle** button to end the current cycle early and immediately start the next one.\n\n"
            "• Data from the current cycle is **preserved** (even if the cycle was shortened)\n"
            "• The next cycle in the queue starts after a brief 0.5s delay\n"
            "• If no cycles remain, Auto-Read starts automatically\n\n"
            "💡 The intelligence bar shows a countdown and previews the next cycle type in the last 10 seconds.",
            "category": "method",
            "keywords": ["next", "cycle", "skip", "advance"],
            "priority": "medium"
        },
        r"edit.*cycle|modify.*cycle": {
            "answer": "To edit cycle data:\n1. Complete your run and stop acquisition\n2. Go to 'Edits' tab\n3. Load your saved Excel file\n4. Click on any cycle in the table\n5. Use the 'Cycle Details & Editing' panel to adjust boundaries and settings",
            "category": "method",
            "keywords": ["edit", "cycle", "modify"],
            "priority": "medium"
        },
        r"method.*example|example.*method|show.*example|sample.*method": {
            "answer": "**Example Methods:**\n\n"
            "**Simple Binding:**\n"
            "```\n"
            "Baseline 5min\n"
            "Concentration 5min [A:100nM] contact 180s\n"
            "Regeneration 30sec [ALL:50mM]\n"
            "```\n\n"
            "**Kinetics (Association + Dissociation):**\n"
            "```\n"
            "Baseline 2min\n"
            "Concentration 5min [A:100nM] contact 120s\n"
            "Baseline 10min\n"
            "Regeneration 30sec [ALL:50mM]\n"
            "```\n\n"
            "**Dose-Response Titration:**\n"
            "```\n"
            "Baseline 5min\n"
            "Concentration 5min [A:10nM] contact 120s\n"
            "Concentration 5min [A:50nM] contact 120s\n"
            "Concentration 5min [A:100nM] contact 120s\n"
            "Concentration 5min [A:500nM] contact 120s\n"
            "Regeneration 30sec [ALL:50mM]\n"
            "```\n\n"
            "💡 Or type `build 5` for quick auto-generated series, or `@spark amine coupling` for full protocols.",
            "category": "method",
            "keywords": ["example", "method", "sample", "show"],
            "priority": "medium"
        },
    },

    "analysis": {
        r"baseline.*drift|baseline.*unstable": {
            "answer": "For baseline drift issues:\n1. Allow 30-60 min warmup time\n2. Ensure temperature is stable\n3. Check for bubbles in flow cell\n4. Verify flow rate is consistent\n5. Consider capturing a new baseline in Settings tab\n6. Use baseline correction in Analysis tab",
            "category": "analysis",
            "keywords": ["baseline", "drift", "unstable"],
            "priority": "medium"
        },
    },

    "general": {
        r"keyboard.*shortcuts|hotkeys": {
            "answer": "Useful keyboard shortcuts:\n• Ctrl+S: Stop acquisition\n• Ctrl+E: Export data\n• Ctrl+Z: Undo (in Method builder)\n• Ctrl+Shift+Z: Redo\n• F5: Refresh detector connection",
            "category": "general",
            "keywords": ["keyboard", "shortcuts", "hotkeys"],
            "priority": "low"
        },
    },
}


def get_all_patterns():
    """Get flattened list of all pattern dicts."""
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
