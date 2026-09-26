import SwiftUI

struct SettingsView: View {
    @EnvironmentObject var model: GardenModel
    @Environment(\.dismiss) private var dismiss
    @State private var url = GardenClient.serverURL
    @State private var demo = GardenClient.demoMode
    @State private var status: String?
    @AppStorage("skyOverride") private var sky = 0.0

    var body: some View {
        NavigationStack {
            Form {
                Section {
                    TextField("http://192.168.1.10:8770", text: $url)
                        .keyboardType(.URL).textInputAutocapitalization(.never).autocorrectionDisabled()
                    Button("Connect") {
                        GardenClient.serverURL = url
                        status = "Checking…"
                        Task {
                            do { let s = try await GardenClient.fetch(); status = "Connected · \(s.totals.phrases) words" ; await model.setDemo(false); demo = false }
                            catch { status = "Couldn't reach it. Is `python -m garden` running, and is this phone on the same Wi-Fi?" }
                        }
                    }
                    if let status { Text(status).font(.footnote).foregroundStyle(.secondary) }
                } header: {
                    Text("Garden on your Mac")
                } footer: {
                    Text("Run `python -m garden` on the Mac and type the “phone widget URL” it prints. The simulator can use http://localhost:8770.")
                }

                Section {
                    Toggle("Show demo garden", isOn: $demo)
                        .onChange(of: demo) { _, on in Task { await model.setDemo(on) } }
                    Picker("Sky", selection: $sky) {
                        Text("Real time").tag(0.0)
                        Text("Morning").tag(7.0)
                        Text("Midday").tag(12.0)
                        Text("Sunset").tag(18.3)
                        Text("Night").tag(22.0)
                    }
                } footer: {
                    Text("The sky follows the time of day. Pick one to show off the other looks.")
                }
            }
            .navigationTitle("Settings")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar { ToolbarItem(placement: .confirmationAction) { Button("Done") { dismiss() } } }
        }
    }
}
