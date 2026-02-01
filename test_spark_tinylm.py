"""Test script for Spark TinyLM integration

Tests the hybrid approach: regex patterns (fast) + TinyLM (conversational)
"""

import sys
import logging

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Test imports
try:
    from affilabs.widgets.spark_tinylm import SparkTinyLM
    print("✓ SparkTinyLM imported successfully")
except ImportError as e:
    print(f"✗ Failed to import SparkTinyLM: {e}")
    print("\n⚠️  TinyLM dependencies not installed")
    print("   Install with: pip install transformers torch")
    sys.exit(1)

# Test questions
test_questions = [
    # Should match regex patterns (fast path)
    "How do I start an acquisition?",
    "How do I export data?",
    "How do I calibrate?",
    
    # Should trigger TinyLM (conversational path)
    "What's the difference between association and dissociation?",
    "Can you explain how to optimize flow rates?",
    "What should I do if my baseline is unstable?",
]

print("\n" + "="*80)
print("TESTING SPARK TINYLM INTEGRATION")
print("="*80)

# Create TinyLM instance
spark = SparkTinyLM()
print(f"\nTinyLM initialized: {spark.is_initialized()}")
print("(Model will lazy load on first conversational question)\n")

# Test each question
for i, question in enumerate(test_questions, 1):
    print(f"\n--- Test {i}/{len(test_questions)} ---")
    print(f"Question: {question}")
    
    # Generate answer
    answer, success = spark.generate_answer(question)
    
    print(f"\nAnswer ({len(answer)} chars):")
    print(answer)
    print(f"\nSuccess: {success}")
    print(f"Model loaded: {spark.is_initialized()}")
    
    if i < len(test_questions):
        input("\nPress Enter to continue...")

print("\n" + "="*80)
print("✓ TESTING COMPLETE")
print("="*80)

# Summary
print("\n🎯 HYBRID SPARK SUMMARY:")
print("  • Fast path: Regex patterns for common questions (<1ms)")
print("  • Conversational path: TinyLM for complex questions (1-3s)")
print("  • Model size: 637 MB (loads on first use)")
print("  • Focused context: SPR/ezControl operations only")
print("\n💡 USAGE:")
print("  • Users ask questions naturally in Spark chat")
print("  • Common questions answered instantly (regex)")
print("  • Complex questions handled by TinyLM")
print("  • All Q&A logged for improvement")
