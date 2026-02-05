"""
Spark AI Service - Internal service for AI-powered help system

This package provides the core functionality for the Spark AI assistant,
including pattern matching, knowledge base search, and AI model integration.

Components:
- answer_engine.py: Main coordinator for answer generation
- pattern_matcher.py: Fast regex-based pattern matching
- knowledge_base.py: TinyDB-based knowledge storage and search
- tinylm.py: TinyLlama AI model integration
- patterns.py: Pattern definitions (single source of truth)

Usage:
    from affilabs.services.spark import SparkAnswerEngine

    engine = SparkAnswerEngine()
    answer, matched = engine.generate_answer("How do I calibrate?")
"""

from .answer_engine import SparkAnswerEngine
from .pattern_matcher import SparkPatternMatcher
from .knowledge_base import SparkKnowledgeBase
from .tinylm import SparkTinyLM

__all__ = [
    'SparkAnswerEngine',
    'SparkPatternMatcher',
    'SparkKnowledgeBase',
    'SparkTinyLM',
]
