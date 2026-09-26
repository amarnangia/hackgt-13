import SwiftUI

struct HomeView: View {
    @EnvironmentObject var people: People
    @State private var cover: Cover?
    @State private var sheet: HomeSheet?

    // One cover and one sheet per view: SwiftUI only honours one of each.
    enum Cover: Identifiable { case session(Connection), newConnection
        var id: String { if case .session(let c) = self { return "s-" + c.id }; return "new" } }
    enum HomeSheet: String, Identifiable { case growth, settings; var id: String { rawValue } }

    private let recent: [(who: String, topic: String, when: String, mins: Int)] = [
        ("ammamma", "Sankranti plans, pulihora, your exam", "Yesterday", 18),
        ("thatayya", "The paddy field, the new tractor", "Tue", 9),
        ("ammamma", "Diwali sweets, cousins visiting", "Sun", 24),
    ]

    var body: some View {
        let n = people.numbers
        ScrollView {
            VStack(alignment: .leading, spacing: 0) {
                HStack {
                    HStack(spacing: 10) { WeaveMark().frame(width: 22, height: 22); Text("Weave").font(Fonts.ui(16, .semibold)).tracking(-0.3) }
                    Spacer()
                    Button { sheet = .settings } label: { Avatar(text: String((people.profileName ?? "S").prefix(1)), size: 34) }
                        .buttonStyle(Pressable())
                }
                .frame(height: 56)
                .reveal(0)

                VStack(alignment: .leading, spacing: 8) {
                    Text("\(greeting), \(people.profileName ?? "Saanvi")").font(Fonts.ui(32, .medium)).tracking(-1.1).foregroundStyle(Theme.text)
                    Text("Ammamma usually calls around this time.").font(Fonts.ui(15)).foregroundStyle(Theme.text2)
                }
                .padding(.top, 20)
                .reveal(1)

                section("Your connections").reveal(2)
                VStack(spacing: 0) {
                    ForEach(Array(people.connections.enumerated()), id: \.element.id) { i, c in
                        if i > 0 { Rectangle().fill(Theme.border).frame(height: 1).padding(.leading, 76) }
                        Button { cover = .session(c) } label: { ConnectionCard(connection: c, myLang: people.myLang) }.buttonStyle(RowStyle())
                    }
                }
                .background(Theme.surface, in: .rect(cornerRadius: Theme.radius))
                .overlay(RoundedRectangle(cornerRadius: Theme.radius).strokeBorder(Theme.border, lineWidth: 1))
                .clipShape(.rect(cornerRadius: Theme.radius))
                .reveal(3)

                Button { cover = .newConnection } label: {
                    Label("Start a connection", systemImage: "plus").font(Fonts.ui(16, .medium)).foregroundStyle(.white)
                        .frame(maxWidth: .infinity).frame(height: 56)
                        .background(Theme.accent, in: .rect(cornerRadius: 16))
                        .overlay(RoundedRectangle(cornerRadius: 16).strokeBorder(.white.opacity(0.1), lineWidth: 1))
                        .shadow(color: Theme.accent.opacity(0.45), radius: 20, y: 10)
                }
                .buttonStyle(Pressable())
                .padding(.top, 20)
                .reveal(4)

                HStack { section("Your language growth"); Spacer(); Button("Details") { sheet = .growth }.font(Fonts.mono(10.5)).foregroundStyle(Theme.text2).padding(.top, 40) }
                    .reveal(5)
                Button { sheet = .growth } label: {
                    HStack(spacing: 1) {
                        teaser("This week", "+\(n.newWords)", "words")
                        teaser("Known", "\(n.known)", "/ \(n.total)")
                        teaser("Hearings", "\(n.hearings)", "")
                    }
                    .background(Theme.border)
                    .clipShape(.rect(cornerRadius: Theme.radius))
                    .overlay(RoundedRectangle(cornerRadius: Theme.radius).strokeBorder(Theme.border, lineWidth: 1))
                }
                .buttonStyle(Pressable())
                .reveal(6)

                section("Recent conversations").reveal(7)
                VStack(spacing: 0) {
                    ForEach(Array(recent.enumerated()), id: \.offset) { i, r in
                        let c = people.connections.first { $0.id == r.who } ?? people.connections[0]
                        if i > 0 { Rectangle().fill(Theme.border).frame(height: 1).padding(.leading, 72) }
                        Button { cover = .session(c) } label: {
                            HStack(spacing: 16) {
                                Avatar(text: c.monogram, size: 40)
                                VStack(alignment: .leading, spacing: 2) {
                                    Text(c.name).font(Fonts.ui(15, .medium)).foregroundStyle(Theme.text)
                                    Text(r.topic).font(Fonts.ui(13)).foregroundStyle(Theme.text2).lineLimit(1)
                                }
                                Spacer(minLength: 8)
                                Text("\(r.when) · \(r.mins)m").font(Fonts.mono(11, .regular)).foregroundStyle(Theme.text3)
                            }
                            .padding(.horizontal, 16).padding(.vertical, 14)
                            .contentShape(Rectangle())
                        }
                        .buttonStyle(RowStyle())
                    }
                }
                .background(Theme.surface, in: .rect(cornerRadius: Theme.radius))
                .overlay(RoundedRectangle(cornerRadius: Theme.radius).strokeBorder(Theme.border, lineWidth: 1))
                .clipShape(.rect(cornerRadius: Theme.radius))
                .reveal(8)
            }
            .padding(.horizontal, 20)
            .padding(.bottom, 48)
        }
        .scrollIndicators(.hidden)
        .background(Backdrop())
        .fullScreenCover(item: $cover) { c in
            switch c {
            case .session(let partner):
                SessionView(convo: Conversation(partner: partner)).environmentObject(people)
            case .newConnection:
                OnboardingView(isNew: true) { new in
                    cover = nil
                    Task { try? await Task.sleep(for: .milliseconds(500)); cover = .session(new) }
                }
                .environmentObject(people)
            }
        }
        .sheet(item: $sheet) { s in
            Group {
                if s == .growth { GrowthSheet(partner: "Ammamma") } else { SettingsView() }
            }
            .environmentObject(people)
            .presentationDetents([.large]).presentationBackground(Theme.bg2).presentationCornerRadius(24)
        }
        .task { await people.loadGrowth() }
        .task {
            if let c = people.pendingSession { people.pendingSession = nil; try? await Task.sleep(for: .milliseconds(500)); cover = .session(c) }
        }
        .task {   // screenshots: -startSession 1
            if UserDefaults.standard.bool(forKey: "startSession") { try? await Task.sleep(for: .milliseconds(1500)); cover = people.connections.first.map { .session($0) } }
            if UserDefaults.standard.bool(forKey: "openGrowth") { try? await Task.sleep(for: .milliseconds(1500)); sheet = .growth }
        }
    }

