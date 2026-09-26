import SwiftUI

struct TodayTab: View {
    @EnvironmentObject var model: GardenModel
    @Binding var selected: Plant?
    @State private var showSettings = false

    var body: some View {
        let snap = model.snapshot
        let starters = Starters.make(snap, rotation: model.rotation)
        ScrollView {
            VStack(alignment: .leading, spacing: 14) {
                header.reveal(0)
                VStack(alignment: .leading, spacing: 2) {
                    Eyebrow(Date.now.formatted(.dateTime.weekday(.wide).month(.wide).day()), color: Theme.gold.opacity(0.8))
                    (Text("Next ").font(Fonts.display(52)).foregroundColor(Theme.ink)
                        + Text("call").font(Fonts.display(52, italic: true)).foregroundStyle(Theme.silk))
                        .tracking(-1)
                    if let last = Starters.lastCall(snap) {
                        Text(last).font(Fonts.ui(15)).foregroundStyle(Theme.ink2)
                    }
                }
                .padding(.bottom, 6)
                .reveal(1)

                if let first = starters.first {
                    OpenerCard(starter: first, plant: snap.plant(first.word)) {
                        model.shuffle()
                    } open: { p in selected = p }
                    .reveal(2)
                } else {
                    Panel { Text("Your first call will suggest things to talk about.").font(Fonts.ui(15)).foregroundStyle(Theme.ink2) }
                }

                HStack(alignment: .top, spacing: 12) {
                    if let phrase = Starters.trySaying(snap, rotation: model.rotation) {
                        Button { selected = phrase } label: {
                            Panel(padding: 16) {
                                Eyebrow("Try saying", color: Theme.peacock)
                                Text(phrase.phrase).font(Fonts.telugu(24)).foregroundStyle(Theme.peacockSilk)
                                    .lineLimit(1).minimumScaleFactor(0.6).padding(.top, 10)
                                Text(phrase.english ?? "").font(Fonts.ui(13)).foregroundStyle(Theme.ink2).lineLimit(1).padding(.top, 2)
                            }
                        }
                        .buttonStyle(Pressable())
                    }
                    StreakPanel(snap: snap)
                }
                .fixedSize(horizontal: false, vertical: true)
                .reveal(3)

                if starters.count > 1 {
                    Panel(padding: 0) {
                        Eyebrow("Also ask").padding([.horizontal, .top], 20).padding(.bottom, 6)
                        ForEach(Array(starters.dropFirst().enumerated()), id: \.element.id) { i, s in
                            if i > 0 { Rectangle().fill(Theme.border).frame(height: 1).padding(.leading, 66) }
                            Button { selected = snap.plant(s.word) } label: {
                                HStack(spacing: 14) {
                                    let tint = [Theme.rani, Theme.peacock, Theme.gold][i % 3]
                                    Image(systemName: s.symbol).font(.system(size: 13, weight: .semibold)).foregroundStyle(tint)
                                        .frame(width: 32, height: 32)
                                        .background(tint.opacity(0.14), in: .rect(cornerRadius: 10))
                                        .overlay(RoundedRectangle(cornerRadius: 10).strokeBorder(tint.opacity(0.25), lineWidth: 1))
                                    starterText(s, size: 18).multilineTextAlignment(.leading).lineLimit(2)
                                    Spacer(minLength: 0)
                                    Image(systemName: "chevron.right").font(.system(size: 11, weight: .semibold)).foregroundStyle(Theme.muted)
                                }
                                .padding(.horizontal, 20).padding(.vertical, 13)
                                .contentShape(Rectangle())
                            }
                            .buttonStyle(Pressable())
                        }
                        Spacer().frame(height: 6)
                    }
                    .reveal(4)
                }

                WeavePanel(snap: snap, selected: $selected).reveal(5)
            }
            .padding(.horizontal, 20)
            .padding(.bottom, 32)
        }
        .scrollIndicators(.hidden)
        .background(Loom())
        .sheet(isPresented: $showSettings) { SettingsView().presentationBackground { Loom(animated: false) } }
    }

    private var header: some View {
        HStack(spacing: 8) {
            HStack(spacing: 7) {
                WeaveMark().frame(width: 22, height: 22)
                Text("Weave").font(Fonts.display(24)).foregroundStyle(Theme.ink)
            }
            Spacer()
            StatusChip(source: model.source, live: model.snapshot.calls.live)
            Button { showSettings = true } label: {
                Image(systemName: "slider.horizontal.3").font(.system(size: 14, weight: .semibold)).foregroundStyle(Theme.ink2)
                    .frame(width: 36, height: 36)
                    .background(Theme.surface, in: .circle)
                    .overlay(Circle().strokeBorder(Theme.sheen, lineWidth: 1))
            }
            .buttonStyle(Pressable())
        }
        .padding(.top, 8)
        .padding(.bottom, 10)
    }
}

