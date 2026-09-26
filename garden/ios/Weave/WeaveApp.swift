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
            .tint(Theme.accent)
            .onChange(of: phase, initial: true) { _, p in
                if p == .active { model.start() } else { model.stop() }
            }
        }
    }
}

struct RootView: View {
    @EnvironmentObject var model: GardenModel
    // Launch arguments for screenshots/testing, e.g. -startTab 2 -openWord ఇడ్లీ
    @State private var tab = UserDefaults.standard.integer(forKey: "startTab")
    @State private var selected: Plant?

    init() {
        // Solid tab bar with a hairline, instead of the translucent default that tints with the content behind it.
        let bar = UITabBarAppearance()
        bar.configureWithOpaqueBackground()
        bar.backgroundColor = UIColor(Theme.bg)
        bar.shadowColor = UIColor(Theme.border)
        UITabBar.appearance().standardAppearance = bar
        UITabBar.appearance().scrollEdgeAppearance = bar
    }

    var body: some View {
        TabView(selection: $tab) {
            TodayTab(selected: $selected)
                .tabItem { Label("Today", systemImage: "text.bubble") }.tag(0)
            WordsTab(selected: $selected)
                .tabItem { Label("Words", systemImage: "character.book.closed") }.tag(1)
            ProgressTab(selected: $selected)
                .tabItem { Label("Progress", systemImage: "chart.bar") }.tag(2)
        }
        .sheet(item: $selected) { plant in
            WordDetail(plant: model.snapshot.plant(plant.phrase) ?? plant)
                .presentationDetents([.medium, .large])
                .presentationCornerRadius(24)
                .presentationBackground(Theme.bg)
        }
        .overlay(alignment: .top) {
            if let p = model.celebration {
                KnownBanner(plant: p)
                    .transition(.move(edge: .top).combined(with: .opacity))
                    .onTapGesture { selected = p; model.celebration = nil }
                    .task(id: p.phrase) {
                        try? await Task.sleep(for: .seconds(3.5))
                        withAnimation(.snappy) { model.celebration = nil }
                    }
            }
        }
        .animation(.snappy(duration: 0.35), value: model.celebration?.phrase)
        .onOpenURL { _ in tab = 0 }
        .task {
            if let w = UserDefaults.standard.string(forKey: "openWord") {
                try? await Task.sleep(for: .seconds(1))
                selected = model.snapshot.plant(w)
            }
        }
    }
}

struct KnownBanner: View {
    let plant: Plant
    var body: some View {
        HStack(spacing: 12) {
            Image(systemName: "checkmark").font(.system(size: 13, weight: .bold)).foregroundStyle(Theme.accent)
                .frame(width: 30, height: 30).background(Theme.accent.opacity(0.12), in: .rect(cornerRadius: 9))
            VStack(alignment: .leading, spacing: 1) {
                Text("\(plant.phrase) is now known").font(.system(size: 15, weight: .semibold)).foregroundStyle(Theme.ink)
                Text("No more subtitles for this one").font(.system(size: 13)).foregroundStyle(Theme.ink2)
            }
            Spacer(minLength: 0)
        }
        .padding(14)
        .background(Theme.surface, in: .rect(cornerRadius: Theme.radius))
        .overlay(RoundedRectangle(cornerRadius: Theme.radius).strokeBorder(Theme.border, lineWidth: 1))
        .padding(.horizontal, 16)
        .padding(.top, 4)
    }
}
