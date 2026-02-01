# Spark AI Training Database Guide

## Current Database Structure

**File:** `spark_qa_history.json` (TinyDB format)

**Schema:**
```json
{
  "questions_answers": {
    "1": {
      "timestamp": "2026-01-31T21:40:37.271985",
      "question": "how do i start an acquisition",
      "answer": "To start an acquisition...",
      "matched": true,  // true = regex pattern match, false = TinyLM generated
      "feedback": null  // Can be: null, "helpful", "not_helpful"
    }
  }
}
```

## Database Fields

| Field | Type | Description | Use for Training |
|-------|------|-------------|------------------|
| `timestamp` | ISO datetime | When question was asked | Time-based analytics, trend analysis |
| `question` | string | User's original question | Training input (X) |
| `answer` | string | Spark's response | Training output (y) |
| `matched` | boolean | Pattern matched (true) or AI-generated (false) | Quality indicator, filtering |
| `feedback` | string/null | User feedback on answer quality | Supervised learning labels |

## Training Approaches

### 1. **Fine-tune Regex Patterns** (Immediate, Low Cost)

**Goal:** Improve pattern matching to handle more questions instantly (<1ms)

**Training Data:**
```python
# Extract common patterns from matched questions
matched_questions = [q for q in db if q['matched'] == True]

# Cluster similar questions
- "how do i start an acquisition"
- "how do i start an acquisitionn"  (typo)
- "what are the steps to start an experiment"
→ Pattern: r'start|begin|run|experiment'
```

**Output:** Update pattern matching in `spark_help_widget.py`

**Benefits:**
- Zero latency
- No model size increase
- Perfect accuracy for common questions

---

### 2. **Fine-tune TinyLlama** (Advanced, GPU Required)

**Goal:** Improve conversational AI for complex questions

**Training Data Format:**
```python
# Convert to instruction-tuning format
training_examples = []
for entry in db:
    if entry['feedback'] == 'helpful' or entry['matched'] == False:
        training_examples.append({
            "instruction": "You are Spark, an AI assistant for ezControl SPR software. Answer briefly and focus on ezControl operations.",
            "input": entry['question'],
            "output": entry['answer']
        })
```

**Training Framework:**
- Hugging Face Transformers
- LoRA (Low-Rank Adaptation) for efficiency
- QLoRA for 4-bit quantization

**Training Script Example:**
```python
from transformers import AutoModelForCausalLM, TrainingArguments, Trainer
from peft import LoraConfig, get_peft_model

# Load base model
model = AutoModelForCausalLM.from_pretrained("TinyLlama/TinyLlama-1.1B-Chat-v1.0")

# Add LoRA adapters
lora_config = LoraConfig(
    r=16,  # Rank
    lora_alpha=32,
    target_modules=["q_proj", "v_proj"],
    lora_dropout=0.05,
)
model = get_peft_model(model, lora_config)

# Train on your Q&A data
trainer = Trainer(
    model=model,
    args=TrainingArguments(...),
    train_dataset=spark_dataset,
)
trainer.train()
```

---

### 3. **Build Custom Small Model** (Medium Effort)

**Goal:** Train a specialized ezControl Q&A model from scratch

**Approach:** Sentence-BERT + Classification
```python
from sentence_transformers import SentenceTransformer, InputExample, losses

# 1. Extract all Q&A pairs
qa_pairs = [(q['question'], q['answer']) for q in db]

# 2. Fine-tune sentence encoder
model = SentenceTransformer('all-MiniLM-L6-v2')  # 80MB model
train_examples = [InputExample(texts=[q, a]) for q, a in qa_pairs]

# 3. For new questions, find most similar and return answer
from sklearn.metrics.pairwise import cosine_similarity
embeddings = model.encode([q for q, _ in qa_pairs])
# Match new question to closest training example
```

**Benefits:**
- Much smaller than TinyLlama (80MB vs 637MB)
- Faster inference
- Better at retrieving exact answers

---

## Data Preparation Pipeline

### Step 1: Export Training Data

