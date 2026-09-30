import SwiftUI

/// "Blue Sea" theme, defined in OKLCH and converted to sRGB (same values as the Qt version).
enum Theme {
    static func oklch(_ l: Double, _ c: Double, _ hDeg: Double) -> Color {
        let h = hDeg * .pi / 180
        let a = cos(h) * c
        let b = sin(h) * c

        let l_ = l + 0.3963377774 * a + 0.2158037573 * b
        let m_ = l - 0.1055613458 * a - 0.0638541728 * b
        let s_ = l - 0.0894841775 * a - 1.2914855480 * b
        let l3 = l_ * l_ * l_, m3 = m_ * m_ * m_, s3 = s_ * s_ * s_

        let rLin = 4.0767416621 * l3 - 3.3077115913 * m3 + 0.2309699292 * s3
        let gLin = -1.2684380046 * l3 + 2.6097574011 * m3 - 0.3413193965 * s3
        let bLin = -0.0041960863 * l3 - 0.7034186147 * m3 + 1.7076147010 * s3

        func toSRGB(_ x: Double) -> Double {
            let v = x <= 0.0031308 ? 12.92 * x : 1.055 * pow(max(x, 0), 1 / 2.4) - 0.055
            return min(max(v, 0), 1)
        }
        return Color(.sRGB, red: toSRGB(rLin), green: toSRGB(gLin), blue: toSRGB(bLin), opacity: 1)
    }

    static let background = oklch(0.2784, 0.1000, 258.0)
    static let foreground = oklch(0.9500, 0, 0)
    static let card = oklch(0.3451, 0.0800, 258.0)
    static let primary = oklch(0.6510, 0.1500, 255.0)
    static let primaryForeground = oklch(1.0, 0, 0)
    static let secondary = oklch(0.8510, 0.0500, 255.0)
    static let muted = oklch(0.4118, 0.0600, 258.0)
    static let mutedForeground = oklch(0.8000, 0, 0)
    static let accent = oklch(0.9529, 0.0800, 55.0)
    static let border = oklch(0.4118, 0.0600, 258.0)
    static let section = Color.white.opacity(0.05)
}

struct ThemedButtonStyle: ButtonStyle {
    var prominent = false
    @State private var hovering = false

    func makeBody(configuration: Configuration) -> some View {
        configuration.label
            .font(.system(size: prominent ? 16 : 14, weight: .bold))
            .foregroundStyle(prominent ? Theme.background : Theme.primaryForeground)
            .padding(.horizontal, 20)
            .padding(.vertical, 10)
            .background(prominent ? Theme.accent : Theme.primary, in: RoundedRectangle(cornerRadius: 8))
            .overlay(
                RoundedRectangle(cornerRadius: 8)
                    .strokeBorder(hovering ? Theme.primary : (prominent ? Theme.accent : Theme.border),
                                  lineWidth: prominent && hovering ? 3 : 2)
            )
            .opacity(configuration.isPressed ? 0.8 : 1)
            .onHover { hovering = $0 }
    }
}
