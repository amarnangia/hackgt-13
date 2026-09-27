import Foundation

/// Conversation starters for the next call, built from the words you're learning.
/// Prompts are English; the Telugu comes straight from the team's lexicon (never generated).
struct Starter: Equatable, Identifiable {
    let before: String      // "Ask how she makes"
    let word: String        // Telugu, as heard: "పులిహోర"
    let gloss: String?      // "tamarind rice"
    var roman: String? = nil // "pulihora"
    let after: String       // "."
    let symbol: String      // SF Symbol for the topic
    let topic: String       // "Food"
    var id: String { word + before }
}

enum Starters {
    static func hash(_ s: String) -> UInt32 {
        var h: UInt32 = 2166136261
        for u in s.unicodeScalars { h = (h ^ u.value) &* 16777619 }
        return h
    }

    private static let templates: [String: [(String, String)]] = [   // (before the word, after it)
        "food": [("Ask how she makes", "."), ("Ask when she last cooked", "."), ("Ask who makes the best", " in the family.")],
        "festival": [("Ask what", " was like when she was young."), ("Ask how the family celebrates", " now.")],
        "place": [("Ask her to describe the", " back home."), ("Ask what she does at the", " these days.")],
        "vehicle": [("Ask where she goes by", " these days."), ("Ask about her first ride in an", ".")],
        "clothing": [("Ask about her favourite", "."), ("Ask when she last wore a", ".")],
        "family": [("Ask for a story about", "."), ("Ask what", " was like as a child.")],
        "idiom": [("Ask what", " really means, and when she says it."), ("Ask her to use", " in a sentence.")],
        "slang": [("Teach her what", " means.")],
    ]
    private static let symbols = ["food": "fork.knife", "festival": "sparkles", "place": "mappin.and.ellipse", "vehicle": "car.fill",
                                  "clothing": "tshirt.fill", "family": "person.2.fill", "idiom": "quote.bubble.fill", "slang": "quote.bubble.fill"]
    private static let topics = ["food": "Food", "festival": "Festivals", "place": "Places", "vehicle": "Getting around",
                                 "clothing": "Clothes", "family": "Family", "idiom": "Sayings", "slang": "Slang"]

    /// Starters about words still being learned (seeds and sprouts), most recently heard first, one per topic.
    /// `rotation` shifts which one leads, so the widget changes through the day.
    /// Words that make sense as a topic: not forms of address like నాన్నా ("dear").
    private static func topical(_ p: Plant) -> Bool {
        templates[p.category] != nil && !(p.roman ?? "").contains("vocative")
    }

    static func make(_ snap: GardenSnapshot, rotation: Int = 0, count: Int = 3) -> [Starter] {
        var pool = snap.plants.filter { topical($0) && $0.stageEnum != .bloom }
            .sorted { ($0.lastHeard ?? 0) > ($1.lastHeard ?? 0) }
        if pool.isEmpty { pool = snap.plants.filter(topical) }
        guard !pool.isEmpty else { return [] }
        var seen = Set<String>(), picked: [Plant] = []
        for i in 0..<pool.count {
            let p = pool[(i + rotation) % pool.count]
            if seen.insert(p.category).inserted { picked.append(p) }
            if picked.count == count { break }
        }
        return picked.map { p in
            let options = templates[p.category]!
            let t = options[Int((hash(p.phrase) &+ UInt32(rotation)) % UInt32(options.count))]
            return Starter(before: t.0, word: p.phrase, gloss: p.english, roman: p.roman.map { $0.replacingOccurrences(of: "_", with: " ") }, after: t.1,
                           symbol: symbols[p.category] ?? "bubble.left.fill", topic: topics[p.category] ?? "Words")
        }
    }

    /// A phrase you already know, to use yourself: a bloomed everyday phrase, family word or saying.
    static func trySaying(_ snap: GardenSnapshot, rotation: Int = 0) -> Plant? {
        // Short and with a plain English meaning, so it fits and is easy to say.
        let known = snap.plants.filter { $0.stageEnum == .bloom && $0.phrase.count <= 18 && !($0.english ?? "").isEmpty && !($0.english ?? "").hasPrefix("'") }
        let phrases = known.filter { ["idiom", "family", "none"].contains($0.category) && !($0.roman ?? "").contains("vocative") }
        let pool = (phrases.isEmpty ? known : phrases).sorted { $0.heard > $1.heard }
        return pool.isEmpty ? nil : pool[rotation % pool.count]
    }

    static func lastCall(_ snap: GardenSnapshot, now: Double = Date().timeIntervalSince1970) -> String? {
        if snap.calls.live { return "On a call now" }
        guard let last = snap.calls.last else { return nil }
        let days = Int((now - last) / 86400)
        return days >= 1 ? "Last call \(days)d ago" : "Last call \(timeAgo(last, now: now))"
    }
}
