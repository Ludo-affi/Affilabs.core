"""
Test suite for Spark AI Help System

Tests all components of the refactored Spark architecture:
- SparkPatternMatcher: Pattern-based instant answers
- SparkAnswerEngine: Hybrid answer coordination
- SparkTinyLM: AI model integration
- SparkQuestionStorage: Database operations
"""

import unittest
from datetime import datetime
from pathlib import Path
import tempfile
import shutil

# Import Spark components
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from affilabs.widgets.spark_pattern_matcher import SparkPatternMatcher
from affilabs.widgets.spark_answer_engine import SparkAnswerEngine


class TestSparkPatternMatcher(unittest.TestCase):
    """Test pattern matching functionality."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.matcher = SparkPatternMatcher()
    
    def test_match_start_acquisition(self):
        """Test matching start acquisition questions."""
        questions = [
            "How do I start an acquisition?",
            "how to start recording",
            "begin acquisition",
            "start data collection",
        ]
        for q in questions:
            answer = self.matcher.match_question(q)
            self.assertIsNotNone(answer, f"Failed to match: {q}")
            self.assertIn("Start Recording", answer)
    
    def test_match_export_data(self):
        """Test matching export questions."""
        questions = [
            "How do I export data?",
            "save data to file",
            "export to Excel",
            "download results",
        ]
        for q in questions:
            answer = self.matcher.match_question(q)
            self.assertIsNotNone(answer, f"Failed to match: {q}")
            self.assertIn("Export", answer)
    
    def test_match_calibration(self):
        """Test matching calibration questions."""
        questions = [
            "How do I calibrate the detector?",
            "calibration procedure",
            "run calibration",
            "OEM LED calibration",
        ]
        for q in questions:
            answer = self.matcher.match_question(q)
            self.assertIsNotNone(answer, f"Failed to match: {q}")
            self.assertIn("OEM LED Calibration", answer)
    
    def test_no_match(self):
        """Test questions that shouldn't match."""
        questions = [
            "What is the meaning of life?",
            "Tell me about quantum physics",
            "Random unrelated question",
        ]
        for q in questions:
            answer = self.matcher.match_question(q)
            self.assertIsNone(answer, f"Incorrectly matched: {q}")
    
    def test_get_all_topics(self):
        """Test getting all supported topics."""
        topics = self.matcher.get_all_topics()
        self.assertIsInstance(topics, list)
        self.assertGreater(len(topics), 0)
        self.assertIn("Starting acquisitions", topics)
        self.assertIn("Exporting data", topics)
        self.assertIn("Detector calibration", topics)
    
    def test_case_insensitive(self):
        """Test that matching is case-insensitive."""
        q1 = "how do i start an ACQUISITION?"
        q2 = "HOW DO I START AN acquisition?"
        q3 = "How Do I Start An Acquisition?"
        
        answer1 = self.matcher.match_question(q1)
        answer2 = self.matcher.match_question(q2)
        answer3 = self.matcher.match_question(q3)
        
        self.assertEqual(answer1, answer2)
        self.assertEqual(answer2, answer3)
    
    def test_partial_keywords(self):
        """Test matching with partial keywords."""
        questions = [
            "acquiring data",  # Should match "acquisition"
            "calibrating",     # Should match "calibrate"
            "exported files",  # Should match "export"
        ]
        for q in questions:
            answer = self.matcher.match_question(q)
            self.assertIsNotNone(answer, f"Failed to match partial keyword: {q}")


