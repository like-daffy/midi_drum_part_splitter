# MIDI Drum Splitter – SwiftUI (macOS)

Native SwiftUI port of the PyQt6 app in the repository root. Same behavior: drop one MIDI file,
click **Proceed**, then drag the Kick / Snare / Hihat / Ride / Crash / Tom tiles out to Finder.
Custom YAML mappings (Cubase octave numbering) and the "use the same configuration" preference are supported.

No third-party dependencies: MIDI parsing/writing, the YAML mapping subset and the splitter are
implemented in `DrumSplitterCore` (replacing `mido` and `PyYAML`).

## Requirements
- macOS 13+
- Xcode 15+ / Swift 5.9+

## Build & run
```bash
cd SwiftUIApp
swift run DrumSplitter          # run directly
swift test                      # core unit tests
./scripts/build_app.sh          # produces dist/DrumSplitter.app
```
You can also open `Package.swift` in Xcode.

## Layout
- `Sources/DrumSplitterCore` – `MidiFile` (SMF read/write), `MidiSplitter`, `MappingHandler`, `DefaultMapping`
- `Sources/DrumSplitterApp` – SwiftUI views, `AppModel`, "Blue Sea" OKLCH theme
- `Tests/DrumSplitterCoreTests`

## Notes on the YAML parser
Supports the `drum_parts:` mapping with block (`- C1`) or flow (`[C1, D1]`) note lists, quotes and `#` comments —
enough for the files the Python app accepts and its exported template. Anchors, multi-document files and other
advanced YAML are not supported.
