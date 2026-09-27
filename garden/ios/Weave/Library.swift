import Charts
import SwiftUI

extension Stage {
    /// One accent, three strengths: faint when new, half while learning, full once known.
    var tint: Color {
        switch self {
        case .bloom: Theme.accent
        case .sprout: Theme.lavender
        case .seed: Theme.accent.opacity(0.14)
        }
    }
}

extension Plant {
    /// Everything the word sheet needs: the team's lexicon and photos when we have them, the garden's own fields otherwise.
    var asWord: Word {
        // The translator plants a word as its first Telugu form (garden.from_lexicon); find that entry again.
        let id = (roman ?? "").replacingOccurrences(of: " ", with: "_")
        if let e = Knowledge.lexicon.first(where: { e in e.forms.contains { $0.trimmingCharacters(in: CharacterSet(charactersIn: " ,.^")) == phrase } || e.id == id }) {
            var w = Knowledge.word(e.id)
            w.telugu = phrase
            return w
        }
        return Word(key: phrase, telugu: phrase, roman: roman, english: english ?? "", note: note, description: nil,
                    image: nil, category: category, pictureName: nil)
    }
}

/// One word in the dictionary: from the family dictionary when there is one (real calls, her voice), else the garden.
struct WordItem: Identifiable {
    let id: String
    let word: Word
    let stage: Stage
    let progress: Int        // 0...8 toward known
    let times: Int
    let voice: String?       // her voice saying it
}

extension People {
    var wordItems: [WordItem] {
        if !dictionary.isEmpty {
            return dictionary.map { id, e in
                var w = Knowledge.lexicon.contains { $0.id == id } ? Knowledge.word(id)
                    : Word(key: id, telugu: e.telugu, roman: e.roman, english: e.english ?? "", note: e.note, description: nil, image: nil, category: e.category ?? "word", pictureName: nil)
                w.telugu = e.telugu ?? w.telugu; w.roman = e.roman ?? w.roman
                if let en = e.english, !en.isEmpty { w.english = en }
                let stage: Stage = e.status == "known" ? .bloom : e.status == "learning" ? .sprout : .seed
                return WordItem(id: id, word: w, stage: stage, progress: stage == .bloom ? 8 : min(7, e.times ?? 0), times: e.times ?? 0, voice: voice(for: id))
            }
            .sorted { ($0.stage == .bloom ? 0 : $0.stage == .sprout ? 1 : 2, -$0.times) < ($1.stage == .bloom ? 0 : $1.stage == .sprout ? 1 : 2, -$1.times) }
        }
        return (growth ?? .empty).plants.sorted { ($0.growth, $0.heard) > ($1.growth, $1.heard) }
            .map { p in WordItem(id: p.id, word: p.asWord, stage: p.stageEnum, progress: p.growth, times: p.heard, voice: voice(for: p.asWord.key)) }
    }
}

// MARK: - Words: the family dictionary

struct WordsView: View {
    @EnvironmentObject var people: People
    @State private var filter: Filter = .all
    @State private var query = ""
    @State private var open: Word?
    @Namespace private var pill

    enum Filter: String, CaseIterable, Identifiable { case all = "All", known = "Known", learning = "Learning", new = "New", saved = "Saved"; var id: String { rawValue } }

