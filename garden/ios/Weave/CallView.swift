import SwiftUI

/// "For your next call": a question the story keeper wrote from her stories.
struct AskCard: View {
    let q: Question
    var label = "Ask"
    var body: some View {
        VStack(alignment: .leading, spacing: 4) {
            Eyebrow(label, color: Theme.warm)
            if let te = q.telugu { Text(te).font(Fonts.telugu(19, .medium)).foregroundStyle(Theme.text).padding(.top, 2) }
            if let r = q.roman { Text(r).font(Fonts.serif(16, italic: true)).foregroundStyle(Theme.text) }
            if let en = q.english { Text(en).font(Fonts.ui(13)).foregroundStyle(Theme.text2) }
        }
        .padding(.horizontal, 14).padding(.vertical, 12)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(LinearGradient(colors: [Theme.warm.opacity(0.14), Theme.surface.opacity(0.9)], startPoint: .top, endPoint: .bottom), in: .rect(cornerRadius: Theme.radius))
        .overlay(RoundedRectangle(cornerRadius: Theme.radius).strokeBorder(Theme.warm.opacity(0.45), lineWidth: 1))
    }
}

struct CallRow: View {
    let call: CallSummary
    var body: some View {
        HStack(spacing: 14) {
            if let pic = call.pictures?.first {
                WordImage(path: pic).frame(width: 44, height: 44).clipShape(.rect(cornerRadius: 10))
            } else {
                Avatar(text: Connection(id: "", name: call.caller, lang: "te", last: .now).monogram, size: 44)
            }
            VStack(alignment: .leading, spacing: 3) {
                Text(call.title).font(Fonts.ui(15, .medium)).foregroundStyle(Theme.text).lineLimit(1)
                Text([call.caller, "\(call.lines ?? 0) lines", (call.new_words ?? 0) > 0 ? "\(call.new_words!) new words" : nil].compactMap { $0 }.joined(separator: " · "))
                    .font(Fonts.ui(13)).foregroundStyle(Theme.text2).lineLimit(1)
            }
            Spacer(minLength: 8)
            VStack(alignment: .trailing, spacing: 3) {
                Text(call.whenLabel).font(Fonts.mono(11, .regular)).foregroundStyle(Theme.text3)
                Text("\(call.minutes)m").font(Fonts.mono(11, .regular)).foregroundStyle(Theme.text3)
            }
        }
        .padding(.horizontal, 16).padding(.vertical, 12)
        .contentShape(Rectangle())
    }
}

