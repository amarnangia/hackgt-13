import SwiftUI
import WidgetKit

// Shared by the widget extension and the app's widget gallery.

struct GardenEntry: TimelineEntry {
    let date: Date
    let snapshot: GardenSnapshot
    let source: GardenClient.Source
    var hour: Double {
        let c = Calendar.current.dateComponents([.hour, .minute], from: date)
        return Double(c.hour ?? 12) + Double(c.minute ?? 0) / 60
    }
}

/// Still garden picture for the widget background.
struct WidgetScene: View {
    let entry: GardenEntry
    let maxPlants: Int
    let rows: Int

    var body: some View {
        Canvas { ctx, size in
            let shown = entry.snapshot.plants
                .sorted { ($0.growth, $0.lastHeard ?? 0) > ($1.growth, $1.lastHeard ?? 0) }
                .prefix(maxPlants)
                .sorted { GardenPainter.hash($0.phrase) < GardenPainter.hash($1.phrase) }
            let n = CGFloat(shown.count)
            let placed = GardenPainter.layout(Array(shown), in: CGSize(width: size.width, height: size.height - 4), rows: rows,
                                              density: rows == 1 ? 1.35 * min(1.2, 8 / max(n, 5)) + 0.4 : 1.25)
            var o = GardenPainter.Options()
            o.hour = entry.hour
            o.animated = false
            o.time = 400
            GardenPainter.drawScene(ctx, size: size, placed: placed, blooms: entry.snapshot.totals.bloom, options: o)
        }
    }
}

struct GardenWidgetView: View {
    @Environment(\.widgetFamily) private var envFamily
    let entry: GardenEntry
    var familyOverride: WidgetFamily? = nil   // lets the app draw the widget for its preview gallery
    private var family: WidgetFamily { familyOverride ?? envFamily }

    private var snap: GardenSnapshot { entry.snapshot }
    private var night: Bool { SkyPalette.at(hour: entry.hour).night > 0.45 }
    private var ink: Color { night ? .white : Color(hex: 0x1d2a20) }

    var body: some View {
        switch family {
        case .accessoryCircular:
            Gauge(value: Double(snap.totals.bloom), in: 0...Double(max(1, snap.totals.phrases))) {
                Image(systemName: "camera.macro")
            } currentValueLabel: {
                Text("\(snap.totals.bloom)")
            }
            .gaugeStyle(.accessoryCircular)
            .widgetAccentable()
            .containerBackground(for: .widget) { AccessoryWidgetBackground() }
        case .accessoryRectangular:
            VStack(alignment: .leading, spacing: 1) {
                Label("\(snap.totals.bloom) in bloom", systemImage: "camera.macro").font(.headline).widgetAccentable()
                Text("\(snap.totals.sprout) sprouting · 🔥 \(snap.streak)").font(.caption)
                if let next = almost.first { Text("\(next.phrase) · \(next.toNext) more").font(.caption).foregroundStyle(.secondary) }
            }
            .containerBackground(for: .widget) { Color.clear }
        case .accessoryInline:
            Text("🌼 \(snap.totals.bloom) blooming · 🔥 \(snap.streak)")
                .containerBackground(for: .widget) { Color.clear }
        case .systemSmall:
            VStack(alignment: .leading, spacing: 0) {
                HStack(alignment: .top) {
                    VStack(alignment: .leading, spacing: -2) {
                        Text("\(snap.totals.bloom)").font(Theme.title(34))
                        Text("in bloom").font(.caption.weight(.bold)).opacity(0.8)
                    }
                    Spacer()
                    streak
                }
                Spacer()
            }
            .foregroundStyle(ink)
            .padding(14)
            .containerBackground(for: .widget) { WidgetScene(entry: entry, maxPlants: 5, rows: 1) }
        case .systemLarge:
            VStack(alignment: .leading, spacing: 10) {
                header
                if !almost.isEmpty {
                    VStack(alignment: .leading, spacing: 5) {
                        Text("ALMOST BLOOMING").font(.system(size: 10, weight: .heavy)).tracking(1).opacity(0.7)
                        ForEach(almost.prefix(3)) { p in
                            HStack(spacing: 8) {
                                Text(p.phrase).font(.subheadline.weight(.semibold)).lineLimit(1).layoutPriority(1)
                                Text(p.english ?? "").font(.caption).opacity(0.75).lineLimit(1)
                                Spacer()
                                Text("\(p.toNext) more").font(.caption.weight(.bold))
                            }
                            .padding(.horizontal, 10).padding(.vertical, 6)
                            .background(.ultraThinMaterial, in: .rect(cornerRadius: 10))
                        }
                    }
                }
                Spacer()
            }
            .foregroundStyle(ink)
            .padding(16)
            .containerBackground(for: .widget) { WidgetScene(entry: entry, maxPlants: 14, rows: 2) }
        default:
            VStack(alignment: .leading) { header; Spacer() }
                .foregroundStyle(ink)
                .padding(16)
                .containerBackground(for: .widget) { WidgetScene(entry: entry, maxPlants: 10, rows: 1) }
        }
    }

    private var almost: [Plant] { snap.plants.filter { $0.stageEnum == .sprout }.sorted { $0.toNext < $1.toNext } }

    private var header: some View {
        HStack(alignment: .top) {
            VStack(alignment: .leading, spacing: 0) {
                Text("WEAVE").font(.system(size: 10, weight: .heavy)).tracking(1.2).opacity(0.7)
                Text("\(snap.totals.bloom) words in bloom").font(Theme.title(20))
                Text(snap.calls.live ? "● On a call, growing live" : "\(snap.totals.sprout) sprouting · \(snap.totals.seed) seeds")
                    .font(.caption.weight(.semibold)).opacity(0.8)
            }
            Spacer()
            streak
        }
    }

    private var streak: some View {
        HStack(spacing: 3) {
            Image(systemName: "flame.fill").foregroundStyle(Color(hex: 0xff7a2e))
            Text("\(snap.streak)").font(.subheadline.weight(.bold))
        }
        .padding(.horizontal, 9).padding(.vertical, 5)
        .background(.ultraThinMaterial, in: .capsule)
    }
}