/// The logo: two threads crossing in a diamond, gold over peacock.
struct WeaveMark: View {
    var body: some View {
        Canvas { ctx, size in
            let w = size.width, h = size.height
            var a = Path(); a.move(to: CGPoint(x: 0, y: h * 0.5)); a.addLine(to: CGPoint(x: w * 0.5, y: 0)); a.addLine(to: CGPoint(x: w, y: h * 0.5))
            var b = Path(); b.move(to: CGPoint(x: 0, y: h * 0.5)); b.addLine(to: CGPoint(x: w * 0.5, y: h)); b.addLine(to: CGPoint(x: w, y: h * 0.5))
            ctx.stroke(b, with: .linearGradient(Gradient(colors: [Theme.peacock, Theme.rani]), startPoint: .zero, endPoint: CGPoint(x: w, y: h)), style: StrokeStyle(lineWidth: 2.4, lineCap: .round, lineJoin: .round))
            ctx.stroke(a, with: .linearGradient(Gradient(colors: [Theme.gold, Theme.vermilion]), startPoint: .zero, endPoint: CGPoint(x: w, y: h)), style: StrokeStyle(lineWidth: 2.4, lineCap: .round, lineJoin: .round))
            ctx.fill(Path(ellipseIn: CGRect(x: w / 2 - 2, y: h / 2 - 2, width: 4, height: 4)), with: .color(Theme.ink))
        }
    }
}

struct OpenerCard: View {
    let starter: Starter
    let plant: Plant?
    let shuffle: () -> Void
    let open: (Plant) -> Void

    var body: some View {
        Panel(padding: 22, silk: true) {
            HStack {
                Eyebrow("Open with", color: Theme.gold)
                Spacer()
                HStack(spacing: 5) {
                    Image(systemName: starter.symbol).font(.system(size: 10, weight: .semibold))
                    Text(starter.topic).font(Fonts.ui(11, .medium))
                }
                .foregroundStyle(Theme.ink2)
                .padding(.horizontal, 9).padding(.vertical, 4)
                .background(Theme.raised, in: .capsule)
            }
            starterText(starter, size: 34)
                .lineSpacing(-2)
                .padding(.top, 16)
                .id(starter.id)
                .transition(.asymmetric(insertion: .opacity.combined(with: .offset(y: 8)), removal: .opacity))
            if let g = starter.gloss {
                Text(g).font(Fonts.ui(15)).foregroundStyle(Theme.ink2).padding(.top, 6)
            }
            ZariTrim().padding(.vertical, 18)
            HStack(spacing: 10) {
                Button(action: shuffle) {
                    Label("Another idea", systemImage: "arrow.triangle.2.circlepath")
                        .font(Fonts.ui(14, .semibold)).foregroundStyle(Color(hex: 0x1a1208))
                        .padding(.horizontal, 16).frame(height: 40)
                        .background(Theme.zari, in: .capsule)
                }
                .buttonStyle(Pressable())
                .sensoryFeedback(.selection, trigger: starter.id)
                Spacer()
                if let plant {
                    Button { open(plant) } label: {
                        HStack(spacing: 4) {
                            Text("The word").font(Fonts.ui(14, .semibold)).lineLimit(1)
                            Image(systemName: "arrow.up.right").font(.system(size: 11, weight: .bold))
                        }
                        .foregroundStyle(Theme.ink)
                        .padding(.horizontal, 14).frame(height: 40)
                        .overlay(Capsule().strokeBorder(Theme.sheen, lineWidth: 1))
                    }
                    .buttonStyle(Pressable())
                }
            }
        }
        .background {
            // soft silk glow behind the card
            RoundedRectangle(cornerRadius: Theme.radius).fill(Theme.silk).blur(radius: 40).opacity(0.18).padding(10)
        }
        .animation(.spring(response: 0.45, dampingFraction: 0.85), value: starter.id)
    }
}