class TestSparkAnswerEngine(unittest.TestCase):
    """Test answer engine coordination."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.engine = SparkAnswerEngine()
    
    def test_pattern_match_path(self):
        """Test fast path (pattern matching)."""
        question = "How do I start an acquisition?"
        answer, matched = self.engine.generate_answer(question)
        
        self.assertTrue(matched, "Should match pattern")
        self.assertIsInstance(answer, str)
        self.assertGreater(len(answer), 0)
        self.assertIn("Start Recording", answer)
    
    def test_ai_fallback_path(self):
        """Test AI fallback for unmatched questions."""
        question = "What are the benefits of SPR technology?"
        answer, matched = self.engine.generate_answer(question)
        
        # May or may not match depending on AI model availability
        self.assertIsInstance(answer, str)
        self.assertGreater(len(answer), 0)
    
    def test_get_supported_topics(self):
        """Test getting supported topics."""
        topics = self.engine.get_supported_topics()
        self.assertIsInstance(topics, list)
        self.assertGreater(len(topics), 0)
    
    def test_empty_question(self):
        """Test handling of empty questions."""
        answer, matched = self.engine.generate_answer("")
        self.assertFalse(matched)
        self.assertIn("instant answers", answer.lower())
    
    def test_whitespace_question(self):
        """Test handling of whitespace-only questions."""
        answer, matched = self.engine.generate_answer("   \n  \t  ")
        self.assertFalse(matched)


class TestSparkIntegration(unittest.TestCase):
    """Integration tests for the complete Spark system."""
    
    def test_common_questions_workflow(self):
        """Test answering common questions end-to-end."""
        engine = SparkAnswerEngine()
        
        # Test a variety of common questions
        test_cases = [
            ("How do I start recording?", True),
            ("How to export data?", True),
            ("Calibrate detector", True),
            ("Build a method", True),
            ("Control flow rate", True),
            ("Adjust graph settings", True),
        ]
        
        for question, should_match in test_cases:
            answer, matched = engine.generate_answer(question)
            self.assertEqual(matched, should_match, 
                           f"Question: {question}, Expected match: {should_match}, Got: {matched}")
            self.assertIsInstance(answer, str)
            self.assertGreater(len(answer), 10)
    
    def test_performance(self):
        """Test that pattern matching is fast."""
        import time
        
        matcher = SparkPatternMatcher()
        question = "How do I start an acquisition?"
        
        # Warm up
        matcher.match_question(question)
        
        # Time 100 matches
        start = time.time()
        for _ in range(100):
            matcher.match_question(question)
        elapsed = time.time() - start
        
        # Should be very fast (< 10ms for 100 matches)
        self.assertLess(elapsed, 0.01, 
                       f"Pattern matching too slow: {elapsed*1000:.2f}ms for 100 matches")


class TestSparkQuestionStorage(unittest.TestCase):
    """Test database operations (requires SparkQuestionStorage from spark_help_widget)."""
    
    def setUp(self):
        """Set up test database."""
        # Import here to avoid circular dependencies
        from affilabs.widgets.spark_help_widget import SparkQuestionStorage
        
        # Create temporary database
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = Path(self.temp_dir) / "test_qa.json"
        
        # Monkey patch the DB path for testing
        import affilabs.widgets.spark_help_widget as shw
        original_path = shw.Path.cwd
        shw.Path.cwd = lambda: Path(self.temp_dir)
        
        self.storage = SparkQuestionStorage()
        
        # Restore original path method
        shw.Path.cwd = original_path
    
    def tearDown(self):
        """Clean up test database."""
        if hasattr(self, 'temp_dir'):
            shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_log_question(self):
        """Test logging questions."""
        doc_id = self.storage.log_question(
            "Test question",
            "Test answer",
            matched=True
        )
        self.assertIsNotNone(doc_id)
        self.assertIsInstance(doc_id, int)
    
    def test_update_feedback(self):
        """Test updating feedback."""
        doc_id = self.storage.log_question("Q", "A", True)
        result = self.storage.update_feedback(doc_id, "helpful")
        self.assertTrue(result)
    
    def test_get_all_questions(self):
        """Test retrieving all questions."""
        # Log some questions
        self.storage.log_question("Q1", "A1", True)
        self.storage.log_question("Q2", "A2", False)
        
        questions = self.storage.get_all_questions()
        self.assertIsInstance(questions, list)
        self.assertGreaterEqual(len(questions), 2)
    
    def test_get_unmatched_questions(self):
        """Test retrieving unmatched questions."""
        self.storage.log_question("Q1", "A1", matched=True)
        self.storage.log_question("Q2", "A2", matched=False)
        
        unmatched = self.storage.get_unmatched_questions()
        self.assertIsInstance(unmatched, list)
        self.assertGreaterEqual(len(unmatched), 1)
        
        # All should be unmatched
        for q in unmatched:
            self.assertFalse(q.get('matched', True))


def run_tests():
    """Run all Spark tests."""
    # Create test suite
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # Add all test classes
    suite.addTests(loader.loadTestsFromTestCase(TestSparkPatternMatcher))
    suite.addTests(loader.loadTestsFromTestCase(TestSparkAnswerEngine))
    suite.addTests(loader.loadTestsFromTestCase(TestSparkIntegration))
    suite.addTests(loader.loadTestsFromTestCase(TestSparkQuestionStorage))
    
    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # Print summary
    print("\n" + "=" * 70)
    print(f"Tests run: {result.testsRun}")
    print(f"Successes: {result.testsRun - len(result.failures) - len(result.errors)}")
    print(f"Failures: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")
    print("=" * 70)
    
    return result.wasSuccessful()


if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)
