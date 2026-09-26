import Foundation

/// Talks to the garden server on the Mac (`python -m garden`). Shared by the app and the widget
/// through an App Group, so the widget uses the same server address and last saved garden.
enum GardenClient {
    static let appGroup = "group.com.weave.garden"
    static let defaults = UserDefaults(suiteName: appGroup) ?? .standard

    /// live: from the Mac just now; saved: the last garden we got; demo: the bundled sample (Settings); offline: nothing yet.
    enum Source: String { case live, saved, demo, offline }

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

    /// From the Mac if it answers, else the last garden we got. The bundled sample only when demo mode is on.
    static func load() async -> (GardenSnapshot, Source) {
        if demoMode { return (.sample, .demo) }
        if let snap = try? await fetch() {
            saved = snap
            return (snap, .live)
        }
        if let snap = saved { return (snap, .saved) }
        return (.empty, .offline)
    }

    static func get<T: Decodable>(_ path: String, as type: T.Type, timeout: TimeInterval = 5) async throws -> T {
        guard let url = URL(string: serverURL + path) else { throw URLError(.badURL) }
        let (data, resp) = try await URLSession.shared.data(for: URLRequest(url: url, cachePolicy: .reloadIgnoringLocalCacheData, timeoutInterval: timeout))
        guard (resp as? HTTPURLResponse)?.statusCode == 200 else { throw URLError(.badServerResponse) }
        return try JSONDecoder().decode(T.self, from: data)
    }

    /// Calls the story keeper saved on the Mac, newest first (cached for when the Mac is away).
    static func calls() async -> [CallSummary] {
        if demoMode { return [] }
        if let c = try? await get("/api/calls", as: [CallSummary].self) {
            defaults.set(try? JSONEncoder().encode(c), forKey: "lastCalls")
            return c
        }
        return defaults.data(forKey: "lastCalls").flatMap { try? JSONDecoder().decode([CallSummary].self, from: $0) } ?? []
    }

    static func call(_ id: String) async -> CallDetail? {
        try? await get("/calls/\(id)/call.json", as: CallDetail.self)
    }

    /// The family dictionary: every word from the calls, with her voice saying it.
    static func dictionary() async -> [String: DictEntry] {
        (try? await get("/calls/family_dictionary.json", as: [String: DictEntry].self)) ?? [:]
    }

    static func url(_ path: String) -> URL? { URL(string: serverURL + "/" + path.trimmingCharacters(in: CharacterSet(charactersIn: "/"))) }

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
