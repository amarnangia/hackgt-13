import Foundation

/// Talks to the garden server on the Mac (`python -m garden`). Shared by the app and the widget
/// through an App Group, so the widget uses the same server address and last saved garden.
enum GardenClient {
    static let appGroup = "group.com.weave.garden"
    static let defaults = UserDefaults(suiteName: appGroup) ?? .standard

    enum Source: String { case live, saved, demo }

    static var serverURL: String {
        get { defaults.string(forKey: "serverURL") ?? "http://localhost:8770" }
        set { defaults.set(newValue.trimmingCharacters(in: .whitespacesAndNewlines).trimmingCharacters(in: CharacterSet(charactersIn: "/")), forKey: "serverURL") }
    }

    /// Show the bundled demo garden instead of asking the server.
    static var demoMode: Bool {
        get { defaults.bool(forKey: "demoMode") }
        set { defaults.set(newValue, forKey: "demoMode") }
    }

    static var saved: GardenSnapshot? {
        get { defaults.data(forKey: "lastSnapshot").flatMap { try? GardenSnapshot.decode($0) } }
        set { defaults.set(newValue?.encoded(), forKey: "lastSnapshot") }
    }

    static func fetch(timeout: TimeInterval = 4) async throws -> GardenSnapshot {
        guard let url = URL(string: serverURL + "/api/garden") else { throw URLError(.badURL) }
        var req = URLRequest(url: url, cachePolicy: .reloadIgnoringLocalCacheData, timeoutInterval: timeout)
        req.httpMethod = "GET"
        let (data, resp) = try await URLSession.shared.data(for: req)
        guard (resp as? HTTPURLResponse)?.statusCode == 200 else { throw URLError(.badServerResponse) }
        return try GardenSnapshot.decode(data)
    }

    /// Live if the server answers, else the last saved garden, else the demo.
    static func load() async -> (GardenSnapshot, Source) {
        if demoMode { return (.sample, .demo) }
        if let snap = try? await fetch() {
            saved = snap
            return (snap, .live)
        }
        if let snap = saved { return (snap, .saved) }
        return (.sample, .demo)
    }

    /// The "I didn't catch that" button: moves the phrase back a stage on the server.
    static func asked(_ phrase: String) async throws {
        guard let url = URL(string: serverURL + "/api/asked") else { throw URLError(.badURL) }
        var req = URLRequest(url: url, timeoutInterval: 4)
        req.httpMethod = "POST"
        req.setValue("application/json", forHTTPHeaderField: "Content-Type")
        req.httpBody = try JSONSerialization.data(withJSONObject: ["phrase": phrase])
        _ = try await URLSession.shared.data(for: req)
    }
}
