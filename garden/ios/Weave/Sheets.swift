import AVFoundation
import SwiftUI

// MARK: - word explanation

struct WordSheet: View {
    let word: Word
    let line: Conversation.Line?
    let partnerName: String
    let live: Bool
    let add: () -> Void
    let forget: () -> Void
    @EnvironmentObject var people: People
    @Environment(\.dismiss) private var dismiss
    @State private var added = false
    @State private var speaking = false
    @State private var imageShown = false
    private static let synth = AVSpeechSynthesizer()

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 0) {
                if word.image != nil {
                    WordImage(path: word.image)
                        .frame(maxWidth: .infinity).aspectRatio(16 / 10, contentMode: .fit)
                        .scaleEffect(imageShown ? 1 : 1.04).opacity(imageShown ? 1 : 0)
                        .overlay(alignment: .bottomLeading) {
                            Text(word.pictureName ?? "").font(Fonts.mono(11, .regular)).foregroundStyle(.white.opacity(0.65)).padding(12)
                        }
                        .background(Theme.surface)
                        .clipShape(.rect(cornerRadius: Theme.radius))
                        .overlay(RoundedRectangle(cornerRadius: Theme.radius).strokeBorder(Theme.border, lineWidth: 1))
                        .onAppear { withAnimation(.easeOut(duration: 1.0)) { imageShown = true } }
                        .reveal(0)
                }
                HStack(alignment: .bottom) {
                    VStack(alignment: .leading, spacing: 4) {
                        Eyebrow("\(word.categoryLabel)\(word.telugu != nil ? " · Telugu" : "")")
                        Text(word.telugu ?? word.english.capitalized).font(Fonts.telugu(34, .medium)).foregroundStyle(Theme.text).padding(.top, 4)
                        if let roman = word.roman { Text(roman).font(Fonts.serif(18, italic: true)).foregroundStyle(Theme.text2) }
                        if people.voice(for: word.key) != nil {
                            Label("Her voice, from your call", systemImage: "waveform").font(Fonts.ui(12)).foregroundStyle(Theme.accent).padding(.top, 2)
                        }
                    }
                    Spacer()
                    if word.telugu != nil {
                        Button(action: say) {
                            Image(systemName: "speaker.wave.2").font(.system(size: 16, weight: .medium))
                                .foregroundStyle(speaking ? Theme.accent : Theme.text)
                                .frame(width: 46, height: 46)
                                .overlay(Circle().strokeBorder(speaking ? Theme.accent.opacity(0.5) : Theme.border2, lineWidth: 1))
                                .symbolEffect(.variableColor.iterative, isActive: speaking)
                        }
                        .buttonStyle(Pressable())
                    }
                }
                .padding(.top, 20)
                .reveal(1)

                Text(word.english.prefix(1).uppercased() + word.english.dropFirst()).font(Fonts.serif(22)).foregroundStyle(Theme.text)
                    .padding(.top, 16).reveal(2)
                if let d = word.note ?? word.description {
                    Text(d).font(Fonts.ui(14)).foregroundStyle(Theme.text2).padding(.top, 6).reveal(2)
                }

                let example = people.dictionary[word.key]
                if line != nil || example?.example_te != nil {
                    VStack(alignment: .leading, spacing: 6) {
                        Eyebrow("As \(partnerName) said it")
                        Text(line?.original ?? example?.example_te ?? "").font(Fonts.telugu(15)).foregroundStyle(Theme.text2).padding(.top, 4)
                        let en = line?.translation ?? example?.example_en ?? ""
                        if !en.isEmpty { Text(en).font(Fonts.serif(17)).foregroundStyle(Theme.text) }
                    }
                    .padding(16)
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .background(Theme.surface, in: .rect(cornerRadius: Theme.radiusSmall))
                    .overlay(RoundedRectangle(cornerRadius: Theme.radiusSmall).strokeBorder(Theme.border, lineWidth: 1))
                    .padding(.top, 20)
                    .reveal(3)
                }

                HStack(spacing: 12) {
                    if live && word.telugu != nil {
                        Button { forget(); dismiss() } label: {
                            Label("Didn't know it", systemImage: "arrow.uturn.backward").font(Fonts.ui(15, .medium)).foregroundStyle(Theme.text)
                                .frame(maxWidth: .infinity).frame(height: 50)
                                .background(Theme.surface, in: .rect(cornerRadius: 14))
                                .overlay(RoundedRectangle(cornerRadius: 14).strokeBorder(Theme.border2, lineWidth: 1))
                        }
                        .buttonStyle(Pressable())
                    }
                    Button {
                        guard !added else { return }
                        withAnimation(.spring(response: 0.32, dampingFraction: 0.8)) { added = true }
                        add()
                        Task { try? await Task.sleep(for: .milliseconds(650)); dismiss() }
                    } label: {
                        HStack(spacing: 8) {
                            Image(systemName: added ? "checkmark" : "plus").font(.system(size: 14, weight: .semibold)).contentTransition(.symbolEffect(.replace))
                            Text(added ? "In your vocabulary" : "Add to vocabulary").font(Fonts.ui(15, .medium)).contentTransition(.opacity)
                        }
                        .foregroundStyle(added ? Theme.accent : .white)
                        .frame(maxWidth: .infinity).frame(height: 50)
                        .background(added ? Theme.accent.opacity(0.14) : Theme.accent, in: .rect(cornerRadius: 14))
                        .shadow(color: Theme.accent.opacity(added ? 0 : 0.45), radius: 16, y: 8)
                    }
                    .buttonStyle(Pressable())
                    .sensoryFeedback(.success, trigger: added)
                }
                .padding(.top, 20)
                .reveal(4)
            }
            .padding(.horizontal, 20).padding(.top, 24).padding(.bottom, 24)
        }
        .scrollIndicators(.hidden)
        .onAppear { added = people.vocab.contains { $0.key == word.key } }
    }

    /// Her voice if the family dictionary has it; the phone's voice only as a stand-in.
    private func say() {
        if let path = people.voice(for: word.key) {
            VoicePlayer.shared.toggle(path)
            speaking = true
            Task { try? await Task.sleep(for: .seconds(1.6)); speaking = false }
            return
        }
        Self.synth.stopSpeaking(at: .immediate)
        let voice = AVSpeechSynthesisVoice(language: "te-IN")
        let u = AVSpeechUtterance(string: voice != nil ? (word.telugu ?? word.english) : (word.roman ?? word.english))
        u.voice = voice ?? AVSpeechSynthesisVoice(language: "en-IN")
        u.rateMultiplier(0.85)
        Self.synth.speak(u)
        speaking = true
        Task { try? await Task.sleep(for: .seconds(1.6)); speaking = false }
    }
}

