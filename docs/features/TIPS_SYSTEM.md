# Tips System — FRS

## Overview

Short, ≤140-character tips are shown to users at startup inside the calibration dialog.
Tips are tag-filtered so only relevant content appears based on connected hardware.

**Current placement:** Startup calibration dialog (pre-calibration phase only).
**Future placements:** Spark proactive messages, sidebar ticker (not yet implemented).

---

## Architecture

```
data/spark/tips.json
    ↓ (loaded at dialog init)
affilabs/services/spark/tips_manager.py  →  TipsManager.get_tip_text(tags)
    ↓
affilabs/dialogs/startup_calib_dialog.py  →  tip_card QFrame + _tip_label QLabel
```

- Tips file is loaded once per `TipsManager` instance
- Random selection within matching tags each call — no rotation state persisted
- Tips are non-critical; all exceptions are silently swallowed so startup is never blocked

---

## Data Format — `data/spark/tips.json`

```json
{
  "version": 1,
  "tips": [
    {
      "id": "tip_001",
      "text": "Tip text here — max 140 characters.",
      "tags": ["general", "science"],
      "source": "science"
    }
  ]
}
```

### Fields

| Field | Type | Description |
|-------|------|-------------|
| `id` | str | Unique identifier. Never reuse or renumber. |
| `text` | str | Tip text. Max 140 characters. Active voice. No jargon. |
| `tags` | list[str] | Used for filtering — see Tag Vocabulary below. |
| `source` | str | `"science"`, `"device"`, `"software"` — for future category display. |

---

## Tag Vocabulary

| Tag | When shown |
|-----|------------|
| `general` | All devices and contexts — used as fallback |
| `p4spr` | P4SPR manual injection instrument only |
| `p4pro` | P4PRO automated flow instrument only |
| `p4proplus` | P4PROPLUS internal pump instrument only |
| `hardware` | Physical device handling tips |
| `chip` | Sensor chip care and insertion |
| `science` | SPR physics / signal interpretation |
| `calibration` | Calibration procedure tips |
| `software` | App features, shortcuts, Spark commands |
| `injection` | Injection technique tips |

---

## Filtering Logic (`TipsManager.get_tip`)

1. Filter to tips where **any tip tag** is in the requested tag set.
2. If no match: fall back to tips tagged `"general"`.
3. If still empty: pick from the full list.
4. Within the filtered set: **random selection** (session-fresh, no persistence).

---

## Startup Dialog Integration

**File:** `affilabs/dialogs/startup_calib_dialog.py`

**Visibility rules:**
- **Shown:** Pre-calibration phase (checklist visible, before Start is clicked).
- **Hidden:** When `show_progress_bar()` is called (calibration running).
- **Never shown:** In error state.

**Device-specific tips:** Call `dialog.set_tip_tags(["p4spr", "general"])` after hardware
is detected (e.g., in the hardware-connected callback) to reload with device-specific tags.

---

## Writing Tips — Guidelines

1. **≤140 characters** — count carefully including spaces.
2. **Active voice.** "Compress your chip before first use" not "The chip should be compressed."
3. **One idea per tip.** No compound tips with "and also...".
4. **No jargon** (FWHM, SNR, evanescent field) unless it's explained in the same tip.
5. **Specific over generic.** "Push the syringe slowly" beats "Be careful during injection."
6. **No emoji** in tip text unless it meaningfully aids comprehension.

## Adding New Tips

1. Open `data/spark/tips.json`.
2. Append a new entry with the next sequential `id` (`tip_016`, `tip_017`, …).
3. Write the text (≤140 chars).
4. Assign appropriate tags from the vocabulary above.
5. Set `source` to `"science"`, `"device"`, or `"software"`.

No code changes needed — `TipsManager` reads the file at runtime.

---

## Future Placements (not implemented)

- **Spark proactive messages:** `SparkHelpWidget` pushes a tip as a system message when the
  user has been idle for 30+ seconds in the Method Builder or Edits tab.
- **Sidebar ticker:** A rotating `QLabel` strip at the bottom of the Spark sidebar, cycling
  tips every 45 seconds during acquisition.
