import SwiftUI
import WidgetKit

struct GardenProvider: TimelineProvider {
    func placeholder(in context: Context) -> GardenEntry { GardenEntry(date: .now, snapshot: .sample, source: .demo) }

    func getSnapshot(in context: Context, completion: @escaping (GardenEntry) -> Void) {
        if context.isPreview { return completion(placeholder(in: context)) }
        Task { let (s, src) = await GardenClient.load(); completion(GardenEntry(date: .now, snapshot: s, source: src)) }
    }

    func getTimeline(in context: Context, completion: @escaping (Timeline<GardenEntry>) -> Void) {
        Task {
            let (s, src) = await GardenClient.load()
            // Same garden, redrawn every 30 minutes so the sky keeps up with the time of day.
            let entries = (0..<6).map { GardenEntry(date: Date.now.addingTimeInterval(Double($0) * 1800), snapshot: s, source: src) }
            completion(Timeline(entries: entries, policy: .after(.now.addingTimeInterval(15 * 60))))
        }
    }
}

struct GardenWidget: Widget {
    var body: some WidgetConfiguration {
        StaticConfiguration(kind: "WeaveGarden", provider: GardenProvider()) { entry in
            GardenWidgetView(entry: entry).widgetURL(URL(string: "weave://garden"))
        }
        .configurationDisplayName("Garden")
        .description("Your Telugu words growing from seed to bloom.")
        .supportedFamilies([.systemSmall, .systemMedium, .systemLarge, .accessoryCircular, .accessoryRectangular, .accessoryInline])
        .contentMarginsDisabled()
    }
}

@main
struct WeaveWidgets: WidgetBundle {
    var body: some Widget { GardenWidget() }
}

#Preview(as: .systemMedium) { GardenWidget() } timeline: { GardenEntry(date: .now, snapshot: .sample, source: .demo) }
