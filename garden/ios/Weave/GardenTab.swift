import SwiftUI

func currentHour(_ date: Date = .now) -> Double {
    let override = UserDefaults.standard.double(forKey: "skyOverride")
    if override > 0 { return override }
    let c = Calendar.current.dateComponents([.hour, .minute], from: date)
    return Double(c.hour ?? 12) + Double(c.minute ?? 0) / 60
}

/// The animated garden. Tap a plant to open it.
struct LiveGardenScene: View {
    let snapshot: GardenSnapshot
    var grown: [String: Double] = [:]
    @Binding var selected: Plant?
    var bottomInset: CGFloat = 0

    var body: some View {
        GeometryReader { geo in
            let layoutSize = CGSize(width: geo.size.width, height: geo.size.height - bottomInset)
            let placed = GardenPainter.layout(snapshot.plants, in: layoutSize)
            TimelineView(.animation(minimumInterval: 1 / 30)) { tl in
                Canvas { ctx, size in
                    var o = GardenPainter.Options()
                    o.time = tl.date.timeIntervalSinceReferenceDate
                    o.hour = currentHour(tl.date)
                    o.grown = grown
                    o.selected = selected?.phrase
                    GardenPainter.drawScene(ctx, size: size, placed: placed, blooms: snapshot.totals.bloom, options: o)
                }
            }
            .contentShape(Rectangle())
            .onTapGesture(coordinateSpace: .local) { pt in
                let hit = placed.reversed().first { $0.hitRect.contains(pt) }
                    ?? placed.min { hypot($0.x - pt.x, $0.y - pt.y) < hypot($1.x - pt.x, $1.y - pt.y) }.flatMap { hypot($0.x - pt.x, $0.y - pt.y) < 40 ? $0 : nil }
                if let hit { selected = hit.plant; UIImpactFeedbackGenerator(style: .light).impactOccurred() }
            }
        }
    }
}

struct GardenTab: View {
    @EnvironmentObject var model: GardenModel
    @Binding var selected: Plant?
    @State private var showSettings = false

    private var snap: GardenSnapshot { model.snapshot }

    var body: some View {
        ScrollView {
            VStack(spacing: 0) {
                ZStack(alignment: .top) {
                    LiveGardenScene(snapshot: snap, grown: model.grown, selected: $selected, bottomInset: 38)
                        .frame(height: 520)
                    header
                        .padding(.top, 62)
                        .padding(.horizontal, 20)
                }
                VStack(spacing: 16) {
                    StageSummary(snap: snap)
                    StreakCard(snap: snap)
                    AlmostBlooming(snap: snap, selected: $selected)
                    LatestCard(snap: snap)
                }
                .padding(.horizontal, 16)
                .padding(.top, 20)
                .padding(.bottom, 30)
                .background(Theme.background, in: UnevenRoundedRectangle(topLeadingRadius: 30, topTrailingRadius: 30))
                .offset(y: -30)
                .padding(.bottom, -30)
            }
        }
        .ignoresSafeArea(edges: .top)
        .background(Theme.background)
        .scrollIndicators(.hidden)
        .sheet(isPresented: $showSettings) { SettingsView().presentationDetents([.large]) }
    }

    private var header: some View {
        let night = SkyPalette.at(hour: currentHour()).night > 0.45
        let ink: Color = night ? .white : Color(hex: 0x1d2a20)
        return VStack(alignment: .leading, spacing: 6) {
            HStack(spacing: 8) {
                Text("WEAVE").font(.caption.weight(.heavy)).tracking(1.4).opacity(0.75)
                Spacer()
                SourceChip(source: model.source, live: snap.calls.live)
                Button { showSettings = true } label: {
                    Image(systemName: "gearshape.fill").font(.system(size: 15, weight: .semibold))
                        .frame(width: 34, height: 34).background(.ultraThinMaterial, in: .circle)
                }
                .tint(ink)
            }
            Text(greeting).font(.subheadline.weight(.semibold)).opacity(0.8).padding(.top, 6)
            Text("\(snap.totals.bloom) words\nin bloom").font(Theme.title(40)).lineSpacing(-4)
                .contentTransition(.numericText())
                .animation(.spring, value: snap.totals.bloom)
        }
        .foregroundStyle(ink)
        .shadow(color: night ? .black.opacity(0.35) : .white.opacity(0.4), radius: 8)
    }

    private var greeting: String {
        switch currentHour() {
        case 5..<12: "Good morning"
        case 12..<17: "Good afternoon"
        case 17..<21: "Good evening"
        default: "Good night"
        }
    }
}

