"""Quick test of Piper TTS voice functionality."""

import os
import subprocess
import numpy as np

def test_voice():
    """Test if voice/TTS is working."""
    print("="*60)
    print("TESTING PIPER TTS VOICE")
    print("="*60)

    # 1. Check sounddevice
    print("\n1. Checking sounddevice library...")
    try:
        import sounddevice as sd
        print(f"   ✓ sounddevice installed (version {sd.__version__})")
    except ImportError:
        print("   ✗ sounddevice NOT installed")
        print("   Install with: pip install sounddevice")
        return False

    # 2. Check Piper executable
    print("\n2. Checking Piper TTS executable...")
    piper_exe = os.path.join("piper", "piper.exe")
    if os.path.exists(piper_exe):
        print(f"   ✓ piper.exe found at: {os.path.abspath(piper_exe)}")
    else:
        print(f"   ✗ piper.exe NOT FOUND at: {os.path.abspath(piper_exe)}")
        print("   Run: python install_qwen_tts.py")
        return False

    # 3. Check selected voice
    print("\n3. Checking voice model...")
    voice_file = os.path.join("piper", "selected_voice.txt")
    if os.path.exists(voice_file):
        with open(voice_file, 'r') as f:
            voice_model = f.read().strip()
        print(f"   ✓ Selected voice: {voice_model}")
    else:
        print("   ✗ selected_voice.txt NOT FOUND")
        return False

    # 4. Check voice model file exists
    print("\n4. Checking voice model file...")
    model_path = os.path.join("piper", f"{voice_model}.onnx")
    if os.path.exists(model_path):
        size_mb = os.path.getsize(model_path) / (1024*1024)
        print(f"   ✓ Voice model found: {voice_model}.onnx ({size_mb:.1f} MB)")
    else:
        print(f"   ✗ Voice model NOT FOUND: {model_path}")
        print(f"\n   Available models:")
        for f in os.listdir("piper"):
            if f.endswith(".onnx"):
                print(f"      - {f}")
        return False

    # 5. Test TTS generation and playback
    print("\n5. Testing TTS generation and playback...")
    test_text = "Hello, this is a test of the Spark AI voice assistant."

    try:
        print(f"   Generating speech: '{test_text}'")
        result = subprocess.run(
            [piper_exe, '--model', model_path, '--output-raw'],
            input=test_text.encode('utf-8'),
            capture_output=True,
            check=True,
            timeout=10,
        )

        # Parse audio data
        audio_data = np.frombuffer(result.stdout, dtype=np.int16)

        if len(audio_data) == 0:
            print("   ✗ No audio data generated")
            return False

        print(f"   ✓ Generated {len(audio_data)} audio samples")
        print(f"   ✓ Duration: {len(audio_data)/22050:.1f} seconds")

        # Play audio
        print("   🔊 Playing audio...")
        sd.play(audio_data, 22050)
        sd.wait()

        print("   ✓ Audio playback completed")

    except subprocess.TimeoutExpired:
        print("   ✗ Piper timed out")
        return False
    except subprocess.CalledProcessError as e:
        print(f"   ✗ Piper failed with exit code: {e.returncode}")
        if e.stderr:
            print(f"   Error: {e.stderr.decode('utf-8', errors='ignore')}")
        return False
    except Exception as e:
        print(f"   ✗ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

    print("\n" + "="*60)
    print("✅ ALL TTS TESTS PASSED - Voice is working!")
    print("="*60)
    return True


if __name__ == "__main__":
    success = test_voice()
    if not success:
        print("\n❌ TTS TEST FAILED")
        print("\nTroubleshooting:")
        print("1. Install sounddevice: pip install sounddevice")
        print("2. Install Piper TTS: python install_qwen_tts.py")
        print("3. Check that selected_voice.txt matches an available .onnx file")
    else:
        print("\n✅ You can now start the application - voice will work in Spark AI!")
