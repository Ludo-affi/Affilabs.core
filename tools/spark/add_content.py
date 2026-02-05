"""Add Content to Spark Knowledge Base

This script helps you add articles and FAQs to Spark's knowledge base.
Run this script to manually add website content that Spark can use to answer questions.

USAGE:
    python add_spark_content.py
"""

from affilabs.widgets.spark_knowledge_base import SparkKnowledgeBase

def add_sample_content():
    """Add sample content - replace with real website content."""
    kb = SparkKnowledgeBase()
    
    # Example: Add a detailed calibration guide
    kb.add_article(
        title="SPR Detector Calibration Guide",
        content=(
            "The SPR detector requires periodic calibration for optimal performance.\n\n"
            "**When to Calibrate:**\n"
            "• After instrument startup (daily)\n"
            "• When baseline appears unstable\n"
            "• After changing buffer conditions\n"
            "• Following maintenance procedures\n\n"
            "**Calibration Procedure:**\n"
            "1. Ensure stable flow (no bubbles)\n"
            "2. Navigate to Settings → OEM LED Calibration\n"
            "3. Click 'Start Calibration'\n"
            "4. Wait 30-60 seconds for completion\n"
            "5. Review calibration report\n"
            "6. Click 'Accept' if values are within range\n\n"
            "**Expected Values:**\n"
            "• Wavelength stability: < 0.01 nm RSD\n"
            "• Intensity variation: < 2%\n"
            "• Baseline drift: < 5 RU/min\n\n"
            "If calibration fails, check for air bubbles, verify flow rate, and ensure temperature stability."
        ),
        category="calibration",
        keywords=["calibrate", "calibration", "baseline", "detector", "OEM", "LED", "stability"],
        url="https://www.affiniteinstruments.com/"
    )
    
    # Example: Add a troubleshooting FAQ
    kb.add_faq(
        question="Why is my baseline noisy or unstable?",
        answer=(
            "Noisy or unstable baselines can have several causes:\n\n"
            "**Common Causes:**\n"
            "1. **Air bubbles** - Degas buffers, check tubing connections\n"
            "2. **Temperature fluctuations** - Allow 30min thermal equilibration\n"
            "3. **Flow rate issues** - Verify pump operation, check for blockages\n"
            "4. **Contaminated flow cell** - Run cleaning protocol\n"
            "5. **Poor calibration** - Recalibrate detector (Settings → OEM LED Calibration)\n\n"
            "**Quick Fixes:**\n"
            "• Prime system with fresh, degassed buffer\n"
            "• Reduce flow rate temporarily\n"
            "• Apply light smoothing filter (Graphic Display tab)\n"
            "• Run baseline capture after stabilization\n\n"
            "If noise persists after these steps, contact support."
        ),
        category="troubleshooting",
        url="https://www.affiniteinstruments.com/"
    )
    
    # Example: Add product information
    kb.add_article(
        title="Multi-Channel SPR Detection",
        content=(
            "Affinity Instruments SPR systems support simultaneous multi-channel detection "
            "for parallel sample analysis.\n\n"
            "**Available Configurations:**\n"
            "• 1-channel: Single detection spot\n"
            "• 2-channel: Dual detection (sample + reference)\n"
            "• 4-channel: Quad detection for throughput\n\n"
            "**Applications:**\n"
            "• Kinetic comparisons across samples\n"
            "• Reference-subtracted measurements\n"
            "• Concentration series screening\n"
            "• Multiplexed assays\n\n"
            "**Channel Selection in ezControl:**\n"
            "Use the Flow tab to route samples to specific channels. "
            "The valve selector (A/B/C/D) controls which channel receives flow. "
            "All active channels are displayed simultaneously on the sensorgram."
        ),
        category="product-features",
        keywords=["multi-channel", "channels", "parallel", "multiplexed", "valve", "flow"],
        url="https://www.affiniteinstruments.com/"
    )
    
    print("✓ Added sample content to knowledge base")
    print("\nKnowledge Base Stats:")
    stats = kb.get_stats()
    print(f"  Total Articles: {stats['total_articles']}")
    print(f"  Total FAQs: {stats['total_faqs']}")
    print(f"  Categories: {', '.join(stats['categories'])}")
    print("\n💡 Edit this script to add your own website content!")


def view_knowledge_base():
    """View current knowledge base contents."""
    kb = SparkKnowledgeBase()
    
    print("\n📚 CURRENT KNOWLEDGE BASE CONTENTS\n")
    print("=" * 60)
    
    print("\nARTICLES:")
    print("-" * 60)
    for article in kb.articles.all():
        print(f"\nTitle: {article['title']}")
        print(f"Category: {article['category']}")
        print(f"Keywords: {', '.join(article.get('keywords', []))}")
        print(f"URL: {article.get('url', 'N/A')}")
        print(f"Preview: {article['content'][:150]}...")
    
    print("\n\nFAQs:")
    print("-" * 60)
    for faq in kb.faqs.all():
        print(f"\nQ: {faq['question']}")
        print(f"Category: {faq['category']}")
        print(f"A: {faq['answer'][:150]}...")


def test_search():
    """Test knowledge base search."""
    kb = SparkKnowledgeBase()
    
    test_queries = [
        "how to calibrate",
        "noisy baseline",
        "multi-channel detection",
        "troubleshooting"
    ]
    
    print("\n🔍 TESTING KNOWLEDGE BASE SEARCH\n")
    print("=" * 60)
    
    for query in test_queries:
        print(f"\nQuery: '{query}'")
        results = kb.search(query, max_results=2)
        
        if results:
            for i, result in enumerate(results, 1):
                print(f"\n  Result {i} (score: {result['score']:.1f}):")
                print(f"    Title: {result['title']}")
                print(f"    Type: {result['type']}")
                print(f"    Preview: {result['content'][:100]}...")
        else:
            print("  No results found")


if __name__ == "__main__":
    import sys
    
    print("="*60)
    print("  SPARK KNOWLEDGE BASE CONTENT MANAGER")
    print("="*60)
    
    if len(sys.argv) > 1:
        command = sys.argv[1].lower()
        
        if command == "add":
            add_sample_content()
        elif command == "view":
            view_knowledge_base()
        elif command == "test":
            test_search()
        else:
            print(f"Unknown command: {command}")
            print("\nAvailable commands:")
            print("  python add_spark_content.py add   - Add sample content")
            print("  python add_spark_content.py view  - View current content")
            print("  python add_spark_content.py test  - Test search functionality")
    else:
        # Interactive mode
        print("\n1. Add sample content")
        print("2. View knowledge base")
        print("3. Test search")
        print("4. Exit")
        
        choice = input("\nChoose an option (1-4): ").strip()
        
        if choice == "1":
            add_sample_content()
        elif choice == "2":
            view_knowledge_base()
        elif choice == "3":
            test_search()
        elif choice == "4":
            print("Goodbye!")
        else:
            print("Invalid choice")
