import SwiftUI

extension Color {
    init(hex: UInt32, opacity: Double = 1) {
        self.init(red: Double((hex >> 16) & 0xff) / 255, green: Double((hex >> 8) & 0xff) / 255, blue: Double(hex & 0xff) / 255, opacity: opacity)
    }
}

/// The same system as the call overlay (extension/panel.css): deep grays and glass, with green accents only for
/// what's active: WhatsApp green (`cyan`), Spotify green (`accent`), dark Spotify green (`violet`); the names are
/// the old ones. "Ask her" is light mint; connected is WhatsApp green.
enum Theme {
    static let bg = Color(hex: 0x121212)
    static let bg2 = Color(hex: 0x161616)
    static let surface = Color(hex: 0x1a1a1a)
    static let surface2 = Color(hex: 0x1f1f21)
    static let surface3 = Color(hex: 0x26262a)
    static let border = Color.white.opacity(0.05)
    static let border2 = Color.white.opacity(0.09)
    static let text = Color(hex: 0xf4f5f7)
    static let text2 = Color(hex: 0xa1a1aa)
    static let text3 = Color(hex: 0x6b6b74)
    static let accent = Color(hex: 0x1db954)
    static let onAccent = Color.white
    static let cyan = Color(hex: 0x25d366)
    static let violet = Color(hex: 0x168d40)
    static let gradient = LinearGradient(colors: [cyan, accent, violet], startPoint: .topLeading, endPoint: .bottomTrailing)
    /// Muted deep greens for big buttons ("Start a connection"), where the bright gradient is too loud
    static let deep = Color(hex: 0x1e3d2e)
    static let deep2 = Color(hex: 0x264c39)
    /// Dark green edges with Spotify green glowing through the middle
    static let deepGradient = LinearGradient(colors: [deep, Color(hex: 0x1a7a3d), deep], startPoint: .leading, endPoint: .trailing)
    static let warm = Color(hex: 0x7ee2a8)      // "Ask her"
    static let onWarm = Color.white
    static let green = cyan                     // connected
    /// A third, quieter accent: muted lavender, for what's in progress (words you're learning) and for depth in the
    /// background. The greens stay the primary accents.
    static let lavender = Color(hex: 0xb3a6d4)
    static let lavenderDeep = Color(hex: 0x5f5680)
    /// Card surfaces lit from above
    static let cardTop = Color(hex: 0x202024)
    static let cardBottom = Color(hex: 0x161618)
    static let danger = Color(hex: 0xff8a8a)

    static let radius: CGFloat = 16
    static let radiusSmall: CGFloat = 12
}

enum Fonts {
    static func ui(_ size: CGFloat, _ weight: Font.Weight = .regular) -> Font { .system(size: size, weight: weight) }
    /// Big headlines: Apple's New York serif, for a little character against the sans UI.
    static func display(_ size: CGFloat, _ weight: Font.Weight = .medium) -> Font { .system(size: size, weight: weight, design: .serif) }
    /// Captions and translations: semibold, like the overlay's English line. (The pronunciation, `italic`, is bold.)
    static func serif(_ size: CGFloat, italic: Bool = false) -> Font { .system(size: size, weight: italic ? .bold : .semibold) }
    /// Numbers and small labels: the system font with even-width digits.
    static func mono(_ size: CGFloat, _ weight: Font.Weight = .semibold) -> Font { .system(size: size, weight: weight).monospacedDigit() }
    static func telugu(_ size: CGFloat, _ weight: Font.Weight = .regular) -> Font { .system(size: size, weight: weight) }
}

// MARK: shared pieces

/// Small uppercase label, like the overlay's .eyebrow.
struct Eyebrow: View {
    let text: String
    var color: Color = Theme.text3
    init(_ text: String, color: Color = Theme.text3) { self.text = text; self.color = color }
    var body: some View {
        Text(text.uppercased()).font(.system(size: 11, weight: .bold)).tracking(0.66).foregroundStyle(color)
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
            .background(Card())
    }
}

/// A raised surface: lit from above, a bright top edge fading down its sides, and a soft shadow under it.
struct Card: View {
    var radius: CGFloat = Theme.radius
    var body: some View {
        RoundedRectangle(cornerRadius: radius)
            .fill(LinearGradient(colors: [Theme.cardTop, Theme.cardBottom], startPoint: .top, endPoint: .bottom))
            .overlay(RoundedRectangle(cornerRadius: radius)
                .strokeBorder(LinearGradient(colors: [.white.opacity(0.13), .white.opacity(0.04), .white.opacity(0.02)], startPoint: .top, endPoint: .bottom), lineWidth: 1))
            .shadow(color: .black.opacity(0.5), radius: 18, y: 10)
            .shadow(color: .black.opacity(0.25), radius: 3, y: 1)
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
                Circle().fill(presence ? Theme.green : Theme.text3).frame(width: 10, height: 10)
                    .overlay(Circle().strokeBorder(Theme.bg, lineWidth: 2)).offset(x: 1, y: 1)
            }
        }
    }
}

extension Stage {
    var label: String { ["bloom": "Known", "sprout": "Learning", "seed": "New"][rawValue]! }
}
