# Queue Manager — Functional Requirements Specification

**Source:** `affilabs/managers/queue_manager.py` (564 lines)
**Version:** 2.0.5.1 | **Date:** 2026-03-01

---

## 1. Purpose

Centralized cycle queue with signal notifications. Manages the ordered list of `Cycle` objects to be executed, supports mid-run appending, locking semantics, method snapshots, and state serialization.

---

## 2. Class

**`QueueManager(QObject)`**

### 2.1 Qt Signals

| Signal | Payload | Purpose |
|--------|---------|---------|
| `queue_changed` | — | General state change (emitted on nearly all operations) |
| `cycle_added` | `Cycle` | New cycle added |
| `cycle_deleted` | `(int, Cycle)` | Cycle removed (index, object) |
| `cycle_reordered` | `(int, int)` | Cycle moved (from_idx, to_idx) |
| `queue_locked` | — | Queue locked for execution |
| `queue_unlocked` | — | Queue unlocked |

### 2.2 Internal State

| Field | Type | Purpose |
|-------|------|---------|
| `_queue` | `List[Cycle]` | Live queue |
| `_completed` | `List[Cycle]` | Completed cycles history |
| `_cycle_counter` | `int` | Auto-incrementing ID generator |
| `_lock` | `bool` | Lock flag |
| `_original_method` | `List[Cycle]` | Deep copy snapshot at run start |
| `_method_progress` | `int` | Completed count in current run |

---

## 3. Queue Operations

| Method | Blocked When Locked? | Purpose |
|--------|---------------------|---------|
| `add_cycle(cycle)` | **No** — always allowed | Assigns ID, appends. Mid-run: also deep-copies into `_original_method` |
| `delete_cycle(index)` | **Yes** | Removes by index |
| `delete_cycles(indices)` | **Yes** | Bulk delete (reverse-sorted) |
| `reorder_cycle(from_idx, to_idx)` | **Yes** | Move cycle position |
| `clear_queue()` | **Yes** | Removes all + clears method snapshot |
| `pop_next_cycle()` | No | FIFO pop — does NOT renumber remaining cycles |

---

## 4. Locking Semantics

| State | `add` | `delete` | `reorder` | `clear` |
|-------|-------|----------|-----------|---------|
| Unlocked | ✅ | ✅ | ✅ | ✅ |
| Locked | ✅ | ❌ | ❌ | ❌ |

**Mid-run append:** When `_lock=True` and `_original_method` is non-empty, `add_cycle()` deep-copies the new cycle into `_original_method` so the execution loop picks it up after pending cycles finish.

---

## 5. Method Snapshot System

Used during method execution to preserve the original queue state.

| Method | Purpose |
|--------|---------|
| `snapshot_method()` | Deep copies `_queue` → `_original_method`, resets progress |
| `advance_method_progress()` | Increments `_method_progress`, emits `queue_changed` |
| `get_original_method()` | Returns copy of immutable snapshot |
| `get_method_progress()` | Completed count in run |
| `get_remaining_from_method()` | Shallow list of remaining cycles |
| `clear_method_snapshot()` | Clears snapshot and progress |
| `has_method_snapshot()` | Check if snapshot exists |

---

## 6. Completed Cycles

| Method | Purpose |
|--------|---------|
| `mark_completed(cycle)` | Adds to `_completed` list |
| `get_completed_cycles()` | Returns copy |
| `clear_completed()` | Clears history |
| `get_completed_count()` | Count |

---

## 7. Access Methods

| Method | Purpose |
|--------|---------|
| `get_queue_snapshot()` | Safe copy of queue |
| `get_cycle_at(index)` | Peek by index |
| `peek_next_cycle()` | Peek first without removing |
| `get_queue_size()` | Queue length |
| `is_empty()` | Empty check |
| `get_total_duration()` | Sum of all `length_minutes` |
| `find_cycle_by_id(cycle_id)` | Search by permanent ID across queue + completed |

---

## 8. Persistence

| Method | Purpose |
|--------|---------|
| `get_state()` | Serializes queue + completed + counter via `Cycle.to_dict()` |
| `restore_state(state)` | Deserializes via `Cycle.from_dict()`, ensures counter ≥ max existing ID |

---

## 9. Dual ID System

| ID | Type | Behavior |
|----|------|----------|
| `cycle_id` | Permanent | Auto-incremented, never reused, survives reorder/delete |
| `cycle_num` | Display | Changes on reorder — `_renumber_cycles()` updates display names to "Cycle N" |

---

## 10. Validation

`_validate_cycle(cycle)` returns a list of warning strings (non-blocking):
- Duration checks
- Contact time checks
- Unit mismatch checks

---

## 11. Domain Object

`Cycle` from `affilabs.domain.cycle` — contains all cycle parameters (name, duration, contact time, flow rate, channels, etc.). Supports `to_dict()` / `from_dict()` for serialization.
