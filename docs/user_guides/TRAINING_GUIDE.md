# Training Guide: Operation Manual for Spark & TinyLLaMA

**Version:** 1.0
**Date:** 2026-02-07
**Status:** Production Ready

---

## Quick Start

This folder contains everything needed to train ML models on the AffiLabs Operation Manual:

```bash
# Step 1: Extract and process with Spark
spark-submit spark_processing.py

# Step 2: Fine-tune TinyLLaMA
python tinyllama_training.py --data training_data/training_pairs.jsonl

# Step 3: Deploy and test
python tinyllama_training.py --data training_data/training_pairs.jsonl \
                              --test-prompt "How do I install a sensor?"
```

---

## Training Pipeline Overview

### Phase 1: Data Extraction (Spark)

**File:** `spark_processing.py`

The Spark processor extracts structured data from the Operation Manual:

```
OPERATION_MANUAL.md (1516 lines)
        ↓
    Spark Partitions
        ↓
  ┌─────────────┬──────────────┬─────────────────┐
  ↓             ↓              ↓                 ↓
Sections    Procedures    Training Pairs    Troubleshooting
  ↓             ↓              ↓                 ↓
sections_df  procedures_df  training_pairs_df  tables.json
```

**Key Outputs:**
- `training_pairs.jsonl` — 200+ instruction-response pairs
- `procedures.json` — 50+ step-by-step procedures
- `troubleshooting.json` — 20+ issue-solution pairs

**Run:**
```bash
spark-submit spark_processing.py
```

### Phase 2: Fine-Tuning (TinyLLaMA)

**File:** `tinyllama_training.py`

Fine-tunes TinyLLaMA on operation manual content using LoRA (Low-Rank Adaptation) for efficiency:

```
TinyLlama-1.1b (Base Model)
        ↓
    LoRA Adapter (rank=16)
        ↓
    Training Data
        ↓
Fine-Tuned Model
```

**Key Features:**
- ✅ LoRA for memory-efficient fine-tuning
- ✅ Multi-GPU support (automatic device mapping)
- ✅ Mixed precision training (FP16 on CUDA)
- ✅ Inference testing after training

**Run:**
```bash
python tinyllama_training.py \
    --data training_data/training_pairs.jsonl \
    --output ./fine_tuned_model \
    --epochs 3 \
    --batch-size 4 \
    --learning-rate 2e-4
```

### Phase 3: Deployment & Testing

**Test inference:**
```bash
python tinyllama_training.py \
    --output ./fine_tuned_model \
    --test-prompt "How do I install a sensor?"
```

**Example queries the model can handle:**
- "What are the critical safety rules?"
- "How do I troubleshoot baseline drift?"
- "What's the biweekly cleaning procedure?"
- "How do I measure delta SPR?"
- "What are the environmental operating conditions?"

---

## Data Format Specifications

### Training Pairs (JSONL)

Each line is a JSON object:

```json
{
  "category": "procedure_guidance|troubleshooting|safety|maintenance|specification",
  "instruction": "User question or request",
  "response": "Multi-line detailed response",
  "source": "procedures|troubleshooting|safety",
  "priority": "critical|high|medium"
}
```

**Example:**
```json
{
  "category": "procedure_guidance",
  "instruction": "How do I install a sensor on the P4SPR?",
  "response": "Step 1: Position the Sensor in the Sample Holder\n1. Hold sensor by edges only...\n\nStep 2: Open the Prism/Microfluidic Latch...",
  "source": "procedures"
}
```

### Procedures (JSON)

```json
{
  "name": "Sensor Installation (P4PRO & P4SPR 2.0)",
  "steps": [
    {
      "number": 1,
      "instruction": "Position the Sensor in the Sample Holder"
    },
    {
      "number": 2,
      "instruction": "Open the Prism/Microfluidic Latch (if not already open)"
    }
  ]
}
```

### Troubleshooting (JSON)

