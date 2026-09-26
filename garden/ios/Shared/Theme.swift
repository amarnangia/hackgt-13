import SwiftUI

extension Color {
    init(hex: UInt32, opacity: Double = 1) {
        self.init(red: Double((hex >> 16) & 0xff) / 255, green: Double((hex >> 8) & 0xff) / 255, blue: Double(hex & 0xff) / 255, opacity: opacity)
    }
}

/// Near-black neutrals and one electric-blue accent. The people are the colour; the interface stays quiet.
enum Theme {
    static let bg = Color(hex: 0x08090b)
    static let bg2 = Color(hex: 0x0c0d10)
    static let surface = Color(hex: 0x111216)
    static let surface2 = Color(hex: 0x16171c)
    static let surface3 = Color(hex: 0x1c1d23)
    static let border = Color.white.opacity(0.07)
    static let border2 = Color.white.opacity(0.12)
    static let text = Color(hex: 0xf3f3f1)
    static let text2 = Color(hex: 0xa2a2a8)
    static let text3 = Color(hex: 0x68686f)
    static let accent = Color(hex: 0x5b8cff)
    static let danger = Color(hex: 0xff8a8a)

    static let radius: CGFloat = 16
    static let radiusSmall: CGFloat = 12
}

enum Fonts {
    static func ui(_ size: CGFloat, _ weight: Font.Weight = .regular) -> Font { .system(size: size, weight: weight) }
    /// Translations read like editorial text (New York).
    static func serif(_ size: CGFloat, italic: Bool = false) -> Font {
        let f = Font.system(size: size, weight: .regular, design: .serif)
        return italic ? f.italic() : f
    }
    static func mono(_ size: CGFloat, _ weight: Font.Weight = .medium) -> Font { .system(size: size, weight: weight, design: .monospaced) }
    static func telugu(_ size: CGFloat, _ weight: Font.Weight = .regular) -> Font { .system(size: size, weight: weight) }
}

// MARK: shared pieces

/// Small uppercase monospaced label.
struct Eyebrow: View {
    let text: String
    var color: Color = Theme.text3
    init(_ text: String, color: Color = Theme.text3) { self.text = text; self.color = color }
    var body: some View {
        Text(text.uppercased()).font(Fonts.mono(10.5)).tracking(0.9).foregroundStyle(color)
    }
}

/// Bordered surface.
struct Panel<Content: View>: View {
    var padding: CGFloat = 16
    @ViewBuilder var content: Content
    var body: some View {
        VStack(alignment: .leading, spacing: 0) { content }
            .padding(padding)
            .frame(maxWidth: .infinity, alignment: .leading)
            .background(Theme.surface, in: .rect(cornerRadius: Theme.radius))
            .overlay(RoundedRectangle(cornerRadius: Theme.radius).strokeBorder(Theme.border, lineWidth: 1))
    }
}

/// Tactile press: slight shrink, 150 ms.
struct Pressable: ButtonStyle {
    func makeBody(configuration: Configuration) -> some View {
        configuration.label
            .scaleEffect(configuration.isPressed ? 0.97 : 1)
            .animation(.easeOut(duration: 0.15), value: configuration.isPressed)
    }
}

/// Staggered entrance: 10 pt rise, spring, 55 ms apart.
struct Reveal: ViewModifier {
    let index: Int
    @State private var shown = false
    func body(content: Content) -> some View {
        content
            .opacity(shown ? 1 : 0)
            .offset(y: shown ? 0 : 10)
            .onAppear { withAnimation(.spring(response: 0.46, dampingFraction: 0.9).delay(0.06 + Double(index) * 0.055)) { shown = true } }
    }
}

extension View {
    func reveal(_ index: Int) -> some View { modifier(Reveal(index: index)) }
}

/// Circle with an initial (a Telugu letter for Telugu-speaking family).
struct Avatar: View {
    let text: String
    var size: CGFloat = 44
    var presence: Bool? = nil
    var body: some View {
        ZStack(alignment: .bottomTrailing) {
            Text(text).font(.system(size: size * 0.4, weight: .medium)).foregroundStyle(Theme.text)
                .frame(width: size, height: size)
                .background(LinearGradient(colors: [Theme.surface3, Theme.surface], startPoint: .top, endPoint: .bottom), in: .circle)
                .overlay(Circle().strokeBorder(Theme.border2, lineWidth: 1))
            if let presence {
                Circle().fill(presence ? Theme.accent : Theme.text3).frame(width: 10, height: 10)
                    .overlay(Circle().strokeBorder(Theme.bg, lineWidth: 2)).offset(x: 1, y: 1)
            }
        }
    }
}

extension Stage {
    var label: String { ["bloom": "Known", "sprout": "Learning", "seed": "New"][rawValue]! }
}