```python
from export_spark_transcript import export_to_json, export_to_csv

# Export all data
export_to_json("training_data.json")
export_to_csv("training_data.csv")
```

### Step 2: Clean and Filter

```python
import json
from collections import Counter

# Load data
with open("training_data.json") as f:
    data = json.load(f)

# Filter quality data
training_set = []
for entry in data:
    # Skip if:
    # - No answer
    # - Feedback marked as "not_helpful"
    # - Duplicate questions
    if entry['answer'] and entry['feedback'] != 'not_helpful':
        training_set.append(entry)

# Find most common questions (good candidates for regex)
question_freq = Counter([q['question'].lower() for q in training_set])
top_questions = question_freq.most_common(20)
```

### Step 3: Augment Data (Optional)

Generate variations to increase dataset size:
```python
import random

augmentation_templates = [
    "How can I {verb}?",
    "What's the best way to {verb}?",
    "I need help with {noun}",
    "{verb} not working",
]

# Example: "start acquisition" → multiple variations
# - "How can I start acquisition?"
# - "start acquisition not working"
```

---

## Training Workflow Recommendations

### **Immediate (Week 1):**
1. ✅ **Already done:** Logging all Q&A to `spark_qa_history.json`
2. Export current data using `export_spark_transcript.py`
3. Analyze top 20 questions manually
4. Add 5-10 new regex patterns for most common questions
5. Test improved response time

### **Short-term (Month 1-2):**
1. Collect 100-500 Q&A pairs from real users
2. Add user feedback buttons (👍/👎) to Spark UI
3. Use feedback to identify which answers need improvement
4. Fine-tune regex patterns monthly

### **Long-term (Month 3-6):**
1. Accumulate 500-1000+ Q&A pairs
2. Fine-tune TinyLlama with LoRA on high-quality subset
3. Deploy updated model (replace existing TinyLlama weights)
4. A/B test: old model vs new model performance

---

## Monitoring & Improvement Loop

```
User asks question
    ↓
Spark answers (regex or TinyLM)
    ↓
Log to database
    ↓
[Weekly] Analyze unmatched questions
    ↓
[Monthly] Update regex patterns
    ↓
[Quarterly] Fine-tune TinyLM if dataset > 500 examples
    ↓
Deploy improved model
```

---

## Sample Training Code

### Extract Training Data:
```python
from tinydb import TinyDB

db = TinyDB("spark_qa_history.json")
qa_table = db.table('questions_answers')
all_data = qa_table.all()

# Prepare for fine-tuning
training_data = []
for entry in all_data:
    # Only use high-quality answers
    if entry.get('matched') or entry.get('feedback') == 'helpful':
        training_data.append({
            'prompt': entry['question'],
            'completion': entry['answer']
        })

# Save in format for your chosen training framework
import json
with open('spark_training_set.jsonl', 'w') as f:
    for item in training_data:
        f.write(json.dumps(item) + '\n')
```

---

## Database Size Expectations

| Timeframe | Expected Entries | Training Readiness |
|-----------|-----------------|-------------------|
| Week 1 | 10-50 | ❌ Too small - focus on regex |
| Month 1 | 100-200 | ⚠️ Can start pattern analysis |
| Month 3 | 300-500 | ✅ Ready for small model training |
| Month 6 | 500-1000+ | ✅ Ready for TinyLlama fine-tuning |

---

## Current Database Status

**Your current database has:**
- 10 Q&A entries
- Mix of pattern-matched and general questions
- No feedback data yet

**Recommendations:**
1. ✅ Keep logging (already implemented)
2. Add feedback buttons to Spark UI
3. Aim for 100+ entries before first training iteration
4. Monthly review of unmatched questions to improve patterns

---

## Next Steps

1. **Add feedback UI:** Let users rate answers (👍/👎)
2. **Monitor usage:** Check database weekly with `export_spark_transcript.py`
3. **First training:** When you hit 100-200 entries, analyze patterns
4. **Fine-tune:** At 500+ entries with feedback, fine-tune TinyLlama

Would you like me to implement the feedback buttons in the Spark UI?