    private var greeting: String {
        switch Calendar.current.component(.hour, from: .now) {
        case 5..<12: "Good morning"
        case 12..<17: "Good afternoon"
        case 17..<22: "Good evening"
        default: "Good night"
        }
    }

    private func section(_ title: String) -> some View { Eyebrow(title).padding(.top, 40).padding(.bottom, 12) }

    private func teaser(_ label: String, _ value: String, _ unit: String) -> some View {
        VStack(alignment: .leading, spacing: 10) {
            Eyebrow(label)
            HStack(alignment: .firstTextBaseline, spacing: 3) {
                Text(value).font(Fonts.ui(24, .medium)).tracking(-0.8).monospacedDigit().foregroundStyle(Theme.text)
                Text(unit).font(Fonts.ui(13)).foregroundStyle(Theme.text2)
            }
        }
        .padding(16)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(Theme.surface)
    }
}

struct RowStyle: ButtonStyle {
    func makeBody(configuration: Configuration) -> some View {
        configuration.label.background(configuration.isPressed ? Theme.surface2 : .clear)
            .animation(.easeOut(duration: 0.15), value: configuration.isPressed)
    }
}

struct ConnectionCard: View {
    let connection: Connection
    let myLang: String
    var body: some View {
        HStack(spacing: 16) {
            Avatar(text: connection.monogram, size: 44, presence: connection.recent)
            VStack(alignment: .leading, spacing: 3) {
                Text(connection.name).font(Fonts.ui(16, .medium)).tracking(-0.2).foregroundStyle(Theme.text)
                HStack(spacing: 6) {
                    Text(Language.name(connection.lang))
                    Image(systemName: "arrow.right").font(.system(size: 10, weight: .medium))
                    Text(Language.name(myLang))
                }
                .font(Fonts.ui(13)).foregroundStyle(Theme.text2)
            }
            Spacer(minLength: 8)
            HStack(spacing: 6) {
                Circle().fill(connection.recent ? Theme.accent : Theme.text3).frame(width: 6, height: 6)
                Text(connection.lastLabel).font(Fonts.ui(12)).foregroundStyle(Theme.text3)
            }
        }
        .padding(16)
        .contentShape(Rectangle())
    }
}

