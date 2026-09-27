import SwiftUI

/// Your language as a plant that grows from a bud into a tree:
///   bud     no words yet: a glowing bud in the soil
///   sprout  your first words: a stem with soft leaves, one more as you meet more words
///   tree    a trunk, branches and a full, rounded, glowing canopy that fills out as you meet and know more
/// Your words are small lights in the leaves: faint when new, green while you're learning them, white when you know
/// them, gray when you haven't heard them in a while. Every time it appears it grows from the bud up to where you are,
/// then sways. Everything is laid out inside a margin, so no glow is ever cut off at the edges. Drawn on a Canvas.
struct GrowthPlant: View {
    let plants: [Plant]
    let totals: GardenSnapshot.Totals
    @State private var start = Date()

    /// How grown you are, 0 (bud) ... 1 (full tree): words met, with words you know counting double.
    private var target: Double { plants.isEmpty ? 0 : min(1, 0.04 + Double(plants.count + 2 * totals.bloom) / 55) }

    var body: some View {
        TimelineView(.animation(minimumInterval: 1 / 40)) { tl in
            let t = tl.date.timeIntervalSince(start)
            Canvas { ctx, size in draw(&ctx, size, t) }
        }
        .frame(height: 380)
        .onAppear { start = Date() }
        .accessibilityElement()
        .accessibilityLabel(plants.isEmpty ? "Your plant: a bud" : "Your plant: \(plants.count) words, \(totals.bloom) you know")
    }

    // MARK: layout

    private let margin: CGFloat = 34          // nothing is drawn closer to the edge than this, glow included

    private func draw(_ ctx: inout GraphicsContext, _ size: CGSize, _ t: Double) {
        let g = target * ease(min(1, t / 2.8))          // grows from the bud up to where you are
        let base = CGPoint(x: size.width / 2, y: size.height - 46)
        ground(&ctx, base)
        let budA = 1 - smooth(g, 0.05, 0.11)
        let sproutA = smooth(g, 0.03, 0.09) * (1 - smooth(g, 0.36, 0.46))
        let treeA = smooth(g, 0.36, 0.46)
        if budA > 0.01 { var c = ctx; c.opacity = budA; bud(&c, base, t) }
        if sproutA > 0.01 { var c = ctx; c.opacity = sproutA; sprout(&c, base, g, t) }
        if treeA > 0.01 { var c = ctx; c.opacity = treeA; tree(&c, size, base, g, t) }
        fireflies(&ctx, size, base, g, t)
    }

    // MARK: stages

    private func ground(_ ctx: inout GraphicsContext, _ base: CGPoint) {
        glowEllipse(&ctx, center: CGPoint(x: base.x, y: base.y + 2), rx: 125, ry: 18, color: Theme.accent.opacity(0.34))
        var line = Path(); line.move(to: CGPoint(x: base.x - 100, y: base.y + 2)); line.addLine(to: CGPoint(x: base.x + 100, y: base.y + 2))
        ctx.stroke(line, with: .linearGradient(Gradient(colors: [.clear, Theme.accent.opacity(0.45), .clear]),
                                               startPoint: CGPoint(x: base.x - 100, y: 0), endPoint: CGPoint(x: base.x + 100, y: 0)), lineWidth: 1)
    }

    private func bud(_ ctx: inout GraphicsContext, _ base: CGPoint, _ t: Double) {
        let pulse = 1 + 0.06 * sin(t * 2.2)
        let r = 9 * pulse
        let c = CGPoint(x: base.x, y: base.y - 8)
        ctx.fill(Path(ellipseIn: CGRect(x: c.x - 34, y: c.y - 34, width: 68, height: 68)),
                 with: .radialGradient(Gradient(colors: [Theme.cyan.opacity(0.35), .clear]), center: c, startRadius: 0, endRadius: 34))
        var b = Path()
        b.move(to: CGPoint(x: c.x, y: c.y - r * 1.5))
        b.addQuadCurve(to: CGPoint(x: c.x, y: c.y + r * 0.8), control: CGPoint(x: c.x + r * 1.3, y: c.y - r * 0.2))
        b.addQuadCurve(to: CGPoint(x: c.x, y: c.y - r * 1.5), control: CGPoint(x: c.x - r * 1.3, y: c.y - r * 0.2))
        var glow = ctx
        glow.addFilter(.shadow(color: Theme.cyan.opacity(0.9), radius: 10))
        glow.fill(b, with: .linearGradient(Gradient(colors: [Theme.warm, Theme.cyan, Theme.accent]),
                                           startPoint: CGPoint(x: c.x, y: c.y - r * 1.5), endPoint: CGPoint(x: c.x, y: c.y + r)))
    }

