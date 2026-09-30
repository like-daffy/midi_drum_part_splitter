// swift-tools-version:5.9
import PackageDescription

let package = Package(
    name: "DrumSplitter",
    platforms: [.macOS(.v13)],
    products: [
        .library(name: "DrumSplitterCore", targets: ["DrumSplitterCore"]),
        .executable(name: "DrumSplitter", targets: ["DrumSplitterApp"]),
    ],
    targets: [
        // Pure Foundation logic: MIDI parsing/writing, YAML mapping, splitting.
        .target(name: "DrumSplitterCore"),
        // SwiftUI front end.
        .executableTarget(name: "DrumSplitterApp", dependencies: ["DrumSplitterCore"]),
        .testTarget(name: "DrumSplitterCoreTests", dependencies: ["DrumSplitterCore"]),
    ]
)
