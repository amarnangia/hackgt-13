import SwiftUI
import UIKit

extension Color {
    init(hex: UInt32, opacity: Double = 1) {
        self.init(red: Double((hex >> 16) & 0xff) / 255, green: Double((hex >> 8) & 0xff) / 255, blue: Double(hex & 0xff) / 255, opacity: opacity)
    }
}

/// Stone neutrals and one terracotta accent. Light and dark are separate steps, not an automatic flip.
enum Theme {
    private static func dynamic(_ light: Color, _ dark: Color) -> Color {
        Color(UIColor { $0.userInterfaceStyle == .dark ? UIColor(dark) : UIColor(light) })
    }
    static let bg = dynamic(Color(hex: 0xf7f5f2), Color(hex: 0x0c0a09))
    static let surface = dynamic(Color(hex: 0xfdfcfb), Color(hex: 0x161412))
    static let raised = dynamic(Color(hex: 0xefebe7), Color(hex: 0x221f1c))
    static let border = dynamic(Color.black.opacity(0.08), Color.white.opacity(0.09))
    static let ink = dynamic(Color(hex: 0x1c1917), Color(hex: 0xfafaf9))
    static let ink2 = dynamic(Color(hex: 0x57534e), Color(hex: 0xa8a29e))
    static let muted = dynamic(Color(hex: 0x8a837d), Color(hex: 0x78716c))
    static let accent = dynamic(Color(hex: 0xb4532a), Color(hex: 0xe0825f))

    static let radius: CGFloat = 16
}

extension Stage {
    /// Plain names in the app: the garden words stay in the data.
    var label: String { ["bloom": "Known", "sprout": "Learning", "seed": "New"][rawValue]! }
    /// Accent strength for this stage: one hue, three steps.
    var fill: Color {
        switch self {
        case .bloom: Theme.accent
        case .sprout: Theme.accent.opacity(0.45)
        case .seed: Theme.accent.opacity(0.14)
        }
    }
}

// MARK: shared pieces

/// Small uppercase section label.
struct Eyebrow: View {
    let text: String
    var color: Color = Theme.muted
    init(_ text: String, color: Color = Theme.muted) { self.text = text; self.color = color }
    var body: some View {
        Text(text.uppercased()).font(.system(size: 11, weight: .semibold)).tracking(0.8).foregroundStyle(color)
    }
}

/// Bordered surface. No shadow.
struct Panel<Content: View>: View {
    var padding: CGFloat = 20
    @ViewBuilder var content: Content
    var body: some View {
        VStack(alignment: .leading, spacing: 0) { content }
            .padding(padding)
            .frame(maxWidth: .infinity, alignment: .leading)
            .background(Theme.surface, in: .rect(cornerRadius: Theme.radius))
            .overlay(RoundedRectangle(cornerRadius: Theme.radius).strokeBorder(Theme.border, lineWidth: 1))
    }
}

/// Tactile press: a slight shrink and dim, 200 ms.
struct Pressable: ButtonStyle {
    func makeBody(configuration: Configuration) -> some View {
        configuration.label
            .scaleEffect(configuration.isPressed ? 0.97 : 1)
            .opacity(configuration.isPressed ? 0.85 : 1)
            .animation(.easeOut(duration: 0.2), value: configuration.isPressed)
    }
}

/// Eight segments from new to known.
struct GrowthBar: View {
    let growth: Int
    var total = 8
    var height: CGFloat = 4
    var body: some View {
        HStack(spacing: 2) {
            ForEach(0..<total, id: \.self) { i in
                Capsule().fill(i < growth ? Theme.accent : Theme.raised).frame(height: height)
            }
        }
        .animation(.easeOut(duration: 0.3), value: growth)
    }
}

/// "Ask how she makes పులిహోర." with the Telugu word in the accent.
func starterText(_ s: Starter, size: CGFloat) -> Text {
    (Text(s.before + " ").foregroundColor(Theme.ink) + Text(s.word).foregroundColor(Theme.accent) + Text(s.after).foregroundColor(Theme.ink))
        .font(.system(size: size, weight: .semibold))
        .tracking(size >= 20 ? -0.6 : -0.2)
}