private extension AVSpeechUtterance {
    func rateMultiplier(_ m: Float) { rate = AVSpeechUtteranceDefaultSpeechRate * m }
}

struct VocabularyCard: View {
    let item: VocabItem
    var body: some View {
        HStack(spacing: 12) {
            WordImage(path: item.image).frame(width: 40, height: 40).clipShape(.rect(cornerRadius: 10))
            VStack(alignment: .leading, spacing: 1) {
                Text(item.telugu ?? item.english).font(Fonts.telugu(16)).foregroundStyle(Theme.text)
                Text([item.roman, item.english].compactMap { $0 }.joined(separator: " · ")).font(Fonts.ui(13)).foregroundStyle(Theme.text3)
            }
            Spacer(minLength: 0)
        }
        .padding(.vertical, 10)
    }
}

// MARK: - learning

struct GrowthSheet: View {
    let partner: String
    @EnvironmentObject var people: People

    var body: some View {
        let n = people.numbers
        ScrollView {
            VStack(alignment: .leading, spacing: 12) {
                VStack(alignment: .leading, spacing: 6) {
                    Eyebrow("With \(partner) · last 14 days")
                    Text("Your language growth").font(Fonts.ui(24, .medium)).tracking(-0.6).foregroundStyle(Theme.text)
                }
                .reveal(0)
                HStack(spacing: 10) {
                    stat("New words", "+\(n.newWords)")
                    stat("Phrases", "+\(n.phrases)")
                    stat("Known", "\(n.known)")
                }
                .reveal(1)
                Panel {
                    let pct = n.total > 0 ? Double(n.known) / Double(n.total) : 0
                    HStack {
                        Eyebrow("Kept in Telugu for you")
                        Spacer()
                        Text("\(Int(pct * 100))%").font(Fonts.mono(13)).foregroundStyle(Theme.text)
                    }
                    Meter(value: pct).padding(.top, 12)
                    Text("Once you know a word, Weave stops translating it and leaves it in Telugu.")
                        .font(Fonts.ui(13)).foregroundStyle(Theme.text2).padding(.top, 10)
                }
                .reveal(2)
                Panel {
                    Eyebrow("Words heard per day")
                    DayBars(days: n.days).frame(height: 64).padding(.top, 14)
                }
                .reveal(3)
                VStack(alignment: .leading, spacing: 0) {
                    Eyebrow("Your vocabulary · \(people.vocab.count)").padding(.bottom, 4)
                    if people.vocab.isEmpty {
                        Text("Tap a highlighted word during a call to keep it here.").font(Fonts.ui(14)).foregroundStyle(Theme.text2).padding(.vertical, 8)
                    }
                    ForEach(Array(people.vocab.prefix(12).enumerated()), id: \.element.id) { i, v in
                        if i > 0 { Rectangle().fill(Theme.border).frame(height: 1) }
                        VocabularyCard(item: v)
                    }
                }
                .padding(.top, 8)
                .reveal(4)
            }
            .padding(20).padding(.top, 8)
        }
        .scrollIndicators(.hidden)
        .task { await people.loadGrowth() }
    }

