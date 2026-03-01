# EXPERIMENT_INDEX_FRS — Experiment Index & Search

**Feature:** `ExperimentIndex` service  
**Planned source:** `affilabs/services/experiment_index.py`  
**Write trigger:** `RecordingManager.stop_recording()` (file-mode only)  
**Index file:** `~/Documents/Affilabs Data/experiment_index.json`  
**Status:** Implemented (v2.0.5)
**Version:** Affilabs.core v2.0.5+

---

## 1. Problem

Recording files are named `Live_Data_20260223_143215.xlsx`. There is no way to find an experiment by chip, user, date range, or keyword without opening every file. This spec defines a write-once, search-always index that solves this.

---

## 2. Index File Location & Format

```
~/Documents/Affilabs Data/experiment_index.json
```

Written by `ExperimentIndex.append_entry()` using append-to-JSON-array logic (no full rewrite; atomic write via temp file + rename).

### Schema

```json
{
  "schema_version": 1,
  "entries": [
    {
      "id": "20260223T143215_lucia",
      "date": "2026-02-23",
      "time": "14:32:15",
      "user": "lucia",
      "file": "lucia/SPR_data/Live_Data_20260223_143215.xlsx",
      "chip_serial": "FLMT09788",
      "hardware_model": "P4PRO",
      "duration_min": 47.2,
      "cycle_count": 8,
      "notes": ""
    }
  ]
}
```

### Field sources

| Field | Source |
|---|---|
| `id` | `{YYYYMMDDTHHMMSS}_{username}` — unique per session |
| `date` / `time` | `recording_start_time` from `RecordingManager` |
| `user` | `user_manager.get_current_user()` |
| `file` | Path relative to `~/Documents/Affilabs Data/` |
| `chip_serial` | `data_collector.metadata.get("detector_serial", "")` |
| `hardware_model` | `data_collector.metadata.get("hardware_model", "")` |
| `duration_min` | `(stop_time - start_time) / 60`, rounded to 1 decimal |
| `cycle_count` | `len(data_collector.cycles)` |
| `notes` | `""` at write time; user can edit via future UI |

---

## 3. Write Behaviour

### Trigger
`ExperimentIndex.append_entry()` is called from `RecordingManager.stop_recording()`, **only when `self.current_file` is not None** (file-mode recording). Memory-only recordings are not indexed.

### Atomic write
1. Load existing `experiment_index.json` (or create `{"schema_version": 1, "entries": []}` if missing).
2. Append the new entry dict to `entries`.
3. Write to `experiment_index.json.tmp` in the same directory.
4. `os.replace()` temp → final (atomic on Windows NTFS).

### Handling corruption
If loading fails (corrupt JSON, disk error), the existing index is backed up to `experiment_index.json.bak` and a fresh index is started. Never silently drop the new entry.

### Failure mode
Index write errors are logged as `WARNING` and never raise to the caller. A failed index write must not interrupt the recording stop flow.

---

## 4. Search API

`ExperimentIndex` exposes a single search method. All filters are optional and ANDed.

```python
class ExperimentIndex:
    def __init__(self, index_path: Path | None = None): ...

    def append_entry(self, entry: dict) -> None: ...

    def search(
        self,
        user: str | None = None,
        chip_serial: str | None = None,
        date_from: str | None = None,   # "YYYY-MM-DD"
        date_to: str | None = None,     # "YYYY-MM-DD"
        keyword: str | None = None,     # substring match on notes + file
        hardware_model: str | None = None,
    ) -> list[dict]:
        """Return matching entries sorted newest-first."""
```

`keyword` matches case-insensitively against `notes` and `file` fields.

---

## 5. Integration Points

### `RecordingManager.stop_recording()`

Add at the point after final Excel save, before `recording_stopped.emit()`:

```python
# Write experiment index entry
if self.current_file:
    try:
        from affilabs.services.experiment_index import ExperimentIndex
        index = ExperimentIndex()
        base = Path.home() / "Documents" / "Affilabs Data"
        rel_file = Path(self.current_file).relative_to(base)
        duration_min = (time.time() - self._recording_start_ts) / 60
        username = self.user_manager.get_current_user() if self.user_manager else ""
        ts = datetime.now()
        index.append_entry({
            "id": f"{ts.strftime('%Y%m%dT%H%M%S')}_{username}",
            "date": ts.strftime("%Y-%m-%d"),
            "time": ts.strftime("%H:%M:%S"),
            "user": username,
            "file": str(rel_file),
            "chip_serial": self.data_collector.metadata.get("detector_serial", ""),
            "hardware_model": self.data_collector.metadata.get("hardware_model", ""),
            "duration_min": round(duration_min, 1),
            "cycle_count": len(self.data_collector.cycles),
            "notes": "",
        })
    except Exception as e:
        logger.warning(f"Failed to write experiment index: {e}")
```

### Future: Experiment Browser dialog

A searchable table dialog (`ExperimentBrowserDialog`) can call `ExperimentIndex().search(...)` and display results, with double-click opening the file in the OS default app. **Not in scope for this FRS.**

---

## 6. Out of Scope

- UI for editing `notes` field (future)
- Cloud sync of the index (notes the index is local-only, like `user_profiles.json`)
- Retroactive indexing of existing recordings (manual migration script, not app code)
- Deleting entries when files are deleted (entries become stale; file existence checked at display time)
