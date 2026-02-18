"""Test Microsoft Zira voice (female) - Extended demo"""

import pyttsx3

# Initialize TTS engine
engine = pyttsx3.init()

# Get voices and select Zira
voices = engine.getProperty('voices')
zira_voice = None

for voice in voices:
    if 'Zira' in voice.name:
        zira_voice = voice
        break

if zira_voice:
    engine.setProperty('voice', zira_voice.id)
    print(f"Using: {zira_voice.name}\n")
else:
    print("Zira voice not found, using default\n")

# Set speech rate (175 = slightly slower for clarity)
engine.setProperty('rate', 175)

# Sample Spark responses
test_messages = [
    "Hi! I'm Spark, your Affilabs.core assistant. How can I help you today?",

    "To start acquisition: First, make sure the detector is connected. Then click the green Start button in the top toolbar.",

    "Calibration completed successfully! The system is now ready for live data acquisition. You can begin recording your experiment.",

    "To export your data: Navigate to the Export tab in the sidebar, choose your preferred format such as Excel or CSV, select the cycles you want to export, and click the Export button.",

    "Baseline drift can be caused by temperature fluctuations, air bubbles in the flow cell, or insufficient warmup time. Allow at least 30 to 60 minutes for the system to stabilize.",

    "For sensor swap calibration: If you're replacing with the same sensor type, run Simple LED Calibration which takes only 10 to 20 seconds. For a different sensor type, run Full System Calibration.",
]

print("=" * 60)
print("ZIRA VOICE DEMO - Spark AI Responses")
print("=" * 60)
print(f"\nPlaying {len(test_messages)} sample responses...\n")

for i, msg in enumerate(test_messages, 1):
    print(f"{i}. {msg[:60]}...")
    engine.say(msg)
    engine.runAndWait()
    print()

print("=" * 60)
print("DEMO COMPLETE")
print("=" * 60)
print("\nWhat do you think of Zira's voice for Spark?")
print("\n1. Perfect - add it to Spark")
print("2. Too robotic - try edge-tts instead")
print("3. Don't add TTS")
