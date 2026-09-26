import SwiftUI
import UIKit

// MARK: - The team's word list, picture library and scripted call (bundled from the repo, read only)

struct LexEntry: Decodable {
    let id: String
    let forms: [String]
    let translate_as: String?
    let category: String
    let note: String?
    let roman: String?
}

struct LibItem: Decodable {
    let name: String?
    let title: String?
    let description: String?
    let image: String?
    let category: String?
}

struct ScriptLine: Decodable {
    let part: Int?
    let text: String
    let meaning: String
    let route: String
}

enum Knowledge {
    static let lexicon: [LexEntry] = {
        guard let data = bundled("lexicon", "json"),
              let raw = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
              let te = raw["te"], let teData = try? JSONSerialization.data(withJSONObject: te) else { return [] }
        return (try? JSONDecoder().decode([LexEntry].self, from: teData)) ?? []
    }()
    static let library: [String: LibItem] = {
        struct File: Decodable { let items: [String: LibItem] }
        guard let data = bundled("library", "json") else { return [:] }
        return (try? JSONDecoder().decode(File.self, from: data).items) ?? [:]
    }()
    static let script: [ScriptLine] = {
        guard let data = bundled("call_script", "json") else { return [] }
        return (try? JSONDecoder().decode([ScriptLine].self, from: data)) ?? []
    }()

    private static func bundled(_ name: String, _ ext: String) -> Data? {
        Bundle.main.url(forResource: name, withExtension: ext).flatMap { try? Data(contentsOf: $0) }
    }

    /// Only these get highlighted: things, places, festivals, customs and sayings worth a picture or an explanation.
    static let worthExplaining: Set<String> = ["food", "vehicle", "place", "clothing", "festival", "culture", "idiom"]
    /// Everyday English that happens to name a picture ("are you well?" is not about a water well).
    static let plainEnglish: Set<String> = ["well", "home", "house", "people", "morning", "today", "fine", "good", "photo", "photos", "time", "water", "come", "rain", "rains", "field", "study", "care"]

    static func hits(in telugu: String) -> [(LexEntry, String)] {
        var out: [(LexEntry, String)] = []
        for e in lexicon where worthExplaining.contains(e.category) {
            if let form = e.forms.map({ $0.trimmingCharacters(in: CharacterSet(charactersIn: ",.")) }).first(where: { telugu.contains($0) }),
               !out.contains(where: { $0.0.id == e.id }) {
                out.append((e, form))
            }
        }
        return out
    }

    static func libraryKey(forEnglish word: String) -> String? {
        let w = word.lowercased()
        guard w.count > 3, !plainEnglish.contains(w) else { return nil }
        let stem = w.hasSuffix("es") ? String(w.dropLast(2)) : w.hasSuffix("s") ? String(w.dropLast()) : w
        return library.first { k, v in k == stem || k.split(separator: "_").last.map(String.init) == stem || (v.name ?? "").lowercased() == stem }?.key
    }

    static func word(_ key: String) -> Word {
        let e = lexicon.first { $0.id == key }
        let lib = e.flatMap { library[$0.id] } ?? library[key]
        return Word(key: key,
                    telugu: e?.forms.first?.trimmingCharacters(in: CharacterSet(charactersIn: ",.")),
                    roman: e.map { $0.roman ?? $0.id.replacingOccurrences(of: "_", with: " ") },
                    english: e?.translate_as ?? lib?.name ?? key.replacingOccurrences(of: "_", with: " "),
                    note: e?.note,
                    description: lib?.description.map { $0.components(separatedBy: ". ").first.map { $0.hasSuffix(".") ? $0 : $0 + "." } ?? $0 },
                    image: lib?.image,
                    category: e?.category ?? lib?.category ?? "word",
                    pictureName: lib?.name)
    }
}

struct Word: Identifiable, Hashable {
    let key: String
    var telugu: String?
    var roman: String?
    var english: String
    var note: String?
    var description: String?
    var image: String?          // "images/pulihora.jpg"
    var category: String
    var pictureName: String?
    var id: String { key }

