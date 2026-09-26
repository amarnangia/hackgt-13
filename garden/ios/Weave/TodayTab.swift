import SwiftUI

struct TodayTab: View {
    @EnvironmentObject var model: GardenModel
    @Binding var selected: Plant?
    @State private var showSettings = false

    var body: some View {
        let snap = model.snapshot
        let starters = Starters.make(snap, rotation: model.rotation)
        ScrollView {
            VStack(alignment: .leading, spacing: 12) {
                header
                VStack(alignment: .leading, spacing: 4) {
                    Eyebrow(Date.now.formatted(.dateTime.weekday(.wide).month(.abbreviated).day()))
                    Text("Next call").font(.system(size: 34, weight: .bold)).tracking(-1.2).foregroundStyle(Theme.ink)
                    if let last = Starters.lastCall(snap) {
                        Text(last).font(.system(size: 15)).foregroundStyle(Theme.ink2)
                    }
                }
                .padding(.bottom, 8)

                if let first = starters.first {
                    OpenerCard(starter: first, plant: snap.plant(first.word)) {
                        model.shuffle()
                    } open: { p in selected = p }
                } else {
                    Panel { Text("Your first call will suggest things to talk about.").font(.system(size: 15)).foregroundStyle(Theme.ink2) }
                }

                HStack(alignment: .top, spacing: 12) {
                    if let phrase = Starters.trySaying(snap, rotation: model.rotation) {
                        Button { selected = phrase } label: {
                            Panel(padding: 16) {
                                Eyebrow("Try saying")
                                Text(phrase.phrase).font(.system(size: 22, weight: .semibold)).tracking(-0.4)
                                    .foregroundStyle(Theme.ink).lineLimit(1).minimumScaleFactor(0.7).padding(.top, 10)
                                Text(phrase.english ?? "").font(.system(size: 13)).foregroundStyle(Theme.ink2).lineLimit(1).padding(.top, 2)
                            }
                        }
                        .buttonStyle(Pressable())
                    }
                    StreakPanel(snap: snap)
                }
                .fixedSize(horizontal: false, vertical: true)

                if starters.count > 1 {
                    Panel(padding: 0) {
                        Eyebrow("Also ask").padding([.horizontal, .top], 20).padding(.bottom, 6)
                        ForEach(Array(starters.dropFirst().enumerated()), id: \.element.id) { i, s in
                            if i > 0 { Rectangle().fill(Theme.border).frame(height: 1).padding(.leading, 64) }
                            Button { selected = snap.plant(s.word) } label: {
                                HStack(spacing: 14) {
                                    Image(systemName: s.symbol).font(.system(size: 13, weight: .semibold)).foregroundStyle(Theme.accent)
                                        .frame(width: 30, height: 30).background(Theme.accent.opacity(0.1), in: .rect(cornerRadius: 9))
                                    starterText(s, size: 15).multilineTextAlignment(.leading).lineLimit(2)
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
                }

                WeavePanel(snap: snap, selected: $selected)
            }
            .padding(.horizontal, 20)
            .padding(.bottom, 32)
        }
        .scrollIndicators(.hidden)
        .background(Theme.bg)
        .sheet(isPresented: $showSettings) { SettingsView().presentationBackground(Theme.bg) }
    }

    private var header: some View {
        HStack(spacing: 8) {
            Text("Weave").font(.system(size: 17, weight: .semibold)).tracking(-0.3).foregroundStyle(Theme.ink)
            Spacer()
            StatusChip(source: model.source, live: model.snapshot.calls.live)
            Button { showSettings = true } label: {
                Image(systemName: "slider.horizontal.3").font(.system(size: 14, weight: .semibold)).foregroundStyle(Theme.ink2)
                    .frame(width: 34, height: 34)
                    .background(Theme.surface, in: .circle)
                    .overlay(Circle().strokeBorder(Theme.border, lineWidth: 1))
            }
            .buttonStyle(Pressable())
        }
        .padding(.top, 8)
        .padding(.bottom, 12)
    }
}

struct OpenerCard: View {
    let starter: Starter
    let plant: Plant?
    let shuffle: () -> Void
    let open: (Plant) -> Void

    var body: some View {
        Panel(padding: 22) {
            HStack {
                Eyebrow("Open with", color: Theme.accent)
                Spacer()
                HStack(spacing: 5) {
                    Image(systemName: starter.symbol).font(.system(size: 10, weight: .semibold))
                    Text(starter.topic).font(.system(size: 11, weight: .medium))
                }
                .foregroundStyle(Theme.ink2)
                .padding(.horizontal, 9).padding(.vertical, 4)
                .overlay(Capsule().strokeBorder(Theme.border, lineWidth: 1))
            }
            starterText(starter, size: 26).padding(.top, 14)
                .contentTransition(.opacity)
            if let g = starter.gloss {
                Text(g).font(.system(size: 15)).foregroundStyle(Theme.ink2).padding(.top, 6)
            }
            Rectangle().fill(Theme.border).frame(height: 1).padding(.vertical, 18)
            HStack(spacing: 10) {
                Button(action: shuffle) {
                    Label("Another idea", systemImage: "arrow.triangle.2.circlepath")
                        .font(.system(size: 14, weight: .semibold)).foregroundStyle(Theme.ink)
                        .padding(.horizontal, 14).frame(height: 38)
                        .background(Theme.raised, in: .capsule)
                }
                .buttonStyle(Pressable())
                .sensoryFeedback(.selection, trigger: starter.id)
                Spacer()
                if let plant {
                    Button { open(plant) } label: {
                        HStack(spacing: 4) {
                            Text("About the word").font(.system(size: 14, weight: .semibold))
                            Image(systemName: "arrow.up.right").font(.system(size: 11, weight: .bold))
                        }
                        .foregroundStyle(Theme.accent)
                        .frame(height: 38)
                    }
                    .buttonStyle(Pressable())
                }
            }
        }
        .animation(.easeOut(duration: 0.2), value: starter.id)
    }
}

struct StreakPanel: View {
    let snap: GardenSnapshot
    var body: some View {
        Panel(padding: 16) {
            Eyebrow("Streak")
            HStack(alignment: .firstTextBaseline, spacing: 4) {
                Text("\(snap.streak)").font(.system(size: 22, weight: .semibold)).monospacedDigit().tracking(-0.4)
                Text(snap.streak == 1 ? "day" : "days").font(.system(size: 13)).foregroundStyle(Theme.ink2)
            }
            .foregroundStyle(Theme.ink)
            .padding(.top, 10)
            HStack(spacing: 4) {
                ForEach(snap.days.suffix(7)) { d in
                    Capsule().fill(d.heard > 0 ? Theme.accent : Theme.raised).frame(height: 4)
                }
            }
            .padding(.top, 9)
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
                .opacity(live && pulse ? 0.35 : 1)
                .animation(live ? .easeInOut(duration: 0.9).repeatForever() : .default, value: pulse)
            Text(label).font(.system(size: 12, weight: .medium)).foregroundStyle(Theme.ink2)
        }
        .padding(.horizontal, 10).frame(height: 28)
        .overlay(Capsule().strokeBorder(Theme.border, lineWidth: 1))
        .onAppear { pulse = true }
    }
    private var label: String { source == .demo ? "Demo" : source == .saved ? "Offline" : live ? "Live" : "Synced" }
    private var dot: Color { source == .live ? (live ? Theme.accent : Color.green.opacity(0.8)) : Theme.muted }
}

/// Every word as one tile, shaded by how well you know it.
struct WeavePanel: View {
    let snap: GardenSnapshot
    @Binding var selected: Plant?

    var body: some View {
        let words = snap.plants.sorted { ($0.firstHeard ?? 0) < ($1.firstHeard ?? 0) }
        Panel {
            HStack(alignment: .firstTextBaseline) {
                Eyebrow("Your weave")
                Spacer()
                Text("\(snap.totals.bloom) of \(snap.totals.phrases) known").font(.system(size: 13, weight: .medium)).monospacedDigit().foregroundStyle(Theme.ink2)
            }
            LazyVGrid(columns: Array(repeating: GridItem(.flexible(), spacing: 5), count: 10), spacing: 5) {
                ForEach(words) { p in
                    WeaveTile(plant: p, selected: selected?.phrase == p.phrase)
                        .onTapGesture { selected = p }
                }
            }
            .padding(.top, 16)
            HStack(spacing: 16) {
                ForEach(Stage.allCases) { s in
                    HStack(spacing: 6) {
                        RoundedRectangle(cornerRadius: 2.5).fill(s.fill).frame(width: 10, height: 10)
                        Text(s.label).font(.system(size: 12, weight: .medium)).foregroundStyle(Theme.ink2)
                    }
                }
                Spacer()
            }
            .padding(.top, 16)
        }
    }
}

struct WeaveTile: View {
    let plant: Plant
    let selected: Bool
    var body: some View {
        RoundedRectangle(cornerRadius: 4)
            .fill(plant.stageEnum.fill)
            .aspectRatio(1, contentMode: .fit)
            .overlay(RoundedRectangle(cornerRadius: 4).strokeBorder(selected ? Theme.ink : .clear, lineWidth: 1.5))
            .keyframeAnimator(initialValue: 1.0, trigger: plant.growth) { v, scale in
                v.scaleEffect(scale)
            } keyframes: { _ in
                SpringKeyframe(1.35, duration: 0.15)
                SpringKeyframe(1.0, duration: 0.4)
            }
            .animation(.easeOut(duration: 0.3), value: plant.stage)
    }
}
