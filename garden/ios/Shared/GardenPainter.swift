import SwiftUI

// Draws the garden with SwiftUI's GraphicsContext. Used live (animated) in the app and as a still in the widget.
// Plant art is drawn in "garden units" with the base at (0, 0), growing up (negative y).

struct RGB {
    var r, g, b: Double
    init(_ hex: UInt32) { r = Double((hex >> 16) & 0xff) / 255; g = Double((hex >> 8) & 0xff) / 255; b = Double(hex & 0xff) / 255 }
    init(r: Double, g: Double, b: Double) { self.r = r; self.g = g; self.b = b }
    func mix(_ o: RGB, _ t: Double) -> RGB { RGB(r: r + (o.r - r) * t, g: g + (o.g - g) * t, b: b + (o.b - b) * t) }
    var color: Color { Color(red: r, green: g, blue: b) }
}

extension Color {
    init(hex: UInt32, opacity: Double = 1) { self = RGB(hex).color.opacity(opacity) }
}

/// Sky, hills and ground colors for a time of day, blended between keyframes.
struct SkyPalette {
    var skyTop, skyBottom, hillBack, hillFront, groundTop, groundBottom, soil: RGB
    var night: Double  // 0 = full day, 1 = full night

    private static let night = SkyPalette(skyTop: RGB(0x0a1430), skyBottom: RGB(0x2a3160), hillBack: RGB(0x1b3024), hillFront: RGB(0x213b2a),
                                          groundTop: RGB(0x294628), groundBottom: RGB(0x1c331d), soil: RGB(0x5e4029), night: 1)
    private static let dawn = SkyPalette(skyTop: RGB(0x7fa6d9), skyBottom: RGB(0xffc9a3), hillBack: RGB(0x9fbf91), hillFront: RGB(0x86ad75),
                                         groundTop: RGB(0x7fae5c), groundBottom: RGB(0x5f8d42), soil: RGB(0x7d5130), night: 0.25)
    private static let day = SkyPalette(skyTop: RGB(0x8fcdf0), skyBottom: RGB(0xfcecd2), hillBack: RGB(0xbcd9a4), hillFront: RGB(0x9dc687),
                                        groundTop: RGB(0x8cbd67), groundBottom: RGB(0x6f9f4c), soil: RGB(0x8a5a33), night: 0)
    private static let dusk = SkyPalette(skyTop: RGB(0x4b4a8f), skyBottom: RGB(0xf59f7a), hillBack: RGB(0x6f8a6e), hillFront: RGB(0x587a58),
                                         groundTop: RGB(0x5e8a47), groundBottom: RGB(0x456d33), soil: RGB(0x6e4a2d), night: 0.45)

    static func at(hour: Double) -> SkyPalette {
        let keys: [(Double, SkyPalette)] = [(0, night), (5, night), (6.5, dawn), (8.5, day), (16.5, day), (18.5, dusk), (20, night), (24, night)]
        let h = hour.truncatingRemainder(dividingBy: 24)
        for i in 0..<keys.count - 1 where h >= keys[i].0 && h <= keys[i + 1].0 {
            let t = (h - keys[i].0) / max(0.001, keys[i + 1].0 - keys[i].0)
            return keys[i].1.mix(keys[i + 1].1, t)
        }
        return day
    }

    func mix(_ o: SkyPalette, _ t: Double) -> SkyPalette {
        SkyPalette(skyTop: skyTop.mix(o.skyTop, t), skyBottom: skyBottom.mix(o.skyBottom, t), hillBack: hillBack.mix(o.hillBack, t),
                   hillFront: hillFront.mix(o.hillFront, t), groundTop: groundTop.mix(o.groundTop, t), groundBottom: groundBottom.mix(o.groundBottom, t),
                   soil: soil.mix(o.soil, t), night: night + (o.night - night) * t)
    }
}

