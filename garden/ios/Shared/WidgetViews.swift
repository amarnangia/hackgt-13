import SwiftUI
import WidgetKit

// The "next conversation" widget. Shared by the widget extension and the app's widget gallery.

struct GardenEntry: TimelineEntry {
    let date: Date
    let snapshot: GardenSnapshot
    let source: GardenClient.Source
    /// What to ask next call, written by the story keeper from her stories last time (newest call that has them).
    var questions: [Question] = []
    var caller: String? = nil
    /// Changes every 3 hours, so the suggestion rotates through the day but stays put between refreshes.
    var rotation: Int { Int(date.timeIntervalSince1970 / 10800) }
}

struct GardenWidgetView: View {
    @Environment(\.widgetFamily) private var envFamily
    let entry: GardenEntry
    var familyOverride: WidgetFamily? = nil   // lets the app draw the widget for its preview gallery
    private var family: WidgetFamily { familyOverride ?? envFamily }

    private var snap: GardenSnapshot { entry.snapshot }
    private var starters: [Starter] { Starters.make(snap, rotation: entry.rotation) }
    private var lastCall: String? { Starters.lastCall(snap, now: entry.date.timeIntervalSince1970) }
    /// A real question from her last call, rotating through the day.
    private var ask: Question? { entry.questions.isEmpty ? nil : entry.questions[entry.rotation % entry.questions.count] }

    /// "Ask" + her words in Telugu, how to say them, and what they mean.
    private func askView(_ q: Question, size: CGFloat) -> some View {
        VStack(alignment: .leading, spacing: 3) {
            if let te = q.telugu { Text(te).font(Fonts.telugu(size, .medium)).foregroundStyle(Theme.text).lineLimit(2).minimumScaleFactor(0.7) }
            if let r = q.roman { Text("“\(r)”").font(Fonts.serif(size * 0.72, italic: true)).foregroundStyle(Theme.accent).lineLimit(2) }
            if let en = q.english { Text(en).font(Fonts.ui(max(11, size * 0.55))).foregroundStyle(Theme.text2).lineLimit(2) }
        }
    }

