import XCTest
@testable import DrumSplitterCore

final class DrumSplitterCoreTests: XCTestCase {
    func testNoteNames() {
        XCTAssertEqual(MidiUtils.nameToNote("C-2"), 0)
        XCTAssertEqual(MidiUtils.nameToNote("C1"), 36)
        XCTAssertEqual(MidiUtils.nameToNote("A#0"), 34)
        XCTAssertEqual(MidiUtils.nameToNote("Db1"), 37)
        XCTAssertEqual(MidiUtils.nameToNote("G8"), 127)
        XCTAssertEqual(MidiUtils.nameToNote("G#8"), -1)
        XCTAssertEqual(MidiUtils.nameToNote("H1"), -1)
        XCTAssertEqual(MidiUtils.nameToNote("C"), -1)
        XCTAssertEqual(MidiUtils.nameToNote(""), -1)
        XCTAssertEqual(MidiUtils.noteToName(36), "C1")
        XCTAssertEqual(MidiUtils.noteToName(0), "C-2")
    }

    func testDefaultMappingLoadsWithoutDuplicates() throws {
        let mapping = try MappingHandler.load(fromYAML: DefaultMapping.yaml)
        XCTAssertEqual(mapping.partNames, DefaultMapping.displayOrder)
        XCTAssertEqual(mapping.notes["Kick"], [34, 35, 36])
        XCTAssertTrue(MappingHandler.findDuplicateNotes(mapping).isEmpty)
    }

    func testMappingErrors() {
        XCTAssertThrowsError(try MappingHandler.load(fromYAML: "foo: bar"))
        XCTAssertThrowsError(try MappingHandler.load(fromYAML: "drum_parts:\n"))
        XCTAssertThrowsError(try MappingHandler.load(fromYAML: "drum_parts:\n  Kick:\n    - Z9\n"))
    }

    func testDuplicateDetection() throws {
        let m = try MappingHandler.load(fromYAML: "drum_parts:\n  A: [C1, D1]\n  B:\n    - D1 # dup\n")
        let dups = MappingHandler.findDuplicateNotes(m)
        XCTAssertEqual(dups, [38: ["A", "B"]])
        XCTAssertEqual(MappingHandler.formatDuplicates(dups), "D1: A, B")
    }

    func testVarLenRoundTrip() {
        XCTAssertEqual(MidiFile.varLen(0), [0])
        XCTAssertEqual(MidiFile.varLen(0x80), [0x81, 0x00])
        XCTAssertEqual(MidiFile.varLen(0x3FFF), [0xFF, 0x7F])
    }

    func testSplitPreservesTiming() throws {
        let src = MidiFile(division: 480, format: 0, tracks: [[
            MidiEvent(delta: 0, kind: .meta(type: MetaType.setTempo, data: [7, 0xA1, 0x20])),
            MidiEvent(delta: 10, kind: .noteOn(channel: 9, note: 36, velocity: 100)),  // kick
            MidiEvent(delta: 10, kind: .noteOn(channel: 9, note: 38, velocity: 90)),   // snare
            MidiEvent(delta: 10, kind: .noteOff(channel: 9, note: 36, velocity: 0)),
            MidiEvent(delta: 5, kind: .other),
            MidiEvent(delta: 5, kind: .noteOff(channel: 9, note: 38, velocity: 0)),
            MidiEvent(delta: 7, kind: .meta(type: MetaType.endOfTrack, data: [])),
        ]])
        let mapping = try MappingHandler.load(fromYAML: "drum_parts:\n  Kick: [C1]\n  Snare: [D1]\n  Tom: [F1]\n")
        let parts = MidiSplitter.split(src, mapping: mapping)
        XCTAssertEqual(parts.map(\.name), ["Kick", "Snare", "Tom"])

        let kick = parts[0].midi.tracks[0]
        XCTAssertEqual(kick.map(\.delta), [0, 10, 20, 17])
        XCTAssertTrue(parts[0].hasNotes)
        XCTAssertFalse(parts[2].hasNotes)

        let snare = parts[1].midi.tracks[0]
        XCTAssertEqual(snare.map(\.delta), [0, 20, 20, 7])
    }

    func testSerializeParseRoundTrip() throws {
        let original = MidiFile(division: 960, format: 1, tracks: [[
            MidiEvent(delta: 0, kind: .meta(type: MetaType.trackName, data: Array("Kick".utf8))),
            MidiEvent(delta: 480, kind: .noteOn(channel: 9, note: 36, velocity: 127)),
            MidiEvent(delta: 200, kind: .noteOff(channel: 9, note: 36, velocity: 0)),
            MidiEvent(delta: 0, kind: .meta(type: MetaType.endOfTrack, data: [])),
        ]])
        let parsed = try MidiFile.parse(original.serialized())
        XCTAssertEqual(parsed, original)
    }

    func testParseRunningStatus() throws {
        var bytes = Array("MThd".utf8) + [0, 0, 0, 6, 0, 0, 0, 1, 1, 0xE0]
        let track: [UInt8] = [0x00, 0x99, 36, 100, 0x10, 38, 90, 0x10, 0x89, 36, 0, 0x00, 0xFF, 0x2F, 0x00]
        bytes += Array("MTrk".utf8) + [0, 0, 0, UInt8(track.count)] + track
        let file = try MidiFile.parse(Data(bytes))
        XCTAssertEqual(file.division, 480)
        XCTAssertEqual(file.tracks[0].count, 4)
        XCTAssertEqual(file.tracks[0][1].kind, .noteOn(channel: 9, note: 38, velocity: 90))
    }

    func testParseRejectsGarbage() {
        XCTAssertThrowsError(try MidiFile.parse(Data([1, 2, 3])))
        XCTAssertThrowsError(try MidiFile.parse(Data("not a midi file".utf8)))
    }
}
