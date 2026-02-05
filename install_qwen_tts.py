"""Install Piper TTS for Spark AI voice.

Piper is a lightweight, high-quality neural TTS engine.
Model size: ~10MB (much smaller than Qwen3-TTS!)
"""

import subprocess
import sys
import os
import zipfile
import urllib.request
from pathlib import Path

def download_file(url, dest_path):
    """Download a file with progress."""
    print(f"Downloading from {url}...")
    urllib.request.urlretrieve(url, dest_path)
    print(f"✓ Downloaded to {dest_path}")

# Available voice models - choose your favorite!
VOICES = {
    "1": {
        "name": "Lessac (Female, Clear & Natural)",
        "path": "en_US-lessac-medium",
        "url": "en/en_US/lessac/medium/en_US-lessac-medium.onnx",
        "config": "en/en_US/lessac/medium/en_US-lessac-medium.onnx.json"
    },
    "2": {
        "name": "Amy (Female, Warm & Friendly)",
        "path": "en_US-amy-medium",
        "url": "en/en_US/amy/medium/en_US-amy-medium.onnx",
        "config": "en/en_US/amy/medium/en_US-amy-medium.onnx.json"
    },
    "3": {
        "name": "Kristin (Female, Professional)",
        "path": "en_US-kristin-medium",
        "url": "en/en_US/kristin/medium/en_US-kristin-medium.onnx",
        "config": "en/en_US/kristin/medium/en_US-kristin-medium.onnx.json"
    },
    "4": {
        "name": "Ryan (Male, Clear)",
        "path": "en_US-ryan-medium",
        "url": "en/en_US/ryan/medium/en_US-ryan-medium.onnx",
        "config": "en/en_US/ryan/medium/en_US-ryan-medium.onnx.json"
    },
    "5": {
        "name": "Libritts (Female, Expressive)",
        "path": "en_US-libritts_r-medium",
        "url": "en/en_US/libritts_r/medium/en_US-libritts_r-medium.onnx",
        "config": "en/en_US/libritts_r/medium/en_US-libritts_r-medium.onnx.json"
    }
}

def install_piper():
    """Install Piper TTS and voice model."""
    print("Installing Piper TTS for Spark AI...")
    print("="*60)
    
    # Create piper directory
    script_dir = Path(__file__).parent
    piper_dir = script_dir / "piper"
    piper_dir.mkdir(exist_ok=True)
    
    # Determine platform
    import platform
    system = platform.system()
    
    if system == "Windows":
        # Download Piper for Windows
        piper_url = "https://github.com/rhasspy/piper/releases/download/2023.11.14-2/piper_windows_amd64.zip"
        piper_zip = piper_dir / "piper.zip"
        
        print("\n1. Downloading Piper TTS executable (~5MB)...")
        download_file(piper_url, piper_zip)
        
        print("\n2. Extracting Piper...")
        with zipfile.ZipFile(piper_zip, 'r') as zip_ref:
            zip_ref.extractall(piper_dir)
        piper_zip.unlink()  # Remove zip file
        print("✓ Piper extracted")
        
        # Move files to correct location
        extracted_dir = piper_dir / "piper"
        if extracted_dir.exists():
            import shutil
            for item in extracted_dir.iterdir():
                target = piper_dir / item.name
                if not target.exists():
                    if item.is_dir():
                        shutil.move(str(item), str(target))
                    else:
                        item.rename(target)
            # Clean up extracted directory if it still exists
            if extracted_dir.exists():
                shutil.rmtree(extracted_dir)
        
        piper_exe = piper_dir / "piper.exe"
        
    else:
        print(f"Unsupported platform: {system}")
        print("Please install Piper manually from: https://github.com/rhasspy/piper")
        return False
    
    # Let user choose voice
    print("\n3. Choose a voice for Spark AI:")
    print("="*60)
    for key, voice in VOICES.items():
        print(f"{key}. {voice['name']}")
    print("="*60)
    
    choice = input("\nEnter your choice (1-5) or press Enter for default [1]: ").strip()
    if not choice:
        choice = "1"
    
    if choice not in VOICES:
        print(f"Invalid choice. Using default (Lessac).")
        choice = "1"
    
    selected_voice = VOICES[choice]
    print(f"\n✓ Selected: {selected_voice['name']}")
    
    # Download voice model
    print("\n4. Downloading voice model (~10MB)...")
    base_url = "https://huggingface.co/rhasspy/piper-voices/resolve/main"
    model_url = f"{base_url}/{selected_voice['url']}"
    model_config_url = f"{base_url}/{selected_voice['config']}"
    
    model_path = piper_dir / f"{selected_voice['path']}.onnx"
    config_path = piper_dir / f"{selected_voice['path']}.onnx.json"
    
    download_file(model_url, model_path)
    download_file(model_config_url, config_path)
    
    # Save selected voice name for the app to use
    voice_file = piper_dir / "selected_voice.txt"
    voice_file.write_text(selected_voice['path'])
    
    # Install sounddevice for audio playback
    print("\n4. Installing audio playback library...")
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "-U", "sounddevice", "numpy"])
        print("✓ sounddevice installed")
    except subprocess.CalledProcessError as e:
        print(f"✗ Failed to install sounddevice: {e}")
        return False
    
    # Test Piper
    print("\n6. Testing Piper TTS...")
    try:
        result = subprocess.run(
            [str(piper_exe), "--version"],
            capture_output=True,
            text=True,
            check=True
        )
        print(f"✓ Piper version: {result.stdout.strip()}")
    except Exception as e:
        print(f"✗ Piper test failed: {e}")
        return False
    
    print("\n" + "="*60)
    print("Installation complete!")
    print("="*60)
    print(f"\nPiper TTS installed to: {piper_dir}")
    print(f"Voice: {selected_voice['name']}")
    print(f"Model: {selected_voice['path']} (~10MB)")
    print("\nSpark AI is ready to use Piper TTS!")
    print("\nTo test the voice, run: python test_qwen_voice.py")
    
    return True

if __name__ == "__main__":
    success = install_piper()
    sys.exit(0 if success else 1)
