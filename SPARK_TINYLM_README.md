# Spark AI Assistant - Technical Documentation

## Overview

Spark AI assistant uses **hybrid intelligence** (transparent to users):
- **Fast path**: Regex patterns for common questions (<1ms)
- **Smart path**: Conversational AI for complex questions (1-3s)

**Important**: Users only see "Spark" - they don't know about the underlying TinyLlama model. All technical details are hidden.

## Architecture

```
User Question
    ↓
Pattern Matching (fast)
    ↓
Match? → Yes → Return answer
    ↓
    No
    ↓
TinyLM (conversational)
    ↓
Generate focused answer
```

## Installation (Bundled with Software)

### Required Dependencies (Included in Install Package)

```bash
# These are bundled with ezControl installer
pip install transformers torch
```

### Model Files

- TinyLlama-1.1B model (~637 MB) bundled in install package
- First run extracts model to app data directory
- Users never see technical loading details

### Verify Installation

```bash
# Developer test only
python test (User-Facing)

### 1. **Instant Answers** 
Common questions answered immediately:
- "How do I start an acquisition?"
- "How do I export data?"
- "How do I calibrate?"
- "How do I build methods?"
- "How do I control channels?"

### 2. **Smart Conversations**
Complex questions handled intelligently:
- "What's the difference between association and dissociation?"
- "Can you explain how to optimize flow rates?"
- "What should I do if my baseline is unstable?"
- "How do I troubleshoot noisy data?"

### 3. **Transparent Loading** (User Never Sees This)
- Model loads silently on first use
- No progress bars or technical messages
- Users just see "Spark is thinking..." (if needed)
- Brief pause on first complex question only

### 4. **Focused on SPR**
All responses stay focused:
- No general chat capabilities
- Only ezControl SPRtext**
TinyLM receives narrow, SPR-specific context:
- No general conversation
- Focus on ezControl operations
- Practical, concise answers (2-3 sentences)

## Usage

### In the Application (User Experience)

1. User opens Help tab
2. Sees Spark chat interface
3. Asks any question
4. Spark responds:
   - Instant for common questions
   - Brief pause for first complex question (model loading silently)
   - Fast for all subsequent questions
   
**User never sees**: "Loading TinyLlama", "Model initializing", or any technical details

### Q&A Logging

All questions and answers logged to `spark_qa_history.json` for:
- Analytics
- Improving pattern matching
- Identifying  (Internal - Not User-Visible)

| Feature | Speed | Memory | User Experience |
|---------|-------|--------|-----------------|
| Regex patterns | <1ms | ~0 MB | Instant answer |
| Model first load | 10-30s | 637 MB | "Thinking..." (silent) |
| AI responses | 1-3s | 637 MB | Natural pause
| TinyLM first load | 10-30s | 637 MB | One-time per session |
| TinyLM responses | 1-3s | 637 MB | After initial load |

## Development Notes

### Files Modified

1. **`affilabs/widgets/spark_help_widget.py`**
   - Added TinyLM import and initialization
   - Modified `_generate_answer()` for hybrid approach
   - Kept all existing regex patterns

2. **`affilabs/widgets/spark_tinylm.py`** (NEW)
   - TinyLM model management
   - Context builder
   - Response generator

3. **`test_spark_tinylm.py`** (NEW)
   - Test script for verification

### Adding More Patterns

To add fast-path patterns, edit `spark_help_widget.py`:

```python
# In _generate_answer() method
elif re.search(r'your|pattern|here', question_lower):
    return (
        "Your helpful answer here\n\n"
        "1. Step one\n"
        "2. Step two",
        True
    )
```

### Customizing TinyLM Context

To improve TinyLM answers, edit `spark_tinylm.py`:

```python
# In _build_context() method
if any(word in question_lower for word in ['keyword1', 'keyword2']):
    context += (
        "Additional documentation here. "
    )
```

## Troubleshooting

### "ModuleNotFoundError: No module named 'transformers'"
- TinyLM dependencies not installed
- Spark still works with regex patterns only
- Install optional: `pip install transformers torch`

### "CUDA out of memory"
- Using GPU but insufficient memory
- Edit `spark_tinylm.py` line 69: force CPU
  ```python
  device = "cpu"  # Force CPU instead of auto-detect
  ```

### "Model loading takes too long"
- First load downloads 637 MB model
- Subsequent loads are instant (cached)
- Use fast internet connection for first run

### "Answers are too generic"
- TinyLM needs more context
- Edit `_build_context()` in `spark_tinylm.py`
- Add more specific SPR/ezControl documentation

## Future Enhancements

- [ ] Fine-tune TinyLlama on ezControl documentation
- [ ] Add more regex patterns from Q&A logs
- [ ] Implement feedback loop (thumbs up/down)
- [ ] Export Q&A analytics dashboard
- [ ] Support multiple languages

## Support

For issues or questions:
- Email: info@affiniteinstruments.com
- Check `spark_qa_history.json` for logged questions
- Review TinyLM logs for model errors
