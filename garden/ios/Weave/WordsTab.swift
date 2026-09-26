import SwiftUI

struct WordsTab: View {
    @EnvironmentObject var model: GardenModel
    @Binding var selected: Plant?
    @State private var filter: Stage? = nil
    @State private var query = ""

    var body: some View {
        let snap = model.snapshot
        let words = snap.plants
            .filter { filter == nil || $0.stageEnum == filter }
            .filter { query.isEmpty || [$0.phrase, $0.english ?? "", $0.roman ?? ""].contains { $0.localizedCaseInsensitiveContains(query) } }
            .sorted { ($0.growth, $0.heard) > ($1.growth, $1.heard) }
        NavigationStack {
            ScrollView {
                VStack(spacing: 14) {
                    ScrollView(.horizontal) {
                        HStack(spacing: 8) {
                            FilterChip(title: "All", count: snap.totals.phrases, on: filter == nil) { filter = nil }
                            ForEach(Stage.allCases) { s in
                                FilterChip(title: s.title, count: s == .bloom ? snap.totals.bloom : s == .sprout ? snap.totals.sprout : snap.totals.seed,
                                           on: filter == s, color: s.color) { filter = filter == s ? nil : s }
                            }
                        }
                        .padding(.horizontal, 16)
                    }
                    .scrollIndicators(.hidden)

                    LazyVStack(spacing: 10) {
                        ForEach(words) { p in
                            Button { selected = p } label: { WordRow(plant: p, bloomAt: snap.thresholds.bloom) }.buttonStyle(.plain)
                        }
                        if words.isEmpty {
                            ContentUnavailableView("No words yet", systemImage: "leaf", description: Text("Words you hear on calls grow here."))
                                .padding(.top, 40)
                        }
                    }
                    .padding(.horizontal, 16)
                    .animation(.spring(duration: 0.35), value: filter)
                }
                .padding(.bottom, 24)
            }
            .background(Theme.background)
            .navigationTitle("Words")
            .searchable(text: $query, prompt: "Telugu or English")
        }
    }
}

struct FilterChip: View {
    let title: String
    let count: Int
    let on: Bool
    var color: Color = Theme.ink
    let action: () -> Void
    var body: some View {
        Button(action: action) {
            HStack(spacing: 6) {
                Text(title).font(.subheadline.weight(.semibold))
                Text("\(count)").font(.caption.weight(.bold)).padding(.horizontal, 6).padding(.vertical, 2)
                    .background(on ? Color.white.opacity(0.25) : Theme.cardRaised, in: .capsule)
            }
            .padding(.horizontal, 14).frame(height: 36)
            .foregroundStyle(on ? .white : Theme.ink)
            .background(on ? AnyShapeStyle(color.gradient) : AnyShapeStyle(Theme.card), in: .capsule)
            .overlay(Capsule().stroke(on ? .clear : Theme.line, lineWidth: 1))
        }
        .buttonStyle(.plain)
        .sensoryFeedback(.selection, trigger: on)
    }
}

struct WordRow: View {
    let plant: Plant
    let bloomAt: Int
    var body: some View {
        HStack(spacing: 14) {
            PlantIcon(plant: plant, flowerOnly: plant.stageEnum == .bloom)
                .padding(plant.stageEnum == .bloom ? 6 : 2)
                .frame(width: 52, height: 52)
                .background(plant.stageEnum.color.opacity(0.12), in: .rect(cornerRadius: 16))
            VStack(alignment: .leading, spacing: 2) {
                Text(plant.phrase).font(.title3.weight(.semibold))
                Text([plant.romanIfUseful, plant.english].compactMap { $0 }.joined(separator: " · "))
                    .font(.subheadline).foregroundStyle(Theme.ink2).lineLimit(1)
            }
            Spacer(minLength: 8)
            VStack(spacing: 3) {
                ZStack {
                    ProgressRing(value: Double(plant.growth) / Double(bloomAt), color: plant.stageEnum.color, width: 3.5)
                    Text("\(plant.heard)×").font(.system(size: 10, weight: .bold))
                }
                .frame(width: 38, height: 38)
            }
            if plant.thirsty { Image(systemName: "drop.fill").font(.caption).foregroundStyle(.blue) }
        }
        .padding(12)
        .background(Theme.card, in: .rect(cornerRadius: 22))
        .overlay(RoundedRectangle(cornerRadius: 22).stroke(Theme.line, lineWidth: 1))
    }
}
