import SwiftUI

struct WordDetail: View {
    @EnvironmentObject var model: GardenModel
    @Environment(\.dismiss) private var dismiss
    let plant: Plant
    @State private var sending = false

    var body: some View {
        let t = model.snapshot.thresholds
        ScrollView {
            VStack(alignment: .leading, spacing: 18) {
                // the plant on its own little patch of garden
                TimelineView(.animation(minimumInterval: 1 / 30)) { tl in
                    Canvas { ctx, size in
                        let sky = SkyPalette.at(hour: currentHour(tl.date))
                        ctx.fill(Path(CGRect(origin: .zero, size: size)),
                                 with: .linearGradient(Gradient(colors: [sky.skyTop.color, sky.skyBottom.color]), startPoint: .zero, endPoint: CGPoint(x: 0, y: size.height * 0.75)))
                        ctx.fill(GardenPainter.hill(w: size.width, h: size.height, y: size.height * 0.72, amp: 10, shift: 0.2), with: .color(sky.hillFront.color))
                        ctx.fill(Path(CGRect(x: 0, y: size.height * 0.8, width: size.width, height: size.height * 0.2)), with: .color(sky.groundTop.color))
                        var c = ctx
                        let s = size.height * 0.72 / (GardenPainter.height(of: plant) + 10)
                        c.translateBy(x: size.width / 2, y: size.height * 0.9)
                        c.scaleBy(x: s, y: s)
                        GardenPainter.drawPlant(c, plant, sway: sin(tl.date.timeIntervalSinceReferenceDate * 0.9) * 0.03, lean: 0, soil: sky.soil.color)
                    }
                }
                .frame(height: 210)
                .clipShape(.rect(cornerRadius: 26))

                VStack(alignment: .leading, spacing: 4) {
                    HStack {
                        Label(plant.stageEnum.title, systemImage: plant.stageEnum.symbol)
                            .font(.caption.weight(.bold)).foregroundStyle(plant.stageEnum.color)
                            .padding(.horizontal, 10).padding(.vertical, 5).background(plant.stageEnum.color.opacity(0.14), in: .capsule)
                        if plant.stageEnum == .bloom {
                            Text(plant.flower.name).font(.caption.weight(.semibold)).foregroundStyle(Theme.ink2)
                        }
                    }
                    Text(plant.phrase).font(.system(size: 40, weight: .bold)).padding(.top, 6)
                    if let roman = plant.romanIfUseful { Text(roman).font(.title3).italic().foregroundStyle(Theme.ink2) }
                    if let en = plant.english { Text(en).font(Theme.title(24)).padding(.top, 2) }
                }

                if let note = plant.note {
                    HStack(alignment: .top, spacing: 10) {
                        Image(systemName: "text.quote").foregroundStyle(Theme.marigold)
                        Text(note).font(.callout)
                    }
                    .padding(14).frame(maxWidth: .infinity, alignment: .leading)
                    .background(Theme.cardRaised, in: .rect(cornerRadius: 18))
                }

                GrowthTrack(plant: plant, t: t)

                HStack(spacing: 12) {
                    Image(systemName: plant.stageEnum == .seed ? "speaker.wave.2.fill" : plant.stageEnum == .sprout ? "captions.bubble.fill" : "ear.fill")
                        .foregroundStyle(plant.stageEnum.color).frame(width: 36, height: 36)
                        .background(plant.stageEnum.color.opacity(0.14), in: .rect(cornerRadius: 12))
                    VStack(alignment: .leading, spacing: 1) {
                        Text("On your next call").font(.caption.weight(.semibold)).foregroundStyle(Theme.ink2)
                        Text(plant.stageEnum.meaning).font(.subheadline.weight(.semibold))
                    }
                }

                Button {
                    sending = true
                    Task { await model.asked(plant); sending = false; dismiss() }
                } label: {
                    Label(sending ? "Sending…" : "I didn't catch this one", systemImage: "drop.fill")
                        .font(.headline).frame(maxWidth: .infinity).frame(height: 50)
                }
                .buttonStyle(.borderedProminent).tint(.blue).buttonBorderShape(.roundedRectangle(radius: 16))
                .disabled(model.source != .live || sending || plant.growth == 0)
                if model.source != .live {
                    Text("Connect to the garden on your Mac to send this.").font(.caption).foregroundStyle(Theme.ink2).frame(maxWidth: .infinity)
                }
            }
            .padding(20)
        }
        .background(Theme.background)
    }
}

/// Eight steps from seed to bloom, with the current one filled.
struct GrowthTrack: View {
    let plant: Plant
    let t: GardenSnapshot.Thresholds
    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            HStack {
                Text("Heard \(plant.heard)×").font(.headline)
                Spacer()
                Text(plant.toNext == 0 ? "In full bloom" : "\(plant.toNext) more to \(plant.stageEnum == .seed ? "sprout" : "bloom")")
                    .font(.subheadline.weight(.semibold)).foregroundStyle(plant.stageEnum.color)
            }
            HStack(spacing: 4) {
                ForEach(0..<t.bloom, id: \.self) { i in
                    let on = i < plant.growth
                    let stage: Stage = i < t.subtitle ? .seed : i < t.bloom - 1 ? .sprout : .bloom
                    RoundedRectangle(cornerRadius: 4).fill(on ? AnyShapeStyle(stage.color.gradient) : AnyShapeStyle(Theme.cardRaised)).frame(height: 10)
                }
            }
            HStack {
                Text("Seed"); Spacer(); Text("Sprout").padding(.trailing, 40); Spacer(); Text("Bloom")
            }
            .font(.caption2.weight(.semibold)).foregroundStyle(Theme.ink2)
        }
        .padding(16)
        .background(Theme.card, in: .rect(cornerRadius: 20))
        .overlay(RoundedRectangle(cornerRadius: 20).stroke(Theme.line, lineWidth: 1))
    }
}