    private func sprout(_ ctx: inout GraphicsContext, _ base: CGPoint, _ g: Double, _ t: Double) {
        let p = max(0, min(1, (g - 0.03) / 0.4))
        let height = 24 + 150 * ease(p)
        func at(_ f: Double) -> CGPoint {
            let sway = sin(t * 0.9) * 5 * pow(f, 1.5)
            return CGPoint(x: base.x + CGFloat(sin(f * .pi) * 6 + sway), y: base.y - CGFloat(height * f))
        }
        var stem = Path(); stem.move(to: base)
        for i in 1...30 { stem.addLine(to: at(Double(i) / 30)) }
        var glow = ctx
        glow.addFilter(.shadow(color: Theme.accent.opacity(0.8), radius: 6))
        glow.stroke(stem, with: .linearGradient(Gradient(colors: [Color(hex: 0x14692f), Theme.accent, Theme.cyan]), startPoint: base, endPoint: at(1)),
                    style: StrokeStyle(lineWidth: 3.2, lineCap: .round))
        // leaves: two at the top from the start, more pairs down the stem as you meet more words
        let count = 2 + Int(p * 6)
        var tips: [CGPoint] = []
        for i in 0..<count {
            let f = 1 - Double(i / 2) * (0.7 / Double(max(1, (count + 1) / 2))) - 0.02
            let side: Double = i % 2 == 0 ? -1 : 1
            let len = (22 + 20 * p) * (1 - 0.18 * Double(i / 2) / Double(max(1, count / 2)))
            let a = side * (0.95 + 0.12 * sin(t * 1.3 + Double(i))) - (i < 2 ? side * 0.35 : 0)   // the top pair points up more
            tips.append(leaf(&ctx, at(f), angle: a, length: len))
        }
        lights(&ctx, tips + (0..<8).map { at(0.25 + Double($0) * 0.08) }, t)
    }

