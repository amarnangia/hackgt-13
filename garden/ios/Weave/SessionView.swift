import SwiftUI

struct SessionView: View {
    @EnvironmentObject var people: People
    @StateObject var convo: Conversation
    @Environment(\.dismiss) private var dismiss
    @State private var openWord: WordContext?
    @State private var sheet: SessionSheet?
    @State private var voiceOn = true
    var forceDemo = false

    enum SessionSheet: String, Identifiable { case growth, summary, menu; var id: String { rawValue } }
    struct WordContext: Identifiable { let word: Word; let line: Conversation.Line?; var id: String { word.key } }

    var body: some View {
        VStack(spacing: 0) {
            ConnectionHeader(convo: convo, close: { dismiss() }, menu: { sheet = .menu })
                .padding(.horizontal, 20)
            ConnectionVisualizer(you: people.profileName ?? "You", youLang: people.myLang, partner: convo.partner,
                                 speaking: convo.speaking, translating: convo.translating > 0, connected: convo.connected)
                .padding(.horizontal, 20)
                .padding(.top, 8)
            Text(nowLine).font(Fonts.ui(13)).foregroundStyle(convo.speaking.isEmpty ? Theme.text3 : Theme.text2)
                .contentTransition(.opacity).animation(.easeOut(duration: 0.25), value: nowLine)
                .padding(.top, 2).padding(.bottom, 8)
            LiveTranscript(convo: convo) { word, line in openWord = WordContext(word: word, line: line) }
            if let ask = convo.ask {
                AskCard(q: ask.q, label: ask.label)
                    .padding(.horizontal, 20).padding(.bottom, 10)
                    .transition(.move(edge: .bottom).combined(with: .opacity))
            }
            SessionControls(mode: convo.mode, voiceOn: $voiceOn, saved: convo.savedThisCall, talk: convo.holdToTalk,
                            growth: { sheet = .growth }, end: { sheet = .summary })
                .padding(.horizontal, 20)
        }
        .background(Backdrop())
        .onAppear { convo.start(forceDemo: forceDemo || GardenClient.demoMode) }
        .onDisappear { convo.stop() }
        .sheet(item: $openWord) { ctx in
            WordSheet(word: ctx.word, line: ctx.line, partnerName: convo.partner.name, live: convo.mode == .live) {
                people.save(ctx.word)
                withAnimation(.spring(response: 0.35, dampingFraction: 0.6)) { convo.savedThisCall += 1 }
            } forget: { convo.forget(ctx.word.key) }
            .presentationDetents([.large])
            .presentationBackground(Theme.bg2)
            .presentationCornerRadius(24)
        }
        .sheet(item: $sheet) { s in
            Group {
                switch s {
                case .growth: GrowthSheet(partner: convo.partner.name)
                case .summary: SummarySheet(convo: convo) { sheet = nil; Task { try? await Task.sleep(for: .milliseconds(350)); dismiss() } }
                case .menu: SessionMenu(convo: convo) { sheet = .growth }
                }
            }
            .presentationDetents(s == .menu ? [.height(260)] : [.medium, .large])
            .presentationBackground(Theme.bg2)
            .presentationCornerRadius(24)
        }
        .preferredColorScheme(.dark)
        .task {
            if let key = UserDefaults.standard.string(forKey: "openWord") {   // screenshots: -openWord pulihora
                while !Task.isCancelled {
                    try? await Task.sleep(for: .milliseconds(400))
                    if let w = convo.seen[key] { openWord = WordContext(word: w, line: convo.lines.last { l in l.matches.contains { $0.key == key } }); break }
                }
            }
        }
    }

    private var nowLine: String {
        if convo.speaking.contains(.them) && convo.speaking.contains(.you) { return "Both speaking" }
        if convo.speaking.contains(.them) { return "\(convo.partner.name) is speaking" }
        if convo.speaking.contains(.you) { return "You're speaking" }
        if convo.mode == .waiting { return "Waiting for the call" }
        return "Listening"
    }
}

