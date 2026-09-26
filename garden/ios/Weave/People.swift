import SwiftUI

struct Language: Identifiable, Hashable {
    let code: String, native: String, english: String
    var id: String { code }
    static let all = [
        Language(code: "en", native: "English", english: "English"), Language(code: "te", native: "తెలుగు", english: "Telugu"),
        Language(code: "hi", native: "हिन्दी", english: "Hindi"), Language(code: "ta", native: "தமிழ்", english: "Tamil"),
        Language(code: "kn", native: "ಕನ್ನಡ", english: "Kannada"), Language(code: "ml", native: "മലയാളം", english: "Malayalam"),
        Language(code: "bn", native: "বাংলা", english: "Bengali"), Language(code: "mr", native: "मराठी", english: "Marathi"),
        Language(code: "es", native: "Español", english: "Spanish"),
    ]
    static func name(_ code: String) -> String { all.first { $0.code == code }?.english ?? code }
}

struct Connection: Identifiable, Codable, Hashable {
    var id: String
    var name: String
    var lang: String
    var last: Date

    /// A Telugu letter for Telugu-speaking family, otherwise the first initial.
    var monogram: String {
        let te = ["ammamma": "అ", "nanamma": "నా", "thatayya": "తా", "amma": "అ", "nanna": "నా", "pinni": "పి", "mamayya": "మా", "attayya": "అ"]
        return (lang == "te" ? te[name.lowercased()] : nil) ?? String(name.prefix(1)).uppercased()
    }
    var lastLabel: String {
        let ago = Date().timeIntervalSince(last)
        return ago < 86400 ? "Connected recently" : ago < 2 * 86400 ? "Yesterday" : "\(Int(ago / 86400)) days ago"
    }
    var recent: Bool { Date().timeIntervalSince(last) < 86400 }
}

struct VocabItem: Identifiable, Codable, Hashable {
    let key: String
    var telugu: String?
    var roman: String?
    var english: String
    var image: String?
    var id: String { key }
}

/// You, the people you talk to, and the words you've kept. Stored on the phone.
@MainActor
final class People: ObservableObject {
    @Published var profileName: String? { didSet { save() } }
    @Published var myLang = "en" { didSet { save() } }
    @Published var connections: [Connection] { didSet { save() } }
    @Published var vocab: [VocabItem] { didSet { save() } }
    @Published var growth: GardenSnapshot?
    @Published var pendingSession: Connection?   // first run: open the call once home appears

    private let defaults = GardenClient.defaults

    init() {
        let d = GardenClient.defaults
        profileName = d.string(forKey: "profileName") ?? UserDefaults.standard.string(forKey: "profileName")  // -profileName Saanvi
        myLang = d.string(forKey: "myLang") ?? "en"
        connections = d.data(forKey: "connections").flatMap { try? JSONDecoder().decode([Connection].self, from: $0) } ?? [
            Connection(id: "ammamma", name: "Ammamma", lang: "te", last: .now.addingTimeInterval(-2 * 3600)),
            Connection(id: "thatayya", name: "Thatayya", lang: "te", last: .now.addingTimeInterval(-3 * 86400)),
            Connection(id: "pinni", name: "Pinni", lang: "te", last: .now.addingTimeInterval(-6 * 86400)),
        ]
        vocab = d.data(forKey: "vocab").flatMap { try? JSONDecoder().decode([VocabItem].self, from: $0) } ?? []
        if UserDefaults.standard.bool(forKey: "resetOnboarding") { profileName = nil }
    }

    private func save() {
        defaults.set(profileName, forKey: "profileName")
        defaults.set(myLang, forKey: "myLang")
        defaults.set(try? JSONEncoder().encode(connections), forKey: "connections")
        defaults.set(try? JSONEncoder().encode(vocab), forKey: "vocab")
    }

    func save(_ w: Word) {
        guard !vocab.contains(where: { $0.key == w.key }) else { return }
        vocab.insert(VocabItem(key: w.key, telugu: w.telugu, roman: w.roman, english: w.english, image: w.image), at: 0)
    }

    func touch(_ c: Connection) {
        if let i = connections.firstIndex(where: { $0.id == c.id }) { connections[i].last = .now }
        else { connections.insert(c, at: 0) }
    }

    func loadGrowth() async {
        let (snap, _) = await GardenClient.load()
        growth = snap
    }

    /// Numbers for "Your language growth"; the Mac's garden when reachable, else the bundled sample.
    var numbers: (newWords: Int, phrases: Int, known: Int, total: Int, hearings: Int, days: [Int]) {
        let g = growth ?? .sample
        let week = g.days.suffix(7).reduce(0) { $0 + $1.new }
        let phrases = g.plants.filter { $0.stageEnum == .bloom && ["idiom", "family", "none"].contains($0.category) }.count
        return (week, phrases, g.totals.bloom, g.totals.phrases, g.totals.heard, g.days.map(\.heard))
    }
}
