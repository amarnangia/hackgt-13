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
                            .font(.system(size: 16, design: .monospaced)).foregroundStyle(Theme.ink)
                            .keyboardType(.URL).textInputAutocapitalization(.never).autocorrectionDisabled()
                            .focused($editing)
                            .padding(.horizontal, 12).frame(height: 44)
                            .background(Theme.raised, in: .rect(cornerRadius: 10))
                            .overlay(RoundedRectangle(cornerRadius: 10).strokeBorder(editing ? Theme.accent : .clear, lineWidth: 1.5))
                            .animation(.easeOut(duration: 0.2), value: editing)
                            .padding(.top, 10)
                        Button(action: connect) {
                            Text("Connect").font(.system(size: 15, weight: .semibold)).foregroundStyle(Theme.bg)
                                .frame(maxWidth: .infinity).frame(height: 44)
                                .background(Theme.ink, in: .rect(cornerRadius: 10))
                        }
                        .buttonStyle(Pressable())
                        .padding(.top, 10)
                        if let status { Text(status).font(.system(size: 13)).foregroundStyle(Theme.ink2).padding(.top, 10) }
                        Text("Run python -m garden on the Mac and enter the “phone widget URL” it prints. The simulator can use http://localhost:8770.")
                            .font(.system(size: 12)).foregroundStyle(Theme.muted).padding(.top, 10)
                    }
                    Panel(padding: 16) {
                        Toggle(isOn: $demo) {
                            VStack(alignment: .leading, spacing: 2) {
                                Text("Demo data").font(.system(size: 15, weight: .semibold)).foregroundStyle(Theme.ink)
                                Text("Two weeks of sample calls, for trying the app without a Mac.").font(.system(size: 12)).foregroundStyle(Theme.ink2)
                            }
                        }
                        .tint(Theme.accent)
                        .onChange(of: demo) { _, on in Task { await model.setDemo(on) } }
                    }
                }
                .padding(20)
            }
            .background(Theme.bg)
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