    var body: some View {
        let all = people.wordItems
        let items = all
            .filter { i in
                switch filter {
                case .all: true
                case .known: i.stage == .bloom
                case .learning: i.stage == .sprout
                case .new: i.stage == .seed
                case .saved: false
                }
            }
            .filter { query.isEmpty || [$0.word.telugu ?? "", $0.word.english, $0.word.roman ?? ""].contains { $0.localizedCaseInsensitiveContains(query) } }
        let saved = people.vocab.filter { query.isEmpty || [$0.telugu ?? "", $0.english, $0.roman ?? ""].contains { $0.localizedCaseInsensitiveContains(query) } }

        ScrollView {
            VStack(alignment: .leading, spacing: 14) {
                VStack(alignment: .leading, spacing: 6) {
                    Text("Words").font(Fonts.display(34, .semibold)).tracking(-0.8).foregroundStyle(Theme.lavender)
                    Text(people.dictionary.isEmpty ? "Every word from your calls." : "Your family dictionary: every word from your calls, in her voice.")
                        .font(Fonts.ui(15)).foregroundStyle(Theme.text2)
                }
                .padding(.top, 16)
                .reveal(0)

                HStack(spacing: 10) {
                    Image(systemName: "magnifyingglass").font(.system(size: 14)).foregroundStyle(Theme.text3)
                    TextField("", text: $query, prompt: Text("Telugu or English").foregroundColor(Theme.text3))
                        .font(Fonts.ui(15)).foregroundStyle(Theme.text).autocorrectionDisabled().textInputAutocapitalization(.never)
                }
                .padding(.horizontal, 14).frame(height: 44)
                .background(Theme.surface, in: .rect(cornerRadius: 12))
                .overlay(RoundedRectangle(cornerRadius: 12).strokeBorder(Theme.border, lineWidth: 1))
                .reveal(1)

                segmented(all).reveal(2)

                if filter == .saved {
                    if saved.isEmpty {
                        empty("Tap a highlighted word during a call, then “Add to vocabulary”.")
                    } else {
                        list(saved.map { v in WordItem(id: v.id, word: Knowledge.lexicon.contains { $0.id == v.key } ? Knowledge.word(v.key) : Word(key: v.key, telugu: v.telugu, roman: v.roman, english: v.english, note: nil, description: nil, image: v.image, category: "word", pictureName: nil),
                                                    stage: .seed, progress: -1, times: 0, voice: people.voice(for: v.key)) })
                    }
                } else if items.isEmpty {
                    empty(!query.isEmpty ? "No words match “\(query)”." : people.source == .offline ? "Connect to Weave on your Mac in Settings to see your words." : "Words from your calls show up here.")
                } else {
                    list(items)
                }
            }
            .padding(.horizontal, 20)
            .padding(.bottom, 32)
            .animation(.easeOut(duration: 0.2), value: filter)
        }
        .scrollIndicators(.hidden)
        .scrollDismissesKeyboard(.immediately)
        .refreshable { await people.loadGrowth() }
        .background(Backdrop())
        .sheet(item: $open) { w in
            WordSheet(word: w, line: nil, partnerName: people.partner.name, live: false) { people.save(w) } forget: {}
                .environmentObject(people)
                .presentationDetents([.large]).presentationBackground(Theme.bg2).presentationCornerRadius(24)
        }
    }

    private func segmented(_ all: [WordItem]) -> some View {
        let counts: [Filter: Int] = [.all: all.count, .known: all.filter { $0.stage == .bloom }.count, .learning: all.filter { $0.stage == .sprout }.count,
                                     .new: all.filter { $0.stage == .seed }.count, .saved: people.vocab.count]
        return ScrollView(.horizontal) {
            HStack(spacing: 2) {
                ForEach(Filter.allCases) { f in
                    let on = filter == f
                    Button { filter = f } label: {
                        HStack(spacing: 5) {
                            Text(f.rawValue).font(Fonts.ui(13, .semibold))
                            Text("\(counts[f] ?? 0)").font(Fonts.mono(11, .regular)).foregroundStyle(Theme.text3)
                        }
                        .foregroundStyle(on ? Theme.text : Theme.text2)
                        .padding(.horizontal, 12).frame(height: 32)
                        .background {
                            if on {
                                RoundedRectangle(cornerRadius: 9).fill(Theme.surface3)
                                    .overlay(RoundedRectangle(cornerRadius: 9).strokeBorder(Theme.border2, lineWidth: 1))
                                    .matchedGeometryEffect(id: "pill", in: pill)
                            }
                        }
                        .contentShape(Rectangle())
                    }
                    .buttonStyle(.plain)
                    .sensoryFeedback(.selection, trigger: on)
                }
            }
            .padding(3)
            .background(Theme.surface, in: .rect(cornerRadius: 12))
            .overlay(RoundedRectangle(cornerRadius: 12).strokeBorder(Theme.border, lineWidth: 1))
            .animation(.snappy(duration: 0.25), value: filter)
        }
        .scrollIndicators(.hidden)
    }

    private func list(_ rows: [WordItem]) -> some View {
        VStack(spacing: 0) {
            ForEach(Array(rows.enumerated()), id: \.element.id) { i, row in
                if i > 0 { Rectangle().fill(Theme.border).frame(height: 1).padding(.leading, 16) }
                Button { open = row.word } label: { WordRow(item: row) }.buttonStyle(RowStyle())
            }
        }
        .background(Card())
        .clipShape(.rect(cornerRadius: Theme.radius))
        .reveal(3)
    }

    private func empty(_ text: String) -> some View {
        Panel { Text(text).font(Fonts.ui(14)).foregroundStyle(Theme.text2) }
    }
}

