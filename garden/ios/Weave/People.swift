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
    /// People you added yourself (onboarding). Everyone else comes from the calls on the Mac.
    @Published var added: [Connection] { didSet { save() } }
    @Published var vocab: [VocabItem] { didSet { save() } }
    @Published var growth: GardenSnapshot?
    @Published var source: GardenClient.Source = .offline
    @Published var calls: [CallSummary] = []
    @Published var dictionary: [String: DictEntry] = [:]
    @Published var family: [Person]?             // everyone, from the Mac (nil: it hasn't answered)

    private let defaults = GardenClient.defaults

    init() {
        let d = GardenClient.defaults
        profileName = d.string(forKey: "profileName") ?? UserDefaults.standard.string(forKey: "profileName")  // -profileName Saanvi
        myLang = d.string(forKey: "myLang") ?? "en"
        added = d.data(forKey: "addedConnections").flatMap { try? JSONDecoder().decode([Connection].self, from: $0) } ?? []
        vocab = d.data(forKey: "vocab").flatMap { try? JSONDecoder().decode([VocabItem].self, from: $0) } ?? []
        if UserDefaults.standard.bool(forKey: "resetOnboarding") { profileName = nil }
    }

    private func save() {
        defaults.set(profileName, forKey: "profileName")
        defaults.set(myLang, forKey: "myLang")
        defaults.set(try? JSONEncoder().encode(added), forKey: "addedConnections")
        defaults.set(try? JSONEncoder().encode(vocab), forKey: "vocab")
    }

    func save(_ w: Word) {
        guard !vocab.contains(where: { $0.key == w.key }) else { return }
        vocab.insert(VocabItem(key: w.key, telugu: w.telugu, roman: w.roman, english: w.english, image: w.image), at: 0)
    }

    /// Whoever the translator has been run for (subtitles.py --caller), newest call first, plus people you added.
    var connections: [Connection] {
        var seen = Set<String>(), out: [Connection] = []
        for c in calls {
            let id = c.caller.lowercased().replacingOccurrences(of: " ", with: "-")
            if seen.insert(id).inserted { out.append(Connection(id: id, name: c.caller, lang: "te", last: c.date ?? .now)) }
        }
        for c in added where seen.insert(c.id).inserted { out.append(c) }
        return out.sorted { $0.last > $1.last }
    }

    /// Someone by name: the connection you already have with them, or a new one (Telugu, like the calls).
    func connection(named name: String) -> Connection {
        connections.first { $0.id == Person.id(for: name) }
            ?? Connection(id: Person.id(for: name), name: name, lang: "te", last: .now)
    }

    /// The person on a live call we haven't saved yet: the translator's own default caller.
    var partner: Connection { connections.first ?? Connection(id: "grandma", name: "Grandma", lang: "te", last: .now) }

    func touch(_ c: Connection) {
        guard !calls.contains(where: { $0.caller.lowercased() == c.name.lowercased() }) else { return }
        if let i = added.firstIndex(where: { $0.id == c.id }) { added[i].last = .now } else { added.insert(c, at: 0) }
    }

    /// Everything from the Mac: the garden, the saved calls and the family dictionary.
    func loadGrowth() async {
        async let g = GardenClient.load()
        async let c = GardenClient.calls()
        async let d = GardenClient.dictionary()
        async let f: Void = loadFamily()
        let (snap, src) = await g
        growth = snap; source = src
        calls = await c
        let dict = await d
        if !dict.isEmpty || src == .live { dictionary = dict }
        await f
    }

    /// Who's who, from the Mac: for "who are you?" and whose voice is personalized.
    func loadFamily() async {
        guard let f = await GardenClient.people() else { return }
        family = f
        // Your name reaches the Mac (and Firebase through it) even if the Mac wasn't there when you typed it.
        if let name = profileName, !f.contains(where: { $0.id == Person.id(for: name) }),
           let added = await GardenClient.addPerson(name) { family = added }
    }

    /// You, as the Mac knows you (nil until it answers or if you're new).
    var me: Person? { family?.first { $0.id == Person.id(for: profileName ?? "") } }

    /// "Who are you?" answered: remember it, and add you to the family on the Mac if you're new.
    func becomes(_ name: String) {
        profileName = name
        guard family?.contains(where: { $0.id == Person.id(for: name) }) != true else { return }
        Task { if let f = await GardenClient.addPerson(name) { family = f } }
    }

    /// Her voice saying this word, if the family dictionary has it.
    func voice(for key: String) -> String? { dictionary[key]?.clip.map { "calls/" + $0 } }

    var numbers: (newWords: Int, phrases: Int, known: Int, total: Int, hearings: Int, days: [Int]) {
        let g = growth ?? .empty
        let week = g.days.suffix(7).reduce(0) { $0 + $1.new }
        let phrases = g.plants.filter { $0.stageEnum == .bloom && ["idiom", "family", "none"].contains($0.category) }.count
        return (week, phrases, g.totals.bloom, g.totals.phrases, g.totals.heard, g.days.map(\.heard))
    }
}