struct SourceChip: View {
    let source: GardenClient.Source
    let live: Bool
    @State private var pulse = false

    var body: some View {
        HStack(spacing: 6) {
            Circle().fill(color).frame(width: 7, height: 7)
                .scaleEffect(pulse && live ? 1.5 : 1).opacity(pulse && live ? 0.5 : 1)
                .animation(live ? .easeInOut(duration: 0.9).repeatForever() : .default, value: pulse)
            Text(label).font(.caption.weight(.bold))
        }
        .padding(.horizontal, 10).frame(height: 30)
        .background(.ultraThinMaterial, in: .capsule)
        .onAppear { pulse = true }
    }
    private var label: String { source == .demo ? "Demo" : source == .saved ? "Offline" : live ? "Live call" : "Synced" }
    private var color: Color { source == .demo ? .orange : source == .saved ? .gray : .green }
}

// MARK: cards

struct Card<Content: View>: View {
    var padding: CGFloat = 16
    @ViewBuilder var content: Content
    var body: some View {
        content
            .padding(padding)
            .frame(maxWidth: .infinity, alignment: .leading)
            .background(Theme.card, in: .rect(cornerRadius: 24))
            .overlay(RoundedRectangle(cornerRadius: 24).stroke(Theme.line, lineWidth: 1))
    }
}

struct StageSummary: View {
    let snap: GardenSnapshot
    var body: some View {
        Card {
            VStack(alignment: .leading, spacing: 14) {
                HStack(spacing: 0) {
                    ForEach(Stage.allCases) { s in
                        VStack(spacing: 4) {
                            PlantIcon(plant: .example(s), flowerOnly: s == .bloom).frame(width: 44, height: 44)
                            Text("\(count(s))").font(Theme.title(28)).contentTransition(.numericText())
                            Text(s.title).font(.caption.weight(.semibold)).foregroundStyle(Theme.ink2)
                        }
                        .frame(maxWidth: .infinity)
                    }
                }
                GeometryReader { geo in
                    HStack(spacing: 3) {
                        ForEach(Stage.allCases) { s in
                            Capsule().fill(s.color.gradient)
                                .frame(width: max(0, (geo.size.width - 6) * CGFloat(count(s)) / CGFloat(max(1, snap.totals.phrases))))
                        }
                    }
                }
                .frame(height: 10)
                Text("\(snap.totals.bloom) of \(snap.totals.phrases) words you understand on your own")
                    .font(.footnote).foregroundStyle(Theme.ink2)
            }
            .animation(.spring, value: snap.totals)
        }
    }
    func count(_ s: Stage) -> Int { s == .bloom ? snap.totals.bloom : s == .sprout ? snap.totals.sprout : snap.totals.seed }
}

struct StreakCard: View {
    let snap: GardenSnapshot
    var body: some View {
        let week = Array(snap.days.suffix(7))
        let today = week.last?.heard ?? 0 > 0
        Card { VStack(spacing: 0) {
            HStack(spacing: 14) {
                ZStack {
                    Circle().fill(Theme.flame.opacity(0.15))
                    Image(systemName: "flame.fill").font(.system(size: 26)).foregroundStyle(Theme.flame.gradient)
                        .symbolEffect(.bounce, value: snap.streak)
                }
                .frame(width: 54, height: 54)
                VStack(alignment: .leading, spacing: 2) {
                    Text("\(snap.streak)-day streak").font(.headline)
                    Text(today ? "You talked with family today" : "Call family today to keep it growing")
                        .font(.footnote).foregroundStyle(Theme.ink2)
                }
                Spacer(minLength: 0)
            }
            HStack(spacing: 0) {
                ForEach(week) { d in
                    VStack(spacing: 6) {
                        ZStack {
                            Circle().fill(d.heard > 0 ? AnyShapeStyle(Theme.flame.gradient) : AnyShapeStyle(Theme.cardRaised))
                            if d.heard > 0 { Image(systemName: "checkmark").font(.system(size: 11, weight: .heavy)).foregroundStyle(.white) }
                        }
                        .frame(width: 28, height: 28)
                        Text(d.day.formatted(.dateTime.weekday(.narrow))).font(.caption2.weight(.semibold)).foregroundStyle(Theme.ink2)
                    }
                    .frame(maxWidth: .infinity)
                }
            }
            .padding(.top, 12)
        } }
    }
}