struct WordRow: View {
    let item: WordItem
    var body: some View {
        let word = item.word
        HStack(spacing: 14) {
            if word.image != nil {
                WordImage(path: word.image).frame(width: 40, height: 40).clipShape(.rect(cornerRadius: 10))
            } else {
                RoundedRectangle(cornerRadius: 10).fill(item.progress >= 0 ? item.stage.tint : Theme.surface2).frame(width: 40, height: 40)
                    .overlay(Text(String((word.telugu ?? word.english).prefix(1))).font(Fonts.telugu(17, .medium)).foregroundStyle(Theme.text))
            }
            VStack(alignment: .leading, spacing: 2) {
                Text(word.telugu ?? word.english).font(Fonts.telugu(17, .medium)).foregroundStyle(Theme.text)
                Text([word.roman, word.english].compactMap { $0 }.filter { !$0.isEmpty }.joined(separator: " · "))
                    .font(Fonts.ui(13)).foregroundStyle(Theme.text2).lineLimit(1)
            }
            Spacer(minLength: 8)
            if item.progress >= 0 {
                VStack(alignment: .trailing, spacing: 6) {
                    Text(item.stage.label).font(Fonts.mono(10.5)).foregroundStyle(item.stage == .bloom ? Theme.accent : Theme.text3)
                    SegmentBar(filled: item.progress).frame(width: 56)
                }
            }
            if let v = item.voice { VoiceButton(path: v, size: 30) }
        }
        .padding(.horizontal, 16).padding(.vertical, 12)
        .contentShape(Rectangle())
    }
}

/// Eight thin steps from new to known.
struct SegmentBar: View {
    let filled: Int
    var total = 8
    var height: CGFloat = 3
    var body: some View {
        HStack(spacing: 2) {
            ForEach(0..<total, id: \.self) { i in
                Capsule().fill(i < filled ? Theme.accent : Theme.surface3).frame(height: height)
            }
        }
        .animation(.easeOut(duration: 0.3), value: filled)
    }
}

// MARK: - Progress

struct ProgressView_: View {
    @EnvironmentObject var people: People
    @State private var picked: Date?
    @State private var open: Word?
    @State private var settings = false

    var body: some View {
        let snap = people.growth ?? .empty
        ScrollView {
            VStack(alignment: .leading, spacing: 12) {
                header(snap)
                GrowthPlant(plants: snap.plants, totals: snap.totals)
                    .padding(.horizontal, -20)
                    .reveal(1)
                if snap.totals.phrases == 0 {
                    Text(people.source == .offline ? "Connect to Weave on your Mac in Settings." : "Your plant grows with every word you hear on your calls.")
                        .font(Fonts.ui(15)).foregroundStyle(Theme.text2).frame(maxWidth: .infinity).multilineTextAlignment(.center)
                } else {

                Grid(horizontalSpacing: 12, verticalSpacing: 12) {
                    GridRow { stat("Known", "\(snap.totals.bloom)", "of \(snap.totals.phrases) words", accent: true); stat("Learning", "\(snap.totals.sprout)", "subtitles only", tint: Theme.lavender) }
                    GridRow { stat("Hearings", "\(snap.totals.heard)", "across all calls"); stat("Streak", "\(snap.streak)", snap.streak == 1 ? "day" : "days") }
                }
                .reveal(1)

                chart(snap).reveal(2)
                weave(snap).reveal(3)
                stages(snap).reveal(4)
                milestones(snap).reveal(5)
                }
            }
            .padding(.horizontal, 20)
            .padding(.bottom, 32)
        }
        .scrollIndicators(.hidden)
        .refreshable { await people.loadGrowth() }
        .background(Backdrop())
        .sheet(isPresented: $settings) { SettingsView().environmentObject(people) }
        .sheet(item: $open) { w in
            WordSheet(word: w, line: nil, partnerName: people.partner.name, live: false) { people.save(w) } forget: {}
                .environmentObject(people)
                .presentationDetents([.large]).presentationBackground(Theme.bg2).presentationCornerRadius(24)
        }
    }