struct PlacedPlant: Identifiable {
    let plant: Plant
    let x, y, scale: CGFloat
    let row: Int
    let phase: Double
    var id: String { plant.id }
    /// Rough tap area in view points.
    var hitRect: CGRect {
        let h = GardenPainter.height(of: plant) * scale
        return CGRect(x: x - 24 * scale, y: y - h - 20 * scale, width: 48 * scale, height: h + 26 * scale)
    }
}

enum GardenPainter {
    // MARK: layout

    static func hash(_ s: String) -> UInt32 {
        var h: UInt32 = 2166136261
        for u in s.unicodeScalars { h = (h ^ u.value) &* 16777619 }
        return h
    }

    struct Rand {
        var seed: UInt32
        mutating func next() -> Double {
            seed = (seed ^ (seed >> 15)) &* 2246822507 &+ 0x9e3779b9
            return Double(seed % 10000) / 10000
        }
    }

    /// van der Corput: each new plant lands in the biggest gap, and nobody moves when a new one arrives.
    static func vdc(_ k: Int) -> Double {
        var x = 0.0, f = 0.5, n = k + 1
        while n > 0 { if n & 1 == 1 { x += f }; n >>= 1; f /= 2 }
        return x
    }

    static func horizon(_ size: CGSize) -> CGFloat { size.height * 0.5 }

    static func layout(_ plants: [Plant], in size: CGSize, rows rowCount: Int = 3, density: CGFloat? = nil) -> [PlacedPlant] {
        let unit = size.height / 440
        let n = plants.count
        let d = density ?? (n <= 12 ? 1.5 : n <= 24 ? 1.2 : n <= 45 ? 0.95 : 0.8)
        let rows: [(y: CGFloat, s: CGFloat)] = rowCount == 1 ? [(0.96, 1)]
            : rowCount == 2 ? [(0.76, 0.8), (0.97, 1)]
            : [(0.7, 0.62), (0.83, 0.8), (0.96, 1)]
        let offsets = [0.0, 0.37, 0.71]
        return plants.enumerated().map { i, p in
            let row = i % rows.count, k = i / rows.count
            var r = Rand(seed: hash(p.phrase) ^ 77)
            let frac = (vdc(k) + offsets[row]).truncatingRemainder(dividingBy: 1)
            let x = size.width * (0.07 + 0.86 * frac) + (r.next() - 0.5) * 12 * unit
            let y = size.height * rows[row].y + (r.next() - 0.5) * 6 * unit
            return PlacedPlant(plant: p, x: x, y: y, scale: rows[row].s * unit * d, row: row, phase: r.next() * .pi * 2)
        }
        .sorted { ($0.row, $0.y) < ($1.row, $1.y) }
    }

    static func height(of p: Plant) -> CGFloat {
        switch p.stageEnum {
        case .seed: 24
        case .sprout: 40 + CGFloat(p.growth - 3) * 9
        case .bloom: 110 + min(20, CGFloat(p.heard - 8) * 1.2)
        }
    }

    // MARK: scene

    struct Options {
        var time: Double = 0          // seconds, drives sway / clouds / critters
        var hour: Double = 12         // local hour, drives the sky
        var animated = true
        var critters = true
        var grown: [String: Double] = [:]  // phrase -> time it last grew, for the pop animation
        var selected: String? = nil
    }