/// Quiet top light so the black has depth.
struct Backdrop: View {
    var body: some View {
        ZStack {
            Theme.bg
            RadialGradient(colors: [Theme.accent.opacity(0.11), .clear], center: .top, startRadius: 0, endRadius: 520).offset(y: -140)
            RadialGradient(colors: [Theme.lavender.opacity(0.13), Theme.lavenderDeep.opacity(0.05), .clear], center: .topTrailing, startRadius: 0, endRadius: 420)
            RadialGradient(colors: [Theme.lavender.opacity(0.10), Theme.lavenderDeep.opacity(0.04), .clear], center: .bottomLeading, startRadius: 0, endRadius: 560)
            RadialGradient(colors: [Theme.cyan.opacity(0.05), .clear], center: UnitPoint(x: 1.1, y: 0.45), startRadius: 0, endRadius: 380)
            Grain().opacity(0.5)
        }
        .ignoresSafeArea()
    }
}

/// Fine film grain, so the dark isn't flat. Drawn once, not animated.
struct Grain: View {
    var body: some View {
        Canvas { ctx, size in
            var s: UInt64 = 0x9E37_79B9
            func r() -> CGFloat { s = s &* 6364136223846793005 &+ 1442695040888963407; return CGFloat(s >> 33) / CGFloat(1 << 31) }
            for _ in 0..<Int(size.width * size.height / 90) {
                let x = r() * size.width, y = r() * size.height, a = r()
                ctx.fill(Path(CGRect(x: x, y: y, width: 1, height: 1)), with: .color(.white.opacity(0.02 + 0.05 * a)))
            }
        }
        .allowsHitTesting(false)
    }
}

// MARK: - header

struct ConnectionHeader: View {
    @ObservedObject var convo: Conversation
    let close: () -> Void
    let menu: () -> Void

    var body: some View {
        HStack(spacing: 12) {
            IconButton(symbol: "chevron.down", action: close)
            HStack(spacing: 8) {
                Circle().fill(convo.connected ? Theme.green : Theme.text3).frame(width: 6, height: 6)
                    .overlay(Circle().stroke(Theme.green.opacity(convo.connected ? 0.25 : 0), lineWidth: 3))
                Text(convo.mode == .waiting ? "Waiting" : "Connected").font(Fonts.ui(14, .medium)).foregroundStyle(Theme.text)
                    .contentTransition(.opacity)
                TimelineView(.periodic(from: .now, by: 1)) { t in
                    let s = Int(t.date.timeIntervalSince(convo.started))
                    Text("\(s / 60):\(String(format: "%02d", s % 60))").font(Fonts.mono(13, .regular)).foregroundStyle(Theme.text3)
                }
            }
            .animation(.easeOut(duration: 0.3), value: convo.connected)
            Spacer()
            Text(convo.mode == .live ? "LIVE" : convo.mode == .demo ? "DEMO" : "WAITING").font(Fonts.mono(10.5)).tracking(0.8)
                .foregroundStyle(convo.mode == .live ? Theme.accent : Theme.text3)
                .padding(.horizontal, 9).frame(height: 24)
                .overlay(Capsule().strokeBorder(convo.mode == .live ? Theme.accent.opacity(0.35) : Theme.border, lineWidth: 1))
            IconButton(symbol: "ellipsis", action: menu)
        }
        .frame(height: 56)
    }
}

struct IconButton: View {
    let symbol: String
    var size: CGFloat = 36
    let action: () -> Void
    var body: some View {
        Button(action: action) {
            Image(systemName: symbol).font(.system(size: 14, weight: .semibold)).foregroundStyle(Theme.text2)
                .frame(width: size, height: size)
                .background(Theme.surface, in: .rect(cornerRadius: 11))
                .overlay(RoundedRectangle(cornerRadius: 11).strokeBorder(Theme.border, lineWidth: 1))
        }
        .buttonStyle(Pressable())
    }
}

// MARK: - the connection

struct ConnectionVisualizer: View {
    let you: String
    let youLang: String
    let partner: Connection
    let speaking: Set<Conversation.Who>
    let translating: Bool
    let connected: Bool

    var body: some View {
        HStack(alignment: .top, spacing: 12) {
            Participant(monogram: String(you.prefix(1)).uppercased(), name: "You", lang: youLang, speaking: speaking.contains(.you))
                .offset(x: connected ? 0 : 36).opacity(connected ? 1 : 0.5)
            Wire(speaking: speaking, translating: translating, connected: connected)
                .frame(height: 56)
            Participant(monogram: partner.monogram, name: partner.name, lang: partner.lang, speaking: speaking.contains(.them))
                .offset(x: connected ? 0 : -36).opacity(connected ? 1 : 0.5)
        }
        .animation(.spring(response: 0.55, dampingFraction: 0.85), value: connected)
    }
}