struct ProgressRing: View {
    let value: Double
    var color: Color = Theme.leaf
    var width: CGFloat = 4
    var body: some View {
        ZStack {
            Circle().stroke(Theme.cardRaised, lineWidth: width)
            Circle().trim(from: 0, to: min(1, value)).stroke(color.gradient, style: StrokeStyle(lineWidth: width, lineCap: .round)).rotationEffect(.degrees(-90))
        }
        .animation(.spring, value: value)
    }
}

struct AlmostBlooming: View {
    let snap: GardenSnapshot
    @Binding var selected: Plant?
    var body: some View {
        let next = snap.plants.filter { $0.stageEnum == .sprout }.sorted { ($0.toNext, -$0.heard) < ($1.toNext, -$1.heard) }.prefix(8)
        if !next.isEmpty {
            VStack(alignment: .leading, spacing: 10) {
                Text("Almost blooming").font(Theme.title(20)).padding(.horizontal, 4)
                ScrollView(.horizontal) {
                    HStack(spacing: 12) {
                        ForEach(Array(next)) { p in
                            Button { selected = p } label: { BudCard(plant: p, bloomAt: snap.thresholds.bloom) }.buttonStyle(.plain)
                        }
                    }
                    .padding(.horizontal, 16)
                }
                .scrollIndicators(.hidden)
                .padding(.horizontal, -16)
            }
        }
    }
}

struct BudCard: View {
    let plant: Plant
    let bloomAt: Int
    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack(alignment: .bottom) {
                PlantIcon(plant: plant).frame(width: 46, height: 64)
                Spacer()
                ZStack {
                    ProgressRing(value: Double(plant.growth) / Double(bloomAt), color: Theme.leaf)
                    Text("\(plant.toNext)").font(.caption.weight(.bold))
                }
                .frame(width: 34, height: 34)
            }
            Text(plant.phrase).font(.headline).lineLimit(1)
            Text(plant.english ?? "").font(.caption).foregroundStyle(Theme.ink2).lineLimit(1)
            Text(plant.toNext == 1 ? "1 more hearing" : "\(plant.toNext) more hearings").font(.caption2.weight(.semibold)).foregroundStyle(Theme.leaf)
        }
        .padding(14)
        .frame(width: 150, alignment: .leading)
        .background(Theme.card, in: .rect(cornerRadius: 22))
        .overlay(RoundedRectangle(cornerRadius: 22).stroke(Theme.line, lineWidth: 1))
    }
}

struct EventRow: View {
    let event: GardenSnapshot.Event
    let plant: Plant?
    let now: Double
    var body: some View {
        HStack(spacing: 12) {
            icon.frame(width: 36, height: 36).background(Theme.cardRaised, in: .rect(cornerRadius: 12))
            VStack(alignment: .leading, spacing: 1) {
                Text(title).font(.subheadline.weight(.semibold))
                Text(subtitle).font(.caption).foregroundStyle(Theme.ink2)
            }
            Spacer(minLength: 0)
            Text(timeAgo(event.ts, now: now)).font(.caption2).foregroundStyle(Theme.ink2)
        }
    }
    @ViewBuilder private var icon: some View {
        switch event.kind {
        case "bloomed": if let plant { PlantIcon(plant: plant, flowerOnly: true).padding(4) }
        case "sprouted": Image(systemName: "leaf.fill").foregroundStyle(Theme.leaf)
        case "asked": Image(systemName: "drop.fill").foregroundStyle(.blue)
        default: Image(systemName: "waveform").foregroundStyle(Theme.ink2)
        }
    }
    private var title: String {
        switch event.kind {
        case "bloomed": "\(event.phrase) bloomed"
        case "sprouted": "\(event.phrase) sprouted"
        case "asked": "You asked about \(event.phrase)"
        default: "Heard \(event.phrase)"
        }
    }
    private var subtitle: String {
        switch event.kind {
        case "bloomed": "No more subtitles for this one"
        case "sprouted": "Telugu with subtitles from now on"
        case "asked": "It gets more help for a while"
        default: plant?.english ?? ""
        }
    }
}

struct LatestCard: View {
    let snap: GardenSnapshot
    var body: some View {
        Card {
            VStack(alignment: .leading, spacing: 14) {
                Text("Lately").font(Theme.title(20))
                if snap.recent.isEmpty {
                    Text("Your first call will plant the first seeds.").font(.subheadline).foregroundStyle(Theme.ink2)
                }
                ForEach(snap.recent.prefix(6)) { e in
                    EventRow(event: e, plant: snap.plant(e.phrase), now: snap.now)
                }
            }
        }
    }
}