/// A saved call: its story, her voice on every line, the pictures and words.
struct CallView: View {
    let summary: CallSummary
    @State private var detail: CallDetail?
    @State private var failed = false
    @ObservedObject private var voice = VoicePlayer.shared

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 0) {
                Eyebrow("\(summary.caller) · \(summary.whenLabel) · \(summary.minutes) min").padding(.top, 8).reveal(0)
                Text(detail?.story?.title ?? summary.title).font(Fonts.ui(26, .medium)).tracking(-0.8).foregroundStyle(Theme.lavender)
                    .padding(.top, 8).reveal(0)
                if let s = detail?.story?.summary ?? summary.summary, !s.isEmpty {
                    Text(s).font(Fonts.serif(18)).foregroundStyle(Theme.text).lineSpacing(3).padding(.top, 10).reveal(1)
                }
                if summary.has_audio == true {
                    let path = "calls/\(summary.id)/call.m4a"
                    Button { voice.toggle(path) } label: {
                        HStack(spacing: 10) {
                            Image(systemName: voice.playing == path ? "stop.fill" : "play.fill").font(.system(size: 13, weight: .semibold))
                            Text(voice.playing == path ? "Playing her side of the call" : "Her side of the call · \(summary.minutes) min").font(Fonts.ui(15, .medium))
                        }
                        .foregroundStyle(voice.playing == path ? Theme.accent : Theme.text)
                        .frame(maxWidth: .infinity).frame(height: 48)
                        .background(Theme.surface, in: .rect(cornerRadius: 14))
                        .overlay(RoundedRectangle(cornerRadius: 14).strokeBorder(voice.playing == path ? Theme.accent.opacity(0.5) : Theme.border2, lineWidth: 1))
                    }
                    .buttonStyle(Pressable())
                    .padding(.top, 16)
                    .reveal(2)
                }

                if let told = detail?.story?.stories, !told.isEmpty {
                    Eyebrow("Stories she told").padding(.top, 28).padding(.bottom, 6)
                    ForEach(Array(told.enumerated()), id: \.offset) { _, t in
                        VStack(alignment: .leading, spacing: 2) {
                            Text(t.title ?? "").font(Fonts.ui(15, .medium)).foregroundStyle(Theme.text)
                            if let s = t.summary { Text(s).font(Fonts.ui(14)).foregroundStyle(Theme.text2) }
                        }
                        .padding(.vertical, 10)
                        .frame(maxWidth: .infinity, alignment: .leading)
                        .overlay(alignment: .top) { Rectangle().fill(Theme.border).frame(height: 1) }
                    }
                }

                if let qs = detail?.story?.questions ?? summary.questions, !qs.isEmpty {
                    Eyebrow("Ask next time").padding(.top, 28).padding(.bottom, 10)
                    VStack(spacing: 8) { ForEach(Array(qs.enumerated()), id: \.offset) { _, q in AskCard(q: q) } }
                }

                if let lines = detail?.lines, !lines.isEmpty {
                    Eyebrow("The call · \(lines.count) lines").padding(.top, 28).padding(.bottom, 4)
                    ForEach(lines) { l in
                        HStack(alignment: .top, spacing: 12) {
                            if let clip = l.clip { VoiceButton(path: "calls/\(summary.id)/\(clip)") } else { Color.clear.frame(width: 34, height: 34) }
                            VStack(alignment: .leading, spacing: 3) {
                                if l.route == "english" {
                                    Text(l.telugu ?? "").font(Fonts.serif(18)).foregroundStyle(Theme.text)
                                } else {
                                    Text(l.telugu ?? "").font(Fonts.telugu(16)).foregroundStyle(Theme.text2)
                                    Text(l.english ?? "").font(Fonts.serif(18)).foregroundStyle(Theme.text)
                                }
                                if let p = l.picture, let img = p.image {
                                    HStack(spacing: 8) {
                                        WordImage(path: img).frame(width: 36, height: 36).clipShape(.rect(cornerRadius: 8))
                                        Text(p.name ?? "").font(Fonts.ui(13)).foregroundStyle(Theme.text2)
                                    }
                                    .padding(.top, 6)
                                }
                            }
                            Spacer(minLength: 4)
                            Text(String((l.time ?? "").prefix(5))).font(Fonts.mono(11, .regular)).foregroundStyle(Theme.text3)
                        }
                        .padding(.vertical, 12)
                        .overlay(alignment: .top) { Rectangle().fill(Theme.border).frame(height: 1) }
                    }
                } else if failed {
                    Text("This call's details aren't on the Mac any more.").font(Fonts.ui(14)).foregroundStyle(Theme.text2).padding(.top, 24)
                } else {
                    SwiftUI.ProgressView().tint(Theme.text2).frame(maxWidth: .infinity).padding(.top, 40)
                }

                if let words = detail?.words, !words.isEmpty {
                    Eyebrow("Words from this call · \(words.count)").padding(.top, 28).padding(.bottom, 4)
                    ForEach(words.prefix(12), id: \.id) { w in
                        VocabularyCard(item: VocabItem(key: w.id, telugu: w.telugu, roman: w.roman,
                                                       english: (w.english ?? "") + (w.status == "new" ? " · new" : ""), image: Knowledge.word(w.id).image))
                    }
                }
            }
            .padding(20)
        }
        .scrollIndicators(.hidden)
        .task {
            detail = await GardenClient.call(summary.id)
            failed = detail == nil
        }
        .onDisappear { voice.stop() }
    }
}

