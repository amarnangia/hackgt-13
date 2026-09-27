import SwiftUI

/// Your language as a glowing tree. It branches more as you meet more words: a sapling at first, a full crown later.
/// Every word you've met is a light in its crown:
///   seed    a faint point (you've just met it)
///   sprout  a green glow (you're learning it)
///   bloom   a bright, white-hot light with a halo (you know it)
///   thirsty dimmed to gray (you haven't heard it in a while)
/// A haze of light fills the crown as you know more, fireflies drift through it (one for every few hearings), and it
/// grows in when it appears and sways, more at the tips. Drawn on a Canvas; the shape is seeded, so it's always your tree.
struct GrowthPlant: View {
    let plants: [Plant]
    let totals: GardenSnapshot.Totals
    @State private var start = Date()

    var body: some View {
        TimelineView(.animation(minimumInterval: 1 / 40)) { tl in
            let t = tl.date.timeIntervalSince(start)
            Canvas { ctx, size in draw(&ctx, size, t) }
        }
        .frame(height: 380)
        .onAppear { start = Date() }
        .accessibilityElement()
        .accessibilityLabel("Your tree: \(plants.count) words, \(totals.bloom) you know")
    }

    // MARK: the tree's shape

    private struct Branch { var from: CGPoint; var to: CGPoint; var depth: Int; var appear: Double }

    /// A small fixed random sequence, so the same words always grow the same tree.
    private struct Seeded {
        var s: UInt64
        mutating func next() -> Double { s = s &* 6364136223846793005 &+ 1442695040888963407; return Double(s >> 33) / Double(1 << 31) }
    }

    private var depth: Int { min(6, 2 + plants.count / 6) }   // more words, more branching

    /// Branches for this frame: sway grows toward the tips; `grow` (0...1) brings them in from the trunk out.
    private func branches(base: CGPoint, trunk: Double, t: Double, grow: Double) -> [Branch] {
        var rng = Seeded(s: 0x5EED_7AEE)
        var out: [Branch] = []
        let maxDepth = depth
        func grow_(_ from: CGPoint, _ angle: Double, _ len: Double, _ d: Int) {
            let appear = Double(d) / Double(maxDepth + 1)
            let shown = max(0, min(1, (grow - appear) / (1 / Double(maxDepth + 1))))   // 0 still recurses, so the shape never shifts
            let sway = sin(t * 0.8 + Double(d) * 0.7) * 0.018 * Double(d) + sin(t * 1.9 + Double(d)) * 0.006 * Double(d)
            let a = angle + sway
            let l = len * ease(shown)
            let to = CGPoint(x: from.x + CGFloat(sin(a) * l), y: from.y - CGFloat(cos(a) * l))
            if shown > 0 { out.append(Branch(from: from, to: to, depth: d, appear: appear)) }
            guard d < maxDepth else { return }
            let spread = 0.36 + rng.next() * 0.22
            let lean = (rng.next() - 0.5) * 0.25
            let ratio = 0.68 + rng.next() * 0.1
            grow_(to, a - spread + lean, len * ratio, d + 1)
            grow_(to, a + spread + lean, len * (ratio - 0.04 + rng.next() * 0.08), d + 1)
            if d >= 2 && rng.next() < 0.28 { grow_(to, a + lean * 2, len * ratio * 0.8, d + 1) }   // a third twig now and then
        }
        grow_(base, (rng.next() - 0.5) * 0.08, trunk, 0)
        return out
    }

    // MARK: drawing

