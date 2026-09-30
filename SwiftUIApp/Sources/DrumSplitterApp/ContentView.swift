import SwiftUI
import UniformTypeIdentifiers

struct ContentView: View {
    @EnvironmentObject var model: AppModel

    var body: some View {
        VStack(spacing: 8) {
            InputSection()
            OutputSection()
            AboutSection()
        }
        .padding(8)
        .background(Theme.background)
        .foregroundStyle(Theme.foreground)
        .preferredColorScheme(.dark)
        .alert(item: $model.alert) { info in
            Alert(title: Text(info.title),
                  message: Text(info.message),
                  dismissButton: .default(Text("OK")) {
                      if info.quitOnDismiss { NSApplication.shared.terminate(nil) }
                  })
        }
    }
}

private struct Card<Content: View>: View {
    @ViewBuilder var content: Content
    var body: some View {
        content
            .padding(16)
            .frame(maxWidth: .infinity)
            .background(Theme.section, in: RoundedRectangle(cornerRadius: 12))
    }
}

// MARK: - Input

struct InputSection: View {
    @EnvironmentObject var model: AppModel

    var body: some View {
        Card {
            VStack(spacing: 12) {
                Text("Drag-and-drop ONE MIDI file below (or click the area to browse), optionally pick a custom YAML mapping,\nthen click Proceed to preview 6 parts you can drag out to Finder to save.")
                    .font(.system(size: 13, weight: .medium))
                    .foregroundStyle(Theme.mutedForeground)
                    .frame(maxWidth: .infinity, alignment: .leading)

                DropZone().frame(height: 100)

                HStack(spacing: 12) {
                    if model.inputURL != nil {
                        Button("Select Again") { model.selectAgain() }
                            .buttonStyle(ThemedButtonStyle())
                            .frame(width: 160)
                    }
                    Button("Proceed") { model.proceed() }
                        .buttonStyle(ThemedButtonStyle(prominent: true))
                        .keyboardShortcut(.defaultAction)
                        .frame(width: 160)
                }

                HStack {
                    TextField("Custom YAML mapping path (optional)", text: $model.yamlPath)
                        .textFieldStyle(.plain)
                        .padding(.horizontal, 12).padding(.vertical, 8)
                        .background(Theme.muted, in: RoundedRectangle(cornerRadius: 8))
                        .overlay(RoundedRectangle(cornerRadius: 8).strokeBorder(Theme.primary, lineWidth: 2))
                    Button("Browse…") { model.browseYAML() }.buttonStyle(ThemedButtonStyle())
                    Button("Default") { model.useDefaultYAML() }.buttonStyle(ThemedButtonStyle())
                }

                HStack {
                    Toggle("Next time use the same configuration", isOn: $model.useSameConfig)
                        .toggleStyle(.checkbox)
                        .foregroundStyle(Theme.mutedForeground)
                    Spacer()
                    Text("You can export").foregroundStyle(Theme.mutedForeground)
                    Button("Default Template (.yaml)") { model.saveTemplate() }
                        .buttonStyle(ThemedButtonStyle())
                }
            }
        }
    }
}

struct DropZone: View {
    @EnvironmentObject var model: AppModel
    @State private var targeted = false