    static func drawScene(_ ctx: GraphicsContext, size: CGSize, placed: [PlacedPlant], blooms: Int, options o: Options) {
        let sky = SkyPalette.at(hour: o.hour)
        let hz = horizon(size), w = size.width, h = size.height, unit = h / 440, t = o.time

        ctx.fill(Path(CGRect(origin: .zero, size: size)),
                 with: .linearGradient(Gradient(colors: [sky.skyTop.color, sky.skyBottom.color]), startPoint: .zero, endPoint: CGPoint(x: 0, y: hz + 30 * unit)))

        // stars
        if sky.night > 0.3 {
            var r = Rand(seed: 42)
            for _ in 0..<80 {
                let x = r.next() * w, y = r.next() * hz * 0.95, rad = (r.next() * 1.1 + 0.3) * max(1, unit)
                let tw = o.animated ? 0.55 + 0.45 * sin(t * (1 + r.next() * 2) + r.next() * 6) : 0.8
                ctx.fill(circle(x, y, rad), with: .color(.white.opacity((sky.night - 0.3) * 1.4 * tw * (0.4 + r.next() * 0.6))))
            }
        }

        // sun by day, moon by night, arcing across the sky with the real hour
        let hr = o.hour.truncatingRemainder(dividingBy: 24)
        let isDay = hr >= 6 && hr < 19
        let p = isDay ? (hr - 6) / 13 : ((hr - 19 + 24).truncatingRemainder(dividingBy: 24)) / 11
        let bx = w * (0.1 + 0.8 * p), by = hz * 0.8 - sin(p * .pi) * hz * 0.42
        if isDay {
            let r = 16 * unit * 1.6
            ctx.fill(circle(bx, by, r * 3.2), with: .radialGradient(Gradient(colors: [Color(hex: 0xffe08a, opacity: 0.55), Color(hex: 0xffe08a, opacity: 0)]),
                                                                    center: CGPoint(x: bx, y: by), startRadius: r * 0.8, endRadius: r * 3.2))
            ctx.fill(circle(bx, by, r), with: .radialGradient(Gradient(colors: [Color(hex: 0xfff6d5), Color(hex: 0xffcf4d)]), center: CGPoint(x: bx, y: by), startRadius: 0, endRadius: r))
        } else {
            let r = 12 * unit * 1.6
            ctx.fill(circle(bx, by, r * 2.6), with: .radialGradient(Gradient(colors: [Color.white.opacity(0.18), .clear]), center: CGPoint(x: bx, y: by), startRadius: r, endRadius: r * 2.6))
            var moon = ctx
            moon.clipToLayer { c in
                c.fill(circle(bx, by, r), with: .color(.black))
            }
            moon.fill(circle(bx, by, r), with: .color(Color(hex: 0xf5eed6)))
            moon.fill(circle(bx + r * 0.45, by - r * 0.3, r * 0.92), with: .color(sky.skyTop.color))
        }

        // clouds
        if sky.night < 0.7 {
            for i in 0..<3 {
                let speed = 4.0 + Double(i) * 2.5, span = w + 200 * unit
                let cx = (Double(i) * span / 3 + (o.animated ? t * speed * unit : 0)).truncatingRemainder(dividingBy: span) - 100 * unit
                let cy = hz * (0.18 + 0.2 * Double(i % 2)), s = unit * (1 - Double(i) * 0.15)
                let c = Color.white.opacity((1 - sky.night) * 0.85)
                ctx.fill(ellipse(cx, cy, 52 * s, 15 * s), with: .color(c))
                ctx.fill(ellipse(cx + 26 * s, cy - 11 * s, 30 * s, 19 * s), with: .color(c))
                ctx.fill(ellipse(cx - 20 * s, cy - 6 * s, 22 * s, 14 * s), with: .color(c))
            }
        }

        // hills + ground
        ctx.fill(hill(w: w, h: h, y: hz - 8 * unit, amp: 26 * unit, shift: 0.0), with: .color(sky.hillBack.color))
        ctx.fill(hill(w: w, h: h, y: hz + 6 * unit, amp: 14 * unit, shift: 0.35), with: .color(sky.hillFront.color))
        ctx.fill(Path(CGRect(x: 0, y: hz + 16 * unit, width: w, height: h - hz)),
                 with: .linearGradient(Gradient(colors: [sky.groundTop.color, sky.groundBottom.color]), startPoint: CGPoint(x: 0, y: hz + 16 * unit), endPoint: CGPoint(x: 0, y: h)))
        for row in Set(placed.map(\.row)).sorted() {
            if let y = placed.first(where: { $0.row == row })?.y {
                ctx.fill(ellipse(w / 2, y + 3 * unit, w * 0.52, 8 * unit * (0.6 + 0.2 * Double(row))), with: .color(sky.soil.color.opacity(0.22)))
            }
        }

        // plants, back to front
        for pp in placed {
            var c = ctx
            c.translateBy(x: pp.x, y: pp.y)
            var s = pp.scale
            if let g = o.grown[pp.id], o.animated {
                let e = t - g
                if e >= 0 && e < 1.2 { s *= 1 + 0.35 * exp(-5 * e) * sin(e * 11) }
            }
            if pp.id == o.selected {
                c.fill(ellipse(0, 2 * pp.scale, 30 * pp.scale, 8 * pp.scale), with: .color(.white.opacity(0.55)))
            }
            c.scaleBy(x: s, y: s)
            let sway = o.animated ? sin(t * 0.9 + pp.phase) * 0.028 : 0
            drawPlant(c, pp.plant, sway: sway, lean: pp.plant.thirsty ? -0.1 : 0, soil: sky.soil.color)
            if let g = o.grown[pp.id], o.animated, pp.plant.stageEnum == .bloom {
                let e = t - g
                if e >= 0 && e < 1.2 {
                    let top = -height(of: pp.plant) + 10
                    for i in 0..<10 {
                        let a = Double(i) / 10 * .pi * 2, d = 14 + e * 40
                        c.fill(circle(cos(a) * d, top + sin(a) * d, 2.6 * (1 - e / 1.2)), with: .color(flowerAccent(pp.plant.flower).opacity(1 - e / 1.2)))
                    }
                }
            }
        }

        // butterflies by day, fireflies by night
        guard o.critters else { return }
        let count = min(4, blooms / 3)
        let wings: [UInt32] = [0xf09a1a, 0xe2638f, 0x9a6ad0, 0xf2b705]
        for i in 0..<count where sky.night < 0.5 {
            let k = Double(i + 1), ph = Double(i) * 1.7
            let x = w * (0.5 + 0.42 * sin(t * 0.11 * k + ph)), y = hz * 1.22 + (h - hz) * 0.2 * sin(t * 0.17 * k + ph * 2)
            let flap = o.animated ? abs(sin(t * 11 + ph)) * 0.8 + 0.2 : 0.8
            var c = ctx
            c.translateBy(x: x, y: y)
            c.scaleBy(x: unit * 1.3, y: unit * 1.3)
            for side in [-1.0, 1.0] {
                c.fill(ellipse(side * 6 * flap, -4, 7 * flap, 5.5), with: .color(Color(hex: wings[i])))
                c.fill(ellipse(side * 5 * flap, 4, 5 * flap, 4), with: .color(Color(hex: wings[i], opacity: 0.85)))
            }
            c.fill(ellipse(0, 0, 1.4, 5), with: .color(Color(hex: 0x3a2a1a)))
        }
        if sky.night > 0.5 {
            var r = Rand(seed: 991)
            for _ in 0..<(count * 3 + 4) {
                let bx = r.next() * w, by = hz + r.next() * (h - hz) * 0.8, sp = 0.3 + r.next() * 0.5, ph = r.next() * 6
                let x = bx + (o.animated ? sin(t * sp + ph) * 18 * unit : 0), y = by + (o.animated ? cos(t * sp * 0.8 + ph) * 12 * unit : 0)
                let a = o.animated ? max(0, sin(t * (0.8 + sp) + ph)) : 0.7
                ctx.fill(circle(x, y, 9 * unit), with: .radialGradient(Gradient(colors: [Color(hex: 0xfff6a8, opacity: a), Color(hex: 0xfff6a8, opacity: 0)]),
                                                                        center: CGPoint(x: x, y: y), startRadius: 0, endRadius: 9 * unit))
            }
        }
    }

