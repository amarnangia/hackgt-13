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
                HomeView().transition(.opacity)
            }
        }
        .animation(.easeOut(duration: 0.35), value: people.profileName == nil)
    }
}