    var categoryLabel: String {
        ["food": "Food", "vehicle": "Getting around", "place": "Place", "clothing": "Clothing", "festival": "Festival",
         "family": "Family", "idiom": "Saying", "slang": "Slang", "culture": "Custom"][category] ?? category.capitalized
    }
}

/// A photo from the bundle if we ship it, otherwise from Weave on the Mac.
struct WordImage: View {
    let path: String?
    var body: some View {
        if let path, let file = path.split(separator: "/").last, let ui = UIImage(named: String(file)) {
            Image(uiImage: ui).resizable().scaledToFill()
        } else if let path, let url = URL(string: GardenClient.serverURL + "/" + path) {
            AsyncImage(url: url, transaction: .init(animation: .easeOut(duration: 0.4))) { phase in
                if let img = phase.image { img.resizable().scaledToFill() } else { Theme.surface2 }
            }
        } else {
            Theme.surface2
        }
    }
}

// MARK: - A conversation: demo from the scripted call, or live from the translation pipeline (subtitles.py)

@MainActor
final class Conversation: ObservableObject {
    enum Who { case you, them }
    enum Mode { case demo, live }

    struct Line: Identifiable {
        let id: String
        let who: Who
        var lang: String
        var original = ""
        var translation = ""
        var pending = false
        var typing = false
        var matches: [(key: String, text: String)] = []   // tappable words and the text they appear as
        var visual: String?                               // word key with a photo
        var note: String?
        var tag: String?
        var voiced = false
        let time = Date()
    }

    @Published private(set) var lines: [Line] = []
    @Published private(set) var speaking: Set<Who> = []
    @Published private(set) var translating = 0
    @Published private(set) var mode: Mode = .demo
    @Published private(set) var connected = false
    @Published private(set) var seen: [String: Word] = [:]
    @Published var savedThisCall = 0

    let partner: Connection
    let started = Date()
    private var task: Task<Void, Never>?
    private var socket: URLSessionWebSocketTask?
    private var replies: [String] = []

    init(partner: Connection) { self.partner = partner }

    func start(forceDemo: Bool = false) {
        task = Task {
            try? await Task.sleep(for: .milliseconds(700))
            withAnimation(.spring(response: 0.55, dampingFraction: 0.85)) { connected = true }
            if !forceDemo, await connectLive() {
                mode = .live
                await receiveLive()
            } else {
                mode = .demo
                await runDemo()
            }
        }
    }

    func stop() {
        task?.cancel()
        socket?.cancel(with: .normalClosure, reason: nil)
        socket = nil
    }

    func holdToTalk(_ on: Bool) {
        setSpeaking(.you, on)
        if !on, mode == .demo, !replies.isEmpty { Task { await youSay(replies.removeFirst(), alreadySpoke: true) } }
    }

