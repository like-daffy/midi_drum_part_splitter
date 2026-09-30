import Foundation

/// Built-in drum mapping (Cubase octave numbering, C-2..B8), tuned for Superior Drummer 3.
public enum DefaultMapping {
    public static let yaml = """
# Drum parts mapping using Cubase octave numbering (C-2..B8)
drum_parts:
  Kick:
    - A#0
    - B0
    - C1
  Snare:
    - F#-2
    - A0
    - C#1
    - D1
    - D#1
    - E1
    - F#3
    - G3
    - G#3
    - A3
    - A#3
    - B3
    - E4
    - F8
    - F#8
    - G8
  Hihat:
    - G-2
    - G#-2
    - A-2
    - A#-2
    - B-2
    - C-1
    - C#-1
    - D-1
    - D#-1
    - E-1
    - F-1
    - F#-1
    - G-1
    - G#-1
    - A-1
    - A#-1
    - B-1
    - C0
    - C#0
    - D0
    - F#1
    - G#1
    - A#1
    - C3
    - C#3
    - D3
    - D#3
    - E3
    - F3
    - B7
    - C8
    - C#8
    - D8
    - D#8
    - E8
  Ride:
    - F0
    - F#0
    - D#2
    - F2
    - B2
    - F7
    - F#7
    - G7
    - G#7
    - A7
    - A#7
  Crash:
    - D#0
    - E0
    - G0
    - G#0
    - C#2
    - D2
    - E2
    - F#2
    - G2
    - G#2
    - A2
    - A#2
    - B4
    - C5
    - C#5
    - D5
    - D#5
    - E5
    - F5
    - F#5
    - G5
    - G#5
    - A5
    - A#5
    - B5
    - C6
    - C#6
    - D6
    - D#6
    - E6
    - F6
    - F#6
    - G6
    - G#6
    - A6
    - A#6
    - B6
    - C7
    - C#7
    - D7
    - D#7
    - E7
  Tom:
    - F1
    - G1
    - A1
    - B1
    - C2
    - C4
    - C#4
    - D4
    - D#4
    - F4
    - F#4
    - G4
    - G#4
    - A4
    - A#4
"""

    /// Order in which parts are shown in the results row.
    public static let displayOrder = ["Kick", "Snare", "Hihat", "Ride", "Crash", "Tom"]
}
