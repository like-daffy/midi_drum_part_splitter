import Foundation

/// A MIDI event with a delta time (in ticks) relative to the previous event of the track.
public struct MidiEvent: Equatable {
    public enum Kind: Equatable {
        case noteOn(channel: UInt8, note: UInt8, velocity: UInt8)
        case noteOff(channel: UInt8, note: UInt8, velocity: UInt8)
        case meta(type: UInt8, data: [UInt8])
        /// Any other channel/sysex message. Its bytes are not retained.
        case other
    }

    public var delta: Int
    public var kind: Kind

    public init(delta: Int, kind: Kind) {
        self.delta = delta
        self.kind = kind
    }
}

public struct MidiFile: Equatable {
    /// Raw division field of the header (ticks per beat, or SMPTE when the top bit is set).
    public var division: UInt16
    public var format: UInt16
    public var tracks: [[MidiEvent]]

    public init(division: UInt16 = 480, format: UInt16 = 1, tracks: [[MidiEvent]] = []) {
        self.division = division
        self.format = format
        self.tracks = tracks
    }
}

public enum MidiFileError: LocalizedError {
    case invalid(String)
    public var errorDescription: String? {
        if case .invalid(let m) = self { return m }
        return nil
    }
}

// MARK: - Meta event types

public enum MetaType {
    public static let trackName: UInt8 = 0x03
    public static let instrumentName: UInt8 = 0x04
    public static let marker: UInt8 = 0x06
    public static let cueMarker: UInt8 = 0x07
    public static let endOfTrack: UInt8 = 0x2F
    public static let setTempo: UInt8 = 0x51
    public static let smpteOffset: UInt8 = 0x54
    public static let timeSignature: UInt8 = 0x58
    public static let keySignature: UInt8 = 0x59

    /// Meta messages that are copied into each split part.
    public static let keep: Set<UInt8> = [
        setTempo, timeSignature, keySignature, smpteOffset,
        trackName, endOfTrack, instrumentName, marker, cueMarker,
    ]
}

// MARK: - Parsing

extension MidiFile {
    public static func parse(_ data: Data) throws -> MidiFile {
        let bytes = [UInt8](data)
        var pos = 0

        func need(_ n: Int) throws {
            if pos + n > bytes.count { throw MidiFileError.invalid("Unexpected end of file") }
        }
        func u16() throws -> UInt16 {
            try need(2); defer { pos += 2 }
            return UInt16(bytes[pos]) << 8 | UInt16(bytes[pos + 1])
        }
        func u32() throws -> Int {
            try need(4); defer { pos += 4 }
            return Int(bytes[pos]) << 24 | Int(bytes[pos + 1]) << 16 | Int(bytes[pos + 2]) << 8 | Int(bytes[pos + 3])
        }

        try need(8)
        guard Array(bytes[0..<4]) == Array("MThd".utf8) else {
            throw MidiFileError.invalid("MThd header not found")
        }
        pos = 4
        let headerLen = try u32()
        guard headerLen >= 6 else { throw MidiFileError.invalid("Invalid header length") }
        let format = try u16()
        let trackCount = Int(try u16())
        let division = try u16()
        pos = 8 + headerLen

        var tracks: [[MidiEvent]] = []
        while tracks.count < trackCount && pos + 8 <= bytes.count {
            let id = Array(bytes[pos..<pos + 4])
            pos += 4
            let length = try u32()
            let end = min(pos + length, bytes.count)
            if id == Array("MTrk".utf8) {
                tracks.append(try parseTrack(bytes, from: pos, to: end))
            }
            pos = end
        }
        return MidiFile(division: division, format: format, tracks: tracks)
    }

