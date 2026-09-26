import SwiftUI

struct WordDetail: View {
    @EnvironmentObject var model: GardenModel
    @Environment(\.dismiss) private var dismiss
    let plant: Plant
    @State private var sending = false

    var body: some View {
        let t = model.snapshot.thresholds
        ScrollView {
            VStack(alignment: .leading, spacing: 12) {
                HStack(spacing: 6) {
                    RoundedRectangle(cornerRadius: 2.5).fill(plant.stageEnum.fill).frame(width: 10, height: 10)
                    Eyebrow(plant.stageEnum.label, color: plant.stageEnum == .bloom ? Theme.accent : Theme.muted)
                }
                .padding(.top, 8)

                VStack(alignment: .leading, spacing: 4) {
                    Text(plant.phrase).font(.system(size: 42, weight: .bold)).tracking(-1).foregroundStyle(Theme.ink)
                        .minimumScaleFactor(0.6).lineLimit(2)
                    if let roman = plant.romanIfUseful {
                        Text(roman).font(.system(size: 17)).italic().foregroundStyle(Theme.ink2)
                    }
                    if let en = plant.english {
                        Text(en).font(.system(size: 22, weight: .semibold)).tracking(-0.4).foregroundStyle(Theme.ink).padding(.top, 6)
                    }
                }
                .padding(.bottom, 8)

                if let note = plant.note {
                    Panel(padding: 16) {
                        Eyebrow("Meaning")
                        Text(note).font(.system(size: 15)).foregroundStyle(Theme.ink).padding(.top, 6)
                    }
                }

                Panel(padding: 16) {
                    HStack(alignment: .firstTextBaseline) {
                        Eyebrow("Heard")
                        Spacer()
                        Text(plant.toNext == 0 ? "Known" : "\(plant.toNext) more to \(plant.stageEnum == .seed ? "learning" : "known")")
                            .font(.system(size: 12, weight: .semibold)).foregroundStyle(Theme.accent)
                    }
                    Text("\(plant.heard)×").font(.system(size: 26, weight: .semibold)).monospacedDigit().tracking(-0.6)
                        .foregroundStyle(Theme.ink).padding(.top, 6)
                    GrowthBar(growth: plant.growth, total: t.bloom, height: 6).padding(.top, 12)
                    HStack {
                        Text("New"); Spacer(); Text("Learning"); Spacer(); Text("Known")
                    }
                    .font(.system(size: 11, weight: .medium)).foregroundStyle(Theme.muted).padding(.top, 8)
                }

                Panel(padding: 16) {
                    Eyebrow("On your next call")
                    Text(plant.stageEnum.meaning).font(.system(size: 15, weight: .semibold)).foregroundStyle(Theme.ink).padding(.top, 6)
                }

                Button {
                    sending = true
                    Task { await model.asked(plant); sending = false; dismiss() }
                } label: {
                    HStack(spacing: 8) {
                        if sending { ProgressView().controlSize(.small) } else { Image(systemName: "arrow.uturn.backward").font(.system(size: 13, weight: .bold)) }
                        Text("I didn't catch this one").font(.system(size: 16, weight: .semibold))
                    }
                    .foregroundStyle(canAsk ? Theme.ink : Theme.muted)
                    .frame(maxWidth: .infinity).frame(height: 52)
                    .background(Theme.surface, in: .rect(cornerRadius: Theme.radius))
                    .overlay(RoundedRectangle(cornerRadius: Theme.radius).strokeBorder(Theme.border, lineWidth: 1))
                }
                .buttonStyle(Pressable())
                .disabled(!canAsk)
                .padding(.top, 4)
                if model.source != .live {
                    Text("Connect to Weave on your Mac to send this.").font(.system(size: 12)).foregroundStyle(Theme.muted)
                        .frame(maxWidth: .infinity)
                }
            }
            .padding(20)
        }
        .scrollIndicators(.hidden)
        .background(Theme.bg)
    }

    private var canAsk: Bool { model.source == .live && !sending && plant.growth > 0 }
}
