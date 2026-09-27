import Foundation

// What the story keeper (calls.py) saves for every real call, as the Weave server serves it.

struct Question: Codable, Hashable {
    var english: String?
    var telugu: String?
    var roman: String?
}

/// /api/calls: one saved call.
struct CallSummary: Codable, Identifiable, Hashable {
    let id: String
    var caller: String
    var started: String?
    var duration_s: Double?
    var title: String
    var summary: String?
    var stories: [String?]?
    var lines: Int?
    var words: Int?
    var new_words: Int?
    var pictures: [String]?
    var page: String?
    var questions: [Question]?
    var has_audio: Bool?
    var message_te: String?   // the story keeper's WhatsApp message in Telugu, to send her after the call
    var message_en: String?   // what it says, in English

    /// calls.py writes local time to the minute ("2026-09-26T18:30"); accept seconds too.
    var date: Date? {
        guard let started else { return nil }
        let f = DateFormatter(); f.locale = Locale(identifier: "en_US_POSIX")
        for format in ["yyyy-MM-dd'T'HH:mm:ss", "yyyy-MM-dd'T'HH:mm"] {
            f.dateFormat = format
            if let d = f.date(from: String(started.prefix(format.count - 2))) { return d }
        }
        return nil
    }
    var minutes: Int { max(1, Int(((duration_s ?? 0) / 60).rounded())) }
    var whenLabel: String {
        guard let d = date else { return "" }
        if Calendar.current.isDateInToday(d) { return "Today " + d.formatted(date: .omitted, time: .shortened) }
        if Calendar.current.isDateInYesterday(d) { return "Yesterday" }
        return d.formatted(.dateTime.month(.abbreviated).day())
    }
}

/// calls/<id>/call.json: the whole call.
struct CallDetail: Codable {
    struct Picture: Codable, Hashable { var name: String?; var description: String?; var image: String? }
    struct Line: Codable, Identifiable, Hashable {
        let id: Int
        var telugu: String?
        var english: String?
        var route: String?
        var intent: String?
        var picture: Picture?
        var time: String?
        var clip: String?
    }
    struct Story: Codable {
        struct Told: Codable, Hashable { var title: String?; var summary: String? }
        var title: String?
        var summary: String?
        var stories: [Told]?
        var questions: [Question]?
    }
    struct CallWord: Codable, Hashable { var id: String; var telugu: String?; var roman: String?; var english: String?; var status: String? }

    let id: String
    var caller: String?
    var started: String?
    var duration_s: Double?
    var lines: [Line]?
    var story: Story?
    var words: [CallWord]?
}

/// calls/family_dictionary.json: one word, with her voice from the call it first came up in.
struct DictEntry: Codable, Hashable {
    var telugu: String?
    var roman: String?
    var english: String?
    var note: String?
    var category: String?
    var times: Int?
    var calls: Int?
    var clip: String?          // "<call id>/clips/<line>.m4a"
    var example_te: String?
    var example_en: String?
    var status: String?        // known | learning | new
}