    /// Your name, what the plant is made of, and Settings.
    private func header(_ snap: GardenSnapshot) -> some View {
        HStack(alignment: .top) {
            VStack(alignment: .leading, spacing: 6) {
                Text("Weave").font(Fonts.display(34, .semibold)).tracking(-0.8).foregroundStyle(Theme.lavender)
                Group {
                    if snap.totals.phrases == 0 {
                        Text("A seed, for now.").foregroundStyle(Theme.text2)
                    } else {
                        Text("\(snap.totals.phrases) words growing").foregroundStyle(Theme.text2)
                            + Text("  ·  \(snap.totals.bloom) in bloom").foregroundStyle(Theme.lavender)
                    }
                }
                .font(Fonts.ui(15)).contentTransition(.numericText())
            }
            Spacer()
            Button { settings = true } label: { Avatar(text: String((people.profileName ?? "S").prefix(1)), size: 34, tint: Theme.lavender) }
                .buttonStyle(Pressable()).accessibilityLabel("Settings")
        }
        .padding(.top, 16)
        .reveal(0)
    }

    private func stat(_ label: String, _ value: String, _ sub: String, accent: Bool = false, tint: Color? = nil) -> some View {
        let glow = tint ?? (accent ? Theme.accent : Theme.text3)
        return Panel {
            Eyebrow(label, color: tint ?? (accent ? Theme.accent : Theme.text3))
            Text(value).font(Fonts.display(36, .medium)).monospacedDigit().foregroundStyle(Theme.text)
                .contentTransition(.numericText()).padding(.top, 10)
            Text(sub).font(Fonts.ui(12)).foregroundStyle(Theme.text2)
        }
        .overlay(
            RadialGradient(colors: [glow.opacity(0.16), .clear], center: .topLeading, startRadius: 0, endRadius: 170)
                .clipShape(RoundedRectangle(cornerRadius: Theme.radius)).allowsHitTesting(false)
        )
    }

    private func chart(_ snap: GardenSnapshot) -> some View {
        let day = picked.flatMap { p in snap.days.first { Calendar.current.isDate($0.day, inSameDayAs: p) } }
        let week = snap.days.suffix(7).reduce(0) { $0 + $1.heard }
        return Panel {
            Eyebrow(day.map { $0.day.formatted(.dateTime.weekday(.wide).month(.abbreviated).day()) } ?? "Last 14 days")
            HStack(alignment: .firstTextBaseline, spacing: 6) {
                Text("\(day?.heard ?? week)").font(Fonts.ui(26, .medium)).tracking(-0.8).monospacedDigit().foregroundStyle(Theme.text)
                    .contentTransition(.numericText())
                Text(day == nil ? "words heard this week" : "words heard").font(Fonts.ui(14)).foregroundStyle(Theme.text2)
            }
            .padding(.top, 6)
            .animation(.easeOut(duration: 0.2), value: day?.date)
            Chart(snap.days) { d in
                BarMark(x: .value("Day", d.day, unit: .day), y: .value("Heard", d.heard), width: .ratio(0.6))
                    .foregroundStyle(day == nil || day?.date == d.date ? Theme.accent : Theme.accent.opacity(0.28))
                    .cornerRadius(3)
                if d.bloomed > 0 {
                    PointMark(x: .value("Day", d.day, unit: .day), y: .value("Heard", d.heard))
                        .symbolSize(16).foregroundStyle(Theme.text).offset(y: -9)
                }
            }
            .chartXSelection(value: $picked)
            .chartXAxis {
                AxisMarks(values: .stride(by: .day, count: 2)) { _ in
                    AxisValueLabel(format: .dateTime.day(), centered: true).foregroundStyle(Theme.text3)
                }
            }
            .chartYAxis {
                AxisMarks(position: .trailing, values: .automatic(desiredCount: 3)) { _ in
                    AxisGridLine().foregroundStyle(Theme.border)
                    AxisValueLabel().foregroundStyle(Theme.text3)
                }
            }
            .frame(height: 170)
            .padding(.top, 14)
            HStack(spacing: 6) {
                Circle().fill(Theme.text).frame(width: 5, height: 5)
                Text("A word became known that day · touch for details").font(Fonts.ui(12)).foregroundStyle(Theme.text3)
            }
            .padding(.top, 12)
        }
    }