    private func draw(_ ctx: inout GraphicsContext, _ size: CGSize, _ t: Double) {
        let w = size.width, h = size.height
        let grow = min(1, t / 2.6)
        let base = CGPoint(x: w / 2, y: h - 36)
        let n = plants.count
        let trunk = (h - 80) * (0.26 + 0.1 * min(1, Double(n) / 36))
        let tree = branches(base: base, trunk: trunk, t: t, grow: grow)
        let tips = tree.filter { $0.depth == depth }
        let known = totals.bloom

        // the ground: a pool of light the tree stands in, and its roots
        ctx.fill(Path(ellipseIn: CGRect(x: base.x - 130, y: base.y - 14, width: 260, height: 32)),
                 with: .radialGradient(Gradient(colors: [Theme.accent.opacity(0.3), .clear]), center: base, startRadius: 0, endRadius: 130))
        for k in 0..<5 {
            let a = (Double(k) - 2) * 0.55
            var root = Path()
            root.move(to: base)
            root.addQuadCurve(to: CGPoint(x: base.x + CGFloat(sin(a) * 46), y: base.y + 8 + CGFloat(abs(a) * 3)),
                              control: CGPoint(x: base.x + CGFloat(sin(a) * 16), y: base.y + 9))
            ctx.stroke(root, with: .color(Theme.accent.opacity(0.35)), style: StrokeStyle(lineWidth: 1.4, lineCap: .round))
        }

        // the crown's haze: soft light around the tips, stronger as you know more
        if !tips.isEmpty {
            let haze = 0.1 + 0.22 * min(1, Double(known) / 12) + 0.06 * min(1, Double(n) / 30)
            for (i, tip) in tips.enumerated() {
                let r = 26 + CGFloat((i * 53) % 18)
                ctx.fill(Path(ellipseIn: CGRect(x: tip.to.x - r, y: tip.to.y - r, width: 2 * r, height: 2 * r)),
                         with: .radialGradient(Gradient(colors: [Theme.cyan.opacity(haze * ease(grow)), .clear]), center: tip.to, startRadius: 0, endRadius: r))
            }
        }

        // the branches: tapered, dark at the trunk and bright at the tips, glowing
        var glow = ctx
        glow.addFilter(.shadow(color: Theme.cyan.opacity(0.7), radius: 7))
        let maxD = Double(depth)
        for b in tree {
            let f = Double(b.depth) / max(1, maxD)
            var p = Path(); p.move(to: b.from)
            let mid = CGPoint(x: (b.from.x + b.to.x) / 2 + CGFloat(sin(Double(b.depth) + t * 0.3) * 1.5), y: (b.from.y + b.to.y) / 2)
            p.addQuadCurve(to: b.to, control: mid)
            let width = 7.5 * pow(0.62, Double(b.depth)) + 0.6
            glow.stroke(p, with: .linearGradient(Gradient(colors: [mix(f), mix(min(1, f + 1 / max(1, maxD)))]), startPoint: b.from, endPoint: b.to),
                        style: StrokeStyle(lineWidth: width, lineCap: .round))
        }

        // your words: lights in the crown, on the tips first, then along the branches
        let spots = tips.map(\.to) + tree.filter { $0.depth >= max(1, depth - 2) && $0.depth < depth }.map(\.to)
        let words = plants.sorted { ($0.firstHeard ?? 0) < ($1.firstHeard ?? 0) }.prefix(spots.count)
        for (i, p) in words.enumerated() {
            let appear = 0.55 + 0.4 * Double(i) / Double(max(1, words.count))
            let shown = ease(max(0, min(1, (grow - appear) / 0.25)))
            guard shown > 0 else { continue }
            let at = spots[i]
            let twinkle = 0.78 + 0.22 * sin(t * (1.1 + Double(i % 5) * 0.23) + Double(i) * 1.7)
            let thirsty = p.thirsty && p.stageEnum != .seed
            let (core, halo, color): (CGFloat, CGFloat, Color) = thirsty ? (2, 6, Theme.text3)
                : p.stageEnum == .bloom ? (3.6, 16, Theme.warm)
                : p.stageEnum == .sprout ? (2.8, 11, Theme.cyan)
                : (1.8, 7, Theme.warm.opacity(0.7))
            let hr = halo * CGFloat(shown)
            ctx.fill(Path(ellipseIn: CGRect(x: at.x - hr, y: at.y - hr, width: 2 * hr, height: 2 * hr)),
                     with: .radialGradient(Gradient(colors: [color.opacity(0.55 * twinkle), .clear]), center: at, startRadius: 0, endRadius: hr))
            let cr = core * CGFloat(shown)
            var dot = ctx
            dot.addFilter(.shadow(color: color, radius: p.stageEnum == .bloom ? 6 : 3))
            dot.fill(Path(ellipseIn: CGRect(x: at.x - cr, y: at.y - cr, width: 2 * cr, height: 2 * cr)),
                     with: .color(p.stageEnum == .bloom && !thirsty ? .white.opacity(0.95 * twinkle) : color.opacity(0.9 * twinkle)))
        }

        // fireflies: one for every few hearings, drifting through the crown
        guard let top = tree.map(\.to.y).min() else { return }
        let tr = CGFloat(trunk)
        let crown = CGRect(x: base.x - tr * 1.4, y: top - 10, width: tr * 2.8, height: max(40, base.y - tr - top + 20))
        for k in 0..<min(24, totals.heard / 3) {
            let s = Double((k * 7919) % 1000) / 1000, s2 = Double((k * 104729) % 1000) / 1000
            let x = crown.midX + CGFloat(sin(t * (0.15 + s * 0.2) + s * 20) * Double(crown.width) / 2)
            let y = crown.midY + CGFloat(cos(t * (0.12 + s2 * 0.2) + s2 * 20) * Double(crown.height) / 2)
            let blink = max(0, sin(t * (0.8 + s) + s * 30))
            let r = 1.2 + s * 1.2
            var m = ctx
            m.addFilter(.shadow(color: Theme.cyan, radius: 4))
            m.fill(Path(ellipseIn: CGRect(x: x - r, y: y - r, width: 2 * r, height: 2 * r)), with: .color(Theme.cyan.opacity(0.75 * blink * ease(grow))))
        }
    }

    /// Trunk to tips: dark green to bright green.
    private func mix(_ f: Double) -> Color {
        f < 0.5 ? Color(hex: 0x14692f).opacity(0.95) : f < 0.85 ? Theme.accent : Theme.cyan
    }
    private func ease(_ x: Double) -> Double { 1 - pow(1 - max(0, min(1, x)), 3) }
}