    /// The "I didn't know this" button: the pipeline goes back to translating that word.
    func forget(_ key: String) {
        socket?.send(.string(#"{"type":"forget","id":"\#(key)"}"#)) { _ in }
    }

    // MARK: state helpers

    private func setSpeaking(_ who: Who, _ on: Bool) {
        withAnimation(.easeOut(duration: 0.25)) { if on { speaking.insert(who) } else { speaking.remove(who) } }
    }

    private func setTranslating(_ delta: Int) {
        withAnimation(.easeOut(duration: 0.25)) { translating = max(0, translating + delta) }
    }

    @discardableResult
    private func add(_ who: Who, lang: String, id: String = UUID().uuidString) -> Int {
        withAnimation(.spring(response: 0.38, dampingFraction: 0.9)) { lines.append(Line(id: id, who: who, lang: lang)) }
        return lines.count - 1
    }

    private func index(_ id: String) -> Int? { lines.firstIndex { $0.id == id } }

    /// Reveal text a few characters at a time, like it's arriving.
    private func type(_ text: String, into i: Int, original: Bool, perSecond: Double) async {
        let chars = Array(text)
        lines[i].typing = true
        var n = 0
        while n < chars.count {
            if Task.isCancelled { return }
            n = min(chars.count, n + 2)
            if original { lines[i].original = String(chars.prefix(n)) } else { lines[i].translation = String(chars.prefix(n)) }
            try? await Task.sleep(for: .seconds(2 / perSecond))
        }
        lines[i].typing = false
    }

    private func attachWords(_ i: Int, telugu: String, english: String) {
        var matches: [(String, String)] = []
        for (e, form) in Knowledge.hits(in: telugu) {
            let w = Knowledge.word(e.id)
            let inEnglish = [w.roman, e.translate_as].compactMap { $0 }.first { english.range(of: $0, options: .caseInsensitive) != nil }
            matches.append((e.id, inEnglish ?? form))
        }
        for token in english.components(separatedBy: CharacterSet.letters.inverted) {
            if let k = Knowledge.libraryKey(forEnglish: token), !matches.contains(where: { $0.0 == k || Knowledge.word($0.0).image == Knowledge.word(k).image }) {
                matches.append((k, token))
            }
        }
        matches.sort { (Knowledge.word($0.0).image != nil ? 0 : 1) < (Knowledge.word($1.0).image != nil ? 0 : 1) }
        matches = Array(matches.prefix(2))
        withAnimation(.easeOut(duration: 0.3)) {
            lines[i].matches = matches.map { (key: $0.0, text: $0.1) }
            for m in matches { seen[m.0] = Knowledge.word(m.0) }
        }
        if let pic = matches.first(where: { Knowledge.word($0.0).image != nil }) {
            Task {
                try? await Task.sleep(for: .milliseconds(260))
                withAnimation(.spring(response: 0.4, dampingFraction: 0.88)) { lines[i].visual = pic.0 }
            }
        }
    }

    // MARK: demo

    private func runDemo() async {
        replies = ["I'm good, Ammamma! Tell Thatayya I said hi.", "It's already getting cold here.", "Pulihora! I miss your cooking so much.",
                   "I'll try to come for Sankranti this year.", "Next Friday. I'm studying a lot, don't worry.", "Yes, I just had dinner."]
        let native = Knowledge.script.filter { $0.route == "native" && !$0.meaning.hasPrefix("(repeat)") }
        let english = Knowledge.script.first { $0.route == "english" && $0.text.localizedCaseInsensitiveContains("very good") }
        try? await Task.sleep(for: .milliseconds(900))
        for (i, l) in native.enumerated() {
            if Task.isCancelled { return }
            await themSay(l)
            try? await Task.sleep(for: .milliseconds(1500))
            if [0, 2, 3, 5, 7, 9].contains(i), !replies.isEmpty {
                await youSay(replies.removeFirst(), alreadySpoke: false)
                try? await Task.sleep(for: .milliseconds(900))
            }
            if i == 6, let english {
                await themSayEnglish(english.text)
                try? await Task.sleep(for: .milliseconds(1400))
            }
        }
    }

    private func themSay(_ l: ScriptLine) async {
        let parts = l.meaning.split(separator: "(", maxSplits: 1)
        let meaning = String(parts.first ?? "").trimmingCharacters(in: .whitespaces)
        var note = parts.count > 1 ? String(parts[1]).trimmingCharacters(in: CharacterSet(charactersIn: ") ")) : nil
        if note?.contains("Telugu with an English word") == true { note = nil }
        setSpeaking(.them, true)
        let i = add(.them, lang: partner.lang)
        await type(l.text, into: i, original: true, perSecond: 26)
        setSpeaking(.them, false)
        guard !Task.isCancelled else { return }
        lines[i].pending = true
        setTranslating(+1)
        try? await Task.sleep(for: .milliseconds(520))
        setTranslating(-1)
        lines[i].pending = false
        await type(meaning, into: i, original: false, perSecond: 70)
        if let note { withAnimation(.easeOut(duration: 0.3)) { lines[i].note = note } }
        attachWords(i, telugu: l.text, english: meaning)
    }

    private func themSayEnglish(_ text: String) async {
        setSpeaking(.them, true)
        let i = add(.them, lang: "en")
        await type(text, into: i, original: true, perSecond: 30)
        setSpeaking(.them, false)
    }

    private func youSay(_ text: String, alreadySpoke: Bool) async {
        if !alreadySpoke {
            if let r = replies.firstIndex(of: text) { replies.remove(at: r) }
            setSpeaking(.you, true)
            try? await Task.sleep(for: .milliseconds(900))
            setSpeaking(.you, false)
        }
        let i = add(.you, lang: "en")
        await type(text, into: i, original: true, perSecond: 55)
    }

    // MARK: live

    private func liveURL() -> URL? {
        guard let host = URL(string: GardenClient.serverURL)?.host else { return nil }
        return URL(string: "ws://\(host):8765")
    }

    private func connectLive() async -> Bool {
        guard let url = liveURL() else { return false }
        let ws = URLSession.shared.webSocketTask(with: url)
        ws.resume()
        let ok = await withTaskGroup(of: Bool.self) { group in
            group.addTask { await withCheckedContinuation { c in ws.sendPing { c.resume(returning: $0 == nil) } } }
            group.addTask { try? await Task.sleep(for: .seconds(1.5)); return false }
            let first = await group.next() ?? false
            group.cancelAll()
            return first
        }
        if ok { socket = ws } else { ws.cancel() }
        return ok
    }

    private func receiveLive() async {
        var partial: Int?
        while let ws = socket, !Task.isCancelled {
            guard let msg = try? await ws.receive() else { break }
            guard case .string(let text) = msg, let data = text.data(using: .utf8),
                  let m = try? JSONSerialization.jsonObject(with: data) as? [String: Any], let type = m["type"] as? String else { continue }
            let id = (m["id"] as? Int).map(String.init) ?? (m["id"] as? String) ?? ""
            switch type {
            case "speaking":
                setSpeaking(.them, true)
                if partial == nil { partial = add(.them, lang: partner.lang) }
            case "partial":
                let t = m["text"] as? String ?? ""
                guard !t.isEmpty else { continue }
                if partial == nil { partial = add(.them, lang: partner.lang) }
                lines[partial!].original = t
                lines[partial!].typing = true
            case "original":
                setSpeaking(.them, false)
                let i: Int
                if let p = partial {
                    i = p
                    lines[i] = Line(id: id, who: .them, lang: partner.lang)
                } else { i = add(.them, lang: partner.lang, id: id) }
                partial = nil
                lines[i].original = m["text"] as? String ?? ""
                if m["route"] as? String == "english" { lines[i].lang = "en" } else { lines[i].pending = true; setTranslating(+1) }
            case "english":
                guard let i = index(id) else { continue }
                if lines[i].pending { lines[i].pending = false; setTranslating(-1) }
                if m["route"] as? String == "english" { continue }
                let english = m["text"] as? String ?? ""
                let kept = (m["kept"] as? [[String: Any]] ?? []).compactMap { k -> (String, String)? in
                    guard let key = k["id"] as? String, let t = k["telugu"] as? String else { return nil }
                    return (key, t)
                }
                let original = lines[i].original
                Task {
                    await self.type(english, into: i, original: false, perSecond: 90)
                    self.attachWords(i, telugu: original, english: english)
                    if !kept.isEmpty {
                        withAnimation { self.lines[i].matches = Array((kept.map { (key: $0.0, text: $0.1) } + self.lines[i].matches).prefix(3)) }
                        for k in kept { self.seen[k.0] = Knowledge.word(k.0) }
                    }
                }
            case "details":
                guard let i = index(id) else { continue }
                if let intent = m["intent"] as? String, intent == "question" || intent == "request" {
                    lines[i].tag = intent == "question" ? "Asked you" : "Request"
                }
            case "picture":
                let i = index(id) ?? lines.lastIndex { $0.who == .them }
                guard let i, let key = m["id"] as? String else { continue }
                if Knowledge.library[key] != nil {
                    withAnimation(.spring(response: 0.4, dampingFraction: 0.88)) { lines[i].visual = key }
                    seen[key] = Knowledge.word(key)
                }
            case "voice":
                if let i = index(id) { lines[i].voiced = true }
            default: break
            }
        }
    }
}
