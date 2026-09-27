import SwiftUI

/// "Next call": what to talk about, and when to reach out. The same idea as the widget and the website's
/// "For your next call" section, on the home screen:
///   - a nudge: when you last talked, and whether it's a good time to call again
///   - questions from her stories last time (the story keeper writes them after each saved call); or, before there are
///     any, starters about words you're learning
///   - a phrase you know well enough to try saying yourself
/// Everything in English letters (romanized words and English), like the overlay.
struct NextCallCard: View {
    @EnvironmentObject var people: People
    let snap: GardenSnapshot
    @State private var page = 0

    private var rotation: Int { Int(Date().timeIntervalSince1970 / 10800) }   // changes every 3 hours, like the widget
    private var latest: CallSummary? { people.calls.first }
    private var withQuestions: CallSummary? { people.calls.first { !($0.questions ?? []).isEmpty } }
    private var who: String { withQuestions?.caller ?? latest?.caller ?? people.partner.name }

    private struct Idea: Hashable { let main: String; let means: String? }
    private var ideas: [Idea] {
        let qs = (withQuestions?.questions ?? []).compactMap { q -> Idea? in
            guard let main = q.roman ?? q.english else { return nil }
            return Idea(main: main, means: q.roman == nil ? nil : q.english)
        }
        if !qs.isEmpty { return Array(qs.prefix(3)) }
        return Starters.make(snap, rotation: rotation).map { s in
            let word = s.roman ?? s.gloss ?? ""
            return Idea(main: "\(s.before) \(word)\(s.after)", means: s.roman != nil ? s.gloss : nil)
        }
    }

    /// When you last talked, as a nudge to reach out.
    private var nudge: String {
        if snap.calls.live { return "You're on a call with \(who) now" }
        let last = latest?.date.map { $0.timeIntervalSince1970 } ?? snap.calls.last
        guard let last else { return "Give \(who) a call" }
        let days = Int((Date().timeIntervalSince1970 - last) / 86400)
        switch days {
        case 0: return "You talked to \(who) today"
        case 1: return "You talked to \(who) yesterday"
        case 2...3: return "It's been \(days) days · a good time to call \(who)"
        default: return "It's been \(days) days · \(who) would love a call"
        }
    }

    var body: some View {
        let list = ideas
        Panel(padding: 18) {
            HStack(spacing: 7) {
                Circle().fill(Theme.lavender).frame(width: 6, height: 6).shadow(color: Theme.lavender, radius: 4)
                Text("NEXT CALL").font(.system(size: 11, weight: .bold)).tracking(1.2).foregroundStyle(Theme.lavender)
                Spacer()
                Image(systemName: "phone.arrow.up.right").font(.system(size: 13, weight: .semibold)).foregroundStyle(Theme.accent)
            }
            Text(nudge).font(Fonts.ui(14)).foregroundStyle(Theme.text2).padding(.top, 8)

            if list.isEmpty {
                Text("After your first call, ideas for the next one show up here.")
                    .font(Fonts.ui(15)).foregroundStyle(Theme.text2).padding(.top, 14)
            } else {
                let idea = list[page % list.count]
                VStack(alignment: .leading, spacing: 5) {
                    Text(withQuestions == nil ? "Something to talk about" : "Ask \(who)").font(Fonts.ui(12, .semibold)).foregroundStyle(Theme.text3)
                    Text(idea.main).font(Fonts.display(22, .semibold)).foregroundStyle(Theme.text).fixedSize(horizontal: false, vertical: true)
                    if let means = idea.means { Text(means).font(Fonts.ui(14)).foregroundStyle(Theme.text2) }
                }
                .id(page)
                .transition(.asymmetric(insertion: .opacity.combined(with: .offset(x: 16)), removal: .opacity.combined(with: .offset(x: -16))))
                .padding(.top, 14)
                if list.count > 1 {
                    HStack(spacing: 6) {
                        ForEach(0..<list.count, id: \.self) { i in
                            Capsule().fill(i == page % list.count ? Theme.lavender : Theme.border2).frame(width: i == page % list.count ? 16 : 6, height: 6)
                        }
                        Spacer()
                        Text("Next idea").font(Fonts.ui(12, .medium)).foregroundStyle(Theme.accent)
                    }
                    .padding(.top, 14)
                }
            }

            if let p = Starters.trySaying(snap, rotation: rotation), let roman = p.roman {
                Rectangle().fill(Theme.border2).frame(height: 1).padding(.vertical, 14)
                HStack(alignment: .firstTextBaseline, spacing: 8) {
                    Text("Try saying").font(Fonts.ui(12, .semibold)).foregroundStyle(Theme.text3)
                    Text(roman.replacingOccurrences(of: "_", with: " ")).font(Fonts.display(17, .semibold)).foregroundStyle(Theme.accent)
                    if let en = p.english { Text(en).font(Fonts.ui(13)).foregroundStyle(Theme.text2).lineLimit(1) }
                }
            }
        }
        .contentShape(Rectangle())
        .onTapGesture { withAnimation(.spring(response: 0.42, dampingFraction: 0.88)) { page += 1 } }
        .onAppear { page = rotation }
    }
}
