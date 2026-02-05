"""Spark Pattern Matcher - Fast Response System

Provides instant pattern-based answers for common questions.
This is the first layer in Spark's hybrid answering approach.

Now uses patterns from patterns.py (single source of truth).
"""

import re
import logging
from typing import Optional
from .patterns import get_all_patterns

logger = logging.getLogger(__name__)


class SparkPatternMatcher:
    """Pattern-based question matching for instant responses."""

    def __init__(self):
        """Initialize pattern matcher with patterns from patterns.py."""
        # Load patterns from centralized patterns.py
        self.patterns = get_all_patterns()

    def match_question(self, question: str) -> Optional[str]:
        """Try to match question against known patterns.

        Args:
            question: User's question text

        Returns:
            Answer string if pattern matched, None otherwise
        """
        question_lower = question.lower()

        # Try each pattern (regex keys from patterns.py)
        for pattern_regex, pattern_data in self.patterns.items():
            if re.search(pattern_regex, question_lower):
                logger.debug(f"Pattern matched: {pattern_regex}")
                return pattern_data["answer"]

        return None

    def get_all_topics(self) -> list[str]:
        """Get list of all supported pattern categories.

        Returns:
            List of unique categories from all patterns
        """
        categories = set()
        for pattern_data in self.patterns.values():
            categories.add(pattern_data.get("category", "general"))
        return sorted(list(categories))
