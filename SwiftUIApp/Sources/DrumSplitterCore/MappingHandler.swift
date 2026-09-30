import Foundation

public struct MappingError: LocalizedError {
    public let message: String
    public init(_ message: String) { self.message = message }
    public var errorDescription: String? { message }
}

/// Part name -> MIDI note numbers, keeping the order parts were declared in.
public struct DrumMapping: Equatable {
    public var partNames: [String]
    public var notes: [String: Set<Int>]

    public init(partNames: [String] = [], notes: [String: Set<Int>] = [:]) {
        self.partNames = partNames
        self.notes = notes
    }
}

/// Loads and validates the `drum_parts` YAML mapping.
///
/// Only the small YAML subset used by the mapping files is supported:
/// a top-level `drum_parts:` key, part names as nested keys, and `- note`
/// list items (block style), plus `[a, b]` flow lists and `#` comments.
public enum MappingHandler {
    public static func load(fromYAML text: String) throws -> DrumMapping {
        var sawDrumParts = false
        var drumPartsIndent = -1
        var current: String?
        var mapping = DrumMapping()

        func addNote(_ raw: String, to part: String) throws {
            let value = unquote(raw)
            let midi = MidiUtils.nameToNote(value)
            if midi < 0 { throw MappingError("Invalid note '\(value)' in part '\(part)'") }
            mapping.notes[part, default: []].insert(midi)
        }

        for (lineNo, rawLine) in text.components(separatedBy: .newlines).enumerated() {
            let line = stripComment(rawLine)
            let trimmed = line.trimmingCharacters(in: .whitespaces)
            if trimmed.isEmpty || trimmed == "---" { continue }
            if line.prefix(while: { $0 == " " || $0 == "\t" }).contains("\t") {
                throw MappingError("Failed to parse YAML: tabs are not allowed for indentation (line \(lineNo + 1))")
            }
            let indent = line.prefix(while: { $0 == " " }).count

            if !sawDrumParts {
                if trimmed == "drum_parts:" {
                    sawDrumParts = true
                    drumPartsIndent = indent
                }
                continue
            }

            // Another key at the same level ends the drum_parts block.
            if indent <= drumPartsIndent && !trimmed.hasPrefix("-") { break }

            if trimmed.hasPrefix("- ") || trimmed == "-" {
                guard let part = current else {
                    throw MappingError("'drum_parts' must be a non-empty mapping")
                }
                let item = String(trimmed.dropFirst()).trimmingCharacters(in: .whitespaces)
                if item.isEmpty { continue }
                try addNote(item, to: part)
                continue
            }

            guard let colon = trimmed.firstIndex(of: ":") else {
                throw MappingError("Failed to parse YAML: unexpected content on line \(lineNo + 1)")
            }
            let name = unquote(String(trimmed[..<colon]).trimmingCharacters(in: .whitespaces))
            let rest = String(trimmed[trimmed.index(after: colon)...]).trimmingCharacters(in: .whitespaces)
            current = name
            if mapping.notes[name] == nil {
                mapping.partNames.append(name)
                mapping.notes[name] = []
            }
            if rest.isEmpty { continue }
            if rest.hasPrefix("[") && rest.hasSuffix("]") {
                let inner = rest.dropFirst().dropLast()
                for item in inner.split(separator: ",") {
                    let t = item.trimmingCharacters(in: .whitespaces)
                    if !t.isEmpty { try addNote(t, to: name) }
                }
            } else {
                throw MappingError("Part '\(name)' must list note names")
            }
        }

        guard sawDrumParts else { throw MappingError("YAML must contain a 'drum_parts' mapping") }
        guard !mapping.partNames.isEmpty else { throw MappingError("'drum_parts' must be a non-empty mapping") }
        return mapping
    }

    /// midi note -> parts it is assigned to, only for notes assigned to more than one part.
    public static func findDuplicateNotes(_ mapping: DrumMapping) -> [Int: [String]] {
        var noteToParts: [Int: [String]] = [:]
        for part in mapping.partNames {
            for note in mapping.notes[part] ?? [] {
                noteToParts[note, default: []].append(part)
            }
        }
        return noteToParts.filter { $0.value.count > 1 }
    }

    public static func formatDuplicates(_ dups: [Int: [String]]) -> String {
        dups.keys.sorted().map { note in
            "\(MidiUtils.noteToName(note)): \(dups[note]!.sorted().joined(separator: ", "))"
        }.joined(separator: "\n")
    }

    // MARK: - Helpers

    private static func stripComment(_ line: String) -> String {
        var inSingle = false, inDouble = false
        var prev: Character = " "
        for (i, ch) in zip(line.indices, line) {
            if ch == "'" && !inDouble { inSingle.toggle() }
            else if ch == "\"" && !inSingle { inDouble.toggle() }
            else if ch == "#" && !inSingle && !inDouble && (prev == " " || prev == "\t" || i == line.startIndex) {
                return String(line[..<i])
            }
            prev = ch
        }
        return line
    }

    private static func unquote(_ s: String) -> String {
        if s.count >= 2, let f = s.first, let l = s.last, f == l, f == "\"" || f == "'" {
            return String(s.dropFirst().dropLast())
        }
        return s
    }
}