    private func tree(_ ctx: inout GraphicsContext, _ size: CGSize, _ base: CGPoint, _ g: Double, _ t: Double) {
        let fill = max(0, min(1, (g - 0.4) / 0.6))               // 0: a young tree ... 1: full
        let s = 0.55 + 0.45 * ease(fill)
        let fullH = size.height - 46 - margin - 26
        let H = fullH * s
        let fork = CGPoint(x: base.x + CGFloat(sin(t * 0.6) * 2 * s), y: base.y - CGFloat(H * 0.38))
        // the canopy's shape, kept inside the margin with room for its glow
        let rx = min(size.width / 2 - margin - 22, CGFloat(H) * 0.56)
        let ry = CGFloat(H) * 0.3
        let center = CGPoint(x: base.x, y: base.y - CGFloat(H) * 0.66)

        // a soft light behind the crown, fading to nothing at its edge
        glowEllipse(&ctx, center: center, rx: rx + 24, ry: ry + 30, color: Theme.accent.opacity(0.24))

        // the trunk: tapered, a little curved, dark wood lit at the edge
        let bw = CGFloat(9 * s), tw = CGFloat(3.5 * s)
        var trunk = Path()
        trunk.move(to: CGPoint(x: base.x - bw, y: base.y))
        trunk.addQuadCurve(to: CGPoint(x: fork.x - tw, y: fork.y), control: CGPoint(x: base.x - bw * 0.3, y: (base.y + fork.y) / 2))
        trunk.addLine(to: CGPoint(x: fork.x + tw, y: fork.y))
        trunk.addQuadCurve(to: CGPoint(x: base.x + bw, y: base.y), control: CGPoint(x: base.x + bw * 0.5, y: (base.y + fork.y) / 2))
        trunk.closeSubpath()
        var wood = ctx
        wood.addFilter(.shadow(color: Theme.accent.opacity(0.6), radius: 6))
        wood.fill(trunk, with: .linearGradient(Gradient(colors: [Color(hex: 0x0e3f1e), Color(hex: 0x1a7a3d)]), startPoint: base, endPoint: fork))

        // branches reaching up into the crown
        var rng = Seeded(s: 0xB2A7_C4E5)
        let angles: [Double] = [-1.05, -0.55, -0.1, 0.4, 0.95]
        for a0 in angles {
            let a = a0 * 0.9 + (rng.next() - 0.5) * 0.15 + sin(t * 0.7 + a0) * 0.02
            let len = Double(H) * (0.27 + rng.next() * 0.08) * (1 - abs(a0) * 0.12)
            let end = CGPoint(x: fork.x + CGFloat(sin(a) * len), y: fork.y - CGFloat(cos(a) * len))
            var b = Path(); b.move(to: fork)
            b.addQuadCurve(to: end, control: CGPoint(x: fork.x + CGFloat(sin(a) * len * 0.3), y: fork.y - CGFloat(len * 0.55)))
            wood.stroke(b, with: .linearGradient(Gradient(colors: [Color(hex: 0x14692f), Theme.accent]), startPoint: fork, endPoint: end),
                        style: StrokeStyle(lineWidth: CGFloat(3.4 * s), lineCap: .round))
        }

        // the crown: many small leaves in a dome, each pointing out from the middle, lit from the top left.
        // Drawn as one layer with one glow, so it reads as foliage, not a pile of shapes.
        let n = 70 + Int(110 * ease(fill))
        struct Spot { var p: CGPoint; var a: Double; var len: Double; var light: Double }
        var spots: [Spot] = []
        for k in 0..<n {
            let rr = sqrt((Double(k) + 0.5) / Double(n)) * (0.92 + 0.08 * rng.next()), a = Double(k) * 2.39996
            let sway = sin(t * 0.7 + Double(k) * 0.37) * 1.8 * rr * s
            let p = CGPoint(x: center.x + CGFloat(cos(a) * rr) * rx + CGFloat(sway),
                            y: center.y + CGFloat(sin(a) * rr) * ry - CGFloat((1 - rr * rr) * 0.18) * ry)
            let out = atan2(Double(p.x - center.x), Double(center.y - p.y) + 0.001)   // pointing away from the middle
            let angle = out * 0.85 + (rng.next() - 0.5) * 0.9 + sin(t * 1.1 + Double(k)) * 0.05
            let light = max(0, min(1, Double((center.y + ry - p.y) / (2 * ry)) * 0.65 + Double((center.x + rx - p.x) / (2 * rx)) * 0.35))
            spots.append(Spot(p: p, a: angle, len: (9 + 7 * rng.next()) * s * (1.1 - 0.25 * rr), light: light))
        }
        var crown = ctx
        crown.addFilter(.shadow(color: Theme.accent.opacity(0.55), radius: 9))
        crown.drawLayer { layer in
            for sp in spots.sorted(by: { $0.light < $1.light }) {   // darker, lower leaves first; lit ones on top
                let dir = CGVector(dx: sin(sp.a), dy: -cos(sp.a)), nrm = CGVector(dx: -dir.dy, dy: dir.dx)
                let base = CGPoint(x: sp.p.x - CGFloat(dir.dx * sp.len * 0.5), y: sp.p.y - CGFloat(dir.dy * sp.len * 0.5))
                let tip = CGPoint(x: base.x + CGFloat(dir.dx * sp.len), y: base.y + CGFloat(dir.dy * sp.len))
                let w = sp.len * 0.45
                func pt(_ f: Double, _ side: Double) -> CGPoint {
                    CGPoint(x: base.x + CGFloat(dir.dx * sp.len * f + nrm.dx * w * side), y: base.y + CGFloat(dir.dy * sp.len * f + nrm.dy * w * side))
                }
                var leaf = Path(); leaf.move(to: base)
                leaf.addCurve(to: tip, control1: pt(0.3, 1), control2: pt(0.75, 0.75))
                leaf.addCurve(to: base, control1: pt(0.75, -0.75), control2: pt(0.3, -1))
                let dark = Color(hex: 0x0f5226), mid = Theme.accent, bright = Theme.cyan
                layer.fill(leaf, with: .linearGradient(Gradient(colors: [dark.opacity(0.9), mid.opacity(0.55 + 0.4 * sp.light), bright.opacity(0.35 + 0.6 * sp.light)]),
                                                      startPoint: base, endPoint: tip))
            }
        }
        lights(&ctx, spots.enumerated().filter { $0.offset % 3 == 0 }.map(\.element).sorted { $0.light > $1.light }.map(\.p), t)
    }

    /// An ellipse of light that fades to nothing at its edge.
    private func glowEllipse(_ ctx: inout GraphicsContext, center: CGPoint, rx: CGFloat, ry: CGFloat, color: Color) {
        var c = ctx
        c.translateBy(x: center.x, y: center.y)
        c.scaleBy(x: 1, y: ry / rx)
        c.fill(Path(ellipseIn: CGRect(x: -rx, y: -rx, width: 2 * rx, height: 2 * rx)),
               with: .radialGradient(Gradient(colors: [color, color.opacity(0.35), .clear]), center: .zero, startRadius: 0, endRadius: rx))
    }

    // MARK: pieces

