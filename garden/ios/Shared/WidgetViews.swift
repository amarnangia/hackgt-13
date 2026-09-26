import SwiftUI
import WidgetKit

// The "next conversation" widget. Shared by the widget extension and the app's widget gallery.

struct GardenEntry: TimelineEntry {
    let date: Date
    let snapshot: GardenSnapshot
    let source: GardenClient.Source
    /// Changes every 3 hours, so the suggestion rotates through the day but stays put between refreshes.
    var rotation: Int { Int(date.timeIntervalSince1970 / 10800) }
}

/// Stone neutrals + one terracotta accent.
struct WidgetPalette {
    let bg, surface, border, ink, ink2, muted, accent: Color
    init(_ scheme: ColorScheme) {
        if scheme == .dark {
            bg = Color(hex: 0x0c0a09); surface = Color(hex: 0x1c1917); border = .white.opacity(0.09)
            ink = Color(hex: 0xfafaf9); ink2 = Color(hex: 0xa8a29e); muted = Color(hex: 0x78716c); accent = Color(hex: 0xe0825f)
        } else {
            bg = Color(hex: 0xfafaf9); surface = Color(hex: 0xf2efec); border = .black.opacity(0.07)
            ink = Color(hex: 0x1c1917); ink2 = Color(hex: 0x57534e); muted = Color(hex: 0x8a837d); accent = Color(hex: 0xb4532a)
        }
    }
}

struct GardenWidgetView: View {
    @Environment(\.widgetFamily) private var envFamily
    @Environment(\.colorScheme) private var scheme
    let entry: GardenEntry
    var familyOverride: WidgetFamily? = nil   // lets the app draw the widget for its preview gallery
    private var family: WidgetFamily { familyOverride ?? envFamily }

    private var snap: GardenSnapshot { entry.snapshot }
    private var p: WidgetPalette { WidgetPalette(scheme) }
    private var starters: [Starter] { Starters.make(snap, rotation: entry.rotation) }
    private var lastCall: String? { Starters.lastCall(snap, now: entry.date.timeIntervalSince1970) }

    var body: some View {
        switch family {
        case .accessoryInline:
            Text(starters.first.map { "Ask about \($0.word)" } ?? "Call family today")
                .containerBackground(for: .widget) { Color.clear }
        case .accessoryCircular:
            ZStack {
                AccessoryWidgetBackground()
                VStack(spacing: 1) {
                    Image(systemName: starters.first?.symbol ?? "phone.fill").font(.system(size: 17, weight: .semibold))
                    Text("Ask").font(.system(size: 11, weight: .semibold))
                }
            }
            .widgetAccentable()
            .containerBackground(for: .widget) { Color.clear }
        case .accessoryRectangular:
            VStack(alignment: .leading, spacing: 1) {
                Text("NEXT CALL").font(.system(size: 11, weight: .bold)).tracking(0.6).widgetAccentable()
                if let s = starters.first { sentence(s, size: 14, accent: .primary).lineLimit(2) }
                else { Text("Call family today").font(.system(size: 14, weight: .semibold)) }
            }
            .frame(maxWidth: .infinity, alignment: .leading)
            .containerBackground(for: .widget) { Color.clear }
        case .systemSmall:
            small.padding(16).containerBackground(for: .widget) { p.bg }
        case .systemLarge:
            large.padding(18).containerBackground(for: .widget) { p.bg }
        default:
            medium.padding(16).containerBackground(for: .widget) { p.bg }
        }
    }

    // MARK: sizes

    private var small: some View {
        VStack(alignment: .leading, spacing: 0) {
            label("Next call")
            Spacer(minLength: 8)
            if let s = starters.first {
                sentence(s, size: 16).lineLimit(4).minimumScaleFactor(0.85)
                if let g = s.gloss { Text(g).font(.system(size: 12)).foregroundStyle(p.ink2).lineLimit(1).padding(.top, 3) }
            } else { empty }
            Spacer(minLength: 8)
            if let lastCall { Text(lastCall).font(.system(size: 11, weight: .medium)).foregroundStyle(p.muted) }
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .leading)
    }

