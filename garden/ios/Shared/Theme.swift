import SwiftUI

extension Color {
    init(hex: UInt32, opacity: Double = 1) {
        self.init(red: Double((hex >> 16) & 0xff) / 255, green: Double((hex >> 8) & 0xff) / 255, blue: Double(hex & 0xff) / 255, opacity: opacity)
    }
}

/// The same system as the call overlay (extension/panel.css): dark glass, a soft blue accent,
/// warm amber for "ask her" and sayings, green for connected.
enum Theme {
    static let bg = Color(hex: 0x0b0d11)
    static let bg2 = Color(hex: 0x0e1015)
    static let surface = Color(hex: 0x14171d)
    static let surface2 = Color(hex: 0x1a1e25)
    static let surface3 = Color(hex: 0x222730)
    static let border = Color.white.opacity(0.08)
    static let border2 = Color.white.opacity(0.12)
    static let text = Color(hex: 0xf1f3f5)
    static let text2 = Color(hex: 0xb4bac3)
    static let text3 = Color(hex: 0x7d8591)
    static let accent = Color(hex: 0x7aa2ff)
    static let onAccent = Color(hex: 0x0b1020)
    static let warm = Color(hex: 0xf5b35c)
    static let onWarm = Color(hex: 0x1b1300)
    static let green = Color(hex: 0x34d399)
    static let danger = Color(hex: 0xff8a8a)

    static let radius: CGFloat = 16
    static let radiusSmall: CGFloat = 12
}

enum Fonts {
    static func ui(_ size: CGFloat, _ weight: Font.Weight = .regular) -> Font { .system(size: size, weight: weight) }
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
                Circle().fill(presence ? Theme.green : Theme.text3).frame(width: 10, height: 10)
                    .overlay(Circle().strokeBorder(Theme.bg, lineWidth: 2)).offset(x: 1, y: 1)
            }
        }
    }
}

extension Stage {
    var label: String { ["bloom": "Known", "sprout": "Learning", "seed": "New"][rawValue]! }
}
