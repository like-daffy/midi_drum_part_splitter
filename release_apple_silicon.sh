#!/usr/bin/env bash
set -euo pipefail

cd "/Users/chanbaek/Python Projects/midi_drum_part_splitter"

# Fresh env for arm64 using system Python (native on Apple Silicon)
/usr/bin/python3 -m venv venv-arm64
source venv-arm64/bin/activate
python -c "import platform; print(platform.machine()); assert platform.machine()=='arm64', 'Not running arm64'"

python -m pip install --upgrade pip
python -m pip install -r requirements.txt

export MACOSX_DEPLOYMENT_TARGET=11.0
pyinstaller --noconfirm --windowed --onedir --name "MIDI_Drum_Splitter" drum_splitter_gui.py

# Verify arch
file "dist/MIDI_Drum_Splitter.app/Contents/MacOS/MIDI_Drum_Splitter"

# Zip (for release upload)
ditto -c -k --sequesterRsrc --keepParent "dist/MIDI_Drum_Splitter.app" "MIDI_Drum_Splitter-macos-arm64.zip"

deactivate