    private var medium: some View {
        HStack(spacing: 12) {
            VStack(alignment: .leading, spacing: 0) {
                HStack(spacing: 6) {
                    label("Next call")
                    if let s = starters.first { topicChip(s) }
                }
                Spacer(minLength: 6)
                if let s = starters.first {
                    sentence(s, size: 18).lineLimit(3).minimumScaleFactor(0.85)
                    if let g = s.gloss { Text(g).font(.system(size: 12)).foregroundStyle(p.ink2).lineLimit(1).padding(.top, 4) }
                } else { empty }
                Spacer(minLength: 6)
                if let lastCall { Text(lastCall).font(.system(size: 11, weight: .medium)).foregroundStyle(p.muted) }
            }
            .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .leading)
            if let phrase = Starters.trySaying(snap, rotation: entry.rotation) {
                trySaying(phrase).frame(width: 118)
            }
        }
    }

    private var large: some View {
        VStack(alignment: .leading, spacing: 0) {
            HStack {
                label("Next call")
                Spacer()
                if let lastCall { Text(lastCall).font(.system(size: 11, weight: .medium)).foregroundStyle(p.muted) }
            }
            if let s = starters.first {
                topicChip(s).padding(.top, 14)
                sentence(s, size: 24).lineLimit(3).minimumScaleFactor(0.8).padding(.top, 8)
                if let g = s.gloss { Text(g).font(.system(size: 13)).foregroundStyle(p.ink2).padding(.top, 4) }
            } else { empty.padding(.top, 14) }
            if starters.count > 1 {
                Text("ALSO ASK").font(.system(size: 10, weight: .bold)).tracking(0.8).foregroundStyle(p.muted).padding(.top, 16)
                VStack(spacing: 0) {
                    ForEach(Array(starters.dropFirst().enumerated()), id: \.element.id) { i, s in
                        if i > 0 { Rectangle().fill(p.border).frame(height: 1).padding(.leading, 40) }
                        HStack(spacing: 10) {
                            Image(systemName: s.symbol).font(.system(size: 12, weight: .semibold)).foregroundStyle(p.accent)
                                .frame(width: 28, height: 28)
                                .background(p.accent.opacity(0.12), in: .rect(cornerRadius: 8))
                            sentence(s, size: 13.5).lineLimit(2)
                            Spacer(minLength: 0)
                        }
                        .padding(.vertical, 8)
                    }
                }
                .padding(.top, 4)
            }
            Spacer(minLength: 10)
            if let phrase = Starters.trySaying(snap, rotation: entry.rotation) {
                HStack(alignment: .firstTextBaseline) {
                    Text("TRY SAYING").font(.system(size: 10, weight: .bold)).tracking(0.8).foregroundStyle(p.muted)
                    Text(phrase.phrase).font(.system(size: 15, weight: .semibold)).foregroundStyle(p.ink)
                    Text(phrase.english ?? "").font(.system(size: 12)).foregroundStyle(p.ink2).lineLimit(1)
                    Spacer(minLength: 0)
                }
                .padding(.horizontal, 12).padding(.vertical, 10)
                .background(p.surface, in: .rect(cornerRadius: 12))
                .overlay(RoundedRectangle(cornerRadius: 12).stroke(p.border, lineWidth: 1))
            }
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .topLeading)
    }

    // MARK: pieces

    private func label(_ text: String) -> some View {
        HStack(spacing: 5) {
            Circle().fill(p.accent).frame(width: 5, height: 5)
            Text(text.uppercased()).font(.system(size: 10, weight: .bold)).tracking(0.8).foregroundStyle(p.accent)
        }
    }

    private func topicChip(_ s: Starter) -> some View {
        HStack(spacing: 4) {
            Image(systemName: s.symbol).font(.system(size: 9, weight: .semibold))
            Text(s.topic).font(.system(size: 10, weight: .semibold))
        }
        .foregroundStyle(p.ink2)
        .padding(.horizontal, 7).padding(.vertical, 3)
        .overlay(Capsule().stroke(p.border, lineWidth: 1))
    }

    /// "Ask how she makes పులిహోర." with the Telugu word in the accent color.
    private func sentence(_ s: Starter, size: CGFloat, accent: Color? = nil) -> Text {
        (Text(s.before + " ").foregroundColor(p.ink)
            + Text(s.word).foregroundColor(accent ?? p.accent)
            + Text(s.after).foregroundColor(p.ink))
            .font(.system(size: size, weight: .semibold))
            .tracking(size >= 18 ? -0.5 : -0.2)
    }

    private func trySaying(_ phrase: Plant) -> some View {
        VStack(alignment: .leading, spacing: 3) {
            Text("TRY SAYING").font(.system(size: 9, weight: .bold)).tracking(0.8).foregroundStyle(p.muted)
            Spacer(minLength: 2)
            Text(phrase.phrase).font(.system(size: 17, weight: .semibold)).foregroundStyle(p.ink).lineLimit(2).minimumScaleFactor(0.8)
            Text(phrase.english ?? "").font(.system(size: 11)).foregroundStyle(p.ink2).lineLimit(2)
        }
        .padding(12)
        .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .topLeading)
        .background(p.surface, in: .rect(cornerRadius: 14))
        .overlay(RoundedRectangle(cornerRadius: 14).stroke(p.border, lineWidth: 1))
    }

    private var empty: some View {
        Text("Your first call will suggest topics here.").font(.system(size: 14, weight: .medium)).foregroundStyle(p.ink2)
    }
}
