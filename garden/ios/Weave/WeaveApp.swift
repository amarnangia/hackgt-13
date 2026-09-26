import SwiftUI

@main
struct WeaveApp: App {
    @StateObject private var people = People()

    var body: some Scene {
        WindowGroup {
            Root()
                .environmentObject(people)
                .preferredColorScheme(.dark)
                .tint(Theme.accent)
        }
    }
}

struct Root: View {
    @EnvironmentObject var people: People

    var body: some View {
        ZStack {
            if UserDefaults.standard.bool(forKey: "widgetGallery") {
                WidgetGallery()
            } else if people.profileName == nil {
                OnboardingView { c in
                    people.pendingSession = c
                    withAnimation(.easeOut(duration: 0.35)) { if people.profileName == nil { people.profileName = "Saanvi" } }
                }
                .transition(.opacity)
            } else {
                MainTabs().transition(.opacity)
            }
        }
        .animation(.easeOut(duration: 0.35), value: people.profileName == nil)
    }
}

/// Home (people and calls), Words (the family dictionary) and Progress.
struct MainTabs: View {
    @EnvironmentObject var people: People
    @State private var tab = UserDefaults.standard.integer(forKey: "startTab")   // screenshots: -startTab 1

    init() {
        let bar = UITabBarAppearance()
        bar.configureWithOpaqueBackground()
        bar.backgroundColor = UIColor(Theme.bg)
        bar.shadowColor = UIColor(Theme.border)
        for item in [bar.stackedLayoutAppearance, bar.inlineLayoutAppearance, bar.compactInlineLayoutAppearance] {
            item.normal.iconColor = UIColor(Theme.text3)
            item.normal.titleTextAttributes = [.foregroundColor: UIColor(Theme.text3)]
            item.selected.iconColor = UIColor(Theme.accent)
            item.selected.titleTextAttributes = [.foregroundColor: UIColor(Theme.accent)]
        }
        UITabBar.appearance().standardAppearance = bar
        UITabBar.appearance().scrollEdgeAppearance = bar
    }

    var body: some View {
        TabView(selection: $tab) {
            HomeView().tag(0).tabItem { Label("Home", systemImage: "person.2") }
            WordsView().tag(1).tabItem { Label("Words", systemImage: "character.book.closed") }
            ProgressView_().tag(2).tabItem { Label("Progress", systemImage: "chart.bar") }
            VoiceTab().tag(3).tabItem { Label("Voice", systemImage: "waveform") }
        }
        .task { await people.loadGrowth() }
        .sensoryFeedback(.selection, trigger: tab)
    }
}