    /// A soft pointed leaf from `at`; returns its tip.
    private func leaf(_ ctx: inout GraphicsContext, _ at: CGPoint, angle: Double, length: Double) -> CGPoint {
        let dir = CGVector(dx: sin(angle), dy: -cos(angle)), nrm = CGVector(dx: -dir.dy, dy: dir.dx)
        let tip = CGPoint(x: at.x + CGFloat(dir.dx * length), y: at.y + CGFloat(dir.dy * length))
        let w = length * 0.42
        func pt(_ f: Double, _ side: Double) -> CGPoint {
            CGPoint(x: at.x + CGFloat(dir.dx * length * f + nrm.dx * w * side), y: at.y + CGFloat(dir.dy * length * f + nrm.dy * w * side))
        }
        var p = Path(); p.move(to: at)
        p.addCurve(to: tip, control1: pt(0.25, 1), control2: pt(0.75, 0.8))
        p.addCurve(to: at, control1: pt(0.75, -0.8), control2: pt(0.25, -1))
        var glow = ctx
        glow.addFilter(.shadow(color: Theme.cyan.opacity(0.5), radius: 6))
        glow.fill(p, with: .linearGradient(Gradient(colors: [Color(hex: 0x14692f), Theme.accent, Theme.cyan.opacity(0.9)]), startPoint: at, endPoint: tip))
        var vein = Path(); vein.move(to: at); vein.addLine(to: pt(0.85, 0))
        ctx.stroke(vein, with: .color(.white.opacity(0.22)), lineWidth: 0.7)
        return tip
    }

    /// Your words, as lights at the given spots.
    private func lights(_ ctx: inout GraphicsContext, _ spots: [CGPoint], _ t: Double) {
        let words = plants.sorted { ($0.firstHeard ?? 0) < ($1.firstHeard ?? 0) }.prefix(spots.count)
        for (i, p) in words.enumerated() {
            let at = spots[i]
            let twinkle = 0.75 + 0.25 * sin(t * (1.1 + Double(i % 5) * 0.2) + Double(i) * 1.7)
            let thirsty = p.thirsty && p.stageEnum != .seed
            let (core, halo, color): (CGFloat, CGFloat, Color) = thirsty ? (1.6, 5, Theme.text3)
                : p.stageEnum == .bloom ? (2.8, 11, Theme.warm)
                : p.stageEnum == .sprout ? (2.2, 8, Theme.cyan)
                : (1.4, 5, Theme.warm.opacity(0.6))
            ctx.fill(Path(ellipseIn: CGRect(x: at.x - halo, y: at.y - halo, width: 2 * halo, height: 2 * halo)),
                     with: .radialGradient(Gradient(colors: [color.opacity(0.6 * twinkle), .clear]), center: at, startRadius: 0, endRadius: halo))
            ctx.fill(Path(ellipseIn: CGRect(x: at.x - core, y: at.y - core, width: 2 * core, height: 2 * core)),
                     with: .color(p.stageEnum == .bloom && !thirsty ? .white.opacity(0.95 * twinkle) : color.opacity(0.95 * twinkle)))
        }
    }

    /// One for every few hearings, drifting inside the margin.
    private func fireflies(_ ctx: inout GraphicsContext, _ size: CGSize, _ base: CGPoint, _ g: Double, _ t: Double) {
        let area = CGRect(x: margin + 20, y: margin + 10, width: size.width - 2 * margin - 40, height: base.y - margin - 30)
        for k in 0..<min(20, totals.heard / 4) {
            let s1 = Double((k * 7919) % 1000) / 1000, s2 = Double((k * 104729) % 1000) / 1000
            let x = area.midX + CGFloat(sin(t * (0.12 + s1 * 0.18) + s1 * 20)) * area.width / 2
            let y = area.midY + CGFloat(cos(t * (0.1 + s2 * 0.18) + s2 * 20)) * area.height / 2
            let blink = max(0, sin(t * (0.7 + s1) + s1 * 30))
            let r = 1.1 + s1 * 1.1
            ctx.fill(Path(ellipseIn: CGRect(x: x - r * 3, y: y - r * 3, width: r * 6, height: r * 6)),
                     with: .radialGradient(Gradient(colors: [Theme.cyan.opacity(0.35 * blink * g), .clear]), center: CGPoint(x: x, y: y), startRadius: 0, endRadius: r * 3))
            ctx.fill(Path(ellipseIn: CGRect(x: x - r, y: y - r, width: 2 * r, height: 2 * r)), with: .color(Theme.cyan.opacity(0.8 * blink * g)))
        }
    }

    /// A small fixed random sequence, so the same tree grows every time.
    private struct Seeded {
        var s: UInt64
        mutating func next() -> Double { s = s &* 6364136223846793005 &+ 1442695040888963407; return Double(s >> 33) / Double(1 << 31) }
    }
    private func smooth(_ x: Double, _ a: Double, _ b: Double) -> Double { let u = max(0, min(1, (x - a) / (b - a))); return u * u * (3 - 2 * u) }
    private func ease(_ x: Double) -> Double { 1 - pow(1 - max(0, min(1, x)), 3) }
}
