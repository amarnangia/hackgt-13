import SwiftUI
import WidgetKit

/// How the home-screen widgets look, in dark and light, without a home screen. Open with -widgetGallery 1.
struct WidgetGallery: View {
    @EnvironmentObject var model: GardenModel
    var body: some View {
        let entry = GardenEntry(date: .now, snapshot: model.snapshot, source: model.source)
        ScrollView {
            VStack(spacing: 16) {
                tile(.systemLarge, entry, .dark, CGSize(width: 356, height: 376))
                ForEach([ColorScheme.dark, .light], id: \.self) { scheme in
                    HStack(spacing: 16) {
                        tile(.systemSmall, entry, scheme, CGSize(width: 170, height: 170))
                        VStack(alignment: .leading, spacing: 12) {
                            GardenWidgetView(entry: entry, familyOverride: .accessoryRectangular).frame(width: 170, height: 58)
                            GardenWidgetView(entry: entry, familyOverride: .accessoryCircular).frame(width: 62, height: 62)
                        }
                        .foregroundStyle(.white)
                        .environment(\.colorScheme, .dark)
                    }
                    tile(.systemMedium, entry, scheme, CGSize(width: 356, height: 170))
                }
            }
            .padding(.top, 60).padding(.bottom, 40)
            .frame(maxWidth: .infinity)
        }
        .background(Color(hex: 0x6b645e))
        .ignoresSafeArea()
    }

    func tile(_ f: WidgetFamily, _ e: GardenEntry, _ scheme: ColorScheme, _ size: CGSize) -> some View {
        GardenWidgetView(entry: e, familyOverride: f)
            .frame(width: size.width, height: size.height)
            .background(WidgetPalette(scheme).bg)
            .clipShape(.rect(cornerRadius: 24))
            .environment(\.colorScheme, scheme)
    }
}
