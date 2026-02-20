"""
Spark AI Service - Internal service for AI-powered help system

2-layer hybrid: pattern matching (instant) + knowledge base (curated).
TinyLM removed — caused 30+ second UI freezes on CPU.

Components:
- answer_engine.py: Main coordinator for answer generation
- pattern_matcher.py: Fast regex-based pattern matching
- knowledge_base.py: TinyDB-based knowledge storage and search
- patterns.py: Pattern definitions (single source of truth)

Usage:
    from affilabs.services.spark import SparkAnswerEngine

    engine = SparkAnswerEngine()
    answer, matched = engine.generate_answer("How do I calibrate?")
"""

from .answer_engine import SparkAnswerEngine
from .pattern_matcher import SparkPatternMatcher
from .knowledge_base import SparkKnowledgeBase

__all__ = [
    'SparkAnswerEngine',
    'SparkPatternMatcher',
    'SparkKnowledgeBase',
]
