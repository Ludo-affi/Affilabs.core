#!/usr/bin/env python3
"""
Spark AI Build Validation Script

Run this script before PyInstaller build to validate all Spark AI dependencies
and data files are properly configured.

Usage:
    python validate_spark_build.py
"""

import sys
import traceback
from pathlib import Path


def check_spark_imports():
    """Verify all Spark components can be imported."""
    print("🔍 Checking Spark AI imports...")

    try:
        # Core Spark components
        from affilabs.services.spark import SparkAnswerEngine, SparkPatternMatcher, SparkKnowledgeBase, SparkTinyLM
        print("✅ Core Spark components imported successfully")

        # Test basic functionality
        engine = SparkAnswerEngine()
        answer, matched = engine.generate_answer("test question")
        print(f"✅ Basic answer generation works: {'Pattern matched' if matched else 'AI fallback'}")

    except Exception as e:
        print(f"❌ Spark import failed: {e}")
        traceback.print_exc()
        return False

    return True


def check_data_files():
    """Verify required data files exist."""
    print("\n🔍 Checking Spark data files...")

    required_files = [
        "affilabs/data/spark/knowledge_base.json",
        "affilabs/services/spark/patterns.py",
        "affilabs/utils/resource_path.py"
    ]

    missing_files = []
    for file_path in required_files:
        if not Path(file_path).exists():
            missing_files.append(file_path)
        else:
            print(f"✅ {file_path}")

    if missing_files:
        print(f"❌ Missing required files: {missing_files}")
        return False

    return True


def check_optional_dependencies():
    """Check optional dependencies (PyTorch, TTS, etc.)."""
    print("\n🔍 Checking optional dependencies...")

    # PyTorch for TinyLM AI
    try:
        import torch
        print(f"✅ PyTorch {torch.__version__} available")
        print(f"   CUDA available: {torch.cuda.is_available()}")
    except ImportError:
        print("⚠️  PyTorch not available - Spark will use pattern matching only")

    # Transformers for TinyLM
    try:
        import transformers
        print(f"✅ Transformers {transformers.__version__} available")
    except ImportError:
        print("⚠️  Transformers not available - Spark will use pattern matching only")

    # TTS dependencies
    try:
        import sounddevice
        print(f"✅ SoundDevice available for TTS")
    except ImportError:
        print("⚠️  SoundDevice not available - Spark voice disabled")

    # TinyDB for knowledge base
    try:
        import tinydb
        print(f"✅ TinyDB {tinydb.__version__} available")
    except ImportError:
        print("❌ TinyDB required for knowledge base")
        return False

    return True


def check_pyinstaller_spec():
    """Verify PyInstaller spec includes Spark dependencies."""
    print("\n🔍 Checking PyInstaller spec configuration...")

    spec_file = Path("Affilabs-Core.spec")
    if not spec_file.exists():
        print("❌ Affilabs-Core.spec not found")
        return False

    spec_content = spec_file.read_text()

    # Check for Spark-related entries
    spark_checks = {
        "affilabs.services.spark": "'affilabs.services.spark'",
        "torch dependencies": "'torch'",
        "transformers": "'transformers'",
        "tinydb": "'tinydb'",
        "spark data files": "('affilabs/services', 'affilabs/services')",
        "knowledge base": "('affilabs/data', 'affilabs/data')"
    }

    missing_configs = []
    for check_name, pattern in spark_checks.items():
        if pattern not in spec_content:
            missing_configs.append(check_name)
        else:
            print(f"✅ {check_name} configured")

    if missing_configs:
        print(f"⚠️  PyInstaller spec might be missing: {missing_configs}")
        print("   Check hiddenimports and datas sections in Affilabs-Core.spec")

    return len(missing_configs) == 0


def check_piper_tts():
    """Check if Piper TTS is available."""
    print("\n🔍 Checking Piper TTS (optional)...")

    piper_exe = Path("piper/piper.exe")
    if piper_exe.exists():
        print(f"✅ Piper TTS found at {piper_exe}")

        voice_file = Path("piper/selected_voice.txt")
        if voice_file.exists():
            voice = voice_file.read_text().strip()
            print(f"✅ Voice model: {voice}")
        else:
            print("⚠️  No voice selected - will use default")
    else:
        print("⚠️  Piper TTS not found - voice features disabled")

    return True


def main():
    """Run all validation checks."""
    print("🚀 Spark AI PyInstaller Build Validation")
    print("=" * 50)

    checks = [
        ("Spark imports", check_spark_imports),
        ("Data files", check_data_files),
        ("Optional dependencies", check_optional_dependencies),
        ("PyInstaller spec", check_pyinstaller_spec),
        ("Piper TTS", check_piper_tts)
    ]

    results = []
    for name, check_func in checks:
        try:
            result = check_func()
            results.append((name, result))
        except Exception as e:
            print(f"❌ {name} check failed with exception: {e}")
            results.append((name, False))

    print("\n" + "=" * 50)
    print("📋 VALIDATION SUMMARY")
    print("=" * 50)

    all_passed = True
    for name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} {name}")
        if not result:
            all_passed = False

    if all_passed:
        print("\n🎉 All checks passed! Spark AI is ready for PyInstaller build.")
        return 0
    else:
        print("\n⚠️  Some issues found. Please fix before building executable.")
        print("\nCommon fixes:")
        print("• Install missing dependencies: pip install torch transformers sounddevice tinydb")
        print("• Update Affilabs-Core.spec hiddenimports and datas sections")
        print("• Ensure all Spark data files are present")
        return 1


if __name__ == "__main__":
    sys.exit(main())