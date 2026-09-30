#!/usr/bin/env bash
# Builds a double-clickable DrumSplitter.app (release, host architecture) into ./dist.
set -euo pipefail
cd "$(dirname "$0")/.."

swift build -c release
APP="dist/DrumSplitter.app"
rm -rf "$APP"
mkdir -p "$APP/Contents/MacOS"
cp ".build/release/DrumSplitter" "$APP/Contents/MacOS/DrumSplitter"
cat > "$APP/Contents/Info.plist" <<'PLIST'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>CFBundleName</key><string>MIDI Drum Splitter</string>
  <key>CFBundleDisplayName</key><string>MIDI Drum Splitter</string>
  <key>CFBundleIdentifier</key><string>com.midiutilities.DrumSplitter</string>
  <key>CFBundleExecutable</key><string>DrumSplitter</string>
  <key>CFBundlePackageType</key><string>APPL</string>
  <key>CFBundleShortVersionString</key><string>1.0</string>
  <key>CFBundleVersion</key><string>1</string>
  <key>LSMinimumSystemVersion</key><string>13.0</string>
  <key>NSHighResolutionCapable</key><true/>
</dict>
</plist>
PLIST
echo "Built $APP"
