"""Train Spark AI Knowledge Base from Markdown Documentation

This script loads all markdown documentation files from docs/spark/ and
adds them to Spark's knowledge base for intelligent Q&A.

USAGE:
    python tools/spark/train_from_markdown.py
"""

import sys
from pathlib import Path
import re

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from affilabs.services.spark.knowledge_base import SparkKnowledgeBase


def extract_metadata_from_markdown(content: str, filename: str) -> dict:
    """Extract metadata from markdown content.

    Args:
        content: Markdown file content
        filename: Source filename for fallback title

    Returns:
        dict with title, category, keywords
    """
    lines = content.split('\n')

    # Extract title (first # heading)
    title = filename.replace('.md', '').replace('_', ' ').title()
    for line in lines[:20]:
        if line.startswith('# '):
            title = line[2:].strip()
            break

    # Extract category from filename or content
    category = "general"
    filename_lower = filename.lower()

    if 'calibration' in filename_lower:
        category = "calibration"
    elif 'pump' in filename_lower or 'flow' in filename_lower:
        category = "pump-control"
    elif 'injection' in filename_lower or 'method' in filename_lower:
        category = "methods"
    elif 'troubleshoot' in filename_lower:
        category = "troubleshooting"

    # Extract keywords from content
    keywords = []

    # Look for common SPR/instrumentation terms
    keyword_patterns = [
        r'\b(calibration|calibrate)\b',
        r'\b(pump|flow|injection)\b',
        r'\b(baseline|association|dissociation)\b',
        r'\b(method|cycle|queue)\b',
        r'\b(sensor|detector|channel)\b',
        r'\b(SPR|spr|surface plasmon)\b',
        r'\b(regeneration|wash|clean)\b',
        r'\b(buffer|sample|analyte)\b',
        r'\b(P4SPR|AffiPump|P4PRO)\b',
        r'\b(manual|automated|auto)\b',
        r'\b(detection|detect|marker)\b',
        r'\b(confidence|threshold)\b',
    ]

    content_lower = content.lower()
    for pattern in keyword_patterns:
        matches = re.findall(pattern, content_lower, re.IGNORECASE)
        keywords.extend(set(m.lower() for m in matches))

    # Remove duplicates and common words
    keywords = list(set(keywords))
    keywords = [k for k in keywords if len(k) > 2]  # Remove very short keywords

    return {
        'title': title,
        'category': category,
        'keywords': keywords[:20]  # Limit to top 20
    }


def chunk_large_document(content: str, max_chunk_size: int = 8000) -> list:
    """Split large documents into smaller chunks for better retrieval.

    Args:
        content: Full document content
        max_chunk_size: Maximum characters per chunk

    Returns:
        List of content chunks
    """
    if len(content) <= max_chunk_size:
        return [content]

    chunks = []
    sections = re.split(r'\n## ', content)

    current_chunk = sections[0]  # Document header

    for section in sections[1:]:
        section = '## ' + section  # Re-add the ## heading

        # If adding this section would exceed limit, save current chunk
        if len(current_chunk) + len(section) > max_chunk_size:
            if current_chunk.strip():
                chunks.append(current_chunk)
            current_chunk = section
        else:
            current_chunk += '\n' + section

    # Add final chunk
    if current_chunk.strip():
        chunks.append(current_chunk)

    return chunks


def load_markdown_documents(docs_dir: Path) -> list:
    """Load all markdown files from a directory.

    Args:
        docs_dir: Directory containing .md files

    Returns:
        List of dicts with filename and content
    """
    documents = []

    for md_file in docs_dir.glob('*.md'):
        try:
            content = md_file.read_text(encoding='utf-8')
            documents.append({
                'filename': md_file.name,
                'filepath': str(md_file),
                'content': content
            })
            print(f"✓ Loaded {md_file.name} ({len(content)} chars)")
        except Exception as e:
            print(f"✗ Failed to load {md_file.name}: {e}")

    return documents


