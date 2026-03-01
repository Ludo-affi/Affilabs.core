# User Profiles — Functional Requirements Specification

**Source:** `affilabs/widgets/user_panel_popup.py` (501 lines), `affilabs/services/user_profile_manager.py` (609 lines), `user_profiles.json`
**Version:** 2.0.5.1 | **Date:** 2026-03-01

---

## 1. Purpose

Multi-user profile system with experience tracking, guidance leveling, and per-user hint dismissal. Users are lab members who share the same instrument — the profile tracks who ran which experiment and adapts UI guidance to skill level.

---

## 2. Architecture

```
UserSidebarPanel (UI)  →  UserProfileManager (service)  →  user_profiles.json (persistence)
```

---

## 3. Data Schema (`user_profiles.json`)

```json
{
  "users": ["Default User", "Sandy"],
  "current_user": "Sandy",
  "user_data": {
    "<username>": {
      "experiment_count": 44,
      "compression_training": { "completed": false, "score": null, "date": null },
      "last_used": "2026-03-01T12:00:00Z",
      "hints_shown": { "hint_connect_shown": true, "hint_calibrate_shown": true },
      "created_date": "2025-10-01T00:00:00Z"
    }
  }
}
```

**Storage path:** `get_writable_data_path("user_profiles.json")`

---

## 4. Experience Level System (UserTitle Enum)

| Level | XP Threshold | Value |
|-------|-------------|-------|
| Novice | 0 | `"Novice"` |
| Operator | 5 | `"Operator"` |
| Specialist | 20 | `"Specialist"` |
| Expert | 50 | `"Expert"` |
| Master | 100 | `"Master"` |

XP increments by 1 per completed experiment (via `increment_experiment_count()`).

---

## 5. Guidance Levels

`get_guidance_level(username)` returns one of:

| Level | Criteria | UI Behavior |
|-------|----------|-------------|
| `"beginner"` | Novice or Operator | Full hints, more hand-holding |
| `"intermediate"` | Specialist | Moderate hints |
| `"advanced"` | Expert or Master | Minimal hints |

Used by `GuidanceCoordinator` to decide which hints to show.

---

## 6. UserProfileManager — Key Methods

### 6.1 CRUD

| Method | Purpose |
|--------|---------|
| `get_profiles()` | List of usernames |
| `get_current_user()` | Active username |
| `set_current_user(username)` | Switch active, fires `on_user_changed` callback |
| `add_user(username)` | Create with initialized data |
| `remove_user(username)` | Delete (must keep ≥ 1) |
| `rename_user(old, new)` | Rename, transfer all data |

### 6.2 Experience

| Method | Purpose |
|--------|---------|
| `get_title(username)` | Returns `(UserTitle, exp_count)` |
| `get_experiment_count(username)` | XP count |
| `increment_experiment_count(username=None)` | +1 XP (defaults to current user) |
| `set_experiment_count(username, count)` | Set absolute XP |
| `get_progression_summary(username)` | Title, XP, next title, compression training |

### 6.3 Guidance & Hints

| Method | Purpose |
|--------|---------|
| `get_guidance_level(username=None)` | beginner / intermediate / advanced |
| `is_hint_shown(hint_key, username=None)` | Check hint dismissal |
| `mark_hint_shown(hint_key, username=None)` | Record hint shown |
| `needs_compression_training(username)` | Training completion check |

### 6.4 Metadata

| Method | Purpose |
|--------|---------|
| `get_user_for_metadata()` | User info dict for Excel export headers |

---

## 7. UserSidebarPanel — UI Widget

**`UserSidebarPanel(QFrame)`** — Fixed-width (380 px) sidebar panel, accessed via Icon Rail user icon.

**Legacy alias:** `UserPanelPopup = UserSidebarPanel`

### UI Layout

1. **Header**: "Lab Users"
2. **Current user banner**: name + title + XP count
3. **Members list**: `QListWidget` (double-click to activate)
4. **Add User** button
5. **Rename + Set Active** button row
6. **Delete** button
7. **Experience Levels** guide card (5-tier table)

### Key Methods

| Method | Purpose |
|--------|---------|
| `set_user_manager(manager)` | Inject `UserProfileManager` reference |
| `toggle()` | Show/hide panel, returns visibility |
| `show_and_refresh()` | Legacy compat |
| `_on_add()` | `QInputDialog` → `manager.add_user()` |
| `_on_rename()` | `QInputDialog` → `manager.rename_user()` |
| `_on_set_active()` | `manager.set_current_user()` |
| `_on_delete()` | Confirm dialog → `manager.remove_user()` |

### Communication

No Qt Signals — communicates entirely through `_user_manager` reference. Panel refreshes itself after each action.
