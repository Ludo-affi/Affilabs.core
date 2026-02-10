"""
TinyLLaMA Fine-Tuning for AffiLabs Operation Manual
===================================================

This script demonstrates how to fine-tune TinyLLaMA on the Operation Manual
for SPR system operation and support chatbot capabilities.

Usage:
    python tinyllama_training.py --data training_data/training_pairs.jsonl \
                                  --output fine_tuned_model

Requirements:
    - torch
    - transformers
    - peft (for LoRA fine-tuning)
    - datasets
    - bitsandbytes (optional, for quantization)
"""

import json
import argparse
from pathlib import Path
from typing import Dict, List

try:
    import torch
    from transformers import (
        AutoTokenizer,
        AutoModelForCausalLM,
        TrainingArguments,
        Trainer,
        DataCollatorForLanguageModeling
    )
    from peft import LoraConfig, get_peft_model
    from datasets import load_dataset
except ImportError:
    print("ERROR: Required packages not installed.")
    print("Install with: pip install torch transformers peft datasets")
    exit(1)


class OperationManualDataset:
    """Dataset loader for operation manual training pairs."""

    def __init__(self, data_file: str, tokenizer):
        self.data_file = Path(data_file)
        self.tokenizer = tokenizer
        self.pairs = self.load_pairs()

    def load_pairs(self) -> List[Dict]:
        """Load training pairs from JSONL file."""
        pairs = []
        with open(self.data_file, 'r', encoding='utf-8') as f:
            for line in f:
                if line.strip():
                    pairs.append(json.loads(line))
        print(f"✓ Loaded {len(pairs)} training pairs")
        return pairs

    def format_instruction(self, instruction: str, response: str) -> str:
        """Format instruction-response pair for LLM training."""
        prompt = f"<s>You are an expert operator of the AffiLabs.core SPR system.\n\n"
        prompt += f"Instruction: {instruction}\n\n"
        prompt += f"Response: {response}</s>"
        return prompt

    def prepare_dataset(self) -> Dict:
        """Prepare dataset for training."""
        texts = []
        for pair in self.pairs:
            text = self.format_instruction(
                pair['instruction'],
                pair['response']
            )
            texts.append(text)

        # Tokenize
        tokenized = self.tokenizer(
            texts,
            padding='max_length',
            max_length=512,
            truncation=True,
            return_tensors='pt'
        )

        return {
            'input_ids': tokenized['input_ids'],
            'attention_mask': tokenized['attention_mask']
        }


class TinyLLaMaTrainer:
    """Fine-tune TinyLLaMA on Operation Manual."""

    def __init__(self, model_name: str = "TinyLlama/TinyLlama-1.1b-chat-v1.0"):
        self.model_name = model_name
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        print(f"Using device: {self.device}")

        # Load tokenizer and model
        self.tokenizer = AutoTokenizer.from_pretrained(model_name)
        self.model = AutoModelForCausalLM.from_pretrained(
            model_name,
            torch_dtype=torch.float16 if self.device == "cuda" else torch.float32,
            device_map="auto"
        )

        # Set pad token
        self.tokenizer.pad_token = self.tokenizer.eos_token

    def setup_lora(self, r: int = 16, lora_alpha: int = 32):
        """Setup LoRA for efficient fine-tuning."""
        lora_config = LoraConfig(
            r=r,
            lora_alpha=lora_alpha,
            target_modules=["q_proj", "v_proj"],
            lora_dropout=0.05,
            bias="none",
            task_type="CAUSAL_LM"
        )

        self.model = get_peft_model(self.model, lora_config)
        print(f"✓ LoRA configured (rank={r}, alpha={lora_alpha})")

    def train(self,
              data_file: str,
              output_dir: str = "./fine_tuned_model",
              epochs: int = 3,
              batch_size: int = 4,
              learning_rate: float = 2e-4):
        """Fine-tune the model."""

        # Prepare dataset
        dataset = OperationManualDataset(data_file, self.tokenizer)
        prepared_data = dataset.prepare_dataset()

        # Training arguments
        training_args = TrainingArguments(
            output_dir=output_dir,
            num_train_epochs=epochs,
            per_device_train_batch_size=batch_size,
            learning_rate=learning_rate,
            save_steps=50,
            save_total_limit=3,
            logging_steps=10,
            warmup_steps=100,
            gradient_accumulation_steps=2,
            fp16=self.device == "cuda",
            remove_unused_columns=False,
        )

        # Data collator
        data_collator = DataCollatorForLanguageModeling(
            tokenizer=self.tokenizer,
            mlm=False
        )

        # Create trainer
        trainer = Trainer(
            model=self.model,
            args=training_args,
            data_collator=data_collator,
            train_dataset=prepared_data,
        )

        # Train
        print(f"\n🚀 Starting training...")
        trainer.train()

        # Save model
        self.model.save_pretrained(output_dir)
        self.tokenizer.save_pretrained(output_dir)
        print(f"✓ Model saved to {output_dir}")

    def inference(self, prompt: str, max_length: int = 256) -> str:
        """Generate response using fine-tuned model."""
        inputs = self.tokenizer(prompt, return_tensors="pt").to(self.device)

        with torch.no_grad():
            outputs = self.model.generate(
                **inputs,
                max_length=max_length,
                do_sample=True,
                top_p=0.95,
                top_k=50,
                temperature=0.7
            )

        return self.tokenizer.decode(outputs[0], skip_special_tokens=True)


def main():
    """Main training pipeline."""
    parser = argparse.ArgumentParser(
        description="Fine-tune TinyLLaMA on Operation Manual"
    )
    parser.add_argument(
        "--data",
        type=str,
        default="training_data/training_pairs.jsonl",
        help="Path to training data (JSONL format)"
    )
    parser.add_argument(
        "--output",
        type=str,
        default="./fine_tuned_model",
        help="Output directory for fine-tuned model"
    )
    parser.add_argument(
        "--model",
        type=str,
        default="TinyLlama/TinyLlama-1.1b-chat-v1.0",
        help="Base model name"
    )
    parser.add_argument(
        "--epochs",
        type=int,
        default=3,
        help="Number of training epochs"
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=4,
        help="Training batch size"
    )
    parser.add_argument(
        "--learning-rate",
        type=float,
        default=2e-4,
        help="Learning rate"
    )
    parser.add_argument(
        "--lora-rank",
        type=int,
        default=16,
        help="LoRA rank (for efficient fine-tuning)"
    )
    parser.add_argument(
        "--test-prompt",
        type=str,
        help="Test prompt for inference after training"
    )

    args = parser.parse_args()

    # Check data file exists
    if not Path(args.data).exists():
        print(f"ERROR: Data file not found: {args.data}")
        print("Run spark_processing.py first to generate training data")
        exit(1)

    # Initialize trainer
    print(f"📚 Loading model: {args.model}")
    trainer = TinyLLaMaTrainer(args.model)

    # Setup LoRA
    trainer.setup_lora(r=args.lora_rank)

    # Train
    trainer.train(
        data_file=args.data,
        output_dir=args.output,
        epochs=args.epochs,
        batch_size=args.batch_size,
        learning_rate=args.learning_rate
    )

    # Test inference
    if args.test_prompt:
        print(f"\n🧪 Testing inference...")
        print(f"Prompt: {args.test_prompt}")
        response = trainer.inference(args.test_prompt)
        print(f"Response: {response}\n")


if __name__ == "__main__":
    main()