    // MARK: plants

    static func drawPlant(_ base: GraphicsContext, _ p: Plant, sway: Double, lean: Double, soil: Color) {
        var r = Rand(seed: hash(p.phrase))
        let g = CGFloat(p.growth)
        base.fill(mound(15), with: .color(soil))
        var c = base
        c.rotate(by: .radians(sway + lean + (r.next() - 0.5) * 0.08))
        switch p.stageEnum {
        case .seed:
            c.fill(ellipse(-3, -4, 4.8, 3.3), with: .color(Color(hex: 0x6e4322)))
            if g >= 1 { c.stroke(line(0, -5, 0, -6 - g * 6), with: .color(Color(hex: 0x4c8b3f)), style: StrokeStyle(lineWidth: 2, lineCap: .round)) }
            if g >= 2 { leaf(c, 0, -16, -35, 10, 0x7dbb62); leaf(c, 0, -16, 215, 9, 0x5fa052) }
            if p.thirsty { drop(c, 14, -20) }
        case .sprout, .bloom:
            let bloom = p.stageEnum == .bloom
            let h = height(of: p) - (bloom ? 26 : 10)
            let bend = (r.next() - 0.5) * 16, tip = bend * 0.45
            var stem = Path()
            stem.move(to: .zero)
            stem.addQuadCurve(to: CGPoint(x: tip, y: -h), control: CGPoint(x: bend, y: -h / 2))
            c.stroke(stem, with: .color(Color(hex: 0x4c8b3f)), style: StrokeStyle(lineWidth: bloom ? 3.4 : 2.7, lineCap: .round))
            let n = bloom ? 6 : min(5, p.growth - 1)
            for i in 0..<max(0, n) {
                let tt = 0.12 + Double(i) / Double(n) * 0.7, side: Double = i % 2 == 1 ? 1 : -1
                let len = (bloom ? 22 : 16) * (1.1 - tt * 0.5)
                let lx = 2 * (1 - tt) * tt * bend + tt * tt * tip
                leaf(c, lx, -h * tt, side > 0 ? -28 - r.next() * 16 : 208 + r.next() * 16, len, i % 3 == 0 ? 0x7dbb62 : 0x5fa052)
            }
            var top = c
            top.translateBy(x: tip, y: -h)
            if bloom {
                let s = 1 + min(0.35, Double(p.heard - 8) * 0.025)
                top.scaleBy(x: s, y: s)
                top.rotate(by: .radians(-sway * 2))
                drawFlower(top, p.flower)
            } else if p.growth >= 6 {
                petal(top, 0, 0, -90, 13, 4.6, flowerAccent(p.flower))
                leaf(top, 0, 0, -65, 9, 0x5fa052); leaf(top, 0, 0, 245, 9, 0x7dbb62)
            } else {
                leaf(top, 0, 0, -50, 12, 0x7dbb62); leaf(top, 0, 0, 230, 11, 0x5fa052)
            }
            if p.thirsty { drop(c, tip + 16, -h - 6) }
        }
    }

