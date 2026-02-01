"""TinyLM integration module for Spark AI assistant

Provides conversational AI capabilities using TinyLlama-1.1B model.
This module handles lazy loading, context building, and response generation.
Model details are kept internal - users just see "Spark" working.
"""

import logging
from transformers import AutoTokenizer, AutoModelForCausalLM, pipeline
import torch

logger = logging.getLogger(__name__)


class SparkTinyLM:
    """TinyLM integration for Spark AI assistant.
    
    Provides conversational AI fallback when pattern matching doesn't work.
    Uses lazy loading - model only loads when first needed.
    """
    
    def __init__(self):
        """Initialize TinyLM (lazy loading - model loads on first use).
        
        Model details kept internal - users don't see technical loading info.
        """
        self._model = None
        self._tokenizer = None
        self._pipeline = None
        self._loading = False
        self._initialized = False
    
    def is_initialized(self) -> bool:
        """Check if TinyLM model is loaded."""
        return self._initialized
    
    def _load_model(self):
        """Load TinyLlama model (called on first use).
        
        Silent loading - no user-visible messages about technical details.
        """
        if self._loading:
            logger.debug("Model already loading...")
            return False
            
        if self._initialized:
            logger.debug("Model already loaded")
            return True
        
        try:
            self._loading = True
            logger.debug("Loading Spark AI model...")
            
            # Detect device (prefer GPU if available, silent fallback to CPU)
            device = "cuda" if torch.cuda.is_available() else "cpu"
            logger.debug(f"Using device: {device}")
            
            # Load model and tokenizer
            model_name = "TinyLlama/TinyLlama-1.1B-Chat-v1.0"
            
            self._tokenizer = AutoTokenizer.from_pretrained(model_name)
            self._model = AutoModelForCausalLM.from_pretrained(
                model_name,
                torch_dtype=torch.float16 if device == "cuda" else torch.float32,
                low_cpu_mem_usage=True
            )
            self._model.to(device)
            
            # Create text generation pipeline
            self._pipeline = pipeline(
                "text-generation",
                model=self._model,
                tokenizer=self._tokenizer,
                device=0 if device == "cuda" else -1,
                max_new_tokens=150,
                temperature=0.7,
                do_sample=True,
                top_p=0.9,
            )
            
            self._initialized = True
            logger.debug("Spark AI model ready")
            return True
            
        except Exception as e:
            logger.error(f"Failed to load Spark AI model: {e}")
            self._initialized = False
            return False
        finally:
            self._loading = False
    
    def _build_context(self, question: str) -> str:
        """Build focused context for the question.
        
        Args:
            question: User's question
            
        Returns:
            Relevant documentation context (narrow, focused on SPR software)
        """
        question_lower = question.lower()
        
        # Base context (always included)
        context = (
            "ezControl is SPR (Surface Plasmon Resonance) analysis software. "
            "It controls optical detectors, pumps, valves, and records real-time binding data. "
        )
        
        # Add specific context based on question keywords
        if any(word in question_lower for word in ['start', 'run', 'acquire', 'record', 'acquisition']):
            context += (
                "Acquisition: Start acquisition after calibration. Data appears on Full Sensorgram graph. "
                "Use Start Recording button in sidebar. "
            )
        
        if any(word in question_lower for word in ['calibrat', 'baseline', 'zero', 'optical']):
            context += (
                "Calibration: OEM LED Calibration in Settings tab calibrates optical detector. "
                "Takes 30-60 seconds. Baseline Capture creates reference during acquisition. "
            )
        
        if any(word in question_lower for word in ['method', 'cycle', 'queue', 'protocol']):
            context += (
                "Methods: Build cycle queues in Method tab. Add cycles (Baseline, Association, Dissociation). "
                "Set duration and concentration. Start Run executes the queue. Progress bar shows current cycle. "
            )
        
        if any(word in question_lower for word in ['export', 'save', 'file', 'csv', 'excel']):
            context += (
                "Export: Export tab saves data in CSV, Excel, or JSON format. "
                "Select channels (A/B/C/D) and export destination folder. "
            )
        
        if any(word in question_lower for word in ['pump', 'flow', 'valve', 'channel', 'inject']):
            context += (
                "Flow Control: Flow tab controls pumps and valves. "
                "Operations: Prime, Cleanup, Buffer, Inject. Set flow rates. "
                "Valves switch between channels A/B/C/D. "
            )
        
        if any(word in question_lower for word in ['graph', 'plot', 'display', 'chart']):
            context += (
                "Graphs: Full Sensorgram shows live data timeline. Active Cycle shows selected region. "
                "Graphic Display tab: grid, autoscale, colorblind mode, filters (None/Light Smoothing). "
            )
        
        if any(word in question_lower for word in ['error', 'problem', 'issue', 'troubleshoot', 'fix']):
            context += (
                "Troubleshooting: Check USB connection, run calibration for noisy data, "
                "verify detector wait time in Advanced Settings, use Emergency Stop for pump issues. "
            )
        
        return context.strip()
    
    def generate_answer(self, question: str) -> tuple[str, bool]:
        """Generate conversational answer using TinyLM.
        
        Args:
            question: User's question
            
        Returns:
            Tuple of (answer_text, success)
        """
        # Load model if needed (lazy loading)
        if not self._initialized:
            if not self._load_model():
                return (
                    "I'm still learning to answer that question. "
                    "Try asking about starting acquisitions, calibration, methods, export, or flow control.",
                    False
                )
        
        try:
            # Build context
            context = self._build_context(question)
            
            # Create prompt with system instructions
            prompt = f"""<|system|>
You are Spark, the helpful assistant for ezControl SPR analysis software.
You provide concise, practical answers about using the software.
Keep responses focused on ezControl features and workflows.
Use 2-3 sentences maximum. Be helpful and friendly.
<|user|>
{context}

User question: {question}
<|assistant|>
"""
            
            # Generate response (silent - no user notification)
            logger.debug("Generating conversational response...")
            response = self._pipeline(
                prompt,
                max_new_tokens=150,
                num_return_sequences=1,
                pad_token_id=self._tokenizer.eos_token_id,
            )
            
            # Extract answer
            full_text = response[0]['generated_text']
            
            # Split by assistant tag
            if '<|assistant|>' in full_text:
                answer = full_text.split('<|assistant|>')[-1].strip()
            else:
                answer = full_text[len(prompt):].strip()
            
            # Clean up
            answer = answer.replace('<|user|>', '').replace('<|system|>', '').strip()
            
            # Remove any trailing special tokens
            for token in ['<|', '|>', '</s>']:
                if token in answer:
                    answer = answer.split(token)[0].strip()
            
            # Validate answer quality
            if len(answer) < 10:
                raise ValueError("Answer too short")
            if len(answer) > 500:
                answer = answer[:500] + "..."
            
            logger.debug(f"Generated response ({len(answer)} chars)")
            return (answer, True)
            
        except Exception as e:
            logger.error(f"Response generation failed: {e}")
            return (
                "I'm having trouble understanding that question. "
                "Try asking about: starting acquisitions, calibration, building methods, "
                "exporting data, or controlling pumps and valves.",
                False
            )
