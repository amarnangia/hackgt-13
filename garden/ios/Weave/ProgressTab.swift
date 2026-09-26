import Charts
import SwiftUI

struct ProgressTab: View {
    @EnvironmentObject var model: GardenModel
    @State private var picked: Date?

    var body: some View {
        let snap = model.snapshot
        NavigationStack {
            ScrollView {
                VStack(spacing: 16) {
                    LazyVGrid(columns: [GridItem(.flexible(), spacing: 12), GridItem(.flexible())], spacing: 12) {
                        StatTile(value: "\(snap.totals.heard)", label: "Words heard", symbol: "waveform", color: Theme.leaf)
                        StatTile(value: "\(snap.totals.phrases)", label: "Words met", symbol: "sparkles", color: Theme.marigold)
                        StatTile(value: "\(snap.calls.count)", label: "Calls", symbol: "phone.fill", color: .blue)
                        StatTile(value: "\(snap.calls.minutes)", label: "Minutes listening", symbol: "clock.fill", color: .purple)
                    }
                    chart(snap)
                    JourneyCard(snap: snap)
                    milestones(snap)
                }
                .padding(16)
            }
            .background(Theme.background)
            .navigationTitle("Progress")
        }
    }

    private func chart(_ snap: GardenSnapshot) -> some View {
        let pickedDay = picked.flatMap { p in snap.days.first { Calendar.current.isDate($0.day, inSameDayAs: p) } }
        let week = snap.days.suffix(7).reduce(0) { $0 + $1.heard }
        return Card {
            VStack(alignment: .leading, spacing: 12) {
                VStack(alignment: .leading, spacing: 2) {
                    Text(pickedDay.map { $0.day.formatted(.dateTime.weekday(.wide).month().day()) } ?? "Last 14 days")
                        .font(.subheadline.weight(.semibold)).foregroundStyle(Theme.ink2)
                    Text(pickedDay.map { "\($0.heard) words heard" } ?? "\(week) words this week").font(Theme.title(24))
                    if let d = pickedDay, d.bloomed + d.new > 0 {
                        Text([d.new > 0 ? "\(d.new) new seeds" : nil, d.bloomed > 0 ? "\(d.bloomed) bloomed" : nil].compactMap { $0 }.joined(separator: " · "))
                            .font(.footnote).foregroundStyle(Theme.ink2)
                    }
                }
                .animation(.snappy, value: pickedDay?.date)
                Chart(snap.days) { d in
                    BarMark(x: .value("Day", d.day, unit: .day), y: .value("Heard", d.heard), width: .ratio(0.62))
                        .foregroundStyle(Theme.leaf.gradient)
                        .cornerRadius(5)
                        .opacity(pickedDay == nil || pickedDay?.date == d.date ? 1 : 0.35)
                        .annotation(position: .top, spacing: 3) {
                            if d.bloomed > 0 {
                                PlantIcon(plant: .example(.bloom), flowerOnly: true).frame(width: 14, height: 14)
                            }
                        }
                }
                .chartXSelection(value: $picked)
                .chartXAxis {
                    AxisMarks(values: .stride(by: .day, count: 2)) { _ in
                        AxisValueLabel(format: .dateTime.day(), centered: true)
                    }
                }
                .chartYAxis { AxisMarks(position: .leading) { _ in AxisGridLine().foregroundStyle(Theme.line); AxisValueLabel() } }
                .frame(height: 200)
                Text("A flower marks a day a word bloomed. Touch the chart for details.").font(.caption).foregroundStyle(Theme.ink2)
            }
        }
    }

    private func milestones(_ snap: GardenSnapshot) -> some View {
        let events = snap.recent.filter { $0.kind != "heard" }
        return Card {
            VStack(alignment: .leading, spacing: 14) {
                Text("Milestones").font(Theme.title(20))
                if events.isEmpty { Text("Blooms and sprouts will show up here.").font(.subheadline).foregroundStyle(Theme.ink2) }
                ForEach(events.prefix(8)) { e in EventRow(event: e, plant: snap.plant(e.phrase), now: snap.now) }
            }
        }
    }
}

struct StatTile: View {
    let value: String
    let label: String
    let symbol: String
    let color: Color
    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            Image(systemName: symbol).font(.system(size: 15, weight: .semibold)).foregroundStyle(color)
                .frame(width: 32, height: 32).background(color.opacity(0.14), in: .rect(cornerRadius: 10))
            Text(value).font(Theme.title(28)).contentTransition(.numericText())
            Text(label).font(.caption.weight(.semibold)).foregroundStyle(Theme.ink2)
        }
        .padding(14)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(Theme.card, in: .rect(cornerRadius: 22))
        .overlay(RoundedRectangle(cornerRadius: 22).stroke(Theme.line, lineWidth: 1))
    }
}

/// How a word moves from seed to bloom.
struct JourneyCard: View {
    let snap: GardenSnapshot
    var body: some View {
        let t = snap.thresholds
        Card {
            VStack(alignment: .leading, spacing: 14) {
                Text("How words grow").font(Theme.title(20))
                ForEach(Stage.allCases.reversed()) { s in
                    HStack(spacing: 14) {
                        PlantIcon(plant: .example(s), flowerOnly: s == .bloom).frame(width: 40, height: 40)
                        VStack(alignment: .leading, spacing: 1) {
                            Text(s.title).font(.subheadline.weight(.bold))
                            Text("\(range(s, t)) · \(s.meaning)").font(.caption).foregroundStyle(Theme.ink2)
                        }
                    }
                }
                Text("Tap “I didn't catch that” on a word and it goes back a stage.").font(.caption).foregroundStyle(Theme.ink2)
            }
        }
    }
    func range(_ s: Stage, _ t: GardenSnapshot.Thresholds) -> String {
        switch s {
        case .seed: "Heard under \(t.subtitle)×"
        case .sprout: "\(t.subtitle)–\(t.bloom - 1)×"
        case .bloom: "\(t.bloom)× or more"
        }
    }
}
