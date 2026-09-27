import SwiftUI

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
                Circle().fill(connection.recent ? Theme.green : Theme.text3).frame(width: 6, height: 6)
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

/// First launch: just your name. It goes to the Mac (/api/people), which adds you to the family and syncs it to
/// Firebase for the team's other laptops (sync.py). No languages, no who-you're-calling: that's set on the Mac.
struct OnboardingView: View {
    let finish: () -> Void
    @EnvironmentObject var people: People
    @State private var me = ""
    @FocusState private var focused: Bool

    private var clean: String { me.trimmingCharacters(in: .whitespaces) }

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            Spacer(minLength: 40)
            WeaveMark().frame(width: 52, height: 22).padding(.bottom, 24)
            Text("What's your name?").font(Fonts.ui(30, .medium)).tracking(-1).foregroundStyle(Theme.text)
            Text("It's how your family sees you in Weave.").font(Fonts.ui(15)).foregroundStyle(Theme.text2).padding(.top, 8).padding(.bottom, 28)
            TextField("", text: $me, prompt: Text("Your name").foregroundColor(Theme.text3))
                .font(Fonts.ui(20, .medium)).foregroundStyle(Theme.text)
                .focused($focused)
                .textInputAutocapitalization(.words).autocorrectionDisabled()
                .submitLabel(.done).onSubmit(done)
                .padding(.horizontal, 16).frame(height: 56)
                .background(Theme.surface, in: .rect(cornerRadius: 14))
                .overlay(RoundedRectangle(cornerRadius: 14).strokeBorder(focused ? Theme.accent.opacity(0.6) : Theme.border2, lineWidth: 1))
                .animation(.easeOut(duration: 0.2), value: focused)
            Spacer()
            Button(action: done) {
                Text("Continue").font(Fonts.ui(16, .medium)).foregroundStyle(Theme.bg)
                    .frame(maxWidth: .infinity).frame(height: 52)
                    .background(Theme.text, in: .rect(cornerRadius: 14))
            }
            .buttonStyle(Pressable())
            .disabled(clean.isEmpty).opacity(clean.isEmpty ? 0.4 : 1)
            .padding(.bottom, 12)
        }
        .padding(.horizontal, 20)
        .background(Backdrop())
        .preferredColorScheme(.dark)
        .onAppear { focused = true }
    }

    private func done() {
        guard !clean.isEmpty else { return }
        people.becomes(clean)
        finish()
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
                                    Image(systemName: "checkmark").font(.system(size: 10, weight: .bold)).foregroundStyle(Theme.onAccent).transition(.scale.combined(with: .opacity))
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