    static func flowerAccent(_ f: Flower) -> Color {
        switch f {
        case .marigold: Color(hex: 0xe8850c)
        case .lotus: Color(hex: 0xe2638f)
        case .hibiscus: Color(hex: 0xdc2f55)
        case .sunflower: Color(hex: 0xf2b705)
        case .morningGlory: Color(hex: 0x4f6bd8)
        case .rose: Color(hex: 0xc2417a)
        case .lavender: Color(hex: 0x9a6ad0)
        case .jasmine: Color(hex: 0xe9e4d0)
        }
    }

    /// Flower head centred at (0, 0), about 30 units across.
    static func drawFlower(_ c: GraphicsContext, _ f: Flower) {
        func ring(_ n: Int, _ rad: Double, _ r: Double, _ hex: UInt32, _ off: Double = 0) {
            for i in 0..<n { let a = Double(i) / Double(n) * .pi * 2 + off; c.fill(circle(cos(a) * rad, sin(a) * rad, r), with: .color(Color(hex: hex))) }
        }
        func petals(_ n: Int, _ len: Double, _ wid: Double, _ hex: UInt32, start: Double = -90, step: Double? = nil) {
            for i in 0..<n { petal(c, 0, 0, start + Double(i) * (step ?? 360 / Double(n)), len, wid, Color(hex: hex)) }
        }
        switch f {
        case .marigold:
            ring(14, 12, 5.4, 0xd9700a); ring(11, 7.6, 4.8, 0xf09a1a, 0.3); ring(7, 3.7, 3.7, 0xfbb934, 0.6)
            c.fill(circle(0, 0, 2.6), with: .color(Color(hex: 0xffd25e)))
        case .lotus:
            petal(c, 0, 2, 190, 25, 6.5, Color(hex: 0xe97ba1)); petal(c, 0, 2, -10, 25, 6.5, Color(hex: 0xe97ba1))
            petals(5, 26, 7.5, 0xec8fb0, start: -154, step: 32); petals(3, 20, 5.5, 0xf8c3d6, start: -122, step: 32)
            c.fill(ellipse(0, -2, 4.5, 3), with: .color(Color(hex: 0xf7cf4a)))
        case .hibiscus:
            petals(5, 22, 11.5, 0xdc2f55, start: -80)
            c.fill(circle(0, 0, 4.2), with: .color(Color(hex: 0x8e1230)))
            c.stroke(line(0, 0, 7, -13), with: .color(Color(hex: 0xf7d36b)), style: StrokeStyle(lineWidth: 1.6, lineCap: .round))
            c.fill(circle(7.5, -14, 2.3), with: .color(Color(hex: 0xf7d36b)))
        case .sunflower:
            petals(14, 20, 3.8, 0xf2b705); petals(14, 15, 3, 0xf7cf3a, start: -77)
            c.fill(circle(0, 0, 7.2), with: .color(Color(hex: 0x6b3f1d))); c.fill(circle(0, 0, 4.2), with: .color(Color(hex: 0x4d2c13)))
        case .morningGlory:
            c.fill(circle(0, 0, 14.5), with: .color(Color(hex: 0x4f6bd8)))
            petals(5, 13.5, 2.6, 0x8ea3ef)
            c.fill(circle(0, 0, 5.6), with: .color(Color(hex: 0xf4f6ff))); c.fill(circle(0, 0, 2), with: .color(Color(hex: 0xf2d66b)))
        case .rose:
            ring(9, 10, 5.8, 0xa92b64); ring(7, 6.3, 5.1, 0xc2417a, 0.4); ring(4, 2.9, 3.7, 0xe2709e, 0.9)
            c.fill(circle(0, 0, 2.5), with: .color(Color(hex: 0xf4a3c2)))
        case .lavender:
            for i in 0..<7 {
                let y = 10 - Double(i) * 5.2
                c.fill(ellipse(i % 2 == 1 ? 3 : -3, y, 4.4 - Double(i) * 0.4, 3.4 - Double(i) * 0.25), with: .color(Color(hex: i % 2 == 1 ? 0xb18ae0 : 0x9a6ad0)))
            }
        case .jasmine:
            petals(5, 17, 6.4, 0xc9bf9c); petals(5, 16, 5.6, 0xfdfcf6)
            c.fill(circle(0, 0, 3.1), with: .color(Color(hex: 0xe6c95a)))
            var small = c
            small.translateBy(x: -13, y: 10); small.scaleBy(x: 0.6, y: 0.6)
            for i in 0..<5 { petal(small, 0, 0, -70 + Double(i) * 72, 16, 5.6, Color(hex: 0xfdfcf6)) }
            small.fill(circle(0, 0, 3.1), with: .color(Color(hex: 0xe6c95a)))
        }
    }

