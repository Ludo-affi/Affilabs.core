"""Quick test of trained Spark AI knowledge base"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from affilabs.services.spark.knowledge_base import SparkKnowledgeBase

def main():
    kb = SparkKnowledgeBase()

    print("=" * 70)
    print("SPARK AI KNOWLEDGE BASE TEST")
    print("=" * 70)

    # Show stats
    stats = kb.get_stats()
    print(f"\nKnowledge Base Status:")
    print(f"  Total Articles: {stats['total_articles']}")
    print(f"  Total FAQs: {stats['total_faqs']}")
    print(f"  Categories: {', '.join(stats['categories'])}")

    # Test queries
    test_queries = [
        "How do I do manual injection?",
        "What is a binding cycle?",
        "How to prime the pump?",
        "How to calibrate detector?",
    ]

    print("\n" + "=" * 70)
    print("TESTING SEARCH FUNCTIONALITY")
    print("=" * 70)

    for query in test_queries:
        print(f"\n📝 Query: '{query}'")
        print("-" * 70)

        results = kb.search(query, max_results=2)

        if results:
            for i, result in enumerate(results, 1):
                print(f"\n  ✓ Result {i} (score: {result['score']:.1f}):")
                print(f"    Title: {result['title']}")
                print(f"    Category: {result.get('category', 'N/A')}")
                print(f"    Preview: {result['content'][:150]}...")
        else:
            print("  ⚠ No results found")

    print("\n" + "=" * 70)
    print("✓ Spark AI is ready to answer questions!")
    print("=" * 70)

if __name__ == "__main__":
    main()
