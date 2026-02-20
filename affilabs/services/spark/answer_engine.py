"""Spark Answer Engine - Core Answer Generation Logic

Coordinates between pattern matching and knowledge base for generating answers.
This is the brain of Spark's answering system.

Architecture: 2-layer hybrid (TinyLM removed — caused 30+ second UI freezes)
  Layer 1: Pattern matching (instant, deterministic, <1ms)
  Layer 2: Knowledge base search (fast, curated content, <50ms)
  Layer 3: Context-aware fallback (instant, topic-detected suggestions)
"""

import logging
from typing import Tuple

from .pattern_matcher import SparkPatternMatcher
from .knowledge_base import SparkKnowledgeBase

logger = logging.getLogger(__name__)


class SparkAnswerEngine:
    """Core answer generation engine using 2-layer hybrid approach."""

    def __init__(self):
        """Initialize answer engine with pattern matcher and knowledge base."""
        self.pattern_matcher = SparkPatternMatcher()
        self.knowledge_base = SparkKnowledgeBase()

    def generate_answer(self, question: str, context: str = "") -> Tuple[str, bool]:
        """Generate answer using 2-layer hybrid approach.

        Layer 1: Pattern matching (instant, deterministic, <1ms)
        Layer 2: Knowledge base search (fast, curated content, <50ms)
        Layer 3: Context-aware fallback suggestions (instant)

        Args:
            question: User's question text
            context: Optional context hint (e.g. "method_builder") for better fallbacks

        Returns:
            Tuple of (answer, matched) where:
                - answer: The generated answer text
                - matched: True if pattern/KB matched, False if fallback
        """
        if not question or not question.strip():
            return ("What would you like to know about Affilabs?", False)

        try:
            # Layer 1: Pattern matching (instant responses, <1ms)
            try:
                pattern_answer = self.pattern_matcher.match_question(question)
                if pattern_answer:
                    logger.debug("Answer via pattern matching (Layer 1)")
                    return (pattern_answer, True)
            except Exception as e:
                logger.warning(f"Pattern matching error (continuing to Layer 2): {e}")

            # Layer 2: Knowledge base search (<50ms)
            try:
                kb_results = self.knowledge_base.search(question, max_results=5)
                if kb_results:
                    for result in kb_results:
                        title = result.get("title", "")
                        content = result.get("content", "")
                        score = result.get("score", 0)

                        # Skip entries that are implementation notes, not user content
                        if any(phrase in title.lower() for phrase in [
                            "training summary", "knowledge training", "spark ai -",
                            "calibration knowledge training"
                        ]):
                            continue
                        if any(phrase in content.lower() for phrase in [
                            "what was done", "technical implementation",
                            "training type:", "knowledge domain:",
                        ]):
                            continue

                        # Lower threshold: score > 0.5 — KB articles are curated so trust them
                        if score > 0.5:
                            logger.debug(f"Answer via knowledge base (Layer 2), score: {score:.1f}, title: {title}")
                            answer = content.strip()
                            url = result.get("url", "")
                            if url and url != "https://www.affiniteinstruments.com/":
                                answer += f"\n\n📚 Source: {url}"
                            return (answer, True)
            except Exception as e:
                logger.warning(f"Knowledge base search error (continuing to Layer 3): {e}")

            # Layer 3: Context-aware fallback
            logger.debug("No pattern/KB match — generating context-aware fallback")
            return (self._context_fallback(question, context), False)

        except Exception as e:
            logger.error(f"Answer engine crashed: {e}")
            return ("Sorry, I had a problem. Please try again or contact support.", False)

    def _context_fallback(self, question: str, context: str) -> str:
        """Generate a context-aware fallback based on question keywords."""
        q = question.lower()

        # Method builder context — suggest relevant commands
        if context == "method_builder" or any(w in q for w in [
            "cycle", "method", "baseline", "binding", "kinetic", "regen",
            "immob", "wash", "contact", "concentration", "inject"
        ]):
            return (
                "I can help with method building. Try:\n\n"
                "• **Cycle syntax** — 'how do I write a binding cycle?'\n"
                "• **Cycle types** — 'what cycle types are available?'\n"
                "• **Templates** — type `@spark titration` or `@spark kinetics`\n"
                "• **Quick build** — type `build 5` to auto-generate 5 cycles\n"
                "• **Contact time** — 'what is contact time?'\n\n"
                "Or click **?** for full syntax docs."
            )

        if any(w in q for w in ["pump", "flow", "prime", "flush", "valve", "block"]):
            return (
                "For pump & flow questions, try:\n\n"
                "• **Priming** — 'how do I prime the pump?'\n"
                "• **Flow rate** — 'how do I set the flow rate?'\n"
                "• **Blockage** — 'pump is blocked'\n"
                "• **Cleanup** — 'how do I remove bubbles?'"
            )

        if any(w in q for w in ["calibrat", "qc", "led", "oem", "polarizer"]):
            return (
                "For calibration questions, try:\n\n"
                "• **Which calibration?** — 'which calibration should I use?'\n"
                "• **Failed** — 'calibration failed'\n"
                "• **Types** — 'what calibrations are available?'\n"
                "• **Startup** — 'startup calibration'"
            )

        if any(w in q for w in ["export", "save", "excel", "csv", "file"]):
            return (
                "For export questions, try:\n\n"
                "• 'how do I export data?'\n"
                "• 'how do I save results?'"
            )

        # Generic fallback
        return (
            "I'm not sure about that. Try asking about:\n\n"
            "• **Getting started** — 'how do I start an experiment?'\n"
            "• **Calibration** — 'how do I calibrate?'\n"
            "• **Method building** — 'how do I create cycles?'\n"
            "• **Flow control** — 'how do I use the pump?'\n"
            "• **Data export** — 'how do I export results?'\n\n"
            "You can also check the Help menu or contact support at info@affiniteinstruments.com."
        )

    def get_supported_topics(self) -> list[str]:
        """Get list of topics with instant pattern-based answers."""
        return self.pattern_matcher.get_all_topics()
