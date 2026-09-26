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
            // Now, then at each 3-hour mark, so the suggested topic rotates even if a refresh is late.
            let block = 10800.0, next = (Date.now.timeIntervalSince1970 / block).rounded(.down) * block + block
            let entries = [GardenEntry(date: .now, snapshot: s, source: src)]
                + (0..<4).map { GardenEntry(date: Date(timeIntervalSince1970: next + Double($0) * block), snapshot: s, source: src) }
            completion(Timeline(entries: entries, policy: .after(.now.addingTimeInterval(15 * 60))))
        }
    }
}

struct GardenWidget: Widget {
    var body: some WidgetConfiguration {
        StaticConfiguration(kind: "WeaveNextCall", provider: GardenProvider()) { entry in
            GardenWidgetView(entry: entry).widgetURL(URL(string: "weave://next-call"))
        }
        .configurationDisplayName("Next call")
        .description("Something to talk about on your next call, from the words you're learning.")
        .supportedFamilies([.systemSmall, .systemMedium, .systemLarge, .accessoryCircular, .accessoryRectangular, .accessoryInline])
        .contentMarginsDisabled()
    }
}

@main
struct WeaveWidgets: WidgetBundle {
    var body: some Widget { GardenWidget() }
}

#Preview(as: .systemMedium) { GardenWidget() } timeline: { GardenEntry(date: .now, snapshot: .sample, source: .demo) }
