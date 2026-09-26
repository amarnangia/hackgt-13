import SwiftUI
import WidgetKit

/// How the home-screen widgets look, for checking them without a home screen. Open with -widgetGallery 1.
struct WidgetGallery: View {
    @EnvironmentObject var model: GardenModel
    var body: some View {
        let entry = GardenEntry(date: .now, snapshot: model.snapshot, source: model.source)
        ScrollView {
            VStack(spacing: 22) {
                HStack(spacing: 22) {
                    tile(.systemSmall, entry, CGSize(width: 170, height: 170))
                    VStack(spacing: 14) {
                        GardenWidgetView(entry: entry, familyOverride: .accessoryRectangular)
                            .frame(width: 160, height: 72).foregroundStyle(.white)
                        GardenWidgetView(entry: entry, familyOverride: .accessoryCircular).frame(width: 72, height: 72).foregroundStyle(.white)
                    }
                }
                tile(.systemMedium, entry, CGSize(width: 364, height: 170))
                tile(.systemLarge, entry, CGSize(width: 364, height: 382))
            }
            .padding(.top, 70).padding(.bottom, 40)
            .frame(maxWidth: .infinity)
        }
        .background(LinearGradient(colors: [Color(hex: 0x3b3f8f), Color(hex: 0xc0587e), Color(hex: 0xf0a060)], startPoint: .top, endPoint: .bottom))
        .ignoresSafeArea()
    }

    func tile(_ f: WidgetFamily, _ e: GardenEntry, _ size: CGSize) -> some View {
        ZStack {
            WidgetScene(entry: e, maxPlants: f == .systemSmall ? 5 : f == .systemMedium ? 10 : 14, rows: f == .systemLarge ? 2 : 1)
            GardenWidgetView(entry: e, familyOverride: f)
        }
        .frame(width: size.width, height: size.height)
        .clipShape(.rect(cornerRadius: 24))
        .shadow(color: .black.opacity(0.25), radius: 14, y: 6)
    }
}
