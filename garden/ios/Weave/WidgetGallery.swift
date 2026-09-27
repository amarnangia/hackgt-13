import SwiftUI
import WidgetKit

/// How the home-screen widgets look, without a home screen. Open with -widgetGallery 1.
struct WidgetGallery: View {
    @State private var snap: GardenSnapshot = .empty
    @State private var source: GardenClient.Source = .offline
    @State private var questions: [Question] = []

    var body: some View {
        let entry = GardenEntry(date: .now, snapshot: snap, source: source, questions: questions)
        ScrollView {
            VStack(spacing: 16) {
                tile(.systemLarge, entry, CGSize(width: 356, height: 376))
                HStack(spacing: 16) {
                    tile(.systemSmall, entry, CGSize(width: 170, height: 170))
                    VStack(alignment: .leading, spacing: 12) {
                        GardenWidgetView(entry: entry, familyOverride: .accessoryRectangular).frame(width: 170, height: 58)
                        GardenWidgetView(entry: entry, familyOverride: .accessoryCircular).frame(width: 62, height: 62)
                    }
                    .foregroundStyle(.white)
                }
                tile(.systemMedium, entry, CGSize(width: 356, height: 170))
            }
            .padding(.top, 60).padding(.bottom, 40)
            .frame(maxWidth: .infinity)
        }
        .background(LinearGradient(colors: [Color(hex: 0x1e3a2a), Color(hex: 0x141d18)], startPoint: .top, endPoint: .bottom))
        .ignoresSafeArea()
        .task {
            let (s, src) = await GardenClient.load(); snap = s; source = src
            questions = await GardenClient.calls().first { !($0.questions ?? []).isEmpty }?.questions ?? []
        }
    }

    func tile(_ f: WidgetFamily, _ e: GardenEntry, _ size: CGSize) -> some View {
        GardenWidgetView(entry: e, familyOverride: f)
            .frame(width: size.width, height: size.height)
            .background(WidgetBackdrop())
            .clipShape(.rect(cornerRadius: 24))
    }
}