    /// Every word as one tile, from faint to full as it becomes known.
    private func weave(_ snap: GardenSnapshot) -> some View {
        let words = snap.plants.sorted { ($0.firstHeard ?? 0) < ($1.firstHeard ?? 0) }
        return Panel {
            HStack(alignment: .firstTextBaseline) {
                Eyebrow("Your weave")
                Spacer()
                Text("\(snap.totals.bloom) of \(snap.totals.phrases) known").font(Fonts.ui(13)).monospacedDigit().foregroundStyle(Theme.text2)
            }
            LazyVGrid(columns: Array(repeating: GridItem(.flexible(), spacing: 5), count: 12), spacing: 5) {
                ForEach(words) { p in
                    RoundedRectangle(cornerRadius: 3.5).fill(p.stageEnum.tint).aspectRatio(1, contentMode: .fit)
                        .overlay(RoundedRectangle(cornerRadius: 3.5).strokeBorder(p.stageEnum == .seed ? Theme.accent.opacity(0.25) : .clear, lineWidth: 1))
                        .onTapGesture { open = p.asWord }
                }
            }
            .padding(.top, 14)
            HStack(spacing: 16) {
                ForEach(Stage.allCases.reversed()) { s in
                    HStack(spacing: 6) {
                        RoundedRectangle(cornerRadius: 2.5).fill(s.tint).frame(width: 10, height: 10)
                        Text(s.label).font(Fonts.ui(12)).foregroundStyle(Theme.text2)
                    }
                }
            }
            .padding(.top, 14)
        }
    }

    private func stages(_ snap: GardenSnapshot) -> some View {
        let t = snap.thresholds
        let rows: [(Stage, String)] = [(.seed, "Heard under \(t.subtitle)×"), (.sprout, "\(t.subtitle)–\(t.bloom - 1)×"), (.bloom, "\(t.bloom)× or more")]
        return Panel(padding: 0) {
            Eyebrow("How words move").padding([.horizontal, .top], 16).padding(.bottom, 4)
            ForEach(Array(rows.enumerated()), id: \.offset) { i, row in
                if i > 0 { Rectangle().fill(Theme.border).frame(height: 1).padding(.leading, 46) }
                HStack(spacing: 14) {
                    RoundedRectangle(cornerRadius: 4).fill(row.0.tint).frame(width: 16, height: 16)
                    VStack(alignment: .leading, spacing: 2) {
                        Text(row.0.label).font(Fonts.ui(15, .medium)).foregroundStyle(Theme.text)
                        Text("\(row.1) · \(row.0.meaning)").font(Fonts.ui(13)).foregroundStyle(Theme.text2)
                    }
                }
                .padding(.horizontal, 16).padding(.vertical, 11)
            }
            Text("“Didn't know it” on a word moves it back a step.").font(Fonts.ui(12)).foregroundStyle(Theme.text3)
                .padding(.horizontal, 16).padding(.top, 2).padding(.bottom, 14)
        }
    }

    private func milestones(_ snap: GardenSnapshot) -> some View {
        let events = snap.recent.filter { $0.kind != "heard" }.prefix(8)
        return Panel(padding: 0) {
            Eyebrow("Milestones").padding([.horizontal, .top], 16).padding(.bottom, 4)
            if events.isEmpty {
                Text("Words you learn will show up here.").font(Fonts.ui(14)).foregroundStyle(Theme.text2).padding(.horizontal, 16).padding(.bottom, 14)
            }
            ForEach(Array(events.enumerated()), id: \.element.id) { i, e in
                if i > 0 { Rectangle().fill(Theme.border).frame(height: 1).padding(.leading, 60) }
                Button { if let p = snap.plant(e.phrase) { open = p.asWord } } label: {
                    HStack(spacing: 14) {
                        Image(systemName: e.kind == "bloomed" ? "checkmark" : e.kind == "sprouted" ? "arrow.up.right" : "arrow.uturn.backward")
                            .font(.system(size: 12, weight: .semibold)).foregroundStyle(e.kind == "bloomed" ? Theme.accent : Theme.text2)
                            .frame(width: 30, height: 30)
                            .background(e.kind == "bloomed" ? Theme.accent.opacity(0.12) : Theme.surface2, in: .rect(cornerRadius: 9))
                        (Text(e.phrase).font(Fonts.telugu(15, .medium)).foregroundColor(Theme.text)
                            + Text(e.kind == "bloomed" ? "  is now known" : e.kind == "sprouted" ? "  moved to learning" : "  needs more help").font(Fonts.ui(14)).foregroundColor(Theme.text2))
                            .lineLimit(1)
                        Spacer(minLength: 8)
                        Text(timeAgo(e.ts, now: snap.now)).font(Fonts.mono(11, .regular)).foregroundStyle(Theme.text3)
                    }
                    .padding(.horizontal, 16).padding(.vertical, 10)
                    .contentShape(Rectangle())
                }
                .buttonStyle(RowStyle())
            }
            Spacer().frame(height: 6)
        }
    }
}
