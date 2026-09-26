import Foundation

// Mirrors the JSON from the garden server's /api/garden (garden/store.py `snapshot()`).
struct GardenSnapshot: Codable, Equatable {
    var plants: [Plant]
    var totals: Totals
    var streak: Int
    var days: [Day]
    var calls: Calls
    var recent: [Event]
    var thresholds: Thresholds
    var now: Double

    struct Totals: Codable, Equatable { var seed, sprout, bloom, phrases, heard: Int }
    struct Day: Codable, Equatable, Identifiable {
        var date: String
        var heard, new, bloomed: Int
        var id: String { date }
        var day: Date { DateFormatter.isoDay.date(from: date) ?? .now }
    }
    struct Calls: Codable, Equatable { var count, minutes: Int; var last: Double?; var live: Bool }
    struct Event: Codable, Equatable, Identifiable {
        var ts: Double
        var phrase: String
        var kind: String  // heard | asked | sprouted | bloomed
        var id: String { "\(ts)-\(phrase)-\(kind)" }
    }
    struct Thresholds: Codable, Equatable { var subtitle, bloom: Int }

    func plant(_ phrase: String) -> Plant? { plants.first { $0.phrase == phrase } }

    /// The bundled demo snapshot, with its dates moved up to today so "2h ago" and the chart still read right.
    static let sample: GardenSnapshot = {
        guard let url = Bundle.main.url(forResource: "sample", withExtension: "json"),
              let data = try? Data(contentsOf: url),
              let snap = try? GardenSnapshot.decode(data) else { return .empty }
        return snap.rebased(to: Date().timeIntervalSince1970)
    }()

    static let empty = GardenSnapshot(plants: [], totals: .init(seed: 0, sprout: 0, bloom: 0, phrases: 0, heard: 0), streak: 0,
                                      days: [], calls: .init(count: 0, minutes: 0, last: nil, live: false), recent: [],
                                      thresholds: .init(subtitle: 3, bloom: 8), now: Date().timeIntervalSince1970)

    static func decode(_ data: Data) throws -> GardenSnapshot {
        let d = JSONDecoder()
        d.keyDecodingStrategy = .convertFromSnakeCase
        return try d.decode(GardenSnapshot.self, from: data)
    }

    func encoded() -> Data? {
        let e = JSONEncoder()
        e.keyEncodingStrategy = .convertToSnakeCase
        return try? e.encode(self)
    }

    func rebased(to newNow: Double) -> GardenSnapshot {
        let shift = newNow - now, dayShift = Int((shift / 86400).rounded())
        var s = self
        s.now = newNow
        s.plants = plants.map { var p = $0; p.firstHeard = p.firstHeard.map { $0 + shift }; p.lastHeard = p.lastHeard.map { $0 + shift }; return p }
        s.recent = recent.map { var e = $0; e.ts += shift; return e }
        s.calls.last = calls.last.map { $0 + shift }
        s.days = days.map { var d = $0; d.date = DateFormatter.isoDay.string(from: Calendar.current.date(byAdding: .day, value: dayShift, to: d.day) ?? d.day); return d }
        return s
    }
}

struct Plant: Codable, Equatable, Identifiable, Hashable {
    var phrase: String
    var english: String?
    var category: String
    var note: String?
    var roman: String?
    var heard: Int
    var asked: Int
    var growth: Int
    var firstHeard: Double?
    var lastHeard: Double?
    var stage: String   // seed | sprout | bloom
    var toNext: Int
    var thirsty: Bool
    var id: String { phrase }

    var stageEnum: Stage { Stage(rawValue: stage) ?? .seed }
    var flower: Flower { Flower(category: category) }
    /// Romanization, unless it just repeats the English.
    var romanIfUseful: String? {
        guard let roman, roman.lowercased() != (english ?? "").lowercased() else { return nil }
        return roman
    }
}

enum Stage: String, CaseIterable, Identifiable {
    case bloom, sprout, seed
    var id: String { rawValue }
    var title: String { ["bloom": "Blooming", "sprout": "Sprouting", "seed": "Seeds"][rawValue]! }
    var meaning: String {
        switch self {
        case .seed: "Dubbed in English"
        case .sprout: "Telugu with subtitles"
        case .bloom: "You understand it on your own"
        }
    }
}

enum Flower: String {
    case marigold, lotus, hibiscus, sunflower, morningGlory, rose, lavender, jasmine
    init(category: String) {
        switch category {
        case "food": self = .marigold
        case "place": self = .lotus
        case "festival": self = .hibiscus
        case "vehicle": self = .sunflower
        case "clothing": self = .morningGlory
        case "family": self = .rose
        case "idiom", "slang": self = .lavender
        default: self = .jasmine
        }
    }
    var name: String { self == .morningGlory ? "morning glory" : rawValue }
}

extension DateFormatter {
    static let isoDay: DateFormatter = {
        let f = DateFormatter()
        f.calendar = Calendar(identifier: .gregorian)
        f.locale = Locale(identifier: "en_US_POSIX")
        f.dateFormat = "yyyy-MM-dd"
        return f
    }()
}

func timeAgo(_ ts: Double, now: Double = Date().timeIntervalSince1970) -> String {
    let s = max(0, now - ts)
    switch s {
    case ..<60: return "just now"
    case ..<3600: return "\(Int(s / 60))m ago"
    case ..<86400: return "\(Int(s / 3600))h ago"
    default: return "\(Int(s / 86400))d ago"
    }
}
