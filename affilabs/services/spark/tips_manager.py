"""
TipsManager — loads tips.json and returns a random tip filtered by device/context tags.

Usage:
    tips = TipsManager("data/spark/tips.json")
    text = tips.get_tip_text(tags=["p4spr", "general"])
"""

from __future__ import annotations

import json
import random
from pathlib import Path


_DEFAULT_TIPS_PATH = "data/spark/tips.json"


class TipsManager:
    """Load and serve tips from a JSON data file, filtered by tags."""

    def __init__(self, tips_path: str | Path | None = None) -> None:
        self._tips: list[dict] = []

        if tips_path is None:
            try:
                from affilabs.utils.resource_path import get_resource_path
                tips_path = get_resource_path(_DEFAULT_TIPS_PATH)
            except Exception:
                tips_path = Path(_DEFAULT_TIPS_PATH)

        path = Path(tips_path)
        if path.exists():
            try:
                with open(path, encoding="utf-8") as f:
                    data = json.load(f)
                self._tips = data.get("tips", [])
            except Exception:
                self._tips = []

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_tip(self, tags: list[str] | None = None) -> dict | None:
        """Return one random tip whose tag list overlaps with *tags*.

        Filtering logic:
        1. If *tags* is given, return a random tip where any tip tag is in *tags*.
        2. If no match, fall back to tips tagged ``"general"``.
        3. If still empty, pick from the full list.
        4. Returns ``None`` if no tips are loaded at all.
        """
        if not self._tips:
            return None

        if tags:
            tag_set = set(tags)
            filtered = [t for t in self._tips if tag_set.intersection(t.get("tags", []))]
            if filtered:
                return random.choice(filtered)

            # Fallback: general tips only
            general = [t for t in self._tips if "general" in t.get("tags", [])]
            if general:
                return random.choice(general)

        # Last resort: any tip
        return random.choice(self._tips)

    def get_tip_text(self, tags: list[str] | None = None) -> str:
        """Convenience wrapper — returns the tip text string, or empty string."""
        tip = self.get_tip(tags=tags)
        return tip["text"] if tip else ""

    def get_shuffled_texts(self, tags: list[str] | None = None, min_count: int = 8) -> list[str]:
        """Return a shuffled list of tip texts for rotation use cases (e.g. calib dialog).

        Filters by tags (same rules as get_tip), then returns all matching texts shuffled.
        If fewer than *min_count* match, pads with general tips (then all tips) until
        *min_count* is reached or the pool is exhausted.
        """
        if not self._tips:
            return []

        tag_set = set(tags) if tags else set()

        if tag_set:
            matched = [t for t in self._tips if tag_set.intersection(t.get("tags", []))]
        else:
            matched = list(self._tips)

        # Pad with general tips if short
        if len(matched) < min_count:
            general = [t for t in self._tips if "general" in t.get("tags", []) and t not in matched]
            matched = matched + general

        # Pad with everything else if still short
        if len(matched) < min_count:
            rest = [t for t in self._tips if t not in matched]
            matched = matched + rest

        random.shuffle(matched)
        return [t["text"] for t in matched]
