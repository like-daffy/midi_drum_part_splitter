import SwiftUI
import AppKit

@main
struct DrumSplitterApp: App {
    @StateObject private var model = AppModel()

    init() {
        // Lets `swift run` launch a regular, focusable app window.
        NSApplication.shared.setActivationPolicy(.regular)
        NSApplication.shared.activate(ignoringOtherApps: true)
    }

    var body: some Scene {
        WindowGroup("MIDI Drum Splitter") {
            ContentView()
                .environmentObject(model)
                .frame(minWidth: 780, minHeight: 700)
        }
    }
}
