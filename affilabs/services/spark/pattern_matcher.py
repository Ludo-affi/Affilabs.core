"""Spark Pattern Matcher - Fast Response System

Provides instant pattern-based answers for common questions.
This is the first layer in Spark's hybrid answering approach.

Now uses patterns from patterns.py (single source of truth).
Performance: Pre-compiles all regex patterns for O(1) lookup.
"""

import re
import logging
from typing import Optional
from .patterns import get_all_patterns

logger = logging.getLogger(__name__)


class SparkPatternMatcher:
    """Pattern-based question matching for instant responses."""

    def __init__(self):
        """Initialize pattern matcher with pre-compiled patterns.
        
        Pre-compiles all regex patterns once for fast matching.
        """
        # Load patterns from centralized patterns.py
        raw_patterns = get_all_patterns()
        
        # Pre-compile all regex patterns for faster matching
        self.patterns = {}
        self._compiled_patterns = []
        
        for pattern_regex, pattern_data in raw_patterns.items():
            try:
                compiled = re.compile(pattern_regex, re.IGNORECASE | re.DOTALL)
                self.patterns[compiled] = pattern_data
                self._compiled_patterns.append((compiled, pattern_data))
            except re.error as e:
                logger.warning(f"Invalid regex pattern '{pattern_regex}': {e}")
                # Keep uncompiled fallback
                self.patterns[pattern_regex] = pattern_data

    def match_question(self, question: str) -> Optional[str]:
        """Try to match question against known patterns.
        
        Uses pre-compiled patterns for O(n) matching where n = number of patterns.
        Typical: <1ms for 50+ patterns.

        Args:
            question: User's question text

        Returns:
            Answer string if pattern matched, None otherwise
        """
        if not question or not question.strip():
            return None
            
        try:
            # Try pre-compiled patterns first (faster)
            for compiled_pattern, pattern_data in self._compiled_patterns:
                try:
                    if compiled_pattern.search(question):
                        logger.debug(f"Pattern matched")
                        return pattern_data.get("answer", "")
                except Exception as e:
                    logger.debug(f"Pattern matching error: {e}")
                    continue

            return None
        except Exception as e:
            logger.error(f"Pattern matcher crashed: {e}")
            return None

    def get_all_topics(self) -> list[str]:
        """Get list of all supported pattern categories.

        Returns:
            List of unique categories from all patterns
        """
        try:
            categories = set()
            for _, pattern_data in self._compiled_patterns:
                categories.add(pattern_data.get("category", "general"))
            return sorted(list(categories))
        except Exception as e:
            logger.error(f"Failed to get topics: {e}")
            return []