struct StreakPanel: View {
    let snap: GardenSnapshot
    var body: some View {
        Panel(padding: 16) {
            Eyebrow("Streak", color: Theme.vermilion)
            HStack(alignment: .firstTextBaseline, spacing: 5) {
                Text("\(snap.streak)").font(Fonts.display(34)).foregroundStyle(Theme.kumkum)
                Text(snap.streak == 1 ? "day" : "days").font(Fonts.ui(13)).foregroundStyle(Theme.ink2)
            }
            .padding(.top, 4)
            HStack(spacing: 4) {
                ForEach(snap.days.suffix(7)) { d in
                    Capsule().fill(d.heard > 0 ? AnyShapeStyle(Theme.kumkum) : AnyShapeStyle(Color.white.opacity(0.07))).frame(height: 4)
                }
            }
            .padding(.top, 6)
        }
    }
}

struct StatusChip: View {
    let source: GardenClient.Source
    let live: Bool
    @State private var pulse = false

    var body: some View {
        HStack(spacing: 6) {
            Circle().fill(dot).frame(width: 6, height: 6)
                .shadow(color: dot, radius: live ? 4 : 0)
                .opacity(live && pulse ? 0.35 : 1)
                .animation(live ? .easeInOut(duration: 0.9).repeatForever() : .default, value: pulse)
            Text(label).font(Fonts.ui(12, .medium)).foregroundStyle(Theme.ink2)
        }
        .padding(.horizontal, 11).frame(height: 30)
        .background(Theme.surface, in: .capsule)
        .overlay(Capsule().strokeBorder(Theme.sheen, lineWidth: 1))
        .onAppear { pulse = true }
    }
    private var label: String { source == .demo ? "Demo" : source == .saved ? "Offline" : live ? "Live" : "Synced" }
    private var dot: Color { source == .live ? (live ? Theme.vermilion : Theme.peacock) : Theme.muted }
}

/// Every word as one thread in the weave: kumkum when new, peacock while learning, zari gold once known.
struct WeavePanel: View {
    let snap: GardenSnapshot
    @Binding var selected: Plant?
    @State private var woven = false

    var body: some View {
        let words = snap.plants.sorted { ($0.firstHeard ?? 0) < ($1.firstHeard ?? 0) }
        Panel {
            HStack(alignment: .firstTextBaseline) {
                Eyebrow("Your weave", color: Theme.gold)
                Spacer()
                (Text("\(snap.totals.bloom)").font(Fonts.display(20)).foregroundStyle(Theme.zari)
                    + Text(" of \(snap.totals.phrases) known").font(Fonts.ui(13, .medium)).foregroundColor(Theme.ink2))
            }
            LazyVGrid(columns: Array(repeating: GridItem(.flexible(), spacing: 5), count: 10), spacing: 5) {
                ForEach(Array(words.enumerated()), id: \.element.id) { i, p in
                    WeaveTile(plant: p, selected: selected?.phrase == p.phrase)
                        .opacity(woven ? 1 : 0)
                        .scaleEffect(woven ? 1 : 0.4)
                        .animation(.spring(response: 0.5, dampingFraction: 0.7).delay(0.4 + Double(i % 10 + i / 10) * 0.035), value: woven)
                        .onTapGesture { selected = p }
                }
            }
            .padding(.top, 16)
            HStack(spacing: 16) {
                ForEach(Stage.allCases.reversed()) { s in
                    HStack(spacing: 6) {
                        RoundedRectangle(cornerRadius: 2.5).fill(s.fill).frame(width: 10, height: 10)
                        Text(s.label).font(Fonts.ui(12, .medium)).foregroundStyle(Theme.ink2)
                    }
                }
                Spacer()
            }
            .padding(.top, 16)
        }
        .onAppear { woven = true }
    }
}

struct WeaveTile: View {
    let plant: Plant
    let selected: Bool
    var body: some View {
        RoundedRectangle(cornerRadius: 4)
            .fill(plant.stageEnum.fill)
            .aspectRatio(1, contentMode: .fit)
            .overlay {
                if plant.stageEnum == .seed {
                    RoundedRectangle(cornerRadius: 4).strokeBorder(Theme.vermilion.opacity(0.45), lineWidth: 1)
                }
            }
            .overlay(RoundedRectangle(cornerRadius: 4).strokeBorder(selected ? Theme.ink : .clear, lineWidth: 1.5))
            .shadow(color: plant.stageEnum == .bloom ? Theme.gold.opacity(0.35) : .clear, radius: 4)
            .keyframeAnimator(initialValue: 1.0, trigger: plant.growth) { v, scale in
                v.scaleEffect(scale)
            } keyframes: { _ in
                SpringKeyframe(1.35, duration: 0.15)
                SpringKeyframe(1.0, duration: 0.4)
            }
            .animation(.easeOut(duration: 0.3), value: plant.stage)
    }
}
