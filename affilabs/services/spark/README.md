# Spark AI Service

Internal service for the Spark AI-powered help system in Affilabs.core.

## Architecture

Spark uses a **3-layer hybrid approach** for answering user questions:

1. **Layer 1: Pattern Matching** (instant, ~0-10ms)
   - 41 pre-defined regex patterns organized into 9 categories
   - Deterministic answers for common questions
   - Located in `patterns.py`

2. **Layer 2: Knowledge Base** (fast, ~50-100ms)
   - TinyDB-based searchable content from website
   - Relevance scoring for best match
   - Falls through if score < 2.0

3. **Layer 3: AI Model** (slower, ~1-5s)
   - TinyLlama-1.1B language model
   - Context-aware responses
   - Lazy-loaded on first use

## Components

### `answer_engine.py`
Main coordinator that orchestrates the 3-layer system.

```python
from affilabs.services.spark import SparkAnswerEngine

engine = SparkAnswerEngine()
answer, matched = engine.generate_answer("How do I calibrate?")
```

### `pattern_matcher.py`
Fast regex-based pattern matching using patterns from `patterns.py`.

### `patterns.py`
**Single source of truth** for all Q&A patterns.

**Pattern format:**
```python
PATTERNS = {
    "category_name": {
        r"regex_pattern": {
            "answer": "Answer text with markdown formatting...",
            "category": "category_name",
            "keywords": ["word1", "word2"],
            "priority": "high|medium|low"
        }
    }
}
```

**Categories:**
- `startup` - Power on, calibration, auto-read mode
- `calibration` - 5 calibration types, troubleshooting
- `pump` - AffiPump and P4PROPLUS control
- `method` - Cycle creation and editing
- `analysis` - Baseline corrections
- `basic` - Start/stop acquisition
- `export` - Data export
- `hardware` - Connection issues
- `general` - Keyboard shortcuts

### `knowledge_base.py`
TinyDB-based searchable storage for website content.

**Data location:** `affilabs/data/spark/knowledge_base.json`

### `tinylm.py`
TinyLlama-1.1B AI model integration with lazy loading.

## Adding New Patterns

Edit `patterns.py` and add to the appropriate category:

```python
r"your.*regex.*pattern": {
    "answer": "**Title:**\n\nYour formatted answer here...",
    "category": "calibration",
    "keywords": ["keyword1", "keyword2"],
    "priority": "high"
},
```

## Adding Knowledge Base Content

Use the utility tool:

```bash
python tools/spark/add_content.py
```

Or programmatically:

```python
from affilabs.services.spark import SparkKnowledgeBase

kb = SparkKnowledgeBase()
kb.add_article(
    title="Article Title",
    content="Article content...",
    category="calibration",
    keywords=["key1", "key2"],
    url="https://example.com/article"
)
```

## Data Files

- **QA History:** `affilabs/data/spark/qa_history.json`
- **Knowledge Base:** `affilabs/data/spark/knowledge_base.json`

## Utilities

Located in `tools/spark/`:
- `add_content.py` - Add articles/FAQs to knowledge base
- `analyze_data.py` - Analyze Q&A history for insights
- `export_transcript.py` - Export Q&A history for analysis

## Performance

| Layer | Response Time | Use Case |
|-------|---------------|----------|
| Pattern | < 10ms | Common questions |
| Knowledge Base | 50-100ms | Website content |
| AI Model (CPU) | 2-5s | Complex questions |
| AI Model (GPU) | 0.5-1s | Complex questions |

## Integration

The Spark service is used by `SparkHelpWidget` in `affilabs/widgets/`:

```python
from affilabs.widgets.spark_help_widget import SparkHelpWidget

# Widget automatically uses SparkAnswerEngine
spark = SparkHelpWidget()
```

## Backward Compatibility

Old imports still work via aliases in `affilabs/widgets/`:
```python
# Deprecated but still functional
from affilabs.widgets.spark_tinylm import SparkTinyLM

# Preferred
from affilabs.services.spark import SparkTinyLM
```
