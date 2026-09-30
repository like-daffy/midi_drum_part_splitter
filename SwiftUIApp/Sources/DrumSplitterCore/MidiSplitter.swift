import Foundation

public struct SplitPart {
    public let name: String
    public let midi: MidiFile
    /// True when at least one audible note-on (velocity > 0) landed in this part.
    public let hasNotes: Bool
}

public enum MidiSplitter {
    /// Splits `original` into one file per mapped part. Non-note messages other than the
    /// whitelisted meta events are dropped, and their delta times are folded into the next
    /// kept event so timing stays aligned.
    public static func split(_ original: MidiFile, mapping: DrumMapping) -> [SplitPart] {
        mapping.partNames.map { name in
            let noteSet = mapping.notes[name] ?? []
            var out = MidiFile(division: original.division, format: 1)
            var hasNotes = false

            for track in original.tracks {
                var newTrack: [MidiEvent] = []
                var accumulated = 0

                for event in track {
                    accumulated += event.delta
                    switch event.kind {
                    case let .meta(type, _):
                        // The trailing end_of_track is re-added below with the leftover time.
                        if MetaType.keep.contains(type) && type != MetaType.endOfTrack {
                            newTrack.append(MidiEvent(delta: accumulated, kind: event.kind))
                            accumulated = 0
                        }
                    case let .noteOn(_, note, velocity):
                        if noteSet.contains(Int(note)) {
                            newTrack.append(MidiEvent(delta: accumulated, kind: event.kind))
                            accumulated = 0
                            if velocity > 0 { hasNotes = true }
                        }
                    case let .noteOff(_, note, _):
                        if noteSet.contains(Int(note)) {
                            newTrack.append(MidiEvent(delta: accumulated, kind: event.kind))
                            accumulated = 0
                        }
                    case .other:
                        break
                    }
                }
                newTrack.append(MidiEvent(delta: accumulated, kind: .meta(type: MetaType.endOfTrack, data: [])))
                out.tracks.append(newTrack)
            }
            return SplitPart(name: name, midi: out, hasNotes: hasNotes)
        }
    }

    public static func split(fileAt url: URL, mapping: DrumMapping) throws -> [SplitPart] {
        let original: MidiFile
        do {
            original = try MidiFile.parse(Data(contentsOf: url))
        } catch {
            throw MidiFileError.invalid("Unrecognizable MIDI file: \(error.localizedDescription)")
        }
        return split(original, mapping: mapping)
    }
}
