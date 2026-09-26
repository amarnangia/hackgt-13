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

    /// The family, and who has a personalized voice (made on the Mac with ElevenLabs). nil: the Mac didn't answer.
    static func people() async -> [Person]? {
        try? await get("/api/people", as: [Person].self)
    }

    /// Adds someone to the family on the Mac (shared with the team's laptops). Returns everyone, or nil.
    static func addPerson(_ name: String) async -> [Person]? {
        guard let url = URL(string: serverURL + "/api/people") else { return nil }
        var req = URLRequest(url: url, timeoutInterval: 6)
        req.httpMethod = "POST"
        req.setValue("application/json", forHTTPHeaderField: "Content-Type")
        req.httpBody = try? JSONSerialization.data(withJSONObject: ["name": name])
        guard let (data, resp) = try? await URLSession.shared.data(for: req), (resp as? HTTPURLResponse)?.statusCode == 200 else { return nil }
        return try? JSONDecoder().decode([Person].self, from: data)
    }

    /// Sends a recording of `name` to the Mac, which makes their ElevenLabs voice (the key stays on the Mac).
    /// Returns nil when it worked, else what went wrong.
    static func makeVoice(name: String, audio: Data) async -> String? {
        var c = URLComponents(string: serverURL + "/api/voice")
        c?.queryItems = [URLQueryItem(name: "name", value: name), URLQueryItem(name: "consent", value: "1")]
        guard let url = c?.url else { return "The Mac's address isn't a URL." }
        var req = URLRequest(url: url, timeoutInterval: 90)
        req.httpMethod = "POST"
        req.setValue("audio/mp4", forHTTPHeaderField: "Content-Type")
        guard let (data, resp) = try? await URLSession.shared.upload(for: req, from: audio) else {
            return "Couldn't reach the Mac. Is python -m garden --lan running?"
        }
        if (resp as? HTTPURLResponse)?.statusCode == 200 { return nil }
        return (try? JSONDecoder().decode([String: String].self, from: data))?["error"] ?? "The Mac couldn't make the voice."
    }

    /// Deletes their voice at ElevenLabs (and on every laptop, through Firebase).
    static func removeVoice(name: String) async -> Bool {
        guard let url = URL(string: serverURL + "/api/voice/remove") else { return false }
        var req = URLRequest(url: url, timeoutInterval: 20)
        req.httpMethod = "POST"
        req.setValue("application/json", forHTTPHeaderField: "Content-Type")
        req.httpBody = try? JSONSerialization.data(withJSONObject: ["name": name])
        guard let (_, resp) = try? await URLSession.shared.data(for: req) else { return false }
        return (resp as? HTTPURLResponse)?.statusCode == 200
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
