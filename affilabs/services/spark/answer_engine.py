"""Spark Answer Engine - Core Answer Generation Logic

Coordinates between pattern matching and AI for generating answers.
This is the brain of Spark's answering system.
"""

import logging
from typing import Tuple

from .pattern_matcher import SparkPatternMatcher
from .knowledge_base import SparkKnowledgeBase
from .tinylm import SparkTinyLM

logger = logging.getLogger(__name__)


class SparkAnswerEngine:
    """Core answer generation engine using 3-layer hybrid approach."""

    def __init__(self):
        """Initialize answer engine with pattern matcher and knowledge base. AI model loads lazily."""
        self.pattern_matcher = SparkPatternMatcher()
        self.knowledge_base = SparkKnowledgeBase()
        self.ai_model = None  # Lazy loading - only initialize when needed

    def generate_answer(self, question: str) -> Tuple[str, bool]:
        """Generate answer using 3-layer hybrid approach.

        Layer 1: Pattern matching (instant, deterministic, <1ms)
        Layer 2: Knowledge base search (fast, website content, <50ms)
        Layer 3: AI model (slower, flexible, 1-5 seconds)

        Args:
            question: User's question text

        Returns:
            Tuple of (answer, matched) where:
                - answer: The generated answer text
                - matched: True if pattern/KB matched, False if AI-generated
        """
        # Validate input
        if not question or not question.strip():
            return ("What would you like to know about Affilabs?", False)

        try:
            # Layer 1: Try pattern matching (instant responses, <1ms)
            try:
                pattern_answer = self.pattern_matcher.match_question(question)
                if pattern_answer:
                    logger.debug("Answer generated via pattern matching (Layer 1)")
                    return (pattern_answer, True)
            except Exception as e:
                logger.warning(f"Pattern matching error (continuing to Layer 2): {e}")

            # Layer 2: Search knowledge base (website content, <50ms)
            try:
                kb_results = self.knowledge_base.search(question, max_results=3)
                if kb_results and len(kb_results) > 0:
                    # Filter out verbose training documentation - only return user-friendly content
                    for result in kb_results:
                        title = result.get("title", "")
                        content = result.get("content", "")

                        # Skip verbose training documentation
                        if any(skip_phrase in title.lower() for skip_phrase in [
                            "training summary", "knowledge training", "spark ai -", "calibration knowledge training"
                        ]):
                            continue

                        # Skip content that looks like training documentation
                        if any(skip_phrase in content.lower() for skip_phrase in [
                            "what was done", "technical implementation", "pattern matching (fast path)",
                            "training type:", "knowledge domain:", "added ** new", "patterns to spark"
                        ]):
                            continue

                        # Use this result if relevance score is good (> 1.5)
                        if result.get("score", 0) > 1.5:
                            logger.debug(f"Answer generated via knowledge base (Layer 2), score: {result['score']}")
                            # Format KB answer with source attribution
                            answer = content.strip()
                            url = result.get("url", "")
                            if url and url != "https://www.affiniteinstruments.com/":
                                answer += f"\n\n📚 Source: {url}"
                            return (answer, True)
            except Exception as e:
                logger.warning(f"Knowledge base search error (continuing to Layer 3): {e}")

            # Layer 3: Use AI model (fallback for complex questions) - Lazy loading
            logger.debug("No pattern/KB match - using AI model (Layer 3)")
            try:
                # Initialize AI model only when needed (lazy loading)
                if self.ai_model is None:
                    self.ai_model = SparkTinyLM()

                ai_answer, success = self.ai_model.generate_answer(question)
                return (ai_answer, success)
            except Exception as e:
                logger.exception(f"AI model error: {e}")
                return (
                    "I'm not sure about that one yet. Try asking about setup, calibration, "
                    "methods, pumps, data export, or troubleshooting.\n\n"
                    "For anything else, reach out to support at info@affiniteinstruments.com.",
                    False
                )

        except Exception as e:
            logger.error(f"Answer engine crashed: {e}")
            return (
                "Sorry, I had a problem. Please try again or contact support.",
                False
            )

    def get_supported_topics(self) -> list[str]:
        """Get list of topics with instant pattern-based answers.

        Returns:
            List of topic names
        """
        return self.pattern_matcher.get_all_topics()
