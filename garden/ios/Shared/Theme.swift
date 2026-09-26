import SwiftUI

extension Color {
    init(hex: UInt32, opacity: Double = 1) {
        self.init(red: Double((hex >> 16) & 0xff) / 255, green: Double((hex >> 8) & 0xff) / 255, blue: Double(hex & 0xff) / 255, opacity: opacity)
    }
}

/// Handloom silk on charcoal: Pochampally ikat and Kanchipuram zari.
/// Dark gray dominates; gold, peacock teal, kumkum vermilion and rani pink are the threads.
enum Theme {
    static let bg = Color(hex: 0x131215)
    static let bgDeep = Color(hex: 0x0b0a0d)
    static let surface = Color(hex: 0x1c1b20, opacity: 0.74)
    static let raised = Color.white.opacity(0.06)
    static let border = Color.white.opacity(0.08)
    static let ink = Color(hex: 0xf6efe4)        // warm ivory, like unbleached cotton
    static let ink2 = Color(hex: 0xb8afa3)
    static let muted = Color(hex: 0x7d766e)

    static let gold = Color(hex: 0xf2b84b)       // zari / turmeric
    static let peacock = Color(hex: 0x2fb9a8)
    static let vermilion = Color(hex: 0xe4572e)  // kumkum
    static let rani = Color(hex: 0xd83a73)       // rani pink silk
    static let accent = gold

    static let silk = LinearGradient(colors: [rani, vermilion, gold], startPoint: .leading, endPoint: .trailing)
    static let zari = LinearGradient(colors: [Color(hex: 0xffe2a0), gold, Color(hex: 0xc4861b)], startPoint: .topLeading, endPoint: .bottomTrailing)
    static let peacockSilk = LinearGradient(colors: [Color(hex: 0x5fdcc8), peacock, Color(hex: 0x1d6e8c)], startPoint: .topLeading, endPoint: .bottomTrailing)
    static let kumkum = LinearGradient(colors: [vermilion, rani], startPoint: .topLeading, endPoint: .bottomTrailing)
    static let sheen = LinearGradient(colors: [.white.opacity(0.16), .white.opacity(0.04)], startPoint: .top, endPoint: .bottom)
    static let silkBorder = AngularGradient(colors: [rani, vermilion, gold, peacock, rani], center: .center)

    static let radius: CGFloat = 18
}

enum Fonts {
    /// Headings and numbers.
    static func display(_ size: CGFloat, italic: Bool = false) -> Font {
        .custom(italic ? "InstrumentSerif-Italic" : "InstrumentSerif-Regular", size: size)
    }
    /// Interface text.
    static func ui(_ size: CGFloat, _ weight: Font.Weight = .regular) -> Font {
        .custom("Bricolage Grotesque", size: size).weight(weight)
    }
    /// Telugu words.
    static func telugu(_ size: CGFloat) -> Font { .custom("TiroTelugu-Regular", size: size) }
}

extension Stage {
    /// Plain names in the app: the garden words stay in the data.
    var label: String { ["bloom": "Known", "sprout": "Learning", "seed": "New"][rawValue]! }
    /// New is kumkum, learning is peacock, known is zari gold.
    var color: Color {
        switch self {
        case .bloom: Theme.gold
        case .sprout: Theme.peacock
        case .seed: Theme.vermilion
        }
    }
    var fill: AnyShapeStyle {
        switch self {
        case .bloom: AnyShapeStyle(Theme.zari)
        case .sprout: AnyShapeStyle(Theme.peacockSilk.opacity(0.85))
        case .seed: AnyShapeStyle(Theme.vermilion.opacity(0.22))
        }
    }
}

// MARK: background

/// Charcoal with slow silk-colored glows and a faint ikat diamond lattice.
struct Loom: View {
    var animated = true
    var body: some View {
        TimelineView(.animation(minimumInterval: 1 / 24, paused: !animated)) { tl in
            let t = animated ? tl.date.timeIntervalSinceReferenceDate : 0
            Canvas { ctx, size in
                Loom.draw(ctx, size: size, t: t)
            }
        }
        .ignoresSafeArea()
    }