    var body: some View {
        switch family {
        case .accessoryInline:
            Text(ask?.roman.map { "Ask “\($0)”" } ?? starters.first.map { "Ask about \($0.word)" } ?? "Call family today")
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
                if let q = ask {
                    Text(q.roman.map { "Ask “\($0)”" } ?? q.english ?? "").font(.system(size: 14)).lineLimit(2)
                } else if let s = starters.first {
                    (Text(s.before + " ") + Text(s.word).bold() + Text(s.after)).font(.system(size: 14)).lineLimit(2)
                } else { Text("Call family today").font(.system(size: 14, weight: .semibold)) }
            }
            .frame(maxWidth: .infinity, alignment: .leading)
            .containerBackground(for: .widget) { Color.clear }
        case .systemSmall:
            small.padding(16).containerBackground(for: .widget) { WidgetBackdrop() }
        case .systemLarge:
            large.padding(18).containerBackground(for: .widget) { WidgetBackdrop() }
        default:
            medium.padding(16).containerBackground(for: .widget) { WidgetBackdrop() }
        }
    }

    // MARK: sizes

    private var small: some View {
        VStack(alignment: .leading, spacing: 0) {
            label
            Spacer(minLength: 8)
            if let q = ask {
                askView(q, size: 19)
            } else if let s = starters.first {
                sentence(s, size: 17).lineLimit(4).minimumScaleFactor(0.85)
                if let g = s.gloss { Text(g).font(Fonts.ui(12)).foregroundStyle(Theme.text2).lineLimit(1).padding(.top, 4) }
            } else { empty }
            Spacer(minLength: 8)
            if let lastCall { Text(lastCall).font(Fonts.mono(10, .regular)).foregroundStyle(Theme.text3) }
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .leading)
    }

    private var medium: some View {
        HStack(spacing: 12) {
            VStack(alignment: .leading, spacing: 0) {
                HStack(spacing: 6) { label; if ask == nil, let s = starters.first { topicChip(s) } }
                Spacer(minLength: 6)
                if let q = ask {
                    askView(q, size: 22)
                } else if let s = starters.first {
                    sentence(s, size: 20).lineLimit(3).minimumScaleFactor(0.85)
                    if let g = s.gloss { Text(g).font(Fonts.ui(12)).foregroundStyle(Theme.text2).lineLimit(1).padding(.top, 4) }
                } else { empty }
                Spacer(minLength: 6)
                if let lastCall { Text(lastCall).font(Fonts.mono(10, .regular)).foregroundStyle(Theme.text3) }
            }
            .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .leading)
            if let phrase = Starters.trySaying(snap, rotation: entry.rotation) {
                VStack(alignment: .leading, spacing: 3) {
                    Eyebrow("Try saying")
                    Spacer(minLength: 2)
                    Text(phrase.phrase).font(Fonts.telugu(18, .medium)).foregroundStyle(Theme.text).lineLimit(2).minimumScaleFactor(0.7)
                    Text(phrase.english ?? "").font(Fonts.ui(11)).foregroundStyle(Theme.text2).lineLimit(2)
                }
                .padding(12)
                .frame(width: 118).frame(maxHeight: .infinity, alignment: .topLeading)
                .background(Theme.surface, in: .rect(cornerRadius: 14))
                .overlay(RoundedRectangle(cornerRadius: 14).strokeBorder(Theme.border, lineWidth: 1))
            }
        }
    }

    private var large: some View {
        VStack(alignment: .leading, spacing: 0) {
            HStack {
                label
                Spacer()
                if let lastCall { Text(lastCall).font(Fonts.mono(10, .regular)).foregroundStyle(Theme.text3) }
            }
            if let q = ask {
                Text("From her stories last call").font(Fonts.ui(12)).foregroundStyle(Theme.text3).padding(.top, 14)
                askView(q, size: 26).padding(.top, 8)
            } else if let s = starters.first {
                topicChip(s).padding(.top, 14)
                sentence(s, size: 26).lineLimit(3).minimumScaleFactor(0.8).padding(.top, 8)
                if let g = s.gloss { Text(g).font(Fonts.ui(13)).foregroundStyle(Theme.text2).padding(.top, 4) }
            } else { empty.padding(.top, 14) }
            if ask != nil, entry.questions.count > 1 {
                Eyebrow("Also ask").padding(.top, 18)
                ForEach(Array(entry.questions.filter { $0 != ask }.prefix(2).enumerated()), id: \.offset) { _, q in
                    HStack(alignment: .firstTextBaseline, spacing: 8) {
                        Text(q.telugu ?? q.roman ?? "").font(Fonts.telugu(15, .medium)).foregroundStyle(Theme.text).lineLimit(1)
                        Text(q.english ?? "").font(Fonts.ui(12)).foregroundStyle(Theme.text2).lineLimit(1)
                    }
                    .padding(.vertical, 6)
                }
            } else if starters.count > 1 {
                Eyebrow("Also ask").padding(.top, 18)
                VStack(spacing: 0) {
                    ForEach(Array(starters.dropFirst().enumerated()), id: \.element.id) { i, s in
                        if i > 0 { Rectangle().fill(Theme.border).frame(height: 1).padding(.leading, 40) }
                        HStack(spacing: 10) {
                            Image(systemName: s.symbol).font(.system(size: 12, weight: .medium)).foregroundStyle(Theme.text2)
                                .frame(width: 28, height: 28)
                                .background(Theme.surface2, in: .rect(cornerRadius: 8))
                            sentence(s, size: 14.5).lineLimit(2)
                            Spacer(minLength: 0)
                        }
                        .padding(.vertical, 8)
                    }
                }
                .padding(.top, 4)
            }
            Spacer(minLength: 10)
            if let phrase = Starters.trySaying(snap, rotation: entry.rotation) {
                HStack(alignment: .firstTextBaseline, spacing: 8) {
                    Eyebrow("Try saying")
                    Text(phrase.phrase).font(Fonts.telugu(15, .medium)).foregroundStyle(Theme.text)
                    Text(phrase.english ?? "").font(Fonts.ui(12)).foregroundStyle(Theme.text2).lineLimit(1)
                    Spacer(minLength: 0)
                }
                .padding(.horizontal, 12).padding(.vertical, 10)
                .background(Theme.surface, in: .rect(cornerRadius: 12))
                .overlay(RoundedRectangle(cornerRadius: 12).strokeBorder(Theme.border, lineWidth: 1))
            }
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .topLeading)
    }

    // MARK: pieces

    private var label: some View {
        HStack(spacing: 6) {
            Circle().fill(Theme.accent).frame(width: 5, height: 5)
            Text("NEXT CALL").font(Fonts.mono(10)).tracking(0.9).foregroundStyle(Theme.accent)
        }
    }

    private func topicChip(_ s: Starter) -> some View {
        HStack(spacing: 4) {
            Image(systemName: s.symbol).font(.system(size: 9, weight: .medium))
            Text(s.topic).font(Fonts.ui(10, .medium))
        }
        .foregroundStyle(Theme.text2)
        .padding(.horizontal, 7).padding(.vertical, 3)
        .overlay(Capsule().strokeBorder(Theme.border2, lineWidth: 1))
    }

    /// "Ask how she makes పులిహోర." in the editorial serif, the Telugu word in the accent.
    private func sentence(_ s: Starter, size: CGFloat) -> Text {
        Text(s.before + " ").font(Fonts.serif(size)).foregroundColor(Theme.text)
            + Text(s.word).font(Fonts.telugu(size * 0.9, .medium)).foregroundColor(Theme.accent)
            + Text(s.after).font(Fonts.serif(size)).foregroundColor(Theme.text)
    }

    private var empty: some View {
        Text("Your first call will suggest things to talk about.").font(Fonts.ui(14, .medium)).foregroundStyle(Theme.text2)
    }
}

/// Near-black with a faint light from above.
struct WidgetBackdrop: View {
    var body: some View {
        ZStack {
            Theme.bg
            RadialGradient(colors: [Theme.accent.opacity(0.12), .clear], center: .topLeading, startRadius: 0, endRadius: 260)
        }
    }
}