    // MARK: primitives

    static func circle(_ x: Double, _ y: Double, _ r: Double) -> Path { Path(ellipseIn: CGRect(x: x - r, y: y - r, width: r * 2, height: r * 2)) }
    static func ellipse(_ x: Double, _ y: Double, _ rx: Double, _ ry: Double) -> Path { Path(ellipseIn: CGRect(x: x - rx, y: y - ry, width: rx * 2, height: ry * 2)) }
    static func line(_ x0: Double, _ y0: Double, _ x1: Double, _ y1: Double) -> Path { var p = Path(); p.move(to: CGPoint(x: x0, y: y0)); p.addLine(to: CGPoint(x: x1, y: y1)); return p }

    static func mound(_ r: Double) -> Path {
        var p = Path()
        p.move(to: CGPoint(x: -r, y: 1)); p.addQuadCurve(to: CGPoint(x: r, y: 1), control: CGPoint(x: 0, y: -r * 0.62)); p.closeSubpath()
        return p
    }

    /// Leaf or petal pointing `deg` degrees from (x, y).
    static func petal(_ c: GraphicsContext, _ x: Double, _ y: Double, _ deg: Double, _ len: Double, _ wid: Double, _ color: Color) {
        let a = deg * .pi / 180, cs = cos(a), sn = sin(a)
        func at(_ u: Double, _ v: Double) -> CGPoint { CGPoint(x: x + u * cs - v * sn, y: y + u * sn + v * cs) }
        var p = Path()
        p.move(to: at(0, 0))
        p.addQuadCurve(to: at(len, 0), control: at(len * 0.45, -wid))
        p.addQuadCurve(to: at(0, 0), control: at(len * 0.45, wid))
        p.closeSubpath()
        c.fill(p, with: .color(color))
    }

