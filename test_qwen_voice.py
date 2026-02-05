"""Test Piper TTS voice for Spark AI."""

import subprocess
from pathlib import Path
import sounddevice as sd
import numpy as np

def test_piper_voice():
    """Test the Piper TTS voice that will be used for Spark."""
    # Find piper executable
    script_dir = Path(__file__).parent
    piper_dir = script_dir / "piper"
    piper_exe = piper_dir / "piper.exe"

    # Load selected voice
    voice_file = piper_dir / "selected_voice.txt"
    if voice_file.exists():
        voice_model = voice_file.read_text().strip()
    else:
        voice_model = "en_US-lessac-medium"

    model_path = piper_dir / f"{voice_model}.onnx"

    if not piper_exe.exists():
        print("✗ Piper not found! Please run: python install_qwen_tts.py")
        return

    if not model_path.exists():
        print("✗ Voice model not found! Please run: python install_qwen_tts.py")
        return

    print("✓ Piper TTS found!")
    print(f"Voice: {voice_model}")
    print(f"Model size: ~10MB")
    print("\nTesting voice with sample Spark messages...")

    # Test messages from Spark
    test_messages = [
        "Welcome! I'm Spark, your AI assistant for Affilabs.core software. How can I help you today?",
        "To start an acquisition, click the Start button in the Live tab. Make sure your detector is connected first.",
        "Great question! Let me explain how the cycle system works in Affilabs.core.",
        "Warning: Make sure to calibrate your system before starting your first acquisition.",
    ]

    print("\n" + "="*60)
    for i, text in enumerate(test_messages, 1):
        print(f"\nTest {i}/{len(test_messages)}")
        print(f"Text: {text[:50]}...")

        try:
            # Generate speech with Piper
            print("Generating audio...")
            result = subprocess.run(
                [str(piper_exe), '--model', str(model_path), '--output-raw'],
                input=text.encode('utf-8'),
                capture_output=True,
                check=True
            )

            # Play audio
            audio_data = np.frombuffer(result.stdout, dtype=np.int16)
            print("Playing audio...")
            sd.play(audio_data, 22050)
            sd.wait()
            print("✓ Playback complete")

        except Exception as e:
            print(f"✗ Error: {e}")

    print("\n" + "="*60)
    print("Voice testing complete!")
    print("="*60)
    print("\nPiper TTS is ready for Spark AI!")
    print(f"Voice: {voice_model}")
    print("Size: Only ~10MB total!")
    print("\nTo change the voice, run: python install_qwen_tts.py")

if __name__ == "__main__":
    try:
        test_piper_voice()
    except Exception as e:
        print(f"\nError during testing: {e}")
        print("\nMake sure you've installed Piper TTS:")
        print("  python install_qwen_tts.py")
