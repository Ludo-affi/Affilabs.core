# Spark AI Assistant - Developer Guide

**Last Updated:** February 2, 2026
**Version:** 2.0 (Consolidated Technical Documentation)

---

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Component Details](#component-details)
3. [Adding New Patterns](#adding-new-patterns)
4. [Extending the Knowledge Base](#extending-the-knowledge-base)
5. [Training & Improving Spark](#training--improving-spark)
6. [Database Schema](#database-schema)
7. [Testing](#testing)
8. [Deployment](#deployment)
9. [Performance Optimization](#performance-optimization)
10. [Quick Reference](#quick-reference)

---

## Architecture Overview

### System Design

Spark uses a **3-layer hybrid intelligence system**:

```
User Question
    ↓
Layer 1: PATTERN MATCHING (< 1ms)
    ├── Regex patterns for common questions
    ├── ~50 pre-defined Q&A patterns
    └── Instant responses
    ↓ (no match)
Layer 2: KNOWLEDGE BASE SEARCH (< 100ms)
    ├── TinyDB database (JSON storage)
    ├── Keyword + content relevance scoring
    └── Website articles & FAQs
    ↓ (no match, score < 2.0)
Layer 3: AI MODEL (2-5 seconds)
    ├── TinyLlama-1.1B-Chat-v1.0
    ├── Context-aware generation
    ├── Lazy loading (first use only)
    └── Conversational understanding
```

### Component Hierarchy

```
SparkHelpWidget (UI Layer)
    ├── SparkAnswerEngine (Core Logic)
    │   ├── SparkPatternMatcher (Fast Path)
    │   ├── SparkKnowledgeBase (Website Content)
    │   └── SparkTinyLM (AI Fallback)
    ├── SparkQuestionStorage (Persistence)
    ├── AnswerGeneratorThread (Background Processing)
    └── MessageWidget (UI Component)
```

### File Structure

```
affilabs/widgets/
├── spark_help_widget.py         # Main UI (617 lines)
├── spark_answer_engine.py       # Answer coordinator (62 lines)
├── spark_pattern_matcher.py     # Pattern matching (137 lines)
├── spark_knowledge_base.py      # Website content search
├── spark_tinylm.py              # AI model integration (233 lines)
└── spark_question_storage.py    # Database operations

Root files:
├── spark_qa_history.json        # Q&A database (auto-created)
├── spark_knowledge_base.json    # Website content (auto-created)
├── add_spark_content.py         # Content management tool
├── export_spark_transcript.py   # Data export tool
└── analyze_spark_data.py        # Analytics tool
```

---

## Component Details

### 1. SparkPatternMatcher

**File:** `affilabs/widgets/spark_pattern_matcher.py`

**Purpose:** Provides instant (<1ms) answers for common questions using regex pattern matching.

**Topics Covered:**
- `start_acquisition` - Starting acquisitions
- `export_data` - Exporting/saving data
- `calibration` - Detector calibration
- `method_building` - Creating methods and cycles
- `flow_control` - Pump and channel control
- `graph_config` - Graph configuration
- `troubleshooting` - Common issues
- `general_help` - Overview of capabilities

**Pattern Structure:**
```python
PATTERNS = {
    "topic_name": {
        "regex": r'keyword1|keyword2|phrase',
        "answer": """Step-by-step answer:

1. First step
2. Second step
3. Third step

Tip: Helpful hint here."""
    },
}
```

### 2. SparkKnowledgeBase

**File:** `affilabs/widgets/spark_knowledge_base.py`

**Purpose:** Searches website content (articles, FAQs, docs) stored locally.

**Features:**
- Relevance scoring (keywords=+3.0, title=+2.0, content=+1.0)
- Category organization (tutorials, faqs, troubleshooting, etc.)
- URL references to source content
- Fast search (<100ms)

**Adding Content:**
```python
from affilabs.widgets.spark_knowledge_base import SparkKnowledgeBase

kb = SparkKnowledgeBase()
kb.add_article(
    title="How to Run an SPR Assay",
    content="Step-by-step guide...",
    category="tutorials",
    keywords=["assay", "run", "start", "spr"],
    url="https://www.affiniteinstruments.com/tutorials/spr-assay"
)
```

### 3. SparkTinyLM

**File:** `affilabs/widgets/spark_tinylm.py`

**Purpose:** Conversational AI fallback using TinyLlama-1.1B-Chat-v1.0 model.

**Features:**
- Lazy loading (10-30s first time, then instant)
- GPU/CPU auto-detection
- Context building for SPR-specific responses
- Temperature=0.7, max_tokens=150

**Model Details:**
- Size: ~637 MB
- Speed: 2-5 seconds per response (after loading)
- Framework: Hugging Face Transformers + PyTorch

### 4. SparkAnswerEngine

**File:** `affilabs/widgets/spark_answer_engine.py`

**Purpose:** Coordinates between all three layers.

**Logic:**
```python
def generate_answer(self, question: str):
    # Phase 1: Pattern matching
    pattern_answer = self.pattern_matcher.match_question(question)
    if pattern_answer:
        return (pattern_answer, True)

    # Phase 2: Knowledge base (if implemented)
    # kb_answer = self.knowledge_base.search(question)
    # if kb_answer and kb_answer['score'] > 2.0:
    #     return (kb_answer['content'], True)

    # Phase 3: AI model
    ai_answer, success = self.ai_model.generate_answer(question)
    return (ai_answer, success)
```

### 5. SparkQuestionStorage

**File:** Part of `spark_help_widget.py`

**Purpose:** TinyDB-based storage for Q&A history and user feedback.

**Schema:**
```json
{
    "timestamp": "2026-02-02T20:30:00.000000",
    "question": "How do I start an acquisition?",
    "answer": "To start an acquisition...",
    "matched": true,
    "feedback": "helpful"
}
```

---

## Adding New Patterns

### Quick Start (5 minutes)

1. **Open** `affilabs/widgets/spark_pattern_matcher.py`

2. **Add to PATTERNS dict:**

```python
PATTERNS = {
    # ... existing patterns ...

    "your_new_pattern": {
        "regex": r'keyword1|keyword2|phrase to match',
        "answer": """Clear step-by-step answer:

1. First step
2. Second step
3. Third step

Tip: Helpful hint here."""
    },
}
```

3. **Test it:**
```python
from affilabs.widgets.spark_pattern_matcher import SparkPatternMatcher
matcher = SparkPatternMatcher()
answer = matcher.match_question("keyword1 question")
print(answer)
```

4. **Done!** No restart needed.

### Regex Pattern Tips

**Case-insensitive matching** (automatic):
```python
"regex": r'calibrate|calibration'  # Matches "Calibrate", "CALIBRATION", etc.
```

**Word boundaries** (prevent partial matches):
```python
"regex": r'\bexport\b'  # Matches "export" but not "exporting"
```

**Multiple phrases**:
```python
"regex": r'start.*acquisition|begin.*record|run.*acquire'
```

**Optional words**:
```python
"regex": r'how( to)? calibrate'  # Matches "how calibrate" or "how to calibrate"
```

**Test your regex:**
```python
import re
pattern = r'your|regex|here'
test = "your test question"
print(bool(re.search(pattern, test, re.IGNORECASE)))
```

---

## Extending the Knowledge Base

### Method 1: Content Manager Script

```bash
# Add sample content
python add_spark_content.py add

# View current content
python add_spark_content.py view

# Test search
python add_spark_content.py test
```

### Method 2: Programmatically

```python
from affilabs.widgets.spark_knowledge_base import SparkKnowledgeBase

kb = SparkKnowledgeBase()

# Add article
kb.add_article(
    title="Multi-Channel Detection Setup",
    content="To configure multi-channel detection:\n1. ...",
    category="tutorials",
    keywords=["multi-channel", "channels", "setup", "configuration"],
    url="https://www.affiniteinstruments.com/docs/channels"
)

# Add FAQ
kb.add_faq(
    question="What buffer should I use?",
    answer="We recommend PBS or HEPES...",
    category="faqs",
    url="https://www.affiniteinstruments.com/faqs"
)
```

### Content Categories

- **getting-started** - First-time user guides
- **calibration** - Calibration procedures
- **troubleshooting** - Error resolution
- **tutorials** - Step-by-step guides
- **product-features** - Product capabilities
- **faqs** - Frequently asked questions
- **support** - Contact and support info

### Search Scoring Algorithm

```python
score = 0
if any(keyword in question for keyword in keywords):
    score += 3.0  # Keyword match
if search_term in title.lower():
    score += 2.0  # Title match
if search_term in content.lower():
    score += 1.0  # Content match

# Return article if score > 2.0
```

---

## Training & Improving Spark

### Approach 1: Fine-tune Regex Patterns (Immediate)

**Goal:** Add more instant-answer patterns based on real user questions.

**Process:**
1. **Analyze unmatched questions:**
```bash
python analyze_spark_data.py
# Look for "Common Unmatched Questions" section
```

2. **Cluster similar questions:**
```python
# Example: Questions about titration
- "how do i run a titration?"
- "what's the titration procedure?"
- "titration steps?"

# Create pattern:
"titration": {
    "regex": r'titration|concentration series|dose response',
    "answer": "To run a titration:\n1. ..."
}
```

3. **Add to `spark_pattern_matcher.py`**

**Benefits:**
- Zero latency (<1ms)
- Perfect accuracy
- No model size increase

### Approach 2: Fine-tune TinyLlama (Advanced, GPU Required)

**Goal:** Improve AI model for complex/conversational questions.

**Training Data:**
```python
# Export Q&A history
from export_spark_transcript import export_to_json
export_to_json("training_data.json")

# Filter for high-quality data
training_data = [
    q for q in qa_history
    if q['feedback'] == 'helpful' or q['matched'] == False
]
```

**Training Framework:**
```python
from transformers import AutoModelForCausalLM, TrainingArguments, Trainer
from peft import LoraConfig, get_peft_model

# Load base model
model = AutoModelForCausalLM.from_pretrained("TinyLlama/TinyLlama-1.1B-Chat-v1.0")

# Add LoRA adapters (efficient fine-tuning)
lora_config = LoraConfig(
    r=16,  # Rank
    lora_alpha=32,
    target_modules=["q_proj", "v_proj"],
    lora_dropout=0.05,
)
model = get_peft_model(model, lora_config)

# Train
trainer = Trainer(
    model=model,
    args=TrainingArguments(
        output_dir="./spark_finetuned",
        num_train_epochs=3,
        per_device_train_batch_size=4,
        learning_rate=2e-4,
    ),
    train_dataset=spark_dataset,
)
trainer.train()

# Save and deploy
model.save_pretrained("./spark_model_v2")
```

### Approach 3: Build Custom Retrieval Model (Medium Effort)

**Goal:** Train specialized Q&A retrieval model.

```python
from sentence_transformers import SentenceTransformer, InputExample

# 1. Fine-tune sentence encoder
model = SentenceTransformer('all-MiniLM-L6-v2')  # 80MB (vs 637MB)
train_examples = [
    InputExample(texts=[q['question'], q['answer']])
    for q in qa_history
]
model.fit(train_examples)

# 2. For new questions, find most similar and return answer
embeddings = model.encode([q['question'] for q in qa_history])
# Use cosine similarity to match
```

**Benefits:**
- Much smaller (80MB vs 637MB)
- Faster inference
- Better at exact answer retrieval

### Data Pipeline

**Step 1: Export**
```bash
python export_spark_transcript.py
# Creates: spark_transcript.json, spark_transcript.csv
```

**Step 2: Clean & Filter**
```python
import json
with open('spark_qa_history.json') as f:
    data = json.load(f)

# Filter high-quality data
quality_data = [
    q for q in data['questions_answers'].values()
    if q['feedback'] == 'helpful' or len(q['answer']) > 50
]
```

**Step 3: Train**
- See approaches above

**Step 4: Deploy**
- Replace model in `spark_tinylm.py`
- Test thoroughly
- Update version number

### Training Milestones

| Month | Q&A Entries | Status |
|-------|-------------|--------|
| Month 1 | 0-50 | Collect data, refine patterns |
| Month 2 | 50-100 | Analyze common questions, add patterns |
| Month 3 | 100-250 | Build knowledge base content |
| Month 6 | 500-1000+ | Ready for TinyLlama fine-tuning |

---

## Database Schema

### Q&A History (`spark_qa_history.json`)

```json
{
  "questions_answers": {
    "1": {
      "timestamp": "2026-02-02T20:30:00.000000",
      "question": "how do i start an acquisition",
      "answer": "To start an acquisition:\n1. ...",
      "matched": true,
      "feedback": "helpful"
    }
  }
}
```

**Fields:**
- `timestamp` - ISO datetime
- `question` - User's original question
- `answer` - Spark's response
- `matched` - true=pattern match, false=AI-generated
- `feedback` - null, "helpful", or "not_helpful"

### Knowledge Base (`spark_knowledge_base.json`)

```json
{
  "articles": {
    "1": {
      "title": "How to Run an SPR Assay",
      "content": "Step-by-step guide...",
      "category": "tutorials",
      "keywords": ["assay", "run", "start"],
      "url": "https://...",
      "last_updated": "2026-02-02T10:30:00"
    }
  }
}
```

---

## Testing

### Running Tests

```bash
# Full test suite
python test_spark.py

# Pattern matching tests only
python test_spark.py TestSparkPatternMatcher

# Performance benchmarks
python test_spark.py TestSparkIntegration.test_performance
```

### Test Coverage

**Unit Tests:**
- SparkPatternMatcher (13 tests)
- SparkAnswerEngine (5 tests)
- SparkQuestionStorage (4 tests)

**Integration Tests:**
- End-to-end answer generation
- Threading and cleanup
- Database operations

### Manual Testing

```python
from affilabs.widgets.spark_answer_engine import SparkAnswerEngine

engine = SparkAnswerEngine()

# Test pattern matching
answer, matched = engine.generate_answer("how do i calibrate?")
print(f"Matched: {matched}")
print(f"Answer: {answer}")

# Test AI fallback
answer, matched = engine.generate_answer("complex question here")
print(f"AI Generated: {not matched}")
```

---

## Deployment

### Installation Dependencies

**Required:**
```bash
pip install transformers torch PySide6 tinydb
```

**Optional (for training):**
```bash
pip install sentence-transformers peft bitsandbytes
```

### Model Files

- **Location:** Auto-downloaded to cache on first use
- **Size:** ~637 MB
- **Cache:** `~/.cache/huggingface/` (Linux/Mac) or `C:\Users\<user>\.cache\huggingface\` (Windows)

### Bundling with Installer

**Option 1: Download on first use** (current)
- Smaller installer
- Requires internet on first AI use

**Option 2: Bundle model weights**
- Larger installer (+637 MB)
- Fully offline capable

---

## Performance Optimization

### Benchmarks

| Operation | Target | Actual |
|-----------|--------|--------|
| Pattern matching | <1ms | ~0.5ms |
| AI first load | <30s | 10-25s |
| AI generation | <5s | 2-4s |
| Database query | <5ms | 1-3ms |
| UI update | <100ms | <50ms |

### Optimization Tips

**1. Add More Patterns**
- Move frequently asked AI questions to patterns
- Instant responses instead of 2-5 second AI calls

**2. Lazy Loading**
- AI model only loads on first complex question
- Don't load if not needed

**3. Background Threading**
- Answer generation in separate thread
- UI remains responsive

**4. Database Indexing**
- TinyDB auto-indexes
- Fast queries even with 10,000+ entries

**5. GPU Acceleration**
- Auto-detects CUDA
- 5-10x faster AI generation with GPU

---

## Quick Reference

### Common Tasks

**Check pattern match coverage:**
```bash
python analyze_spark_data.py
```

**Add feedback manually:**
```python
from affilabs.widgets.spark_help_widget import SparkQuestionStorage
storage = SparkQuestionStorage()
doc_id = storage.log_question("Q", "A", matched=True)
storage.update_feedback(doc_id, "helpful")
```

**Get all topics:**
```python
from affilabs.widgets.spark_answer_engine import SparkAnswerEngine
engine = SparkAnswerEngine()
topics = engine.get_supported_topics()
```

**Enable debug logging:**
```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

### File Locations

| File | Purpose |
|------|---------|
| `spark_pattern_matcher.py` | Add/edit patterns |
| `spark_answer_engine.py` | Modify answer logic |
| `spark_help_widget.py` | UI changes |
| `spark_tinylm.py` | AI model config |
| `spark_knowledge_base.py` | Website content |
| `spark_qa_history.json` | Q&A database |

### Performance Targets

- Pattern matching: **<1ms**
- AI generation: **2-5s** (after load)
- Database operations: **<5ms**
- UI updates: **<100ms**

---

## Support

**Developer Questions:**
- Email: info@affiniteinstruments.com
- Docs: https://www.affiniteinstruments.com/docs

**See also:**
- [SPARK_GUIDE.md](SPARK_GUIDE.md) - User guide
- [SPARK_QUICK_REF.md](../SPARK_QUICK_REF.md) - Quick reference
