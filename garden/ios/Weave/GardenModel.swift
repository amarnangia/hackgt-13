import SwiftUI
import WidgetKit

@MainActor
final class GardenModel: ObservableObject {
    @Published private(set) var snapshot: GardenSnapshot = .sample
    @Published private(set) var source: GardenClient.Source = .demo
    @Published private(set) var grown: [String: Double] = [:]      // phrase -> when it last grew (reference-date seconds)
    @Published var celebration: Plant?                             // just bloomed: shown as a banner
    @Published private(set) var rotation = Int(Date().timeIntervalSince1970 / 10800)  // which conversation starters lead
    private var polling: Task<Void, Never>?
    private var lastWidgetReload = Date.distantPast

    func start() {
        guard polling == nil else { return }
        polling = Task { [weak self] in
            while !Task.isCancelled {
                await self?.refresh()
                try? await Task.sleep(for: .seconds(3))
            }
        }
    }

    func stop() {
        polling?.cancel()
        polling = nil
    }

    func refresh() async {
        let (next, src) = await GardenClient.load()
        let before = Dictionary(uniqueKeysWithValues: snapshot.plants.map { ($0.phrase, $0) })
        let now = Date().timeIntervalSinceReferenceDate
        var bloomed: Plant?
        if src == source {  // don't animate the whole garden when switching between demo and live
            for p in next.plants where before[p.phrase]?.growth != p.growth {
                grown[p.phrase] = now
                if p.stageEnum == .bloom, before[p.phrase]?.stageEnum != .bloom { bloomed = p }
            }
        }
        if next != snapshot { snapshot = next }
        source = src
        if let bloomed {
            celebration = bloomed
            UINotificationFeedbackGenerator().notificationOccurred(.success)
        }
        if src == .live, Date().timeIntervalSince(lastWidgetReload) > 60 {
            lastWidgetReload = Date()
            WidgetCenter.shared.reloadAllTimelines()
        }
    }

    func shuffle() {
        rotation += 1
    }

    func asked(_ plant: Plant) async {
        try? await GardenClient.asked(plant.phrase)
        await refresh()
    }

    func setDemo(_ on: Bool) async {
        GardenClient.demoMode = on
        await refresh()
        WidgetCenter.shared.reloadAllTimelines()
    }
}
