"""
Spark Analytics - Analyze Q&A history to improve the system

This utility analyzes the Spark Q&A database to:
1. Identify common unmatched questions (candidates for new patterns)
2. Analyze feedback to find problematic answers
3. Generate reports on usage patterns
4. Suggest improvements to pattern matching

Usage:
    python analyze_spark_data.py
"""

import json
from pathlib import Path
from datetime import datetime
from collections import Counter, defaultdict
import re

# Data file location (moved to organized structure)
DATA_DIR = Path(__file__).parent.parent.parent / "affilabs" / "data" / "spark"
QA_HISTORY_PATH = DATA_DIR / "qa_history.json"


class SparkAnalytics:
    """Analyze Spark Q&A history for insights."""
    
    def __init__(self, db_path: str = None):
        """Initialize analytics with database path."""
        if db_path is None:
            db_path = QA_HISTORY_PATH
        self.db_path = Path(db_path)
        self.data = self._load_data()
    
    def _load_data(self) -> dict:
        """Load Q&A history from database."""
        if not self.db_path.exists():
            print(f"⚠️  Database not found: {self.db_path}")
            return {"_default": {}}
        
        try:
            with open(self.db_path, 'r') as f:
                data = json.load(f)
            print(f"✓ Loaded {len(data.get('_default', {}))} Q&A records")
            return data
        except Exception as e:
            print(f"❌ Error loading database: {e}")
            return {"_default": {}}
    
    def get_all_questions(self) -> list:
        """Get all Q&A records."""
        return list(self.data.get('_default', {}).values())
    
    def analyze_unmatched_questions(self, min_count: int = 2) -> list:
        """Find common unmatched questions that should become patterns.
        
        Args:
            min_count: Minimum occurrences to be considered for pattern
            
        Returns:
            List of (question_text, count) tuples sorted by frequency
        """
        questions = self.get_all_questions()
        
        # Get unmatched questions
        unmatched = [q['question'] for q in questions if not q.get('matched', True)]
        
        if not unmatched:
            return []
        
        # Normalize questions (lowercase, remove punctuation)
        normalized = []
        for q in unmatched:
            norm = q.lower().strip()
            norm = re.sub(r'[^\w\s]', '', norm)
            normalized.append(norm)
        
        # Count occurrences
        counts = Counter(normalized)
        
        # Filter by minimum count
        common = [(q, c) for q, c in counts.items() if c >= min_count]
        common.sort(key=lambda x: x[1], reverse=True)
        
        return common
    
    def analyze_feedback(self) -> dict:
        """Analyze feedback patterns.
        
        Returns:
            Dict with feedback statistics
        """
        questions = self.get_all_questions()
        
        stats = {
            'total': len(questions),
            'with_feedback': 0,
            'helpful': 0,
            'not_helpful': 0,
            'helpful_rate': 0.0,
            'matched_helpful_rate': 0.0,
            'unmatched_helpful_rate': 0.0,
        }
        
        # Count feedback
        helpful_questions = []
        not_helpful_questions = []
        matched_helpful = 0
        matched_total = 0
        unmatched_helpful = 0
        unmatched_total = 0
        
        for q in questions:
            feedback = q.get('feedback')
            matched = q.get('matched', False)
            
            if feedback:
                stats['with_feedback'] += 1
                
                if feedback == 'helpful':
                    stats['helpful'] += 1
                    helpful_questions.append(q['question'])
                    
                    if matched:
                        matched_helpful += 1
                elif feedback == 'not_helpful':
                    stats['not_helpful'] += 1
                    not_helpful_questions.append(q['question'])
            
            # Track matched vs unmatched
            if matched:
                matched_total += 1
            else:
                unmatched_total += 1
        
        # Calculate rates
        if stats['with_feedback'] > 0:
            stats['helpful_rate'] = stats['helpful'] / stats['with_feedback']
        
        if matched_total > 0:
            stats['matched_helpful_rate'] = matched_helpful / matched_total
        
        if unmatched_total > 0:
            stats['unmatched_helpful_rate'] = unmatched_helpful / unmatched_total
        
        stats['helpful_questions'] = helpful_questions[:10]  # Top 10
        stats['not_helpful_questions'] = not_helpful_questions[:10]  # Top 10
        
        return stats
    
    def extract_keywords(self, questions: list, top_n: int = 20) -> list:
        """Extract common keywords from questions.
        
        Args:
            questions: List of question strings
            top_n: Number of top keywords to return
            
        Returns:
            List of (keyword, count) tuples
        """
        # Common stop words to exclude
        stop_words = {
            'how', 'do', 'i', 'the', 'a', 'an', 'to', 'is', 'what', 'why',
            'when', 'where', 'can', 'my', 'in', 'on', 'for', 'with', 'and',
            'or', 'of', 'it', 'that', 'this', 'are', 'be', 'at', 'as', 'by'
        }
        
        # Extract words
        words = []
        for q in questions:
            # Lowercase and split
            tokens = re.findall(r'\w+', q.lower())
            # Filter stop words and short words
            words.extend([w for w in tokens if w not in stop_words and len(w) > 2])
        
        # Count and return top N
        counts = Counter(words)
        return counts.most_common(top_n)
    
    def generate_pattern_suggestions(self) -> list:
        """Generate suggestions for new patterns based on unmatched questions.
        
        Returns:
            List of pattern suggestions with keywords and example questions
        """
        questions = self.get_all_questions()
        unmatched = [q for q in questions if not q.get('matched', True)]
        
        if not unmatched:
            return []
        
        # Group by keywords
        keyword_groups = defaultdict(list)
        for q in unmatched:
            keywords = self.extract_keywords([q['question']], top_n=3)
            for keyword, _ in keywords:
                keyword_groups[keyword].append(q['question'])
        
        # Find significant groups (multiple questions with same keyword)
        suggestions = []
        for keyword, questions_list in keyword_groups.items():
            if len(questions_list) >= 2:  # At least 2 questions
                suggestions.append({
                    'keyword': keyword,
                    'count': len(questions_list),
                    'example_questions': questions_list[:5]
                })
        
        # Sort by count
        suggestions.sort(key=lambda x: x['count'], reverse=True)
        return suggestions[:10]  # Top 10
    
    def print_report(self):
        """Print comprehensive analytics report."""
        print("\n" + "=" * 70)
        print("SPARK ANALYTICS REPORT")
        print("=" * 70)
        print(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        
        # Overall stats
        questions = self.get_all_questions()
        matched_count = sum(1 for q in questions if q.get('matched', False))
        unmatched_count = len(questions) - matched_count
        
        print(f"📊 OVERALL STATISTICS")
        print(f"   Total questions: {len(questions)}")
        print(f"   Matched (pattern): {matched_count} ({matched_count/len(questions)*100:.1f}%)")
        print(f"   Unmatched (AI): {unmatched_count} ({unmatched_count/len(questions)*100:.1f}%)")
        print()
        
        # Feedback analysis
        print(f"👍 FEEDBACK ANALYSIS")
        feedback = self.analyze_feedback()
        print(f"   Questions with feedback: {feedback['with_feedback']}/{feedback['total']}")
        print(f"   Helpful: {feedback['helpful']} ({feedback['helpful_rate']*100:.1f}%)")
        print(f"   Not helpful: {feedback['not_helpful']}")
        print(f"   Matched helpful rate: {feedback['matched_helpful_rate']*100:.1f}%")
        print(f"   Unmatched helpful rate: {feedback['unmatched_helpful_rate']*100:.1f}%")
        print()
        
        # Common unmatched questions
        print(f"🔍 COMMON UNMATCHED QUESTIONS")
        common_unmatched = self.analyze_unmatched_questions(min_count=2)
        if common_unmatched:
            for i, (question, count) in enumerate(common_unmatched[:10], 1):
                print(f"   {i}. [{count}x] {question}")
        else:
            print("   None (all questions matched patterns)")
        print()
        
        # Pattern suggestions
        print(f"💡 PATTERN SUGGESTIONS")
        suggestions = self.generate_pattern_suggestions()
        if suggestions:
            for i, sug in enumerate(suggestions[:5], 1):
                print(f"   {i}. Keyword: '{sug['keyword']}' ({sug['count']} questions)")
                print(f"      Example: {sug['example_questions'][0]}")
        else:
            print("   No new patterns needed")
        print()
        
        # Keyword analysis
        print(f"🔤 TOP KEYWORDS (All Questions)")
        all_q_text = [q['question'] for q in questions]
        keywords = self.extract_keywords(all_q_text, top_n=15)
        for i, (word, count) in enumerate(keywords[:15], 1):
            print(f"   {i:2d}. {word:15s} ({count:3d} times)")
        print()
        
        print("=" * 70)
        
        # Recommendations
        print("\n📋 RECOMMENDATIONS")
        if unmatched_count > matched_count:
            print("   ⚠️  More unmatched than matched questions!")
            print("   → Add patterns for common unmatched questions above")
        
        if feedback['helpful_rate'] < 0.7 and feedback['with_feedback'] > 5:
            print("   ⚠️  Low helpful rate (<70%)")
            print("   → Review and improve answer quality")
        
        if len(suggestions) > 3:
            print(f"   💡 {len(suggestions)} potential new patterns identified")
            print("   → Consider adding patterns for top suggestions")
        
        if feedback['with_feedback'] < len(questions) * 0.1:
            print("   📊 Low feedback rate (<10%)")
            print("   → Encourage users to provide feedback")
        
        print()


def main():
    """Run Spark analytics."""
    analytics = SparkAnalytics()
    analytics.print_report()
    
    # Export suggestions for review
    suggestions = analytics.generate_pattern_suggestions()
    if suggestions:
        export_path = Path("spark_pattern_suggestions.json")
        with open(export_path, 'w') as f:
            json.dump(suggestions, f, indent=2)
        print(f"✓ Exported pattern suggestions to: {export_path}\n")


if __name__ == "__main__":
    main()
