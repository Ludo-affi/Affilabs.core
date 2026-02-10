"""Spark Knowledge Base - Website content storage and retrieval

This module manages a searchable knowledge base of website content
that Spark can use to answer questions. Content can be manually added
or scraped from the Affinity Instruments website.

USAGE:
    kb = SparkKnowledgeBase()

    # Add content manually
    kb.add_article(
        title="How to Calibrate SPR Detector",
        content="Calibration steps...",
        category="calibration",
        url="https://www.affiniteinstruments.com/docs/calibration"
    )

    # Search for relevant content
    results = kb.search("calibration steps")
"""

from datetime import datetime
from pathlib import Path
import re
from typing import List, Dict
import logging

logger = logging.getLogger(__name__)


class SparkKnowledgeBase:
    """Searchable knowledge base for Spark AI help."""

    def __init__(self, db_path=None):
        """Initialize knowledge base.

        Args:
            db_path: Path to TinyDB database file. If None, uses default location
                    in affilabs/data/spark/knowledge_base.json
        """
        from tinydb import TinyDB

        if db_path is None:
            # Default to organized data location
            from affilabs.utils.resource_path import get_resource_path

            db_path = get_resource_path("data/spark/knowledge_base.json")
        self.db = TinyDB(str(db_path))
        self.articles = self.db.table("articles")
        self.faqs = self.db.table("faqs")

        # Initialize with default content if empty
        if len(self.articles) == 0:
            self._populate_default_content()

    def _populate_default_content(self):
        """Populate with initial default content."""
        logger.info("Initializing Spark knowledge base with default content")

        # Default articles structure - can be expanded later
        default_articles = [
            {
                "title": "Getting Started with Affilabs",
                "content": (
                    "Affilabs is Affinity Instruments' SPR data acquisition software. "
                    "To get started:\n\n"
                    "1. Connect your SPR instrument via USB\n"
                    "2. Launch Affilabs - it will auto-detect your device\n"
                    "3. Run OEM LED Calibration (Settings tab)\n"
                    "4. Start acquiring data using the Start Recording button\n\n"
                    "For detailed tutorials, visit the Support section on our website."
                ),
                "category": "getting-started",
                "keywords": ["start", "begin", "setup", "connect", "installation", "first time"],
                "url": "https://www.affiniteinstruments.com/",
                "last_updated": datetime.now().isoformat(),
            },
            {
                "title": "SPR Technology Overview",
                "content": (
                    "Surface Plasmon Resonance (SPR) is a label-free detection method "
                    "for measuring biomolecular interactions in real-time. "
                    "Affinity Instruments provides compact, user-friendly SPR systems "
                    "suitable for research and quality control applications.\n\n"
                    "Our instruments offer:\n"
                    "• Multi-channel detection (up to 4 channels)\n"
                    "• Real-time kinetic measurements\n"
                    "• Temperature control\n"
                    "• Integrated microfluidics\n\n"
                    "Learn more about SPR technology on our website."
                ),
                "category": "technology",
                "keywords": ["spr", "surface plasmon", "technology", "how it works", "principle"],
                "url": "https://www.affiniteinstruments.com/",
                "last_updated": datetime.now().isoformat(),
            },
            {
                "title": "Contact Support",
                "content": (
                    "For technical support, questions, or assistance:\n\n"
                    "• Email: info@affiniteinstruments.com\n"
                    "• Website: https://www.affiniteinstruments.com/\n"
                    "• Submit questions through our contact form\n\n"
                    "Our support team typically responds within 1 business day."
                ),
                "category": "support",
                "keywords": ["contact", "support", "help", "email", "phone", "assistance"],
                "url": "https://www.affiniteinstruments.com/",
                "last_updated": datetime.now().isoformat(),
            },
        ]

        for article in default_articles:
            self.articles.insert(article)

        logger.info(f"Added {len(default_articles)} default articles to knowledge base")

    def add_article(
        self, title: str, content: str, category: str, keywords: List[str] = None, url: str = None
    ) -> int:
        """Add an article to the knowledge base.

        Args:
            title: Article title
            content: Article content (can include markdown)
            category: Category (e.g., 'calibration', 'troubleshooting', 'tutorial')
            keywords: List of keywords for searching
            url: URL to the original content on website

        Returns:
            int: Database ID of inserted article
        """
        article = {
            "title": title,
            "content": content,
            "category": category,
            "keywords": keywords or [],
            "url": url or "https://www.affiniteinstruments.com/",
            "last_updated": datetime.now().isoformat(),
        }

        doc_id = self.articles.insert(article)
        logger.debug(f"Added article: {title} (ID: {doc_id})")
        return doc_id

    def add_faq(
        self, question: str, answer: str, category: str = "general", url: str = None
    ) -> int:
        """Add a FAQ entry.

        Args:
            question: The question text
            answer: The answer text
            category: Category for organization
            url: URL to FAQ page on website

        Returns:
            int: Database ID of inserted FAQ
        """
        faq = {
            "question": question,
            "answer": answer,
            "category": category,
            "url": url or "https://www.affiniteinstruments.com/",
            "last_updated": datetime.now().isoformat(),
        }

        doc_id = self.faqs.insert(faq)
        logger.debug(f"Added FAQ: {question[:50]}... (ID: {doc_id})")
        return doc_id

    def search(self, query: str, max_results: int = 3) -> List[Dict]:
        """Search knowledge base for relevant content.

        Uses keyword matching and content search to find relevant articles.

        Args:
            query: Search query
            max_results: Maximum number of results to return

        Returns:
            List of matching articles/FAQs with relevance scores
        """
        query_lower = query.lower()
        query_words = set(re.findall(r"\w+", query_lower))

        results = []

        # Search articles
        for article in self.articles.all():
            score = self._calculate_relevance(query_lower, query_words, article)
            if score > 0:
                results.append(
                    {
                        "type": "article",
                        "title": article["title"],
                        "content": article["content"],
                        "category": article["category"],
                        "url": article.get("url", "https://www.affiniteinstruments.com/"),
                        "score": score,
                    }
                )

        # Search FAQs
        for faq in self.faqs.all():
            # Check if question matches
            q_score = self._calculate_relevance(
                query_lower, query_words, {"content": faq["question"], "keywords": []}
            )

            if q_score > 0:
                results.append(
                    {
                        "type": "faq",
                        "title": faq["question"],
                        "content": faq["answer"],
                        "category": faq["category"],
                        "url": faq.get("url", "https://www.affiniteinstruments.com/"),
                        "score": q_score + 0.5,  # Boost FAQ scores slightly
                    }
                )

        # Sort by relevance score
        results.sort(key=lambda x: x["score"], reverse=True)

        return results[:max_results]

    def _calculate_relevance(self, query_lower: str, query_words: set, item: dict) -> float:
        """Calculate relevance score for an item.

        Args:
            query_lower: Lowercase query string
            query_words: Set of query words
            item: Article or FAQ dict

        Returns:
            float: Relevance score (0.0 - 10.0)
        """
        score = 0.0

        # Check keywords (highest weight)
        keywords = item.get("keywords", [])
        for keyword in keywords:
            if keyword.lower() in query_lower:
                score += 3.0

        # Check content (medium weight)
        content = item.get("content", "").lower()
        for word in query_words:
            if len(word) > 3:  # Ignore short words
                if word in content:
                    score += 1.0

        # Check title if present (high weight)
        title = item.get("title", "").lower()
        for word in query_words:
            if len(word) > 3 and word in title:
                score += 2.0

        return score

    def get_by_category(self, category: str) -> List[Dict]:
        """Get all articles in a category.

        Args:
            category: Category name

        Returns:
            List of articles in that category
        """
        from tinydb import Query

        Article = Query()
        return self.articles.search(Article.category == category)

    def update_article(self, doc_id: int, **fields):
        """Update an article.

        Args:
            doc_id: Database ID
            **fields: Fields to update
        """
        fields["last_updated"] = datetime.now().isoformat()
        self.articles.update(fields, doc_ids=[doc_id])

    def delete_article(self, doc_id: int):
        """Delete an article.

        Args:
            doc_id: Database ID
        """
        self.articles.remove(doc_ids=[doc_id])

    def clear_all(self):
        """Clear all knowledge base content."""
        self.articles.truncate()
        self.faqs.truncate()
        logger.warning("Knowledge base cleared")

    def get_stats(self) -> dict:
        """Get knowledge base statistics.

        Returns:
            dict: Statistics about the knowledge base
        """
        return {
            "total_articles": len(self.articles),
            "total_faqs": len(self.faqs),
            "categories": list(set(a["category"] for a in self.articles.all())),
        }