def train_knowledge_base(docs_dir: Path, clear_first: bool = False):
    """Train Spark knowledge base from markdown documentation.

    Args:
        docs_dir: Directory containing markdown files
        clear_first: If True, clear existing articles before adding new ones
    """
    print("\n" + "=" * 70)
    print("SPARK AI KNOWLEDGE BASE TRAINING")
    print("=" * 70)

    # Initialize knowledge base
    print("\n[1/4] Initializing knowledge base...")
    kb = SparkKnowledgeBase()

    # Optionally clear existing content
    if clear_first:
        print("\n[2/4] Clearing existing articles...")
        kb.articles.truncate()
        print("  ✓ Cleared all existing articles")
    else:
        print("\n[2/4] Keeping existing articles (appending new content)")

    # Load markdown documents
    print("\n[3/4] Loading markdown documentation...")
    documents = load_markdown_documents(docs_dir)

    if not documents:
        print(f"\n✗ No markdown files found in {docs_dir}")
        return

    print(f"\n  ✓ Found {len(documents)} markdown files")

    # Add documents to knowledge base
    print("\n[4/4] Adding documents to knowledge base...")

    total_articles = 0
    total_chunks = 0

    for doc in documents:
        filename = doc['filename']
        content = doc['content']

        # Extract metadata
        metadata = extract_metadata_from_markdown(content, filename)

        # Chunk large documents
        chunks = chunk_large_document(content, max_chunk_size=8000)

        # Add each chunk as a separate article
        for i, chunk in enumerate(chunks):
            if len(chunks) > 1:
                title = f"{metadata['title']} (Part {i+1}/{len(chunks)})"
            else:
                title = metadata['title']

            kb.add_article(
                title=title,
                content=chunk,
                category=metadata['category'],
                keywords=metadata['keywords'],
                url=f"docs/spark/{filename}"
            )

            total_chunks += 1

        total_articles += 1
        print(f"  ✓ {filename} → {len(chunks)} chunk(s)")

    # Show statistics
    print("\n" + "=" * 70)
    print("TRAINING COMPLETE!")
    print("=" * 70)

    stats = kb.get_stats()
    print(f"\nKnowledge Base Statistics:")
    print(f"  Documents processed: {total_articles}")
    print(f"  Total articles: {stats['total_articles']}")
    print(f"  Total chunks: {total_chunks}")
    print(f"  Total FAQs: {stats['total_faqs']}")
    print(f"  Categories: {', '.join(stats['categories'])}")

    print("\n✓ Spark AI is now trained on all documentation!")
    print("\nTest it with queries like:")
    print("  • 'How do I do manual injection?'")
    print("  • 'What pumps are supported?'")
    print("  • 'How to calibrate the detector?'")
    print("  • 'Explain binding cycles'")


def test_trained_kb():
    """Test the trained knowledge base with sample queries."""
    kb = SparkKnowledgeBase()

    print("\n" + "=" * 70)
    print("TESTING TRAINED KNOWLEDGE BASE")
    print("=" * 70)

    test_queries = [
        "How do I do manual injection?",
        "What is a binding cycle?",
        "How to prime the pump?",
        "Calibration procedures",
        "Injection not detected",
        "What cycle types are available?",
    ]

    for query in test_queries:
        print(f"\n📝 Query: {query}")
        print("-" * 70)

        results = kb.search(query, max_results=2)

        if results:
            for i, result in enumerate(results, 1):
                print(f"\n  Result {i} (score: {result['score']:.1f}):")
                print(f"    Title: {result['title']}")
                print(f"    Category: {result.get('category', 'N/A')}")
                print(f"    Source: {result.get('url', 'N/A')}")
                print(f"    Preview: {result['content'][:200]}...")
        else:
            print("  ⚠ No results found")


def main():
    """Main training workflow."""
    # Locate docs/spark directory
    script_dir = Path(__file__).parent
    project_root = script_dir.parent.parent
    docs_dir = project_root / "docs" / "spark"

    if not docs_dir.exists():
        print(f"✗ Documentation directory not found: {docs_dir}")
        print("  Please ensure docs/spark/ exists with .md files")
        return

    print(f"Training from: {docs_dir}")

    # Train knowledge base
    # clear_first=True will replace all existing articles
    # clear_first=False will append to existing articles
    train_knowledge_base(docs_dir, clear_first=True)

    # Test the trained knowledge base
    print("\n" + "=" * 70)
    response = input("Would you like to test the knowledge base? (y/n): ")
    if response.lower() == 'y':
        test_trained_kb()


if __name__ == "__main__":
    main()
