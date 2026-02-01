"""Export Spark AI transcript for OEM analysis and improvement.

This utility exports the Q&A history from Spark AI in various formats
for analysis by the AffiLabs team to improve responses and documentation.
"""

import json
import csv
from datetime import datetime
from pathlib import Path
from tinydb import TinyDB


def export_to_json(output_path: str = None):
    """Export transcript to JSON format (complete data).
    
    Args:
        output_path: Output file path. If None, uses default naming.
    
    Returns:
        str: Path to exported file
    """
    if output_path is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = f"spark_transcript_{timestamp}.json"
    
    db = TinyDB("spark_qa_history.json")
    qa_table = db.table('questions_answers')
    all_data = qa_table.all()
    
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(all_data, f, indent=2, ensure_ascii=False)
    
    db.close()
    return output_path


def export_to_csv(output_path: str = None):
    """Export transcript to CSV format (easy to analyze in Excel).
    
    Args:
        output_path: Output file path. If None, uses default naming.
    
    Returns:
        str: Path to exported file
    """
    if output_path is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = f"spark_transcript_{timestamp}.csv"
    
    db = TinyDB("spark_qa_history.json")
    qa_table = db.table('questions_answers')
    all_data = qa_table.all()
    
    if not all_data:
        print("No data to export")
        db.close()
        return None
    
    # CSV columns
    fieldnames = ['timestamp', 'question', 'answer', 'matched', 'feedback']
    
    with open(output_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        
        for entry in all_data:
            # Only write the relevant fields
            row = {k: entry.get(k, '') for k in fieldnames}
            writer.writerow(row)
    
    db.close()
    return output_path


def export_unmatched_questions(output_path: str = None):
    """Export only questions that didn't match patterns (for improvement).
    
    Args:
        output_path: Output file path. If None, uses default naming.
    
    Returns:
        str: Path to exported file
    """
    if output_path is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = f"spark_unmatched_{timestamp}.txt"
    
    db = TinyDB("spark_qa_history.json")
    qa_table = db.table('questions_answers')
    
    from tinydb import Query
    Q = Query()
    unmatched = qa_table.search(Q.matched == False)
    
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write("SPARK AI - UNMATCHED QUESTIONS\n")
        f.write("=" * 80 + "\n")
        f.write(f"Exported: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"Total unmatched: {len(unmatched)}\n\n")
        
        for i, entry in enumerate(unmatched, 1):
            f.write(f"\n[{i}] {entry.get('timestamp', 'N/A')}\n")
            f.write(f"Q: {entry.get('question', '')}\n")
            f.write(f"A: {entry.get('answer', '')[:200]}...\n")
            f.write("-" * 80 + "\n")
    
    db.close()
    return output_path


def generate_analytics_report():
    """Generate analytics report about Spark usage.
    
    Returns:
        dict: Analytics data
    """
    db = TinyDB("spark_qa_history.json")
    qa_table = db.table('questions_answers')
    all_data = qa_table.all()
    
    from tinydb import Query
    Q = Query()
    
    total_questions = len(all_data)
    matched = len(qa_table.search(Q.matched == True))
    unmatched = len(qa_table.search(Q.matched == False))
    with_feedback = len([e for e in all_data if e.get('feedback')])
    
    # Most common questions (simple frequency count)
    question_freq = {}
    for entry in all_data:
        q = entry.get('question', '').lower().strip()
        if q:
            question_freq[q] = question_freq.get(q, 0) + 1
    
    top_questions = sorted(question_freq.items(), key=lambda x: x[1], reverse=True)[:10]
    
    analytics = {
        'total_questions': total_questions,
        'matched_count': matched,
        'unmatched_count': unmatched,
        'match_rate': f"{(matched/total_questions*100):.1f}%" if total_questions > 0 else "N/A",
        'feedback_count': with_feedback,
        'top_questions': top_questions,
    }
    
    db.close()
    return analytics


def print_analytics():
    """Print analytics report to console."""
    analytics = generate_analytics_report()
    
    print("\n" + "=" * 80)
    print("SPARK AI ANALYTICS REPORT")
    print("=" * 80)
    print(f"Total Questions:     {analytics['total_questions']}")
    print(f"Pattern Matched:     {analytics['matched_count']} ({analytics['match_rate']})")
    print(f"AI Fallback:         {analytics['unmatched_count']}")
    print(f"With Feedback:       {analytics['feedback_count']}")
    
    if analytics['top_questions']:
        print("\nTop 10 Questions:")
        print("-" * 80)
        for i, (question, count) in enumerate(analytics['top_questions'], 1):
            print(f"{i:2}. [{count}x] {question[:70]}")
    
    print("=" * 80 + "\n")


def export_all_formats():
    """Export transcript in all formats for comprehensive OEM analysis.
    
    Returns:
        dict: Paths to all exported files
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    exports = {
        'json': export_to_json(f"spark_transcript_{timestamp}.json"),
        'csv': export_to_csv(f"spark_transcript_{timestamp}.csv"),
        'unmatched': export_unmatched_questions(f"spark_unmatched_{timestamp}.txt"),
    }
    
    # Save analytics report
    analytics_path = f"spark_analytics_{timestamp}.txt"
    with open(analytics_path, 'w', encoding='utf-8') as f:
        analytics = generate_analytics_report()
        f.write("SPARK AI ANALYTICS REPORT\n")
        f.write("=" * 80 + "\n")
        f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        f.write(f"Total Questions:     {analytics['total_questions']}\n")
        f.write(f"Pattern Matched:     {analytics['matched_count']} ({analytics['match_rate']})\n")
        f.write(f"AI Fallback:         {analytics['unmatched_count']}\n")
        f.write(f"With Feedback:       {analytics['feedback_count']}\n\n")
        
        if analytics['top_questions']:
            f.write("Top Questions:\n")
            f.write("-" * 80 + "\n")
            for i, (question, count) in enumerate(analytics['top_questions'], 1):
                f.write(f"{i:2}. [{count}x] {question}\n")
    
    exports['analytics'] = analytics_path
    
    return exports


if __name__ == "__main__":
    print("\nSpark AI Transcript Exporter")
    print("=" * 80)
    
    # Check if database exists
    if not Path("spark_qa_history.json").exists():
        print("❌ No spark_qa_history.json found")
        print("   Spark needs to be used at least once to generate data.")
        exit(1)
    
    # Show analytics first
    print_analytics()
    
    # Export all formats
    print("Exporting transcripts...")
    exports = export_all_formats()
    
    print("\n✅ Export Complete!\n")
    print("Files created:")
    for format_type, path in exports.items():
        if path:
            size = Path(path).stat().st_size
            print(f"  • {format_type:12} → {path} ({size:,} bytes)")
    
    print("\n💡 Share these files with AffiLabs OEM team for:")
    print("   • Improving pattern matching")
    print("   • Enhancing TinyLM context")
    print("   • Updating documentation")
    print("   • Identifying common user needs\n")
