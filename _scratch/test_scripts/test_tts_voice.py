"""Test pyttsx3 voice quality - hear how it sounds before adding to Spark"""

try:
    import pyttsx3

    # Initialize TTS engine
    engine = pyttsx3.init()

    # Get available voices
    voices = engine.getProperty('voices')

    print("=" * 60)
    print("PYTTSX3 VOICE DEMO")
    print("=" * 60)
    print(f"\nFound {len(voices)} voices on your system:\n")

    for i, voice in enumerate(voices):
        print(f"{i+1}. {voice.name}")
        print(f"   ID: {voice.id}")
        print(f"   Languages: {voice.languages}")
        print()

    # Test with sample Spark responses
    test_messages = [
        "Hi! I'm Spark, your Affilabs.core assistant.",
        "To start acquisition: Click the green Start button in the top toolbar.",
        "Calibration completed successfully! The system is ready for live data acquisition.",
        "To export data: Go to the Export tab in the sidebar, choose your format, and click Export."
    ]

    print("=" * 60)
    print("TESTING VOICES")
    print("=" * 60)
    print("\nYou'll hear 4 sample Spark responses with different voices.\n")

    # Test first 2 voices (usually one male, one female)
    for i, voice in enumerate(voices[:2]):
        print(f"\nVoice {i+1}: {voice.name}")
        engine.setProperty('voice', voice.id)

        # Adjust speed (200 = default, lower = slower, higher = faster)
        engine.setProperty('rate', 175)  # Slightly slower for clarity

        for msg in test_messages[:2]:  # Test with 2 messages per voice
            print(f"  Speaking: '{msg[:50]}...'")
            engine.say(msg)
            engine.runAndWait()

    print("\n" + "=" * 60)
    print("DEMO COMPLETE")
    print("=" * 60)
    print("\nDid you like the voice quality?")
    print("\nOptions:")
    print("  1. Keep as-is (good for lab/scientific use)")
    print("  2. Try edge-tts instead (better quality, needs internet)")
    print("  3. Don't add TTS to Spark")

except ImportError:
    print("❌ pyttsx3 not installed yet")
    print("\nInstalling pyttsx3...")
    import subprocess
    import sys
    subprocess.check_call([sys.executable, "-m", "pip", "install", "pyttsx3"])
    print("\n✅ Installed! Run this script again to hear the voice.")

except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()
