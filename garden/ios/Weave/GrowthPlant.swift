import SwiftUI

/// Your language as a plant: every word you've met on a call is a leaf on it.
///   seed    a small, faint new leaf (you've just met it)
///   sprout  a young leaf, translucent (you're learning it)
///   bloom   a full, bright leaf with a bud at its tip (you know it)
///   thirsty a leaf that droops and fades (you haven't heard it in a while)
/// The stem grows with the number of words, flowers open at the top as you know more, and every few hearings rises
/// as a mote of light. It grows in when it appears and sways a little, like it's alive. Drawn on a Canvas.
struct GrowthPlant: View {
    let plants: [Plant]
    let totals: GardenSnapshot.Totals
    @State private var start = Date()

    var body: some View {
        TimelineView(.animation(minimumInterval: 1 / 40)) { tl in
            let t = tl.date.timeIntervalSince(start)
            Canvas { ctx, size in draw(&ctx, size, t) }
        }
        .frame(height: 360)
        .onAppear { start = Date() }
        .accessibilityElement()
        .accessibilityLabel("Your plant: \(plants.count) words, \(totals.bloom) you know")
    }

    // MARK: drawing

    private struct Leaf { let plant: Plant; let at: Double; let side: Double; let appear: Double }

    private func draw(_ ctx: inout GraphicsContext, _ size: CGSize, _ t: Double) {
        let w = size.width, h = size.height
        let grow = ease(min(1, t / 2.2))                         // grows in over ~2 s
        let base = CGPoint(x: w / 2, y: h - 34)
        let n = plants.count
        let stemFrac = n == 0 ? 0.12 : min(1, 0.22 + Double(n) / 36 * 0.78)
        let stemH = (h - 70) * stemFrac * grow

        // the ground: a soft pool of light and a thin horizon
        ctx.fill(Path(ellipseIn: CGRect(x: base.x - 120, y: base.y - 16, width: 240, height: 36)),
                 with: .radialGradient(Gradient(colors: [Theme.accent.opacity(0.28), .clear]), center: base, startRadius: 0, endRadius: 120))
        var horizon = Path(); horizon.move(to: CGPoint(x: base.x - 110, y: base.y)); horizon.addLine(to: CGPoint(x: base.x + 110, y: base.y))
        ctx.stroke(horizon, with: .linearGradient(Gradient(colors: [.clear, Theme.accent.opacity(0.5), .clear]),
                                                   startPoint: CGPoint(x: base.x - 110, y: 0), endPoint: CGPoint(x: base.x + 110, y: 0)), lineWidth: 1)

        // the stem: a gentle S that sways more toward the top
        func point(_ f: Double) -> CGPoint {
            let y = base.y - stemH * f
            let sway = sin(t * 0.9) * 7 * pow(f, 1.6) + sin(t * 2.3 + 1) * 1.5 * f
            let curve = sin(f * .pi * 1.2) * 10
            return CGPoint(x: base.x + curve + sway, y: y)
        }
        var stem = Path()
        stem.move(to: base)
        for i in 1...40 { stem.addLine(to: point(Double(i) / 40)) }
        var glow = ctx
        glow.addFilter(.shadow(color: Theme.accent.opacity(0.9), radius: 8))
        glow.stroke(stem, with: .linearGradient(Gradient(colors: [Theme.violet, Theme.accent, Theme.cyan]),
                                                startPoint: base, endPoint: point(1)),
                    style: StrokeStyle(lineWidth: 3.2, lineCap: .round))

        // the leaves: your words, oldest at the bottom, alternating sides
        let words = plants.sorted { ($0.firstHeard ?? 0) < ($1.firstHeard ?? 0) }.suffix(40)
        let leaves = words.enumerated().map { i, p in
            Leaf(plant: p, at: 0.12 + 0.8 * Double(i + 1) / Double(words.count + 1), side: i % 2 == 0 ? -1 : 1, appear: Double(i) / Double(max(1, words.count)))
        }
        for (i, leaf) in leaves.enumerated() {
            let shown = ease(max(0, min(1, (grow - leaf.appear * 0.7) / 0.3)))
            guard shown > 0.01 else { continue }
            let p = leaf.plant, at = point(leaf.at)
            let stage = p.stageEnum
            let thirsty = p.thirsty && stage != .seed
            let len = (stage == .bloom ? 36 : stage == .sprout ? 25 : 15) * shown * (0.85 + 0.3 * Double((i * 37) % 10) / 10)
            let droop = thirsty ? 0.55 : 0
            let angle = leaf.side * (.pi / 3.1 + droop) + sin(t * 1.4 + Double(i)) * 0.07   // from straight up: out to its side
            let dir = CGVector(dx: sin(angle), dy: -cos(angle))
            let tip = CGPoint(x: at.x + CGFloat(dir.dx * len), y: at.y + CGFloat(dir.dy * len))
            let nrm = CGVector(dx: -dir.dy, dy: dir.dx)
            let width = len * 0.36
            let mid = CGPoint(x: (at.x + tip.x) / 2, y: (at.y + tip.y) / 2)
            var shape = Path()
            shape.move(to: at)
            shape.addQuadCurve(to: tip, control: CGPoint(x: mid.x + CGFloat(nrm.dx * width), y: mid.y + CGFloat(nrm.dy * width)))
            shape.addQuadCurve(to: at, control: CGPoint(x: mid.x - CGFloat(nrm.dx * width), y: mid.y - CGFloat(nrm.dy * width)))
            let fill = thirsty ? Gradient(colors: [Theme.text3.opacity(0.35), Theme.text3.opacity(0.15)])
                : stage == .bloom ? Gradient(colors: [Theme.violet, Theme.accent, Theme.cyan])
                : stage == .sprout ? Gradient(colors: [Theme.accent.opacity(0.35), Theme.cyan.opacity(0.55)])
                : Gradient(colors: [Theme.accent.opacity(0.14), Theme.warm.opacity(0.3)])
            var leafCtx = ctx
            if stage == .bloom && !thirsty { leafCtx.addFilter(.shadow(color: Theme.cyan.opacity(0.55), radius: 6)) }
            leafCtx.fill(shape, with: .linearGradient(fill, startPoint: at, endPoint: tip))
            leafCtx.stroke(shape, with: .color((thirsty ? Theme.text3 : stage == .seed ? Theme.warm : Theme.cyan).opacity(stage == .bloom ? 0.5 : stage == .seed ? 0.45 : 0.7)), lineWidth: 0.8)
            // the vein
            var vein = Path(); vein.move(to: at); vein.addLine(to: tip)
            ctx.stroke(vein, with: .color(.white.opacity(stage == .bloom ? 0.28 : 0.14)), lineWidth: 0.6)
            if stage == .bloom && !thirsty {   // a bud at the tip of a word you know
                let r = 2.4 * shown
                var b = ctx
                b.addFilter(.shadow(color: Theme.warm, radius: 5))
                b.fill(Path(ellipseIn: CGRect(x: tip.x - r, y: tip.y - r, width: 2 * r, height: 2 * r)), with: .color(Theme.warm))
            }
        }

        // the flower: opens as you know more words
        let known = totals.bloom
        let top = point(1)
        if known > 0 {
            let open = ease(max(0, min(1, (grow - 0.6) / 0.4)))
            let petals = min(9, 4 + known / 3)
            let r = (9 + min(22, Double(known) * 1.4)) * open
            var flower = ctx
            flower.addFilter(.shadow(color: Theme.cyan.opacity(0.9), radius: 14))
            for k in 0..<petals {
                let a = Double(k) / Double(petals) * 2 * .pi + t * 0.15
                let c = CGPoint(x: top.x + CGFloat(cos(a) * r * 0.55), y: top.y + CGFloat(sin(a) * r * 0.55))
                flower.fill(Path(ellipseIn: CGRect(x: c.x - r * 0.42, y: c.y - r * 0.42, width: r * 0.84, height: r * 0.84)),
                            with: .radialGradient(Gradient(colors: [Theme.warm, Theme.cyan.opacity(0.35)]), center: c, startRadius: 0, endRadius: r * 0.42))
            }
            let core = r * 0.28 * (1 + 0.06 * sin(t * 2))
            flower.fill(Path(ellipseIn: CGRect(x: top.x - core, y: top.y - core, width: 2 * core, height: 2 * core)), with: .color(.white.opacity(0.92)))
        } else {   // not yet: a closed bud at the top
            let r = 4.5 * grow
            var bud = ctx
            bud.addFilter(.shadow(color: Theme.cyan.opacity(0.9), radius: 8))
            bud.fill(Path(ellipseIn: CGRect(x: top.x - r, y: top.y - r * 1.3, width: 2 * r, height: 2.6 * r)), with: .color(Theme.warm.opacity(0.9)))
        }

        // hearings: motes of light drifting up from the ground
        let motes = min(28, totals.heard / 3)
        for k in 0..<motes {
            let seed = Double((k * 7919) % 1000) / 1000
            let speed = 14 + seed * 18
            let life = (h - 60)
            let y = base.y - CGFloat((t * speed + seed * life).truncatingRemainder(dividingBy: life))
            let x = base.x + CGFloat(sin(seed * 40 + t * 0.6) * (40 + seed * 90))
            let fade = sin(Double(base.y - y) / life * .pi)
            let r = 1.2 + seed * 1.4
            var m = ctx
            m.addFilter(.shadow(color: Theme.cyan, radius: 4))
            m.fill(Path(ellipseIn: CGRect(x: x - r, y: y - r, width: 2 * r, height: 2 * r)), with: .color(Theme.cyan.opacity(0.55 * fade)))
        }
    }

    private func ease(_ x: Double) -> Double { 1 - pow(1 - x, 3) }
}