// MARK: - Message tab

/// After a call, a short loving WhatsApp message in Telugu for her, written by the story keeper (calls.py
/// "message_te"). The newest call's message comes first, with Copy and Share (WhatsApp is in the share sheet);
/// earlier calls' messages are below. The call's English title and summary say what it's about.
struct MessageView: View {
    @EnvironmentObject var people: People
    @State private var copied: String?

    private var withMessage: [CallSummary] { people.calls.filter { !($0.message_te ?? "").isEmpty } }

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 14) {
                VStack(alignment: .leading, spacing: 6) {
                    Text("Message").font(Fonts.display(34, .semibold)).tracking(-0.8).foregroundStyle(Theme.lavender)
                    Text("After each call, a note in Telugu to send \(withMessage.first?.caller ?? people.partner.name), so she keeps the call too.")
                        .font(Fonts.ui(15)).foregroundStyle(Theme.text2)
                }
                .padding(.top, 16)
                .reveal(0)

                if withMessage.isEmpty {
                    Panel {
                        Text(people.source == .offline ? "Start Roots on your Mac to see your messages."
                             : "After your next call, a message to send her shows up here.")
                            .font(Fonts.ui(15)).foregroundStyle(Theme.text2)
                    }
                    .reveal(1)
                } else {
                    ForEach(Array(withMessage.enumerated()), id: \.element.id) { i, call in
                        card(call, latest: i == 0).reveal(min(i + 1, 4))
                    }
                }
            }
            .padding(.horizontal, 20)
            .padding(.bottom, 32)
        }
        .scrollIndicators(.hidden)
        .refreshable { await people.loadGrowth() }
        .background(Backdrop())
    }

    private func card(_ call: CallSummary, latest: Bool) -> some View {
        let text = call.message_te ?? ""
        return Panel(padding: 18) {
            HStack {
                Eyebrow(latest ? "From your last call · \(call.whenLabel)" : call.whenLabel, color: latest ? Theme.lavender : Theme.text3)
                Spacer()
            }
            Text(call.title).font(Fonts.ui(15, .medium)).foregroundStyle(Theme.text).padding(.top, 6)
            Text(text).font(Fonts.telugu(latest ? 19 : 16)).foregroundStyle(Theme.text)
                .textSelection(.enabled).fixedSize(horizontal: false, vertical: true).padding(.top, 10)
            if let en = call.message_en, !en.isEmpty {
                Text(en).font(Fonts.ui(14)).foregroundStyle(Theme.text2).fixedSize(horizontal: false, vertical: true).padding(.top, 6)
            }
            HStack(spacing: 10) {
                Button {
                    UIPasteboard.general.string = text
                    withAnimation(.easeOut(duration: 0.2)) { copied = call.id }
                    Task { try? await Task.sleep(for: .seconds(2)); if copied == call.id { copied = nil } }
                } label: {
                    Label(copied == call.id ? "Copied" : "Copy", systemImage: copied == call.id ? "checkmark" : "doc.on.doc")
                        .font(Fonts.ui(14, .medium)).foregroundStyle(Theme.onAccent)
                        .frame(maxWidth: .infinity).frame(height: 44)
                        .background(Theme.accent, in: .rect(cornerRadius: 12))
                }
                .buttonStyle(Pressable())
                .sensoryFeedback(.success, trigger: copied == call.id)
                ShareLink(item: text) {
                    Label("Send", systemImage: "square.and.arrow.up")
                        .font(Fonts.ui(14, .medium)).foregroundStyle(Theme.text)
                        .frame(maxWidth: .infinity).frame(height: 44)
                        .background(Theme.surface2, in: .rect(cornerRadius: 12))
                        .overlay(RoundedRectangle(cornerRadius: 12).strokeBorder(Theme.border2, lineWidth: 1))
                }
            }
            .padding(.top, 14)
        }
    }
}
