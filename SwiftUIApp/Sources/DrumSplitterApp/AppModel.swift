import SwiftUI
import AppKit
import UniformTypeIdentifiers
import DrumSplitterCore

struct AlertInfo: Identifiable {
    let id = UUID()
    let title: String
    let message: String
    var quitOnDismiss = false
}

/// One split part that can be dragged out to Finder.
final class PartResult: Identifiable {
    let name: String
    let midi: MidiFile
    let hasNotes: Bool
    let fileName: String
    private let tempDir: URL
    private var tempURL: URL?

    var id: String { name }

    init(name: String, midi: MidiFile, hasNotes: Bool, baseName: String, tempDir: URL) {
        self.name = name
        self.midi = midi
        self.hasNotes = hasNotes
        self.fileName = "\(baseName)-\(name.lowercased()).mid"
        self.tempDir = tempDir
    }

    /// Writes the part to the temp dir on first use.
    func ensureTempFile() throws -> URL {
        if let url = tempURL, FileManager.default.fileExists(atPath: url.path) { return url }
        let url = tempDir.appendingPathComponent(fileName)
        try midi.serialized().write(to: url, options: .atomic)
        tempURL = url
        return url
    }
}

@MainActor
final class AppModel: ObservableObject {
    private enum Key {
        static let useCustom = "use_custom_config"
        static let customPath = "custom_config_path"
    }

    @Published var inputURL: URL?
    @Published var yamlPath: String {
        didSet { if useSameConfig { persistPreferences() }; mapping = nil }
    }
    @Published var useSameConfig: Bool {
        didSet { persistPreferences() }
    }
    @Published var results: [PartResult] = []
    @Published var alert: AlertInfo?

    private var mapping: DrumMapping?
    private var resultsDir: URL?
    private let defaults = UserDefaults.standard

    init() {
        useSameConfig = defaults.bool(forKey: Key.useCustom)
        yamlPath = defaults.string(forKey: Key.customPath) ?? ""
        loadEffectiveMapping()
        NotificationCenter.default.addObserver(
            forName: NSApplication.willTerminateNotification, object: nil, queue: .main
        ) { [weak self] _ in
            MainActor.assumeIsolated { self?.shutdown() }
        }
    }

    // MARK: Preferences & mapping

    private func persistPreferences() {
        defaults.set(useSameConfig, forKey: Key.useCustom)
        defaults.set(yamlPath.trimmingCharacters(in: .whitespaces), forKey: Key.customPath)
    }

    private var trimmedYAMLPath: String { yamlPath.trimmingCharacters(in: .whitespaces) }

    private func effectiveYAMLText() -> String {
        let path = trimmedYAMLPath
        if useSameConfig && !path.isEmpty {
            do {
                return try String(contentsOfFile: path, encoding: .utf8)
            } catch {
                alert = AlertInfo(title: "YAML Error",
                                  message: "Failed to read custom YAML:\n\(error.localizedDescription)\nUsing default mapping instead.")
            }
        }
        return DefaultMapping.yaml
    }

    func loadEffectiveMapping() {
        let isCustom = useSameConfig && !trimmedYAMLPath.isEmpty
        let text = effectiveYAMLText()

        let loaded: DrumMapping
        do {
            loaded = try MappingHandler.load(fromYAML: text)
        } catch {
            mapping = nil
            alert = AlertInfo(title: "YAML Error", message: "Invalid YAML mapping:\n\(error.localizedDescription)")
            if isCustom { resetYAMLSettings() }
            return
        }

        let dups = MappingHandler.findDuplicateNotes(loaded)
        if !dups.isEmpty {
            let details = MappingHandler.formatDuplicates(dups)
            mapping = nil
            if isCustom {
                alert = AlertInfo(title: "Duplicate Notes in Mapping",
                                  message: "The selected YAML contains duplicate notes assigned to multiple parts.\n\n\(details)\n\nPlease resolve and try again.")
                resetYAMLSettings()
            } else {
                alert = AlertInfo(title: "Default Mapping Error",
                                  message: "Default YAML contains duplicate notes (developer fix required):\n\n\(details)",
                                  quitOnDismiss: true)
            }
            return
        }
        mapping = loaded
    }

    private func resetYAMLSettings() {
        yamlPath = ""
        useSameConfig = false
        persistPreferences()
    }

    // MARK: Actions