    static func draw(_ ctx: GraphicsContext, size: CGSize, t: Double) {
        let w = size.width, h = size.height
        ctx.fill(Path(CGRect(origin: .zero, size: size)),
                 with: .linearGradient(Gradient(colors: [Theme.bg, Theme.bgDeep]), startPoint: .zero, endPoint: CGPoint(x: 0, y: h)))
        func glow(_ x: Double, _ y: Double, _ r: Double, _ color: Color, _ a: Double) {
            let c = CGPoint(x: x, y: y)
            ctx.fill(Path(ellipseIn: CGRect(x: x - r, y: y - r, width: r * 2, height: r * 2)),
                     with: .radialGradient(Gradient(colors: [color.opacity(a), color.opacity(0)]), center: c, startRadius: 0, endRadius: r))
        }
        glow(w * (0.12 + 0.06 * sin(t * 0.07)), h * (0.1 + 0.03 * cos(t * 0.05)), w * 0.95, Theme.peacock, 0.26)
        glow(w * (1.02 + 0.05 * cos(t * 0.06)), h * (0.42 + 0.05 * sin(t * 0.04)), w * 0.8, Theme.rani, 0.18)
        glow(w * (0.3 + 0.08 * sin(t * 0.05)), h * 1.02, w * 0.9, Theme.gold, 0.12)
        glow(w * 0.85, h * 0.92, w * 0.5, Theme.vermilion, 0.08)

        // Ikat lattice: diamonds with a smaller stepped diamond inside every other cell.
        let s = 30.0
        var lattice = Path(), inner = Path()
        var row = 0
        var y = -s
        while y < h + s {
            var x = (row % 2 == 0 ? 0 : s / 2) - s
            while x < w + s {
                lattice.move(to: CGPoint(x: x, y: y - s / 2)); lattice.addLine(to: CGPoint(x: x + s / 2, y: y))
                lattice.addLine(to: CGPoint(x: x, y: y + s / 2)); lattice.addLine(to: CGPoint(x: x - s / 2, y: y)); lattice.closeSubpath()
                if (row + Int(x / s)) % 2 == 0 {
                    let d = s * 0.16
                    inner.addRect(CGRect(x: x - d / 2, y: y - d / 2, width: d, height: d))
                }
                x += s
            }
            y += s / 2
            row += 1
        }
        ctx.stroke(lattice, with: .color(.white.opacity(0.03)), lineWidth: 0.6)

        ctx.fill(inner, with: .color(Theme.gold.opacity(0.05)))
    }
}

// MARK: shared pieces

/// Small uppercase section label.
struct Eyebrow: View {
    let text: String
    var color: Color = Theme.muted
    init(_ text: String, color: Color = Theme.muted) { self.text = text; self.color = color }
    var body: some View {
        Text(text.uppercased()).font(Fonts.ui(10.5, .semibold)).tracking(1.4).foregroundStyle(color)
    }
}

/// Glassy surface over the loom, with a sheen on its border.
struct Panel<Content: View>: View {
    var padding: CGFloat = 20
    var silk = false
    @ViewBuilder var content: Content
    var body: some View {
        VStack(alignment: .leading, spacing: 0) { content }
            .padding(padding)
            .frame(maxWidth: .infinity, alignment: .leading)
            .background(Theme.surface, in: .rect(cornerRadius: Theme.radius))
            .overlay {
                if silk {
                    RoundedRectangle(cornerRadius: Theme.radius).strokeBorder(Theme.silkBorder.opacity(0.85), lineWidth: 1)
                } else {
                    RoundedRectangle(cornerRadius: Theme.radius).strokeBorder(Theme.sheen, lineWidth: 1)
                }
            }
    }
}

/// A row of small zari diamonds, like the border of a sari.
struct ZariTrim: View {
    var count = 24
    var body: some View {
        Canvas { ctx, size in
            let step = size.width / Double(count), r = min(step, size.height) * 0.28
            for i in 0..<count {
                let x = step * (Double(i) + 0.5), y = size.height / 2
                var p = Path()
                p.move(to: CGPoint(x: x, y: y - r)); p.addLine(to: CGPoint(x: x + r, y: y))
                p.addLine(to: CGPoint(x: x, y: y + r)); p.addLine(to: CGPoint(x: x - r, y: y)); p.closeSubpath()
                ctx.fill(p, with: .color(Theme.gold.opacity(i % 2 == 0 ? 0.55 : 0.22)))
            }
        }
        .frame(height: 8)
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

/// Staggered entrance: fade up out of a slight blur.
struct Reveal: ViewModifier {
    let index: Int
    @State private var shown = false
    func body(content: Content) -> some View {
        content
            .opacity(shown ? 1 : 0)
            .offset(y: shown ? 0 : 18)
            .blur(radius: shown ? 0 : 6)
            .onAppear {
                withAnimation(.spring(response: 0.7, dampingFraction: 0.86).delay(0.05 + Double(index) * 0.07)) { shown = true }
            }
    }
}

extension View {
    func reveal(_ index: Int) -> some View { modifier(Reveal(index: index)) }
}

/// Eight segments from new to known, each in its stage's thread color.
struct GrowthBar: View {
    let growth: Int
    var total = 8
    var subtitleAt = 3
    var height: CGFloat = 4
    var body: some View {
        HStack(spacing: 2) {
            ForEach(0..<total, id: \.self) { i in
                let stage: Stage = i < subtitleAt ? .seed : i < total - 1 ? .sprout : .bloom
                Capsule().fill(i < growth ? AnyShapeStyle(stage == .seed ? AnyShapeStyle(Theme.kumkum) : stage.fill) : AnyShapeStyle(Color.white.opacity(0.07)))
                    .frame(height: height)
            }
        }
        .animation(.easeOut(duration: 0.3), value: growth)
    }
}

/// "Ask how she makes పులిహోర." English in the display serif, the Telugu word in Tiro Telugu, woven in silk.
func starterText(_ s: Starter, size: CGFloat) -> Text {
    Text(s.before + " ").font(Fonts.display(size)).foregroundColor(Theme.ink)
        + Text(s.word).font(Fonts.telugu(size * 0.86)).foregroundStyle(Theme.silk)
        + Text(s.after).font(Fonts.display(size)).foregroundColor(Theme.ink)
}
