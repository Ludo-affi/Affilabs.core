# Operation Manual - Training Dataset

**Version:** 1.0
**Last Updated:** 2026-02-07
**Status:** Production-Ready for ML Training

---

## Overview

This folder contains the official **AffiLabs.core v2.0 Operation Manual** - a comprehensive guide for operating the P4SPR surface plasmon resonance system.

**Primary File:** `OPERATION_MANUAL.md` (1516 lines, ~63 KB)

---

## Content Structure

The Operation Manual is organized into 10 major sections:

1. **Critical Sensor Handling Disclaimer** - Safety and liability information
2. **Quick Start Guide** - First-time setup and power requirements
3. **System Overview** - Hardware specs, environmental conditions, power requirements
4. **Software Purpose & Scope** - Two-phase workflow and design philosophy
5. **Getting to Auto-Read Section** - Auto-baseline acquisition procedures
6. **Creating a Method** - Method builder workflow and cycle configuration
7. **Recording an Experiment** - Live tab data acquisition procedures
8. **Editing & Analyzing Data** - Edit tab analysis tools and ΔSPR measurement
9. **Data Export Formats** - Raw and analysis file specifications
10. **Manual Operation** - Sensor installation, channel addressing, pump control
11. **Maintenance** - Daily, Weekly, Biweekly, Monthly, Quarterly/Annual procedures
12. **Software Compatibility** - System requirements and environmental specs
13. **Troubleshooting** - 20+ issue entries with solutions
14. **Safety & Liability Summary** - Critical safety rules and emergency contacts

---

## Training Use Cases

This manual is optimized for:

### 1. **Domain-Specific Language Models (TinyLLaMA)**
- Fine-tune TinyLLaMA on SPR system operation and maintenance
- Build chatbots for user support and procedure guidance
- Generate context-aware responses for troubleshooting queries
- Domain vocabulary: SPR, sensorgram, ΔSPR, microfluidic cell, polarizer, optical contact, etc.

### 2. **Distributed Processing (Apache Spark)**
- Process manual content for knowledge extraction
- Build searchable index of procedures and troubleshooting steps
- Extract entity relationships (components, maintenance cycles, safety rules)
- Generate summaries and cross-references
- Create training datasets for classification (procedure type, complexity, urgency)

### 3. **Information Retrieval Systems**
- Semantic search for similar procedures
- Question-answering systems for user queries
- Automatic documentation linking
- Cross-reference generation between related sections

---

## File Format & Preparation

**Format:** Markdown (.md)
**Encoding:** UTF-8
**Line Endings:** LF (Unix-style)
**Total Lines:** 1516
**Approximate Size:** 63 KB

**Key Characteristics:**
- Comprehensive table structures (20+ data tables)
- Code blocks for procedures and configurations
- Cross-references and navigation links
- Hierarchical headers (H1-H4)
- Mixed list formats (ordered, unordered, checklist)
- Emphasis markers (bold, italic, code formatting)

---

## Training Recommendations

### For TinyLLaMA Fine-Tuning:

```
Domain: Laboratory Equipment Operation & Maintenance
Task: Instruction following, procedure documentation, troubleshooting
Training Approach:
  - Context: User question or scenario
  - Instruction: Procedure or solution from manual
  - Response: Step-by-step guidance from relevant sections

Example Pairs:
  Q: "How do I install a new sensor?"
  A: [Sensor Installation procedure steps 1-7]

  Q: "What should I do if baseline drift > 1 nm/min?"
  A: [Troubleshooting response with immediate actions]
```

### For Spark Processing:

```
Data Extraction Tasks:
  1. Extract all maintenance procedures and schedules
  2. Identify all hardware components and specifications
  3. Build procedure dependency graph
  4. Extract safety rules and critical warnings
  5. Generate component cross-references

Distributed Pipeline:
  - Read/partition markdown by section
  - Parse tables into structured data
  - Extract entity relationships
  - Build searchable indices
  - Generate embeddings for semantic search
```

---

## Dataset Statistics

| Metric | Value |
|--------|-------|
| **Total Lines** | 1,516 |
| **File Size** | ~63 KB |
| **Total Sections** | 14 |
| **Tables** | 25+ |
| **Code Blocks** | 5+ |
| **Procedures** | 50+ |
| **Hardware Components** | 15+ |
| **Maintenance Tasks** | 30+ |
| **Troubleshooting Issues** | 20+ |
| **Safety Rules** | 10+ critical |

---

## Content Quality Standards

✅ **Production-Ready Characteristics:**
- All procedures tested and verified
- Critical safety information marked with ⚠️ symbols
- Complete table structures with proper formatting
- Hierarchical organization with clear navigation
- Cross-referenced sections and links
- Device-specific configurations (FLMT09788)
- Affinité-official procedures (CLN-KIT cleaning protocol)
- GLP/GMP-compliant formatting
- Emergency contact information
- Liability and responsibility statements

---

## Usage Guidelines for ML Training

### 1. **Preprocessing**
- Preserve markdown structure for context awareness
- Keep tables in original format (supports structured learning)
- Maintain hierarchical relationships
- Extract procedure blocks as atomic training units
- Preserve warning/emphasis markers for importance weighting

### 2. **Tokenization**
- Handle technical vocabulary (SPR terminology)
- Preserve special characters in tables
- Support multi-line code blocks
- Maintain list structure markers

### 3. **Training Data Generation**
- Create question-answer pairs from procedures
- Generate troubleshooting scenarios
- Build maintenance schedule datasets
- Extract safety rule compliance checks
- Generate component specification lookups

### 4. **Evaluation**
- Test against real user scenarios
- Validate procedure completeness
- Check safety rule compliance in generated responses
- Verify equipment specification accuracy

---

## Integration Points

### For Affilabs Systems:
- **Live Tab:** Reference for data acquisition procedures
- **Edit Tab:** Guidance for analysis and ΔSPR measurement
- **Settings/Configuration:** Hardware specs and calibration parameters
- **Help System:** Context-sensitive documentation lookup

### For User Support:
- **Chatbot Backend:** Procedure and troubleshooting responses
- **Knowledge Base:** Searchable documentation system
- **Training Materials:** Onboarding for new operators
- **Maintenance Scheduler:** Automated maintenance reminders

---

## Version Control

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | 2026-02-07 | Initial production release with cleaning kit procedures, environmental specs, OS compatibility |
| — | — | Previous versions in archive folder |

---

## Support & Feedback

For questions about this manual or to request updates:
- **Sensor/Hardware Issues:** Contact Affinité Instruments
- **Software/UI Issues:** [Support contact]
- **Manual Corrections:** [Development Team]

---

**Last Generated:** 2026-02-07
**Ready for Training:** ✅ Yes
**Format:** Markdown (UTF-8, LF line endings)
**Recommended Model Size:** TinyLLaMA (1.1B parameters or larger)
**Recommended Spark Partitions:** 5-10 (balanced for table processing)
