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
        """Initialize answer engine with pattern matcher, knowledge base, and AI model."""
        self.pattern_matcher = SparkPatternMatcher()
        self.knowledge_base = SparkKnowledgeBase()
        self.ai_model = SparkTinyLM()

    def generate_answer(self, question: str) -> Tuple[str, bool]:
        """Generate answer using 3-layer hybrid approach.

        Layer 1: Pattern matching (instant, deterministic)
        Layer 2: Knowledge base search (fast, website content)
        Layer 3: AI model (slower, flexible)

        Args:
            question: User's question text

        Returns:
            Tuple of (answer, matched) where:
                - answer: The generated answer text
                - matched: True if pattern/KB matched, False if AI-generated
        """
        if not question or not question.strip():
            return ("Please ask a question about using Affilabs.core.", False)

        # Layer 1: Try pattern matching (instant responses)
        pattern_answer = self.pattern_matcher.match_question(question)
        if pattern_answer:
            logger.debug("Answer generated via pattern matching (Layer 1)")
            return (pattern_answer, True)

        # Layer 2: Search knowledge base (website content)
        try:
            kb_results = self.knowledge_base.search(question, max_results=1)
            if kb_results and len(kb_results) > 0:
                # Use KB result if relevance score is good (> 2.0)
                top_result = kb_results[0]
                if top_result.get("score", 0) > 2.0:
                    logger.debug(f"Answer generated via knowledge base (Layer 2), score: {top_result['score']}")
                    # Format KB answer with source attribution
                    answer = top_result.get("content", "")
                    url = top_result.get("url", "")
                    if url:
                        answer += f"\n\n📚 Source: {url}"
                    return (answer, True)
        except Exception as e:
            logger.warning(f"Knowledge base search error: {e}")

        # Layer 3: Use AI model (fallback for complex questions)
        logger.debug("No pattern/KB match - using AI model (Layer 3)")
        try:
            ai_answer, success = self.ai_model.generate_answer(question)
            return (ai_answer, success)
        except Exception as e:
            logger.exception(f"AI model error: {e}")
            return (
                "Sorry, I encountered an error generating an answer. "
                "Please try rephrasing your question or contact support.",
                False
            )

    def get_supported_topics(self) -> list[str]:
        """Get list of topics with instant pattern-based answers.

        Returns:
            List of topic names
        """
        return self.pattern_matcher.get_all_topics()
