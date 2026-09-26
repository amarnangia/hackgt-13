import Charts
import SwiftUI

struct ProgressTab: View {
    @EnvironmentObject var model: GardenModel
    @Binding var selected: Plant?
    @State private var picked: Date?

    var body: some View {
        let snap = model.snapshot
        NavigationStack {
            ScrollView {
                VStack(alignment: .leading, spacing: 12) {
                    Grid(horizontalSpacing: 12, verticalSpacing: 12) {
                        GridRow { stat("\(snap.totals.bloom)", "Known", "of \(snap.totals.phrases) words", Theme.zari, Theme.gold); stat("\(snap.streak)", "Streak", snap.streak == 1 ? "day" : "days", Theme.kumkum, Theme.vermilion) }
                        GridRow { stat("\(snap.totals.heard)", "Hearings", "across all calls", Theme.peacockSilk, Theme.peacock); stat("\(snap.calls.minutes)", "Minutes", "\(snap.calls.count) calls", Theme.silk, Theme.rani) }
                    }
                    chart(snap)
                    stages(snap)
                    milestones(snap)
                }
                .padding(.horizontal, 20)
                .padding(.bottom, 32)
            }
            .scrollIndicators(.hidden)
            .background(Loom())
            .navigationTitle("Progress")
        }
    }

    private func stat<S: ShapeStyle>(_ value: String, _ label: String, _ sub: String, _ style: S, _ tint: Color) -> some View {
        Panel(padding: 16) {
            Eyebrow(label, color: tint)
            Text(value).font(Fonts.display(44)).foregroundStyle(style)
                .contentTransition(.numericText()).padding(.top, 2)
            Text(sub).font(Fonts.ui(12)).foregroundStyle(Theme.ink2)
        }
    }

    private func chart(_ snap: GardenSnapshot) -> some View {
        let day = picked.flatMap { p in snap.days.first { Calendar.current.isDate($0.day, inSameDayAs: p) } }
        let week = snap.days.suffix(7).reduce(0) { $0 + $1.heard }
        return Panel {
            Eyebrow(day.map { $0.day.formatted(.dateTime.weekday(.wide).month(.abbreviated).day()) } ?? "Last 14 days")
            HStack(alignment: .firstTextBaseline, spacing: 6) {
                Text("\(day?.heard ?? week)").font(Fonts.display(38)).foregroundStyle(Theme.ink)
                Text(day == nil ? "words heard this week" : "words heard").font(Fonts.ui(14)).foregroundStyle(Theme.ink2)
            }
            .foregroundStyle(Theme.ink)
            .padding(.top, 6)
            .animation(.easeOut(duration: 0.2), value: day?.date)
            Chart(snap.days) { d in
                BarMark(x: .value("Day", d.day, unit: .day), y: .value("Heard", d.heard), width: .ratio(0.6))
                    .foregroundStyle(LinearGradient(colors: [Theme.peacock.opacity(day == nil || day?.date == d.date ? 1 : 0.3), Theme.gold.opacity(day == nil || day?.date == d.date ? 1 : 0.3)], startPoint: .bottom, endPoint: .top))
                    .cornerRadius(3)
                if d.bloomed > 0 {
                    PointMark(x: .value("Day", d.day, unit: .day), y: .value("Heard", d.heard))
                        .symbolSize(22).foregroundStyle(Theme.rani)
                        .offset(y: -9)
                }
            }
            .chartXSelection(value: $picked)
            .chartXAxis {
                AxisMarks(values: .stride(by: .day, count: 2)) { _ in
                    AxisValueLabel(format: .dateTime.day(), centered: true).foregroundStyle(Theme.muted)
                }
            }
            .chartYAxis {
                AxisMarks(position: .trailing, values: .automatic(desiredCount: 3)) { _ in
                    AxisGridLine().foregroundStyle(Theme.border)
                    AxisValueLabel().foregroundStyle(Theme.muted)
                }
            }
            .frame(height: 170)
            .padding(.top, 14)
            HStack(spacing: 6) {
                Circle().fill(Theme.rani).frame(width: 6, height: 6)
                Text("A word became known that day").font(Fonts.ui(12)).foregroundStyle(Theme.muted)
            }
            .padding(.top, 12)
        }
    }