/// Two people and the thread between them.
struct WeaveMark: View {
    var body: some View {
        Canvas { ctx, size in
            let w = size.width, h = size.height, r = w * 0.13
            ctx.stroke(Path(ellipseIn: CGRect(x: w * 0.08, y: h / 2 - r, width: r * 2, height: r * 2)), with: .color(Theme.text), lineWidth: 1.6)
            ctx.fill(Path(ellipseIn: CGRect(x: w * 0.92 - r * 2, y: h / 2 - r, width: r * 2, height: r * 2)), with: .color(Theme.accent))
            var p = Path(); p.move(to: CGPoint(x: w * 0.08 + r * 2 + 2, y: h / 2)); p.addLine(to: CGPoint(x: w * 0.92 - r * 2 - 2, y: h / 2))
            ctx.stroke(p, with: .color(Theme.accent), style: StrokeStyle(lineWidth: 1.6, lineCap: .round, dash: [2, 2.4]))
        }
    }
}

// MARK: - onboarding

struct OnboardingView: View {
    var isNew = false
    let finish: (Connection) -> Void
    @EnvironmentObject var people: People
    @Environment(\.dismiss) private var dismiss
    @State private var step = 0
    @State private var mine = "en"
    @State private var theirs = "te"
    @State private var name = "Ammamma"
    @State private var connected = false
    @FocusState private var nameFocused: Bool

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            HStack(spacing: 6) {
                ForEach(0..<4, id: \.self) { i in
                    Capsule().fill(i <= step ? Theme.text : Theme.border2).frame(height: 3)
                        .animation(.spring(response: 0.4, dampingFraction: 0.9), value: step)
                }
            }
            .padding(.top, 20).padding(.bottom, 40)

            Group {
                switch step {
                case 0: stepView("What language do you speak?", "Everything will reach you in this language.") { LanguageSelector(selected: $mine) }
                case 1: stepView("Who are you talking with?", "Pick the language they speak.") { LanguageSelector(selected: $theirs, exclude: mine) }
                case 2: stepView("What do you call them?", "The name you'd use on a call.") { nameStep }
                default: stepView("You and \(name).", "\(Language.name(theirs)) becomes \(Language.name(mine)) for you as \(name) speaks, and the words you learn stay in \(Language.name(theirs)).") {
                    ConnectionVisualizer(you: people.profileName ?? "Saanvi", youLang: mine,
                                         partner: Connection(id: name.lowercased(), name: name, lang: theirs, last: .now),
                                         speaking: [], translating: false, connected: connected)
                        .padding(.top, 24)
                        .onAppear { Task { try? await Task.sleep(for: .milliseconds(250)); connected = true } }
                }
                }
            }
            .id(step)
            .transition(.asymmetric(insertion: .opacity.combined(with: .offset(x: 24)), removal: .opacity.combined(with: .offset(x: -24))))

            Spacer(minLength: 16)
            HStack(spacing: 12) {
                if step > 0 || isNew {
                    Button { back() } label: {
                        Image(systemName: "chevron.left").font(.system(size: 15, weight: .semibold)).foregroundStyle(Theme.text)
                            .frame(width: 52, height: 52)
                            .background(Theme.surface, in: .rect(cornerRadius: 14))
                            .overlay(RoundedRectangle(cornerRadius: 14).strokeBorder(Theme.border2, lineWidth: 1))
                    }
                    .buttonStyle(Pressable())
                }
                Button { next() } label: {
                    HStack(spacing: 8) {
                        Text(step == 3 ? "Start conversation" : "Continue")
                        if step == 3 { Image(systemName: "arrow.right").font(.system(size: 14, weight: .semibold)) }
                    }
                    .font(Fonts.ui(16, .medium))
                    .foregroundStyle(step == 3 ? .white : Theme.bg)
                    .frame(maxWidth: .infinity).frame(height: 52)
                    .background(step == 3 ? Theme.accent : Theme.text, in: .rect(cornerRadius: 14))
                    .shadow(color: Theme.accent.opacity(step == 3 ? 0.45 : 0), radius: 18, y: 8)
                }
                .buttonStyle(Pressable())
            }
            .padding(.bottom, 12)
        }
        .padding(.horizontal, 20)
        .background(Backdrop())
        .preferredColorScheme(.dark)
        .onAppear { if isNew { step = 1; name = "Nanamma" } }
    }

    private func stepView<C: View>(_ title: String, _ sub: String, @ViewBuilder content: () -> C) -> some View {
        VStack(alignment: .leading, spacing: 0) {
            Text(title).font(Fonts.ui(28, .medium)).tracking(-0.9).foregroundStyle(Theme.text)
            Text(sub).font(Fonts.ui(15)).foregroundStyle(Theme.text2).padding(.top, 8).padding(.bottom, 24)
            content()
        }
    }

    private var nameStep: some View {
        VStack(alignment: .leading, spacing: 16) {
            TextField("", text: $name)
                .font(Fonts.ui(20, .medium)).foregroundStyle(Theme.text)
                .focused($nameFocused)
                .padding(.horizontal, 16).frame(height: 56)
                .background(Theme.surface, in: .rect(cornerRadius: 14))
                .overlay(RoundedRectangle(cornerRadius: 14).strokeBorder(nameFocused ? Theme.accent.opacity(0.6) : Theme.border2, lineWidth: 1))
                .animation(.easeOut(duration: 0.2), value: nameFocused)
                .onAppear { nameFocused = true }
                .submitLabel(.next).onSubmit { next() }
            FlowChips(options: ["Ammamma", "Nanamma", "Thatayya", "Amma", "Nanna", "Pinni"], selected: $name)
        }
    }

    private func next() {
        guard step == 3 else { withAnimation(.spring(response: 0.4, dampingFraction: 0.9)) { step += 1 }; return }
        if people.profileName == nil { people.profileName = "Saanvi" }
        people.myLang = mine
        let clean = name.trimmingCharacters(in: .whitespaces).isEmpty ? "Ammamma" : name.trimmingCharacters(in: .whitespaces)
        let c = people.connections.first { $0.name.lowercased() == clean.lowercased() } ?? Connection(id: clean.lowercased(), name: clean, lang: theirs, last: .now)
        people.touch(c)
        finish(c)
    }

    private func back() {
        if step == 0 || (isNew && step == 1) { dismiss(); return }
        withAnimation(.spring(response: 0.4, dampingFraction: 0.9)) { step -= 1 }
    }
}