struct Participant: View {
    let monogram: String
    let name: String
    let lang: String
    let speaking: Bool

    var body: some View {
        VStack(spacing: 10) {
            ZStack {
                if speaking {
                    TimelineView(.animation) { t in
                        let p = t.date.timeIntervalSinceReferenceDate.truncatingRemainder(dividingBy: 1.6) / 1.6
                        Circle().strokeBorder(Theme.accent.opacity(0.6 * (1 - p)), lineWidth: 1)
                            .scaleEffect(1 + p * 0.55)
                    }
                    .frame(width: 56, height: 56)
                }
                Avatar(text: monogram, size: 56)
                    .overlay(Circle().strokeBorder(Theme.accent.opacity(speaking ? 0.7 : 0), lineWidth: 1))
                    .shadow(color: Theme.accent.opacity(speaking ? 0.5 : 0), radius: 16)
            }
            VoiceBars(active: speaking).frame(height: 16)
            VStack(spacing: 3) {
                Text(name.uppercased()).font(Fonts.mono(11)).tracking(0.9).foregroundStyle(Theme.text)
                Text(Language.name(lang)).font(Fonts.ui(12)).foregroundStyle(Theme.text3)
            }
        }
        .frame(width: 92)
        .animation(.easeOut(duration: 0.3), value: speaking)
    }
}

/// A breathing waveform while someone talks.
struct VoiceBars: View {
    let active: Bool
    var body: some View {
        TimelineView(.animation(minimumInterval: 1 / 30, paused: !active)) { t in
            let s = t.date.timeIntervalSinceReferenceDate
            HStack(spacing: 3) {
                ForEach(0..<7, id: \.self) { i in
                    Capsule().fill(Theme.accent).frame(width: 3, height: active ? 4 + 12 * Self.level(i, at: s) : 4)
                }
            }
        }
        .opacity(active ? 1 : 0)
    }

    static func level(_ i: Int, at s: Double) -> CGFloat {
        let bar = Double(i)
        let wave: Double = abs(sin(s / (0.14 + bar * 0.023) + bar * 1.7))
        let envelope: Double = 0.6 + 0.4 * sin(s / 0.42)
        return CGFloat(0.25 + 0.75 * wave * envelope)
    }
}

/// The thin line between the two people. Pulses travel toward whoever is listening; it shimmers while translating.
struct Wire: View {
    let speaking: Set<Conversation.Who>
    let translating: Bool
    let connected: Bool

    var body: some View {
        TimelineView(.animation(minimumInterval: 1 / 60, paused: !connected)) { tl in
            Canvas { ctx, size in
                Wire.draw(ctx, size: size, t: tl.date.timeIntervalSinceReferenceDate, speaking: speaking, translating: translating, connected: connected)
            }
        }
        .overlay(alignment: .center) {
            Text(!connected ? "CONNECTING" : translating ? "TRANSLATING" : "CONNECTED")
                .font(Fonts.mono(10.5)).tracking(0.7)
                .foregroundStyle(translating ? Theme.accent : Theme.text3)
                .offset(y: 16)
                .contentTransition(.opacity)
                .animation(.easeOut(duration: 0.25), value: translating)
        }
        .scaleEffect(x: connected ? 1 : 0.001, anchor: .center)
        .animation(.spring(response: 0.55, dampingFraction: 0.9), value: connected)
    }
}

