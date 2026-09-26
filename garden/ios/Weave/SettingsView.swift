import SwiftUI

struct SettingsView: View {
    @EnvironmentObject var model: GardenModel
    @Environment(\.dismiss) private var dismiss
    @State private var url = GardenClient.serverURL
    @State private var demo = GardenClient.demoMode
    @State private var status: String?
    @FocusState private var editing: Bool

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(alignment: .leading, spacing: 12) {
                    Panel(padding: 16) {
                        Eyebrow("Weave on your Mac")
                        TextField("http://192.168.1.10:8770", text: $url)
                            .font(Fonts.ui(16).monospacedDigit()).foregroundStyle(Theme.ink)
                            .keyboardType(.URL).textInputAutocapitalization(.never).autocorrectionDisabled()
                            .focused($editing)
                            .padding(.horizontal, 12).frame(height: 44)
                            .background(Theme.raised, in: .rect(cornerRadius: 10))
                            .overlay(RoundedRectangle(cornerRadius: 10).strokeBorder(editing ? Theme.accent : .clear, lineWidth: 1.5))
                            .animation(.easeOut(duration: 0.2), value: editing)
                            .padding(.top, 10)
                        Button(action: connect) {
                            Text("Connect").font(Fonts.ui(15, .semibold)).foregroundStyle(Color(hex: 0x1a1208))
                                .frame(maxWidth: .infinity).frame(height: 44)
                                .background(Theme.zari, in: .rect(cornerRadius: 10))
                        }
                        .buttonStyle(Pressable())
                        .padding(.top, 10)
                        if let status { Text(status).font(Fonts.ui(13)).foregroundStyle(Theme.ink2).padding(.top, 10) }
                        Text("Run python -m garden on the Mac and enter the “phone widget URL” it prints. The simulator can use http://localhost:8770.")
                            .font(Fonts.ui(12)).foregroundStyle(Theme.muted).padding(.top, 10)
                    }
                    Panel(padding: 16) {
                        Toggle(isOn: $demo) {
                            VStack(alignment: .leading, spacing: 2) {
                                Text("Demo data").font(Fonts.ui(15, .semibold)).foregroundStyle(Theme.ink)
                                Text("Two weeks of sample calls, for trying the app without a Mac.").font(Fonts.ui(12)).foregroundStyle(Theme.ink2)
                            }
                        }
                        .tint(Theme.accent)
                        .onChange(of: demo) { _, on in Task { await model.setDemo(on) } }
                    }
                }
                .padding(20)
            }
            .background(Loom(animated: false))
            .navigationTitle("Settings")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar { ToolbarItem(placement: .confirmationAction) { Button("Done") { dismiss() }.fontWeight(.semibold) } }
        }
    }

    private func connect() {
        editing = false
        GardenClient.serverURL = url
        status = "Checking…"
        Task {
            do {
                let s = try await GardenClient.fetch()
                status = "Connected · \(s.totals.phrases) words"
                demo = false
                await model.setDemo(false)
            } catch {
                status = "Couldn't reach it. Is python -m garden running, and is this phone on the same Wi-Fi?"
            }
        }
    }
}