struct LanguageSelector: View {
    @Binding var selected: String
    var exclude: String? = nil
    var body: some View {
        ScrollView {
            VStack(spacing: 0) {
                ForEach(Array(Language.all.filter { $0.code != exclude }.enumerated()), id: \.element.id) { i, l in
                    if i > 0 { Rectangle().fill(Theme.border).frame(height: 1).padding(.leading, 16) }
                    Button { withAnimation(.spring(response: 0.3, dampingFraction: 0.8)) { selected = l.code } } label: {
                        HStack(spacing: 16) {
                            Text(l.native).font(Fonts.ui(17)).foregroundStyle(Theme.text)
                            Spacer()
                            if l.native != l.english { Text(l.english).font(Fonts.ui(13)).foregroundStyle(Theme.text3) }
                            ZStack {
                                Circle().strokeBorder(selected == l.code ? Theme.accent : Theme.border2, lineWidth: 1.5)
                                if selected == l.code {
                                    Circle().fill(Theme.accent)
                                    Image(systemName: "checkmark").font(.system(size: 10, weight: .bold)).foregroundStyle(.white).transition(.scale.combined(with: .opacity))
                                }
                            }
                            .frame(width: 20, height: 20)
                        }
                        .padding(.horizontal, 16).padding(.vertical, 14)
                        .contentShape(Rectangle())
                    }
                    .buttonStyle(RowStyle())
                    .sensoryFeedback(.selection, trigger: selected == l.code)
                }
            }
            .background(Theme.surface, in: .rect(cornerRadius: Theme.radius))
            .overlay(RoundedRectangle(cornerRadius: Theme.radius).strokeBorder(Theme.border, lineWidth: 1))
            .clipShape(.rect(cornerRadius: Theme.radius))
        }
        .scrollIndicators(.hidden)
    }
}

struct FlowChips: View {
    let options: [String]
    @Binding var selected: String
    var body: some View {
        let rows = [Array(options.prefix(3)), Array(options.dropFirst(3))]
        VStack(alignment: .leading, spacing: 8) {
            ForEach(Array(rows.enumerated()), id: \.offset) { _, row in
                HStack(spacing: 8) {
                    ForEach(row, id: \.self) { o in
                        let on = o == selected
                        Button { withAnimation(.easeOut(duration: 0.2)) { selected = o } } label: {
                            Text(o).font(Fonts.ui(14)).foregroundStyle(on ? Theme.text : Theme.text2)
                                .padding(.horizontal, 14).frame(height: 34)
                                .background(on ? Theme.accent.opacity(0.16) : .clear, in: .capsule)
                                .overlay(Capsule().strokeBorder(on ? Theme.accent.opacity(0.5) : Theme.border2, lineWidth: 1))
                        }
                        .buttonStyle(Pressable())
                    }
                }
            }
        }
    }
}