extension Wire {
    static func draw(_ ctx: GraphicsContext, size: CGSize, t: Double, speaking: Set<Conversation.Who>, translating: Bool, connected: Bool) {
        let y: CGFloat = size.height / 2
        let w: CGFloat = size.width
        let both = speaking.count == 2
        var line = Path()
        line.move(to: CGPoint(x: 0, y: y))
        line.addLine(to: CGPoint(x: w, y: y))

        let base: Double = connected ? (speaking.isEmpty ? 0.28 : (both ? 0.6 : 0.4)) : 0.12
        let stops: [Gradient.Stop] = [
            .init(color: .clear, location: 0), .init(color: Theme.accent.opacity(base), location: 0.12),
            .init(color: Theme.accent.opacity(base), location: 0.88), .init(color: .clear, location: 1),
        ]
        let baseShading = GraphicsContext.Shading.linearGradient(Gradient(stops: stops), startPoint: .zero, endPoint: CGPoint(x: w, y: 0))
        ctx.stroke(line, with: baseShading, lineWidth: both ? 1.5 : 1)

        if translating {
            let p: Double = (t / 1.1).truncatingRemainder(dividingBy: 1) * 1.4 - 0.2
            let x: CGFloat = w * CGFloat(p)
            let shimmer = Gradient(colors: [.clear, Theme.accent.opacity(0.95), .clear])
            ctx.stroke(line, with: .linearGradient(shimmer, startPoint: CGPoint(x: x - w * 0.2, y: 0), endPoint: CGPoint(x: x + w * 0.2, y: 0)), lineWidth: 1.5)
        }

        for who in speaking {
            for k in 0..<2 {
                let p: Double = ((t / 1.1) + Double(k) * 0.5).truncatingRemainder(dividingBy: 1)
                let frac: CGFloat = who == .you ? CGFloat(0.04 + 0.92 * p) : CGFloat(0.96 - 0.92 * p)
                let x: CGFloat = w * frac
                let alpha: Double = min(1, min(p, 1 - p) * 6)
                let seg = CGRect(x: x - 18, y: y - 1.5, width: 36, height: 3)
                let glow = Gradient(colors: [.clear, Theme.accent.opacity(alpha), .clear])
                ctx.fill(Path(roundedRect: seg, cornerRadius: 1.5),
                         with: .linearGradient(glow, startPoint: CGPoint(x: seg.minX, y: 0), endPoint: CGPoint(x: seg.maxX, y: 0)))
            }
        }
    }
}

// MARK: - transcript

struct LiveTranscript: View {
    @ObservedObject var convo: Conversation
    let open: (Word, Conversation.Line) -> Void

    var body: some View {
        ScrollViewReader { proxy in
            ScrollView {
                LazyVStack(alignment: .leading, spacing: 0) {
                    if convo.lines.isEmpty {
                        Text(convo.mode == .waiting
                             ? "Waiting for the call.\nStart subtitles.py and call \(convo.partner.name) on WhatsApp Web. This connects by itself."
                             : "When \(convo.partner.name) speaks, it appears here in English.")
                            .font(Fonts.ui(14)).foregroundStyle(Theme.text3).multilineTextAlignment(.center)
                            .frame(maxWidth: .infinity).padding(.top, 60)
                    }
                    ForEach(Array(convo.lines.enumerated()), id: \.element.id) { i, line in
                        TranslationMessage(line: line, partner: convo.partner.name, first: i == 0, open: open)
                            .id(line.id)
                            .transition(.asymmetric(insertion: .opacity.combined(with: .offset(y: 8)), removal: .opacity))
                    }
                    Color.clear.frame(height: 12).id("bottom")
                }
                .padding(.horizontal, 20)
            }
            .scrollIndicators(.hidden)
            .mask(LinearGradient(stops: [.init(color: .clear, location: 0), .init(color: .black, location: 0.05), .init(color: .black, location: 1)], startPoint: .top, endPoint: .bottom))
            .onChange(of: convo.lines.last?.translation) { withAnimation(.easeOut(duration: 0.2)) { proxy.scrollTo("bottom", anchor: .bottom) } }
            .onChange(of: convo.lines.last?.original) { withAnimation(.easeOut(duration: 0.2)) { proxy.scrollTo("bottom", anchor: .bottom) } }
            .onChange(of: convo.lines.last?.visual) { withAnimation(.easeOut(duration: 0.3)) { proxy.scrollTo("bottom", anchor: .bottom) } }
        }
    }
}

struct TranslationMessage: View {
    let line: Conversation.Line
    let partner: String
    let first: Bool
    let open: (Word, Conversation.Line) -> Void

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            if !first { Rectangle().fill(Theme.border).frame(height: 1).padding(.bottom, 18) }
            HStack(spacing: 8) {
                Text(line.who == .you ? "YOU" : partner.uppercased()).font(Fonts.mono(11)).tracking(0.9)
                    .foregroundStyle(line.who == .them ? Theme.accent : Theme.text)
                if let tag = line.tag {
                    Text(tag.uppercased()).font(.system(size: 10, weight: .heavy)).tracking(0.6).foregroundStyle(Color(hex: 0x06121a))
                        .padding(.horizontal, 6).padding(.vertical, 3).background(Theme.cyan, in: .rect(cornerRadius: 6))
                }
                Text("·").foregroundStyle(Theme.text3)
                Text(Language.name(line.lang)).font(Fonts.mono(11, .regular)).foregroundStyle(Theme.text3)
                if line.voiced { Image(systemName: "speaker.wave.2").font(.system(size: 10)).foregroundStyle(Theme.text3) }
                Spacer()
                Text(line.time.formatted(date: .omitted, time: .shortened)).font(Fonts.mono(11, .regular)).foregroundStyle(Theme.text3)
            }
            .padding(.bottom, 10)

