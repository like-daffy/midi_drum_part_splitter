import Foundation

/// Note-name helpers using Cubase octave numbering (MIDI 0 == C-2).
public enum MidiUtils {
    private static let noteNames = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]

    private static let semitones: [String: Int] = [
        "C": 0, "C#": 1, "DB": 1,
        "D": 2, "D#": 3, "EB": 3,
        "E": 4,
        "F": 5, "F#": 6, "GB": 6,
        "G": 7, "G#": 8, "AB": 8,
        "A": 9, "A#": 10, "BB": 10,
        "B": 11,
    ]

    public static func noteToName(_ note: Int) -> String {
        let octave = note / 12 - 2
        return "\(noteNames[note % 12])\(octave)"
    }

    /// Returns -1 when the name is invalid or out of the 0...127 range.
    public static func nameToNote(_ name: String) -> Int {
        let s = name.trimmingCharacters(in: .whitespaces)
            .uppercased()
            .replacingOccurrences(of: "♯", with: "#")
            .replacingOccurrences(of: "♭", with: "B")
        guard !s.isEmpty else { return -1 }

        let chars = Array(s)
        var idx = chars.count - 1
        while idx >= 0 && (chars[idx].isASCII && chars[idx].isNumber || chars[idx] == "-") {
            idx -= 1
        }
        let letter = String(chars[..<(idx + 1)])
        let octaveStr = String(chars[(idx + 1)...])
        guard !octaveStr.isEmpty, let octave = Int(octaveStr),
              let semitone = semitones[letter] else { return -1 }

        let note = (octave + 2) * 12 + semitone
        return (0...127).contains(note) ? note : -1
    }
}