    static func leaf(_ c: GraphicsContext, _ x: Double, _ y: Double, _ deg: Double, _ len: Double, _ hex: UInt32) {
        petal(c, x, y, deg, len, len * 0.34, Color(hex: hex))
        let a = deg * .pi / 180
        c.stroke(line(x, y, x + cos(a) * len * 0.75, y + sin(a) * len * 0.75), with: .color(.black.opacity(0.08)), lineWidth: 0.6)
    }

    static func drop(_ c: GraphicsContext, _ x: Double, _ y: Double) {
        var p = Path()
        p.move(to: CGPoint(x: x, y: y - 8))
        p.addCurve(to: CGPoint(x: x, y: y + 3.5), control1: CGPoint(x: x + 4.5, y: y - 2), control2: CGPoint(x: x + 4.5, y: y + 2.5))
        p.addCurve(to: CGPoint(x: x, y: y - 8), control1: CGPoint(x: x - 4.5, y: y + 2.5), control2: CGPoint(x: x - 4.5, y: y - 2))
        c.fill(p, with: .color(Color(hex: 0x5aa9e6)))
        c.stroke(p, with: .color(.white), lineWidth: 1)
    }

    static func hill(w: Double, h: Double, y: Double, amp: Double, shift: Double) -> Path {
        var p = Path()
        p.move(to: CGPoint(x: 0, y: y + amp * 0.2))
        let steps = 4
        for i in 0..<steps {
            let x0 = w * Double(i) / Double(steps), x1 = w * Double(i + 1) / Double(steps)
            let up = sin(Double(i) * 2.1 + shift * 7) * amp
            p.addQuadCurve(to: CGPoint(x: x1, y: y + sin(Double(i + 1) * 1.3 + shift * 5) * amp * 0.3), control: CGPoint(x: (x0 + x1) / 2, y: y - abs(up)))
        }
        p.addLine(to: CGPoint(x: w, y: h)); p.addLine(to: CGPoint(x: 0, y: h)); p.closeSubpath()
        return p
    }
}

/// A single plant (or flower) as a small icon, for lists and cards.
struct PlantIcon: View {
    let plant: Plant
    var flowerOnly = false

    var body: some View {
        Canvas { ctx, size in
            let s = size.height / (flowerOnly ? 34 : GardenPainter.height(of: plant) + 12)
            var c = ctx
            if flowerOnly {
                c.translateBy(x: size.width / 2, y: size.height / 2 + (plant.flower == .lavender ? size.height * 0.1 : 0))
                c.scaleBy(x: s, y: s)
                GardenPainter.drawFlower(c, plant.flower)
            } else {
                c.translateBy(x: size.width / 2, y: size.height - 4 * s)
                c.scaleBy(x: s, y: s)
                GardenPainter.drawPlant(c, plant, sway: 0, lean: 0, soil: Color(hex: 0x8a5a33))
            }
        }
    }
}