            if line.who == .you || line.lang == "en" {
                caretText(Text(line.original), show: line.typing && line.translation.isEmpty)
                    .font(Fonts.serif(20)).foregroundStyle(Theme.text)
            } else {
                caretText(Text(styled(line.original, telugu: true)), show: line.typing && line.translation.isEmpty && !line.pending)
                    .font(Fonts.telugu(17)).foregroundStyle(Theme.text2).lineSpacing(3)
                if line.pending {
                    Translating().padding(.top, 10)
                } else if !line.translation.isEmpty {
                    caretText(Text(styled(line.translation, telugu: false)), show: line.typing)
                        .font(Fonts.serif(22)).foregroundStyle(Theme.text).lineSpacing(2)
                        .padding(.top, 6)
                }
            }
            if let note = line.note {
                (Text("Context").fontWeight(.medium).foregroundColor(Theme.text2) + Text(" · \(note)"))
                    .font(Fonts.ui(13)).foregroundStyle(Theme.text3).padding(.top, 8)
                    .transition(.opacity)
            }
            if let key = line.visual {
                let w = Knowledge.word(key)
                Button { open(w, line) } label: {
                    HStack(spacing: 12) {
                        WordImage(path: w.image).frame(width: 44, height: 44).clipShape(.rect(cornerRadius: 8))
                        VStack(alignment: .leading, spacing: 1) {
                            Text(w.pictureName ?? w.english).font(Fonts.ui(14, .medium)).foregroundStyle(Theme.text)
                            Text("Tap to see what this is").font(Fonts.ui(12)).foregroundStyle(Theme.text3)
                        }
                    }
                    .padding(6).padding(.trailing, 8)
                    .background(Theme.surface, in: .rect(cornerRadius: 12))
                    .overlay(RoundedRectangle(cornerRadius: 12).strokeBorder(Theme.border, lineWidth: 1))
                }
                .buttonStyle(Pressable())
                .padding(.top, 12)
                .transition(.opacity.combined(with: .offset(y: 6)))
            }
        }
        .padding(.vertical, first ? 4 : 0)
        .padding(.bottom, 18)
        .frame(maxWidth: .infinity, alignment: .leading)
        .environment(\.openURL, OpenURLAction { url in
            guard url.scheme == "weave-word", let key = url.host(percentEncoded: false) ?? url.host else { return .discarded }
            open(Knowledge.word(key), line)
            return .handled
        })
    }

    private func caretText(_ text: Text, show: Bool) -> some View {
        (text + Text(show ? " ▍" : "").foregroundColor(Theme.accent))
    }

    /// Mark tappable words: a soft accent underline, opening the word sheet.
    private func styled(_ s: String, telugu: Bool) -> AttributedString {
        var a = AttributedString(s)
        for m in line.matches {
            let w = Knowledge.word(m.key)
            let candidates = telugu ? [w.telugu, m.text].compactMap { $0 } : [m.text, w.roman, w.english].compactMap { $0 }
            for c in candidates where !c.isEmpty {
                if let r = a.range(of: c, options: .caseInsensitive) {
                    if a[r].link != nil { break }
                    a[r].link = URL(string: "weave-word://\(m.key)")
                    a[r].underlineStyle = Text.LineStyle(pattern: .solid, color: Theme.accent.opacity(0.55))
                    a[r].foregroundColor = Theme.text
                    break
                }
            }
        }
        return a
    }
}

struct Translating: View {
    var body: some View {
        HStack(spacing: 8) {
            TimelineView(.animation) { t in
                let p = (t.date.timeIntervalSinceReferenceDate / 0.9).truncatingRemainder(dividingBy: 1)
                Capsule().fill(LinearGradient(colors: [.clear, Theme.accent, .clear], startPoint: .leading, endPoint: .trailing))
                    .frame(width: 14, height: 1.5).offset(x: -6 + p * 18).frame(width: 26, alignment: .leading).clipped()
            }
            Text("TRANSLATING").font(Fonts.mono(11)).tracking(0.9).foregroundStyle(Theme.accent)
        }
        .frame(height: 30)
    }
}

