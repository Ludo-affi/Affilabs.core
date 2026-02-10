"""
Spark Data Processing Pipeline for Operation Manual Training
=============================================================

This script demonstrates how to use Apache Spark to extract, process, and
structure the Operation Manual for use with TinyLLaMA and other ML models.

Usage:
    spark-submit spark_processing.py

Requirements:
    - Apache Spark 3.3+
    - PySpark
    - Python 3.8+
"""

from pyspark.sql import SparkSession
from pyspark.sql.functions import col, split, explode, regexp_extract, collect_list
import re
import json
from pathlib import Path


class OperationManualProcessor:
    """Process AffiLabs Operation Manual for ML training."""

    def __init__(self, manual_path: str, spark: SparkSession):
        self.manual_path = Path(manual_path)
        self.spark = spark
        self.manual_text = self.read_manual()

    def read_manual(self) -> str:
        """Read the operation manual file."""
        with open(self.manual_path, 'r', encoding='utf-8') as f:
            return f.read()

    def extract_sections(self) -> dict:
        """Extract major sections from manual."""
        sections = {}
        section_pattern = r'^## (.+?)$'

        current_section = None
        current_content = []

        for line in self.manual_text.split('\n'):
            section_match = re.match(section_pattern, line)
            if section_match:
                if current_section:
                    sections[current_section] = '\n'.join(current_content)
                current_section = section_match.group(1)
                current_content = []
            else:
                current_content.append(line)

        if current_section:
            sections[current_section] = '\n'.join(current_content)

        return sections

    def extract_procedures(self) -> list:
        """Extract all procedures with steps."""
        procedures = []
        procedure_pattern = r'^#### (.+?)$'
        step_pattern = r'^(\d+)\. (.+?)$'

        lines = self.manual_text.split('\n')
        current_procedure = None
        current_steps = []

        for i, line in enumerate(lines):
            proc_match = re.match(procedure_pattern, line)
            step_match = re.match(step_pattern, line)

            if proc_match:
                if current_procedure:
                    procedures.append({
                        'name': current_procedure,
                        'steps': current_steps
                    })
                current_procedure = proc_match.group(1)
                current_steps = []
            elif step_match and current_procedure:
                current_steps.append({
                    'number': int(step_match.group(1)),
                    'instruction': step_match.group(2)
                })

        if current_procedure:
            procedures.append({
                'name': current_procedure,
                'steps': current_steps
            })

        return procedures

    def extract_tables(self) -> list:
        """Extract all markdown tables."""
        tables = []
        table_pattern = r'\n(\|.+?\|)\n(\|[\-:|\s]+\|)\n((?:\|.+?\|\n)*)'

        for match in re.finditer(table_pattern, self.manual_text, re.MULTILINE):
            header_raw = match.group(1)
            rows_raw = match.group(3)

            headers = [h.strip() for h in header_raw.split('|')[1:-1]]
            rows = []

            for row_raw in rows_raw.strip().split('\n'):
                if row_raw.strip():
                    row_data = [cell.strip() for cell in row_raw.split('|')[1:-1]]
                    rows.append(dict(zip(headers, row_data)))

            tables.append({
                'headers': headers,
                'rows': rows,
                'row_count': len(rows)
            })

        return tables

    def extract_safety_rules(self) -> list:
        """Extract all critical safety warnings."""
        safety_rules = []
        warning_pattern = r'⚠️\s*(.+?)(?=\n\n|\n[A-Z])'

        for match in re.finditer(warning_pattern, self.manual_text, re.DOTALL):
            rule = match.group(1).strip()
            safety_rules.append({
                'content': rule,
                'priority': 'critical' if 'STOP' in rule or 'IMMEDIATELY' in rule else 'high'
            })

        return safety_rules

    def extract_troubleshooting(self) -> list:
        """Extract troubleshooting table entries."""
        troubleshooting = []

        lines = self.manual_text.split('\n')
        in_troubleshooting = False

        for i, line in enumerate(lines):
            if 'Troubleshooting Common Issues' in line:
                in_troubleshooting = True
                continue

            if in_troubleshooting and line.startswith('|'):
                # Parse troubleshooting table
                if '---' not in line and not line.startswith('| Issue'):
                    parts = [p.strip() for p in line.split('|')[1:-1]]
                    if len(parts) >= 3:
                        troubleshooting.append({
                            'issue': parts[0],
                            'cause': parts[1],
                            'solution': parts[2]
                        })

            if in_troubleshooting and line.startswith('---'):
                break

        return troubleshooting

    def create_training_pairs(self) -> list:
        """Generate instruction-response pairs for TinyLLaMA training."""
        pairs = []

        # Procedure-based pairs
        procedures = self.extract_procedures()
        for proc in procedures:
            if proc['steps']:
                steps_text = '\n'.join([
                    f"{step['number']}. {step['instruction']}"
                    for step in proc['steps']
                ])
                pairs.append({
                    'category': 'procedure_guidance',
                    'instruction': f"How do I perform: {proc['name']}?",
                    'response': steps_text,
                    'source': 'procedures'
                })

        # Troubleshooting pairs
        troubleshooting = self.extract_troubleshooting()
        for ts in troubleshooting:
            pairs.append({
                'category': 'troubleshooting',
                'instruction': f"What should I do if: {ts['issue']}?",
                'response': f"Cause: {ts['cause']}\n\nSolution: {ts['solution']}",
                'source': 'troubleshooting'
            })

        # Safety rule pairs
        safety_rules = self.extract_safety_rules()
        for rule in safety_rules:
            pairs.append({
                'category': 'safety',
                'instruction': "What are the critical safety rules?",
                'response': rule['content'],
                'source': 'safety',
                'priority': rule['priority']
            })

        return pairs

    def process_to_spark_dataframe(self):
        """Create Spark DataFrame from processed data."""
        sections = self.extract_sections()
        procedures = self.extract_procedures()
        tables = self.extract_tables()
        training_pairs = self.create_training_pairs()

        # Create DataFrames
        sections_df = self.spark.createDataFrame([
            {'section': k, 'content': v} for k, v in sections.items()
        ])

        procedures_df = self.spark.createDataFrame(procedures)

        training_pairs_df = self.spark.createDataFrame(training_pairs)

        return {
            'sections': sections_df,
            'procedures': procedures_df,
            'tables': tables,
            'training_pairs': training_pairs_df
        }

    def save_training_data(self, output_dir: str):
        """Save processed data in training-ready format."""
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        # Extract and save training pairs
        training_pairs = self.create_training_pairs()
        training_file = output_path / 'training_pairs.jsonl'

        with open(training_file, 'w', encoding='utf-8') as f:
            for pair in training_pairs:
                f.write(json.dumps(pair) + '\n')

        print(f"✓ Saved {len(training_pairs)} training pairs to {training_file}")

        # Save procedures
        procedures_file = output_path / 'procedures.json'
        with open(procedures_file, 'w', encoding='utf-8') as f:
            json.dump(self.extract_procedures(), f, indent=2)

        print(f"✓ Saved procedures to {procedures_file}")

        # Save troubleshooting
        troubleshooting_file = output_path / 'troubleshooting.json'
        with open(troubleshooting_file, 'w', encoding='utf-8') as f:
            json.dump(self.extract_troubleshooting(), f, indent=2)

        print(f"✓ Saved troubleshooting entries to {troubleshooting_file}")


def main():
    """Main processing pipeline."""
    spark = SparkSession.builder \
        .appName("OperationManualProcessor") \
        .getOrCreate()

    # Initialize processor
    manual_path = "OPERATION_MANUAL.md"
    processor = OperationManualProcessor(manual_path, spark)

    # Process and save
    output_dir = "./training_data"
    processor.save_training_data(output_dir)

    # Create Spark DataFrames
    dfs = processor.process_to_spark_dataframe()

    print(f"\n✓ Processing complete!")
    print(f"  - Sections: {dfs['sections'].count()}")
    print(f"  - Procedures: {dfs['procedures'].count()}")
    print(f"  - Training pairs: {dfs['training_pairs'].count()}")

    # Show sample training pairs
    print(f"\n📋 Sample training pairs:")
    dfs['training_pairs'].limit(3).show(truncate=False)

    spark.stop()


if __name__ == "__main__":
    main()