    func setInput(_ url: URL) {
        guard ["mid", "midi"].contains(url.pathExtension.lowercased()),
              FileManager.default.fileExists(atPath: url.path) else { return }
        clearResults()
        inputURL = url
    }

    func selectAgain() {
        clearResults()
        inputURL = nil
    }

    func browseMIDI() {
        let panel = NSOpenPanel()
        panel.title = "Select MIDI File"
        panel.allowedContentTypes = ["mid", "midi"].compactMap { UTType(filenameExtension: $0) }
        panel.directoryURL = inputURL?.deletingLastPathComponent()
        if panel.runModal() == .OK, let url = panel.url { setInput(url) }
    }

    func browseYAML() {
        let panel = NSOpenPanel()
        panel.title = "Select YAML Mapping"
        panel.allowedContentTypes = ["yml", "yaml"].compactMap { UTType(filenameExtension: $0) }
        if !trimmedYAMLPath.isEmpty {
            panel.directoryURL = URL(fileURLWithPath: trimmedYAMLPath).deletingLastPathComponent()
        }
        guard panel.runModal() == .OK, let url = panel.url else { return }
        yamlPath = url.path
        useSameConfig = true
        persistPreferences()
        loadEffectiveMapping()
    }

    func useDefaultYAML() {
        resetYAMLSettings()
        loadEffectiveMapping()
    }

    func saveTemplate() {
        let panel = NSSavePanel()
        panel.title = "Save Default Mapping Template"
        panel.nameFieldStringValue = "default.yaml"
        panel.allowedContentTypes = ["yaml"].compactMap { UTType(filenameExtension: $0) }
        guard panel.runModal() == .OK, var url = panel.url else { return }
        if url.pathExtension.lowercased() != "yaml" {
            url = url.deletingPathExtension().appendingPathExtension("yaml")
        }
        do {
            try DefaultMapping.yaml.write(to: url, atomically: true, encoding: .utf8)
            alert = AlertInfo(title: "Saved", message: "Template saved to:\n\(url.path)")
        } catch {
            alert = AlertInfo(title: "Write Error", message: "Failed to save template:\n\(error.localizedDescription)")
        }
    }

    func proceed() {
        guard let input = inputURL else {
            alert = AlertInfo(title: "No File", message: "Please drag-and-drop ONE MIDI file to proceed.")
            return
        }
        loadEffectiveMapping()
        guard let mapping else { return }

        let parts: [SplitPart]
        do {
            parts = try MidiSplitter.split(fileAt: input, mapping: mapping)
        } catch {
            alert = AlertInfo(title: "Split Error", message: "Failed to split MIDI file:\n\(error.localizedDescription)")
            return
        }

        clearResults()
        let dir = FileManager.default.temporaryDirectory
            .appendingPathComponent("drum_split_\(UUID().uuidString)", isDirectory: true)
        do {
            try FileManager.default.createDirectory(at: dir, withIntermediateDirectories: true)
        } catch {
            alert = AlertInfo(title: "Export Error", message: "Failed to create temporary folder:\n\(error.localizedDescription)")
            return
        }
        resultsDir = dir

        let base = input.deletingPathExtension().lastPathComponent
        let byName = Dictionary(uniqueKeysWithValues: parts.map { ($0.name, $0) })
        // Standard parts first (in display order), then any custom parts from the YAML.
        let order = DefaultMapping.displayOrder + parts.map(\.name).filter { !DefaultMapping.displayOrder.contains($0) }
        results = order.map { name in
            if let part = byName[name] {
                return PartResult(name: name, midi: part.midi, hasNotes: part.hasNotes, baseName: base, tempDir: dir)
            }
            return PartResult(name: name, midi: MidiFile(), hasNotes: false, baseName: base, tempDir: dir)
        }
    }

    func provider(for part: PartResult) -> NSItemProvider {
        do {
            let url = try part.ensureTempFile()
            return NSItemProvider(contentsOf: url) ?? NSItemProvider(object: url as NSURL)
        } catch {
            alert = AlertInfo(title: "Export Error",
                              message: "Failed to create temporary file for \(part.name):\n\(error.localizedDescription)")
            return NSItemProvider()
        }
    }

    private func clearResults() {
        results = []
        if let dir = resultsDir { try? FileManager.default.removeItem(at: dir) }
        resultsDir = nil
    }

    func shutdown() {
        clearResults()
        if !useSameConfig { defaults.set("", forKey: Key.customPath) }
    }
}
