import SwiftUI

struct WordsTab: View {
    @EnvironmentObject var model: GardenModel
    @Binding var selected: Plant?
    @State private var filter: Stage? = nil
    @State private var query = ""
    @Namespace private var pill

    var body: some View {
        let snap = model.snapshot
        let words = snap.plants
            .filter { filter == nil || $0.stageEnum == filter }
            .filter { query.isEmpty || [$0.phrase, $0.english ?? "", $0.roman ?? ""].contains { $0.localizedCaseInsensitiveContains(query) } }
            .sorted { ($0.growth, $0.heard) > ($1.growth, $1.heard) }
        NavigationStack {
            ScrollView {
                VStack(alignment: .leading, spacing: 14) {
                    segmented(snap)
                    if words.isEmpty {
                        Panel { Text(query.isEmpty ? "Words you hear on calls show up here." : "No words match “\(query)”.")
                            .font(Fonts.ui(15)).foregroundStyle(Theme.ink2) }
                    } else {
                        Panel(padding: 0) {
                            ForEach(Array(words.enumerated()), id: \.element.id) { i, p in
                                if i > 0 { Rectangle().fill(Theme.border).frame(height: 1).padding(.leading, 20) }
                                Button { selected = p } label: { WordRow(plant: p) }.buttonStyle(Pressable())
                            }
                        }
                    }
                }
                .padding(.horizontal, 20)
                .padding(.bottom, 32)
                .animation(.easeOut(duration: 0.2), value: filter)
            }
            .scrollIndicators(.hidden)
            .background(Loom())
            .navigationTitle("Words")
            .searchable(text: $query, prompt: "Telugu or English")
        }
    }

    private func segmented(_ snap: GardenSnapshot) -> some View {
        let options: [(Stage?, String, Int)] = [(nil, "All", snap.totals.phrases), (.bloom, "Known", snap.totals.bloom),
                                                (.sprout, "Learning", snap.totals.sprout), (.seed, "New", snap.totals.seed)]
        return HStack(spacing: 2) {
            ForEach(options, id: \.1) { stage, title, count in
                let on = filter == stage
                Button { filter = stage } label: {
                    HStack(spacing: 5) {
                        Text(title).font(Fonts.ui(13, .semibold))
                        Text("\(count)").font(Fonts.ui(12, .medium)).monospacedDigit().foregroundStyle(Theme.muted)
                    }
                    .foregroundStyle(on ? Theme.ink : Theme.ink2)
                    .frame(maxWidth: .infinity).frame(height: 32)
                    .background {
                        if on {
                            RoundedRectangle(cornerRadius: 9).fill(Color.white.opacity(0.09))
                                .overlay(RoundedRectangle(cornerRadius: 9).strokeBorder(stage?.color.opacity(0.6) ?? Theme.gold.opacity(0.5), lineWidth: 1))
                                .matchedGeometryEffect(id: "pill", in: pill)
                        }
                    }
                    .contentShape(Rectangle())
                }
                .buttonStyle(.plain)
                .sensoryFeedback(.selection, trigger: on)
            }
        }
        .padding(3)
        .background(Theme.surface, in: .rect(cornerRadius: 12))
        .overlay(RoundedRectangle(cornerRadius: 12).strokeBorder(Theme.sheen, lineWidth: 1))
        .animation(.snappy(duration: 0.25), value: filter)
    }
}

struct WordRow: View {
    let plant: Plant
    var body: some View {
        HStack(spacing: 14) {
            VStack(alignment: .leading, spacing: 2) {
                Text(plant.phrase).font(Fonts.telugu(19)).foregroundStyle(Theme.ink)
                Text([plant.romanIfUseful, plant.english].compactMap { $0 }.joined(separator: " · "))
                    .font(Fonts.ui(13)).foregroundStyle(Theme.ink2).lineLimit(1)
            }
            Spacer(minLength: 8)
            VStack(alignment: .trailing, spacing: 6) {
                HStack(spacing: 5) {
                    if plant.thirsty { Image(systemName: "arrow.uturn.backward").font(.system(size: 9, weight: .bold)).foregroundStyle(Theme.vermilion) }
                    Text(plant.stageEnum.label).font(Fonts.ui(11, .semibold)).foregroundStyle(plant.stageEnum.color)
                }
                GrowthBar(growth: plant.growth, height: 3).frame(width: 56)
            }
        }
        .padding(.horizontal, 20).padding(.vertical, 13)
        .contentShape(Rectangle())
    }
}