    var body: some View {
        ZStack {
            RoundedRectangle(cornerRadius: 12)
                .fill(Theme.card.opacity(model.inputURL == nil ? 0 : 1))
            RoundedRectangle(cornerRadius: 12)
                .strokeBorder(model.inputURL == nil ? Color.gray : Theme.primary,
                              style: StrokeStyle(lineWidth: 2, dash: model.inputURL == nil ? [2, 4] : []))
            if targeted { RoundedRectangle(cornerRadius: 12).fill(Theme.primary.opacity(0.2)) }

            if let url = model.inputURL {
                VStack(spacing: 2) {
                    Text(url.lastPathComponent).font(.system(size: 14, weight: .bold))
                    Text(url.deletingLastPathComponent().path)
                        .font(.system(size: 11)).foregroundStyle(Theme.mutedForeground)
                        .lineLimit(1).truncationMode(.head)
                }
                .padding(.horizontal, 12)
            } else {
                Text("Drag & drop a MIDI file here\n(or click to browse)")
                    .font(.system(size: 14, weight: .bold))
                    .multilineTextAlignment(.center)
                    .foregroundStyle(Color.gray)
            }
        }
        .contentShape(Rectangle())
        .onTapGesture { if model.inputURL == nil { model.browseMIDI() } }
        .onDrop(of: [.fileURL], isTargeted: $targeted) { providers in
            for provider in providers {
                _ = provider.loadObject(ofClass: URL.self) { url, _ in
                    guard let url else { return }
                    DispatchQueue.main.async { model.setInput(url) }
                }
            }
            return true
        }
    }
}

// MARK: - Output

struct OutputSection: View {
    @EnvironmentObject var model: AppModel

    var body: some View {
        Card {
            if model.results.isEmpty {
                Text("Output Result\n\nClick \"Proceed\" to split MIDI file")
                    .font(.system(size: 16, weight: .bold))
                    .multilineTextAlignment(.center)
                    .foregroundStyle(Color(white: 0.4))
                    .frame(maxWidth: .infinity, maxHeight: .infinity)
                    .overlay(RoundedRectangle(cornerRadius: 12)
                        .strokeBorder(Color(white: 0.4), style: StrokeStyle(lineWidth: 2, dash: [2, 4])))
            } else {
                VStack(alignment: .leading, spacing: 12) {
                    Text("Drag out to save")
                        .font(.system(size: 14, weight: .heavy))
                    ScrollView(.horizontal) {
                        HStack(alignment: .top, spacing: 12) {
                            ForEach(model.results) { PartTile(part: $0) }
                        }
                        .padding(.bottom, 8)
                    }
                    Spacer(minLength: 0)
                }
                .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .topLeading)
            }
        }
        .frame(maxHeight: .infinity)
    }
}

struct PartTile: View {
    @EnvironmentObject var model: AppModel
    let part: PartResult

    var body: some View {
        VStack(spacing: 6) {
            Text(part.name).font(.system(size: 16, weight: .bold))
            Text(part.hasNotes ? "Drag\nout\nto\nsave" : "Empty")
                .font(.system(size: 14, weight: .heavy))
                .multilineTextAlignment(.center)
                .foregroundStyle(part.hasNotes ? Color(red: 0.26, green: 0.65, blue: 0.96) : Color.gray)
                .frame(maxHeight: .infinity)
        }
        .padding(8)
        .frame(width: 110, height: 150)
        .overlay(RoundedRectangle(cornerRadius: 8)
            .strokeBorder(part.hasNotes ? Color(red: 0.42, green: 0.66, blue: 0.91) : Color(white: 0.47),
                          style: StrokeStyle(lineWidth: 2, dash: [5, 3])))
        .opacity(part.hasNotes ? 1 : 0.5)
        .onDrag {
            model.provider(for: part)
        } preview: {
            Text(part.fileName)
                .font(.system(size: 12, weight: .bold))
                .padding(.horizontal, 12).padding(.vertical, 8)
                .background(Color(red: 0.1, green: 0.46, blue: 0.82))
                .foregroundStyle(.white)
        }
        .allowsHitTesting(part.hasNotes)
        .help(part.hasNotes ? "Drag to Finder to save \(part.fileName)" : "No notes in this part")
    }
}

// MARK: - About

struct AboutSection: View {
    var body: some View {
        Card {
            Link("Copyright (c) 2025 Sochan, X(twitter): @sochan_life",
                 destination: URL(string: "https://x.com/sochan_life")!)
                .font(.system(size: 14))
                .foregroundStyle(Color(white: 0.73))
                .frame(maxWidth: .infinity, alignment: .leading)
        }
    }
}