// MARK: - controls

struct SessionControls: View {
    let mode: Conversation.Mode
    @Binding var voiceOn: Bool
    let saved: Int
    let talk: (Bool) -> Void
    let growth: () -> Void
    let end: () -> Void
    @State private var holding = false

    var body: some View {
        HStack(spacing: 10) {
            if mode != .demo {
                // A real call: nothing to press, the captions come from the call itself.
                HStack(spacing: 10) {
                    Circle().fill(mode == .live ? Theme.green : Theme.text3).frame(width: 7, height: 7)
                    Text(mode == .live ? "Captions from the call" : "Waiting for subtitles.py").font(Fonts.ui(15, .medium))
                }
                .foregroundStyle(mode == .live ? Theme.text : Theme.text3)
                .frame(maxWidth: .infinity).frame(height: 52)
                .background(mode == .live ? Theme.accent.opacity(0.08) : Theme.surface, in: .rect(cornerRadius: 16))
                .overlay(RoundedRectangle(cornerRadius: 16).strokeBorder(mode == .live ? Theme.accent.opacity(0.3) : Theme.border, lineWidth: 1))
            } else {
            HStack(spacing: 10) {
                Image(systemName: "mic").font(.system(size: 15, weight: .medium))
                Text(holding ? "Listening to you…" : "Hold to talk").font(Fonts.ui(15, .medium)).contentTransition(.opacity)
            }
            .foregroundStyle(holding ? Theme.onAccent : Theme.text)
            .frame(maxWidth: .infinity).frame(height: 52)
            .background(holding ? Theme.accent : Theme.surface, in: .rect(cornerRadius: 16))
            .overlay(RoundedRectangle(cornerRadius: 16).strokeBorder(holding ? Theme.accent : Theme.border2, lineWidth: 1))
            .shadow(color: Theme.accent.opacity(holding ? 0.45 : 0), radius: 18, y: 8)
            .scaleEffect(holding ? 0.985 : 1)
            .gesture(DragGesture(minimumDistance: 0)
                .onChanged { _ in if !holding { holding = true; talk(true); UIImpactFeedbackGenerator(style: .soft).impactOccurred() } }
                .onEnded { _ in holding = false; talk(false) })
            .animation(.easeOut(duration: 0.2), value: holding)
            }
            DockButton(symbol: "book", selected: false, action: growth)
                .overlay(alignment: .topTrailing) {
                    Text("\(saved)").font(.system(size: 10, weight: .semibold)).foregroundStyle(Theme.onAccent)
                        .padding(.horizontal, 5).frame(minWidth: 18, minHeight: 18).background(Theme.accent, in: .capsule)
                        .offset(x: 5, y: -5).scaleEffect(saved > 0 ? 1 : 0.01)
                        .animation(.spring(response: 0.35, dampingFraction: 0.55), value: saved)
                }
            Button(action: end) {
                Text("End").font(Fonts.ui(15, .medium)).foregroundStyle(Theme.danger)
                    .padding(.horizontal, 18).frame(height: 52)
                    .background(Theme.danger.opacity(0.1), in: .rect(cornerRadius: 16))
                    .overlay(RoundedRectangle(cornerRadius: 16).strokeBorder(Theme.danger.opacity(0.2), lineWidth: 1))
            }
            .buttonStyle(Pressable())
        }
        .padding(.top, 10)
        .padding(.bottom, 6)
    }
}

struct DockButton: View {
    let symbol: String
    let selected: Bool
    let action: () -> Void
    var body: some View {
        Button(action: action) {
            Image(systemName: symbol).font(.system(size: 16, weight: .medium))
                .foregroundStyle(selected ? Theme.accent : Theme.text2)
                .frame(width: 52, height: 52)
                .background(selected ? Theme.accent.opacity(0.08) : Theme.surface, in: .rect(cornerRadius: 16))
                .overlay(RoundedRectangle(cornerRadius: 16).strokeBorder(selected ? Theme.accent.opacity(0.35) : Theme.border, lineWidth: 1))
                .contentTransition(.symbolEffect(.replace))
        }
        .buttonStyle(Pressable())
    }
}