    private func stat(_ label: String, _ value: String) -> some View {
        Panel(padding: 14) {
            Eyebrow(label)
            Text(value).font(Fonts.ui(26, .medium)).tracking(-0.8).monospacedDigit().foregroundStyle(Theme.text).padding(.top, 10)
                .contentTransition(.numericText())
        }
    }
}

struct Meter: View {
    let value: Double
    @State private var shown = false
    var body: some View {
        GeometryReader { g in
            ZStack(alignment: .leading) {
                Capsule().fill(Theme.surface3)
                Capsule().fill(Theme.accent).frame(width: g.size.width * (shown ? value : 0))
            }
        }
        .frame(height: 4)
        .onAppear { withAnimation(.spring(response: 0.9, dampingFraction: 0.9).delay(0.2)) { shown = true } }
    }
}

struct DayBars: View {
    let days: [Int]
    @State private var shown = false
    var body: some View {
        let top = max(1, days.max() ?? 1)
        HStack(alignment: .bottom, spacing: 4) {
            ForEach(Array(days.enumerated()), id: \.offset) { i, d in
                UnevenRoundedRectangle(topLeadingRadius: 3, topTrailingRadius: 3)
                    .fill(i == days.count - 1 ? Theme.accent : Theme.accent.opacity(0.35))
                    .frame(maxWidth: .infinity)
                    .frame(height: max(2, CGFloat(d) / CGFloat(top) * 64 * (shown ? 1 : 0)))
                    .animation(.spring(response: 0.6, dampingFraction: 0.85).delay(Double(i) * 0.025), value: shown)
            }
        }
        .frame(maxHeight: .infinity, alignment: .bottom)
        .onAppear { shown = true }
    }
}

// MARK: - end of call