    private static func parseTrack(_ b: [UInt8], from start: Int, to end: Int) throws -> [MidiEvent] {
        var pos = start
        var events: [MidiEvent] = []
        var runningStatus: UInt8 = 0

        func byte() throws -> UInt8 {
            guard pos < end else { throw MidiFileError.invalid("Unexpected end of track") }
            defer { pos += 1 }
            return b[pos]
        }
        func varLen() throws -> Int {
            var value = 0
            for _ in 0..<4 {
                let c = try byte()
                value = value << 7 | Int(c & 0x7F)
                if c & 0x80 == 0 { return value }
            }
            throw MidiFileError.invalid("Invalid variable-length quantity")
        }
        func take(_ n: Int) throws -> [UInt8] {
            guard n >= 0, pos + n <= end else { throw MidiFileError.invalid("Unexpected end of track") }
            defer { pos += n }
            return Array(b[pos..<pos + n])
        }

        while pos < end {
            let delta = try varLen()
            var status = try byte()
            var firstData: UInt8?

            if status < 0x80 {
                guard runningStatus != 0 else { throw MidiFileError.invalid("Data byte without running status") }
                firstData = status
                status = runningStatus
            }

            switch status {
            case 0xFF:
                runningStatus = 0
                let type = try byte()
                let len = try varLen()
                let data = try take(len)
                events.append(MidiEvent(delta: delta, kind: .meta(type: type, data: data)))
            case 0xF0, 0xF7:
                runningStatus = 0
                let len = try varLen()
                _ = try take(len)
                events.append(MidiEvent(delta: delta, kind: .other))
            case 0x80...0xEF:
                runningStatus = status
                let d1 = try firstData ?? byte()
                let type = status & 0xF0
                let channel = status & 0x0F
                if type == 0xC0 || type == 0xD0 {
                    events.append(MidiEvent(delta: delta, kind: .other))
                } else {
                    let d2 = try byte()
                    switch type {
                    case 0x80: events.append(MidiEvent(delta: delta, kind: .noteOff(channel: channel, note: d1, velocity: d2)))
                    case 0x90: events.append(MidiEvent(delta: delta, kind: .noteOn(channel: channel, note: d1, velocity: d2)))
                    default: events.append(MidiEvent(delta: delta, kind: .other))
                    }
                }
            default:
                // System common / realtime messages (no data or fixed data we cannot know); skip.
                runningStatus = 0
                switch status {
                case 0xF1, 0xF3: _ = try byte()
                case 0xF2: _ = try take(2)
                default: break
                }
                events.append(MidiEvent(delta: delta, kind: .other))
            }
        }
        return events
    }
}

// MARK: - Serialization

extension MidiFile {
    public func serialized() -> Data {
        var out = [UInt8]()
        out += Array("MThd".utf8)
        out += be32(6)
        out += be16(format)
        out += be16(UInt16(tracks.count))
        out += be16(division)

        for track in tracks {
            var body = [UInt8]()
            for event in track {
                if case .other = event.kind { continue }
                body += Self.varLen(event.delta)
                switch event.kind {
                case let .noteOn(ch, note, vel): body += [0x90 | (ch & 0x0F), note & 0x7F, vel & 0x7F]
                case let .noteOff(ch, note, vel): body += [0x80 | (ch & 0x0F), note & 0x7F, vel & 0x7F]
                case let .meta(type, data): body += [0xFF, type] + Self.varLen(data.count) + data
                case .other: break
                }
            }
            out += Array("MTrk".utf8)
            out += be32(body.count)
            out += body
        }
        return Data(out)
    }

    static func varLen(_ value: Int) -> [UInt8] {
        var v = max(0, value)
        var bytes = [UInt8(v & 0x7F)]
        v >>= 7
        while v > 0 {
            bytes.insert(UInt8(v & 0x7F) | 0x80, at: 0)
            v >>= 7
        }
        return bytes
    }

    private func be16(_ v: UInt16) -> [UInt8] { [UInt8(v >> 8), UInt8(v & 0xFF)] }
    private func be32(_ v: Int) -> [UInt8] {
        [UInt8((v >> 24) & 0xFF), UInt8((v >> 16) & 0xFF), UInt8((v >> 8) & 0xFF), UInt8(v & 0xFF)]
    }
}
