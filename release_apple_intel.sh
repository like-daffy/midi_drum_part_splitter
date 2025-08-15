#!/usr/bin/env bash
set -euo pipefail

cd "/Users/chanbaek/Python Projects/midi_drum_part_splitter"

# Create Intel (x86_64) venv using Rosetta with system Python
if ! /usr/sbin/softwareupdate --install-rosetta --agree-to-license >/dev/null 2>&1; then
  echo "Rosetta may already be installed. Proceeding..."
fi

arch -x86_64 /usr/bin/python3 -m venv venv-x86_64
source venv-x86_64/bin/activate
arch -x86_64 python -c "import platform; print(platform.machine()); assert platform.machine()=='x86_64', 'Not running x86_64'"

# Ensure all tooling runs under Intel
export PIP_ONLY_BINARY=:all:
arch -x86_64 python -m pip install --upgrade pip
arch -x86_64 python -m pip install -r requirements.txt

export MACOSX_DEPLOYMENT_TARGET=11.0
arch -x86_64 pyinstaller --noconfirm --windowed --onedir --name "MIDI_Drum_Splitter" drum_splitter_gui.py

# Verify arch
file "dist/MIDI_Drum_Splitter.app/Contents/MacOS/MIDI_Drum_Splitter"

# Zip (for release upload)
ditto -c -k --sequesterRsrc --keepParent "dist/MIDI_Drum_Splitter.app" "MIDI_Drum_Splitter-macos-x86_64.zip"

deactivate