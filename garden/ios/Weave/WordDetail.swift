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
                    Eyebrow(plant.stageEnum.label, color: plant.stageEnum.color)
                }
                .padding(.top, 8)

                VStack(alignment: .leading, spacing: 4) {
                    Text(plant.phrase).font(Fonts.telugu(54)).foregroundStyle(Theme.silk)
                        .minimumScaleFactor(0.6).lineLimit(2)
                    if let roman = plant.romanIfUseful {
                        Text(roman).font(Fonts.display(22, italic: true)).foregroundStyle(Theme.ink2)
                    }
                    if let en = plant.english {
                        Text(en).font(Fonts.display(32)).foregroundStyle(Theme.ink).padding(.top, 2)
                    }
                }
                .padding(.bottom, 8)

                if let note = plant.note {
                    Panel(padding: 16) {
                        Eyebrow("Meaning")
                        Text(note).font(Fonts.ui(15)).foregroundStyle(Theme.ink).padding(.top, 6)
                    }
                }

                Panel(padding: 16) {
                    HStack(alignment: .firstTextBaseline) {
                        Eyebrow("Heard")
                        Spacer()
                        Text(plant.toNext == 0 ? "Known" : "\(plant.toNext) more to \(plant.stageEnum == .seed ? "learning" : "known")")
                            .font(Fonts.ui(12, .semibold)).foregroundStyle(plant.stageEnum.color)
                    }
                    Text("\(plant.heard)×").font(Fonts.display(40))
                        .foregroundStyle(Theme.zari).padding(.top, 6)
                    GrowthBar(growth: plant.growth, total: t.bloom, subtitleAt: t.subtitle, height: 6).padding(.top, 12)
                    HStack {
                        Text("New"); Spacer(); Text("Learning"); Spacer(); Text("Known")
                    }
                    .font(Fonts.ui(11, .medium)).foregroundStyle(Theme.muted).padding(.top, 8)
                }

                Panel(padding: 16) {
                    Eyebrow("On your next call")
                    Text(plant.stageEnum.meaning).font(Fonts.ui(15, .semibold)).foregroundStyle(Theme.ink).padding(.top, 6)
                }

                Button {
                    sending = true
                    Task { await model.asked(plant); sending = false; dismiss() }
                } label: {
                    HStack(spacing: 8) {
                        if sending { ProgressView().controlSize(.small) } else { Image(systemName: "arrow.uturn.backward").font(Fonts.ui(13, .bold)) }
                        Text("I didn't catch this one").font(Fonts.ui(16, .semibold))
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
                    Text("Connect to Weave on your Mac to send this.").font(Fonts.ui(12)).foregroundStyle(Theme.muted)
                        .frame(maxWidth: .infinity)
                }
            }
            .padding(20)
        }
        .scrollIndicators(.hidden)
        .background(Loom(animated: false))
    }

    private var canAsk: Bool { model.source == .live && !sending && plant.growth > 0 }
}