    private func stages(_ snap: GardenSnapshot) -> some View {
        let t = snap.thresholds
        let rows: [(Stage, String)] = [(.seed, "Heard under \(t.subtitle)×"), (.sprout, "\(t.subtitle)–\(t.bloom - 1)×"), (.bloom, "\(t.bloom)× or more")]
        return Panel(padding: 0) {
            Eyebrow("How words move").padding([.horizontal, .top], 20).padding(.bottom, 6)
            ForEach(Array(rows.enumerated()), id: \.offset) { i, row in
                if i > 0 { Rectangle().fill(Theme.border).frame(height: 1).padding(.leading, 50) }
                HStack(spacing: 16) {
                    RoundedRectangle(cornerRadius: 4).fill(row.0.fill).frame(width: 16, height: 16)
                    VStack(alignment: .leading, spacing: 2) {
                        Text(row.0.label).font(Fonts.display(21)).foregroundStyle(row.0.color)
                        Text("\(row.1) · \(row.0.meaning)").font(Fonts.ui(13)).foregroundStyle(Theme.ink2)
                    }
                }
                .padding(.horizontal, 20).padding(.vertical, 12)
            }
            Text("Tapping “I didn't catch this one” moves a word back a step.")
                .font(Fonts.ui(12)).foregroundStyle(Theme.muted)
                .padding(.horizontal, 20).padding(.top, 4).padding(.bottom, 18)
        }
    }

    private func milestones(_ snap: GardenSnapshot) -> some View {
        let events = snap.recent.filter { $0.kind != "heard" }.prefix(8)
        return Panel(padding: 0) {
            Eyebrow("Milestones").padding([.horizontal, .top], 20).padding(.bottom, 6)
            if events.isEmpty {
                Text("Words you learn will show up here.").font(Fonts.ui(14)).foregroundStyle(Theme.ink2)
                    .padding(.horizontal, 20).padding(.bottom, 18)
            }
            ForEach(Array(events.enumerated()), id: \.element.id) { i, e in
                if i > 0 { Rectangle().fill(Theme.border).frame(height: 1).padding(.leading, 64) }
                Button { selected = snap.plant(e.phrase) } label: { EventRow(event: e, now: snap.now) }.buttonStyle(Pressable())
            }
            Spacer().frame(height: 6)
        }
    }
}

struct EventRow: View {
    let event: GardenSnapshot.Event
    let now: Double
    var body: some View {
        HStack(spacing: 14) {
            Image(systemName: icon).font(.system(size: 13, weight: .semibold)).foregroundStyle(tint)
                .frame(width: 32, height: 32)
                .background(tint.opacity(0.14), in: .rect(cornerRadius: 10))
                .overlay(RoundedRectangle(cornerRadius: 10).strokeBorder(tint.opacity(0.25), lineWidth: 1))
            (Text(event.phrase).font(Fonts.telugu(16)).foregroundColor(Theme.ink) + Text(" " + verb).font(Fonts.ui(15)).foregroundColor(Theme.ink2))
                .lineLimit(1)
            Spacer(minLength: 8)
            Text(timeAgo(event.ts, now: now)).font(Fonts.ui(12)).monospacedDigit().foregroundStyle(Theme.muted)
        }
        .padding(.horizontal, 20).padding(.vertical, 11)
        .contentShape(Rectangle())
    }
    private var tint: Color {
        switch event.kind { case "bloomed": Theme.gold; case "sprouted": Theme.peacock; case "asked": Theme.vermilion; default: Theme.ink2 }
    }
    private var icon: String {
        switch event.kind { case "bloomed": "checkmark"; case "sprouted": "arrow.up.right"; case "asked": "arrow.uturn.backward"; default: "waveform" }
    }
    private var verb: String {
        switch event.kind { case "bloomed": "is now known"; case "sprouted": "moved to learning"; case "asked": "needs more help"; default: "heard" }
    }
}