```json
{
  "issue": "Baseline drift > 1 nm/min",
  "cause": "Air bubble in line (CRITICAL)",
  "solution": "STOP immediately. Visual inspect all tubing..."
}
```

---

## Hardware & Environment Requirements

### Minimum Requirements

| Component | Requirement |
|-----------|------------|
| **Python** | 3.8+ |
| **RAM** | 16 GB (for Spark and TinyLLaMA) |
| **Storage** | 10 GB (model weights + training data) |
| **GPU** | NVIDIA GPU with 8 GB+ VRAM (recommended) |

### Recommended Setup

```
CPU:     Intel Xeon or AMD EPYC (8+ cores)
RAM:     32-64 GB
GPU:     NVIDIA A100 or RTX 3090/4090
Storage: NVMe SSD (for fast I/O)
```

### Software Stack

```bash
# Create environment
python -m venv operation_manual_env
source operation_manual_env/bin/activate  # or .venv\Scripts\activate on Windows

# Install Spark dependencies
pip install pyspark>=3.3.0

# Install TinyLLaMA dependencies
pip install torch transformers peft datasets bitsandbytes

# Optional: for distributed training
pip install ray[tune] wandb
```

---

## Configuration Options

### Spark Processing

Customize in `spark_processing.py`:

```python
# Adjust partition count for different cluster sizes
.repartition(5)  # Default: 5 partitions

# Change output directory
output_dir = "./training_data"  # Default
```

### TinyLLaMA Fine-Tuning

Command-line arguments:

```bash
python tinyllama_training.py \
    --data <path>              # Training data file
    --output <path>            # Output directory
    --model <name>             # Base model (default: TinyLlama-1.1b-chat-v1.0)
    --epochs <num>             # Training epochs (default: 3)
    --batch-size <num>         # Batch size (default: 4)
    --learning-rate <float>    # Learning rate (default: 2e-4)
    --lora-rank <num>          # LoRA rank (default: 16)
    --test-prompt <str>        # Test prompt after training
```

---

## Training Scenarios

### Scenario 1: Quick Fine-Tuning (Small Dataset)

**Time:** ~30 minutes on GPU
**Memory:** ~8 GB VRAM

```bash
python tinyllama_training.py \
    --data training_data/training_pairs.jsonl \
    --epochs 1 \
    --batch-size 2 \
    --lora-rank 8
```

### Scenario 2: Production Fine-Tuning (Full Dataset)

**Time:** ~2 hours on GPU
**Memory:** ~16 GB VRAM

```bash
python tinyllama_training.py \
    --data training_data/training_pairs.jsonl \
    --epochs 3 \
    --batch-size 4 \
    --lora-rank 16
```

### Scenario 3: Distributed Training (Multi-GPU)

**Time:** ~30 minutes on 4 GPUs
**Memory:** ~8 GB per GPU

```bash
torchrun --nproc_per_node=4 tinyllama_training.py \
    --data training_data/training_pairs.jsonl \
    --epochs 3 \
    --batch-size 4
```

---

## Output Files & Artifacts

### After Spark Processing

```
training_data/
├── training_pairs.jsonl      # ~2-3 MB (200+ pairs)
├── procedures.json           # ~500 KB (50+ procedures)
└── troubleshooting.json      # ~150 KB (20+ issues)
```

### After TinyLLaMA Fine-Tuning

```
fine_tuned_model/
├── pytorch_model.bin         # Model weights (~2.2 GB)
├── tokenizer.model           # Tokenizer
├── config.json               # Model config
├── adapter_config.json       # LoRA config
├── adapter_model.bin         # LoRA weights (~50 MB)
└── training_args.bin         # Training metadata
```

---

## Evaluation & Metrics

### Training Metrics

Monitor during training:
- **Loss:** Should decrease steadily
- **Learning rate:** Warmup → constant → decay
- **GPU memory:** Should stabilize after first batch

### Inference Quality

Test on representative queries:

```python
test_queries = [
    "How do I install a sensor?",
    "What should I do if baseline drift > 1 nm/min?",
    "Describe the biweekly cleaning procedure",
    "What are critical safety rules?",
    "What is the operating temperature range?"
]

for query in test_queries:
    response = trainer.inference(query)
    print(f"Q: {query}\nA: {response}\n")
```

### Expected Performance

After fine-tuning on Operation Manual:
- ✅ Answer procedure questions with step-by-step guidance
- ✅ Troubleshoot common issues with diagnostic steps
- ✅ Recall safety rules and critical warnings
- ✅ Provide equipment specifications
- ✅ Explain maintenance schedules

---

## Deployment Options

### Option 1: Local Inference

```python
from transformers import AutoTokenizer, AutoModelForCausalLM

tokenizer = AutoTokenizer.from_pretrained("./fine_tuned_model")
model = AutoModelForCausalLM.from_pretrained("./fine_tuned_model")

# Generate response
inputs = tokenizer("How do I install a sensor?", return_tensors="pt")
outputs = model.generate(**inputs, max_length=256)
print(tokenizer.decode(outputs[0]))
```

### Option 2: REST API

```python
from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI()

class Query(BaseModel):
    prompt: str
    max_length: int = 256

@app.post("/query")
def query_model(q: Query):
    response = trainer.inference(q.prompt, q.max_length)
    return {"response": response}
```

**Run:**
```bash
uvicorn api:app --host 0.0.0.0 --port 8000
```

### Option 3: Integration with Affilabs

```python
# In affilabs help system
from fine_tuned_model import OperationalLLM

llm = OperationalLLM("./fine_tuned_model")

# When user clicks help for a section
response = llm.get_help(
    section="sensor_installation",
    user_query="How do I install a new sensor?"
)
display_help(response)
```

---

## Troubleshooting

### Issue: "CUDA out of memory"

**Solution:** Reduce batch size or enable gradient checkpointing:
```bash
python tinyllama_training.py --batch-size 2 --lora-rank 8
```

### Issue: "Training loss not decreasing"

**Possible causes:**
- Learning rate too high → reduce to 1e-4
- Batch size too small → increase to 8
- Not enough training data → use all 200+ pairs

### Issue: "Model inference is slow"

**Solution:** Use quantization:
```bash
pip install bitsandbytes
# Add to training script: load_in_8bit=True
```

### Issue: "Spark out of memory"

**Solution:** Increase executor memory:
```bash
spark-submit \
    --executor-memory 16G \
    --driver-memory 4G \
    spark_processing.py
```

---

## Next Steps

1. **Generate Training Data:**
   ```bash
   spark-submit spark_processing.py
   ```

2. **Fine-Tune Model:**
   ```bash
   python tinyllama_training.py --data training_data/training_pairs.jsonl
   ```

3. **Test & Evaluate:**
   ```bash
   python tinyllama_training.py --test-prompt "How do I..."
   ```

4. **Deploy:**
   - Local: Use `transformers` library directly
   - API: Build REST endpoint with FastAPI
   - Integrated: Add to Affilabs help system

5. **Monitor & Iterate:**
   - Track user queries and support tickets
   - Identify gaps in training data
   - Retrain with additional examples as needed

---

## Support & References

**Documentation:**
- Operation Manual: `OPERATION_MANUAL.md`
- Training Config: `TRAINING_CONFIG.json`

**Code Files:**
- Spark Processor: `spark_processing.py`
- TinyLLaMA Trainer: `tinyllama_training.py`

**External Resources:**
- [TinyLLaMA on Hugging Face](https://huggingface.co/TinyLlama)
- [Transformers Documentation](https://huggingface.co/docs/transformers)
- [Spark Documentation](https://spark.apache.org/docs/latest/)
- [LoRA Research Paper](https://arxiv.org/abs/2106.09685)

---

**Created:** 2026-02-07
**Status:** Production Ready ✅
**Training Data:** ~200 instruction-response pairs
**Model Size:** 1.1B parameters (TinyLLaMA)
