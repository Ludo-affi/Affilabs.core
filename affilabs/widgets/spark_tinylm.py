"""REMOVED: SparkTinyLM was removed (caused 30+ second UI freezes on CPU).

Spark now uses 2-layer pattern matching + knowledge base only.
Import SparkAnswerEngine instead:

    from affilabs.services.spark import SparkAnswerEngine
"""

# SparkTinyLM no longer exists — stub to prevent import errors from old code
class SparkTinyLM:
    def __init__(self): pass
    def is_initialized(self): return False
    def generate_answer(self, _question): return ("", False)

__all__ = ['SparkTinyLM']