struct SummarySheet: View {
    @ObservedObject var convo: Conversation
    let done: () -> Void
    @Environment(\.dismiss) private var dismiss

    var body: some View {
        let minutes = max(1, Int(Date().timeIntervalSince(convo.started) / 60))
        let lines = convo.lines.filter { $0.who == .them }.count
        let words = Array(convo.seen.values)
        ScrollView {
            VStack(alignment: .leading, spacing: 12) {
                VStack(alignment: .leading, spacing: 6) {
                    Eyebrow("Conversation ended")
                    Text("You and \(convo.partner.name)").font(Fonts.ui(24, .medium)).tracking(-0.6).foregroundStyle(Theme.text)
                }
                .reveal(0)
                HStack(spacing: 10) {
                    cell("Minutes", minutes); cell("Lines", lines); cell("Words", words.count)
                }
                .reveal(1)
                if !words.isEmpty {
                    VStack(alignment: .leading, spacing: 0) {
                        Eyebrow("From this call").padding(.bottom, 4)
                        ForEach(Array(words.prefix(6).enumerated()), id: \.element.key) { i, w in
                            if i > 0 { Rectangle().fill(Theme.border).frame(height: 1) }
                            VocabularyCard(item: VocabItem(key: w.key, telugu: w.telugu, roman: w.roman, english: w.english, image: w.image))
                        }
                    }
                    .padding(.top, 8)
                    .reveal(2)
                }
                HStack(spacing: 12) {
                    Button { dismiss() } label: {
                        Text("Keep talking").font(Fonts.ui(15, .medium)).foregroundStyle(Theme.text).frame(maxWidth: .infinity).frame(height: 50)
                            .background(Theme.surface, in: .rect(cornerRadius: 14))
                            .overlay(RoundedRectangle(cornerRadius: 14).strokeBorder(Theme.border2, lineWidth: 1))
                    }
                    Button(action: done) {
                        Text("Done").font(Fonts.ui(15, .medium)).foregroundStyle(Theme.bg).frame(maxWidth: .infinity).frame(height: 50)
                            .background(Theme.text, in: .rect(cornerRadius: 14))
                    }
                }
                .buttonStyle(Pressable())
                .padding(.top, 12)
                .reveal(3)
            }
            .padding(20).padding(.top, 8)
        }
        .scrollIndicators(.hidden)
    }

    private func cell(_ label: String, _ n: Int) -> some View {
        Panel(padding: 14) {
            Eyebrow(label)
            Text("\(n)").font(Fonts.ui(26, .medium)).tracking(-0.8).monospacedDigit().foregroundStyle(Theme.text).padding(.top, 10)
        }
    }
}

struct SessionMenu: View {
    @ObservedObject var convo: Conversation
    let growth: () -> Void
    @Environment(\.dismiss) private var dismiss

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            Eyebrow("Session")
            Text(convo.partner.name).font(Fonts.ui(24, .medium)).tracking(-0.6).foregroundStyle(Theme.text).padding(.top, 6).padding(.bottom, 10)
            row("book", "Your language growth") { growth() }
            Rectangle().fill(Theme.border).frame(height: 1)
            row(convo.mode == .live ? "dot.radiowaves.left.and.right" : "play.circle",
                convo.mode == .live ? "Connected to the live call" : "Playing a demo call · start subtitles.py for live") { dismiss() }
        }
        .padding(20).padding(.top, 8)
        .frame(maxWidth: .infinity, alignment: .leading)
    }

    private func row(_ symbol: String, _ title: String, action: @escaping () -> Void) -> some View {
        Button(action: action) {
            HStack(spacing: 12) {
                Image(systemName: symbol).font(.system(size: 15)).frame(width: 22)
                Text(title).font(Fonts.ui(15))
                Spacer()
            }
            .foregroundStyle(Theme.text2)
            .padding(.vertical, 14)
            .contentShape(Rectangle())
        }
        .buttonStyle(Pressable())
    }
}
