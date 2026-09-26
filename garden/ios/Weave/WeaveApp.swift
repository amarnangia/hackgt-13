import SwiftUI

@main
struct WeaveApp: App {
    @StateObject private var model = GardenModel()
    @Environment(\.scenePhase) private var phase

    var body: some Scene {
        WindowGroup {
            Group {
                if UserDefaults.standard.bool(forKey: "widgetGallery") { WidgetGallery() } else { RootView() }
            }
                .environmentObject(model)
                .tint(Theme.marigold)
                .onChange(of: phase, initial: true) { _, p in
                    if p == .active { model.start() } else { model.stop() }
                }
        }
    }
}

struct RootView: View {
    @EnvironmentObject var model: GardenModel
    // Launch arguments for screenshots/testing, e.g. -startTab 2 -openWord ఇడ్లీ -skyOverride 12
    @State private var tab = UserDefaults.standard.integer(forKey: "startTab")
    @State private var selected: Plant?

    var body: some View {
        TabView(selection: $tab) {
            GardenTab(selected: $selected)
                .tabItem { Label("Garden", systemImage: "leaf.fill") }.tag(0)
            WordsTab(selected: $selected)
                .tabItem { Label("Words", systemImage: "character.book.closed.fill") }.tag(1)
            ProgressTab()
                .tabItem { Label("Progress", systemImage: "chart.bar.fill") }.tag(2)
        }
        .sheet(item: $selected) { plant in
            WordDetail(plant: model.snapshot.plant(plant.phrase) ?? plant)
                .presentationDetents([.medium, .large])
                .presentationCornerRadius(32)
        }
        .overlay(alignment: .top) {
            if let p = model.celebration {
                BloomBanner(plant: p)
                    .transition(.move(edge: .top).combined(with: .opacity))
                    .onTapGesture { selected = p; model.celebration = nil }
                    .task(id: p.phrase) {
                        try? await Task.sleep(for: .seconds(3.5))
                        withAnimation(.spring) { model.celebration = nil }
                    }
            }
        }
        .animation(.spring(duration: 0.5), value: model.celebration?.phrase)
        .onOpenURL { _ in tab = 0 }
        .task {
            if let w = UserDefaults.standard.string(forKey: "openWord") {
                try? await Task.sleep(for: .seconds(1))
                selected = model.snapshot.plant(w)
            }
        }
    }
}

struct BloomBanner: View {
    let plant: Plant
    var body: some View {
        HStack(spacing: 12) {
            PlantIcon(plant: plant, flowerOnly: true).frame(width: 40, height: 40)
            VStack(alignment: .leading, spacing: 1) {
                Text("\(plant.phrase) bloomed!").font(.headline)
                Text("You'll hear it without subtitles now").font(.subheadline).foregroundStyle(.secondary)
            }
            Spacer(minLength: 0)
        }
        .padding(.horizontal, 16).padding(.vertical, 12)
        .background(.regularMaterial, in: .rect(cornerRadius: 22))
        .shadow(color: .black.opacity(0.15), radius: 20, y: 8)
        .padding(.horizontal, 16)
        .padding(.top, 6)
    }
}
