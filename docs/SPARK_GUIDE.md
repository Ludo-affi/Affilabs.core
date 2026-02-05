# Spark AI Assistant - User Guide

**Last Updated:** February 2, 2026
**Version:** 2.0 (Consolidated Documentation)

---

## Table of Contents

1. [What is Spark?](#what-is-spark)
2. [How to Use Spark](#how-to-use-spark)
3. [Common Questions](#common-questions)
4. [Features](#features)
5. [Tips for Best Results](#tips-for-best-results)
6. [Troubleshooting](#troubleshooting)

---

## What is Spark?

**Spark ⚡** is your built-in AI help assistant in ezControl. It answers questions about how to use the software, provides step-by-step guidance, and helps troubleshoot issues.

### How Spark Answers Questions

Spark uses a **3-layer hybrid system** (transparent to you):

1. **Instant Answers** - Common questions answered in milliseconds using pattern matching
2. **Knowledge Base** - Searches documentation and FAQs from our website
3. **AI Understanding** - For complex questions, uses conversational AI (TinyLlama model)

**You don't see these layers** - just ask your question naturally!

---

## How to Use Spark

### Opening Spark

1. Launch ezControl
2. Click the **Help** tab in the sidebar
3. Type your question in the chat box
4. Press **Enter** or click the **Ask Spark** button

### Example Questions

**Getting Started:**
- "How do I start an acquisition?"
- "How do I export data?"
- "What's a baseline cycle?"
- "How do I build a method?"

**Configuration:**
- "How do I calibrate the detector?"
- "How do I configure flow settings?"
- "How do I set up multi-channel detection?"

**Troubleshooting:**
- "Why is my baseline noisy?"
- "What does flow error mean?"
- "How do I fix detector issues?"

**Advanced:**
- "What's the difference between association and dissociation?"
- "How do I optimize flow rates?"
- "How do I run kinetics experiments?"

### Using @ Commands

Type `@spark` before your question for quick access:
```
@spark how do I run a titration?
@spark show me kinetics
@spark what's a full cycle?
```

---

## Common Questions

### Starting an Acquisition

**Q: How do I start data collection?**

A: To start an acquisition:
1. Open the **Acquisition** tab
2. Configure your cycle (Baseline, Association, etc.)
3. Set time and flow parameters
4. Click **Start Acquisition** button
5. Monitor real-time data in the graph

### Exporting Data

**Q: How do I export my results?**

A: To export data:
1. Complete your acquisition
2. Go to **File → Export**
3. Choose format (CSV, Excel, or ANIML)
4. Select data channels
5. Choose save location

### Building Methods

**Q: How do I create a reusable method?**

A: To build a method:
1. Go to **Method** tab
2. Add cycles to queue (Baseline, Association, Dissociation, etc.)
3. Configure each cycle's parameters
4. Click **Save Method** to reuse later
5. Load saved methods anytime from **Method Manager**

### Calibration

**Q: How do I calibrate the system?**

A: To calibrate:
1. Go to **Settings → Calibration**
2. Ensure system is clean and stable
3. Click **Run Calibration**
4. Wait for automatic calibration (~2 minutes)
5. Check calibration results
6. Save calibration to EEPROM

### Flow Control

**Q: How do I adjust flow rates?**

A: To control flow:
1. Open **Flow** tab
2. Set desired flow rate (μL/min)
3. Select channel (A, B, C, or Buffer)
4. Click **Set Flow** to apply
5. Monitor flow status in real-time

---

## Features

### 1. Instant Responses

Common questions are answered **immediately** (<1ms):
- Starting/stopping acquisition
- Exporting data
- Calibration procedures
- Method building basics
- Flow control
- Graph configuration

### 2. Conversational Understanding

Spark can handle:
- **Follow-up questions:** "What about buffer B?" after asking about buffer A
- **Vague questions:** "How?" after mentioning calibration
- **Complex queries:** "What's the difference between X and Y?"
- **Context awareness:** Remembers your last 3 questions

### 3. Helpful Feedback

After each answer:
- Click 👍 **Helpful** if the answer worked
- Click 👎 **Not Helpful** if you need more help

This helps improve Spark over time!

### 4. Offline Capability

Spark works **without internet** for:
- Pattern-based answers (instant)
- Knowledge base search (fast)
- AI answers (after first-time model load)

**First-time AI use:** ~10-30 seconds to load model (one-time per session)
**Subsequent AI answers:** ~2-5 seconds

---

## Tips for Best Results

### 1. Be Specific

❌ "How does it work?"
✅ "How do I start an acquisition?"

❌ "Issues"
✅ "Why is my baseline noisy?"

### 2. Use Keywords

Include relevant terms:
- "calibration," "baseline," "flow"
- "export," "data," "CSV"
- "method," "cycle," "association"

### 3. Ask Follow-up Questions

Spark remembers context:
```
You: "How do I run a titration?"
Spark: [explains titration setup]
You: "What concentration should I use?"
Spark: [understands you're still talking about titrations]
```

### 4. Try Different Phrasings

If first answer doesn't help, rephrase:
- "How do I calibrate?" → "What's the calibration procedure?"
- "Export help" → "How do I save my data?"

### 5. Use @ Commands for Speed

Type `@spark` at the start:
```
@spark how do I regenerate?
```

---

## Troubleshooting

### Spark Doesn't Understand My Question

**Try:**
1. Rephrase using different keywords
2. Break complex questions into smaller parts
3. Ask about specific features (not general concepts)

**Example:**
- Instead of: "How do I do everything?"
- Ask: "How do I start an acquisition?" then "How do I export data?"

### Spark Takes a Long Time (First Complex Question)

**Why:** The AI model is loading for the first time this session (10-30 seconds)

**What to do:** Wait for the model to load. All subsequent questions will be fast (2-5 seconds).

### Spark Gives Wrong/Incomplete Answer

**What to do:**
1. Click 👎 **Not Helpful** button
2. Rephrase your question with more details
3. Try asking step-by-step
4. Contact support if issue persists

### Can't Find Spark

**Check:**
1. You're in the **Help** tab (sidebar)
2. Chat box is visible at bottom
3. ezControl version is up-to-date

### Spark Stopped Working

**Try:**
1. Restart ezControl
2. Check logs folder for error messages
3. Contact support: info@affiniteinstruments.com

---

## Performance

| Type | Speed | When |
|------|-------|------|
| **Instant Answers** | <1ms | Common questions (calibration, export, etc.) |
| **Knowledge Base** | <100ms | Documentation searches |
| **AI First Load** | 10-30s | First complex question per session |
| **AI Answers** | 2-5s | After initial model load |

---

## Privacy & Data

### What Spark Stores Locally

- Your questions and Spark's answers
- Helpful/Not Helpful feedback
- Timestamps

**File:** `spark_qa_history.json` (in ezControl directory)

### What Spark Does NOT Store

- Personal information
- Experimental data
- File contents
- System passwords

### Online Features (Optional)

If enabled:
- Questions can be sent to Affinity support team
- Helps improve Spark's knowledge base
- Completely optional - Spark works offline

---

## Getting More Help

### In Spark
Just ask! Try:
- "How do I contact support?"
- "Where can I find tutorials?"
- "What's the user manual?"

### Direct Support

**Email:** info@affiniteinstruments.com
**Website:** https://www.affiniteinstruments.com/support
**Documentation:** https://www.affiniteinstruments.com/docs

---

## Version History

**v2.0 (Feb 2026)** - Consolidated documentation, improved AI integration
**v1.5** - Added knowledge base search
**v1.0** - Initial Spark release with pattern matching

---

**Questions about this guide?** Ask Spark: "Tell me about the Spark guide"
