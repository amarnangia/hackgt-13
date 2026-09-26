import SwiftUI

struct SettingsView: View {
    @EnvironmentObject var people: People
    @Environment(\.dismiss) private var dismiss
    @State private var url = GardenClient.serverURL
    @State private var status: String?
    @State private var demo = GardenClient.demoMode
    @FocusState private var editing: Bool

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack {
                Text("Settings").font(Fonts.ui(24, .medium)).tracking(-0.6).foregroundStyle(Theme.text)
                Spacer()
                Button("Done") { dismiss() }.font(Fonts.ui(15, .medium)).foregroundStyle(Theme.accent)
            }
            .padding(.bottom, 8)
            Panel {
                Eyebrow("Weave on your Mac")
                TextField("http://192.168.1.10:8770", text: $url)
                    .font(Fonts.mono(15, .regular)).foregroundStyle(Theme.text)
                    .keyboardType(.URL).textInputAutocapitalization(.never).autocorrectionDisabled()
                    .focused($editing)
                    .padding(.horizontal, 12).frame(height: 46)
                    .background(Theme.surface2, in: .rect(cornerRadius: 10))
                    .overlay(RoundedRectangle(cornerRadius: 10).strokeBorder(editing ? Theme.accent.opacity(0.6) : Theme.border, lineWidth: 1))
                    .animation(.easeOut(duration: 0.2), value: editing)
                    .padding(.top, 10)
                Button(action: connect) {
                    Text("Connect").font(Fonts.ui(15, .medium)).foregroundStyle(Theme.bg).frame(maxWidth: .infinity).frame(height: 46)
                        .background(Theme.text, in: .rect(cornerRadius: 10))
                }
                .buttonStyle(Pressable()).padding(.top, 10)
                if let status { Text(status).font(Fonts.ui(13)).foregroundStyle(Theme.text2).padding(.top, 10) }
                Text("Run python -m garden on the Mac and enter the URL it prints. Live calls come from subtitles.py on the same Mac.")
                    .font(Fonts.ui(12)).foregroundStyle(Theme.text3).padding(.top, 10)
            }
            Panel {
                Toggle(isOn: $demo) {
                    VStack(alignment: .leading, spacing: 2) {
                        Text("Demo mode").font(Fonts.ui(15, .medium)).foregroundStyle(Theme.text)
                        Text("Sample words and the team's scripted call, for showing Weave without the Mac. Off: everything comes from your real calls.").font(Fonts.ui(12)).foregroundStyle(Theme.text2)
                    }
                }
                .tint(Theme.accent)
                .onChange(of: demo) { _, on in GardenClient.demoMode = on; Task { await people.loadGrowth() } }
            }
            Spacer()
        }
        .padding(20)
        .preferredColorScheme(.dark)
    }

    private func connect() {
        editing = false
        GardenClient.serverURL = url
        status = "Checking…"
        Task {
            do { let s = try await GardenClient.fetch(); status = "Connected · \(s.totals.phrases) words"; await people.loadGrowth() }
            catch { status = "Couldn't reach it. Is python -m garden running, and is this phone on the same Wi-Fi?" }
        }
    }
}
