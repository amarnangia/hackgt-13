import SwiftUI

/// Your profile: your name, and the family's personalized voices. Everything else comes from the Mac on its own.
struct SettingsView: View {
    @EnvironmentObject var people: People
    @Environment(\.dismiss) private var dismiss
    @State private var switching = false

    var body: some View {
        ScrollView {
        VStack(alignment: .leading, spacing: 12) {
            HStack {
                Text("Profile").font(Fonts.ui(24, .medium)).tracking(-0.6).foregroundStyle(Theme.lavender)
                Spacer()
                Button("Done") { dismiss() }.font(Fonts.ui(15, .medium)).foregroundStyle(Theme.accent)
            }
            .padding(.bottom, 8)
            Panel {
                HStack {
                    VStack(alignment: .leading, spacing: 2) {
                        Eyebrow("Your name")
                        Text(people.profileName ?? "Not set").font(Fonts.ui(17, .medium)).foregroundStyle(Theme.text).padding(.top, 4)
                    }
                    Spacer()
                    Button("Change") { switching = true }.font(Fonts.ui(14, .medium)).foregroundStyle(Theme.accent)
                }
            }
            FamilyVoices()
        }
        .padding(20)
        }
        .preferredColorScheme(.dark)
        .task { await people.loadFamily() }
        .sheet(isPresented: $switching) { SwitchPersonView() }
    }
}

/// Everyone's personalized voice: record, redo or remove (Settings and the Voice tab).
struct FamilyVoices: View {
    @EnvironmentObject var people: People
    @State private var recordingFor: VoiceTarget?

    /// You, then the family and the people you call: whose translations can be spoken in their own voice.
    private var voicePeople: [VoiceTarget] {
        var seen = Set<String>()
        let me = VoiceTarget(name: people.profileName ?? "You", isYou: true)
        let others = (people.family ?? []).map(\.name) + people.connections.map(\.name)
        return ([me] + others.map { VoiceTarget(name: $0, isYou: false) }).filter { seen.insert($0.id).inserted }
    }

    var body: some View {
        Panel {
            Eyebrow("Personalized voices")
            Text("Record someone reading for about a minute, and Weave speaks their translations in their own voice, in English and Telugu. The Mac makes the voice with ElevenLabs.")
                .font(Fonts.ui(12)).foregroundStyle(Theme.text2).padding(.top, 6)
            if people.family == nil {
                Text("Connect to the Mac to see or record voices.").font(Fonts.ui(13)).foregroundStyle(Theme.text3).padding(.top, 12)
            } else {
                ForEach(voicePeople) { target in
                    let has = people.family?.contains { $0.id == target.id && $0.voice } == true
                    HStack {
                        VStack(alignment: .leading, spacing: 2) {
                            Text(target.isYou ? "\(target.name) (you)" : target.name).font(Fonts.ui(15, .medium)).foregroundStyle(Theme.text)
                            Text(has ? "Their own voice" : "Stock voice").font(Fonts.ui(12)).foregroundStyle(has ? Theme.accent : Theme.text3)
                        }
                        Spacer()
                        if has {
                            Button("Remove") {
                                Task { _ = await GardenClient.removeVoice(name: target.name); await people.loadFamily() }
                            }
                            .font(Fonts.ui(13)).foregroundStyle(Theme.danger)
                        }
                        Button(has ? "Redo" : "Record") { recordingFor = target }
                            .font(Fonts.ui(13, .medium)).foregroundStyle(Theme.accent).padding(.leading, 12)
                    }
                    .padding(.top, 14)
                }
                Text("On the Mac, subtitles.py uses a voice when --me or --caller matches the name here.")
                    .font(Fonts.ui(12)).foregroundStyle(Theme.text3).padding(.top, 14)
            }
        }
        .sheet(item: $recordingFor, onDismiss: { Task { await people.loadFamily() } }) { target in
            VoiceSetupView(target: target).environmentObject(people)
        }
    }
}

struct VoiceTarget: Identifiable {
    let name: String
    let isYou: Bool
    var id: String { Person.id(for: name) }
}

/// Record someone reading, with their consent, and have the Mac make their personalized voice.
struct VoiceSetupView: View {
    let target: VoiceTarget
    var embedded = false              // in the Voice tab rather than a sheet: no Cancel, stays open when done
    var onDone: (() -> Void)? = nil
    @Environment(\.dismiss) private var dismiss
    @StateObject private var recorder = VoiceRecorder()
    @State private var consent = false
    @State private var sending = false
    @State private var status: String?

    private static let minimum: TimeInterval = 30
    private var whose: String { target.isYou ? "your" : "\(target.name)'s" }

    var body: some View {
        if embedded {
            content
        } else {
            ScrollView { content.padding(20) }.preferredColorScheme(.dark)
        }
    }

    private var content: some View {
            VStack(alignment: .leading, spacing: 12) {
                if !embedded {
                    HStack {
                        Text("Record \(whose) voice").font(Fonts.ui(24, .medium)).tracking(-0.6).foregroundStyle(Theme.lavender)
                        Spacer()
                        Button("Cancel") { recorder.stop(); dismiss() }.font(Fonts.ui(15, .medium)).foregroundStyle(Theme.accent)
                    }
                    .padding(.bottom, 8)
                }
                Panel {
                    Eyebrow("Read this aloud, or just talk")
                    Text(target.isYou ? Self.englishScript : Self.teluguScript)
                        .font(Fonts.serif(18)).foregroundStyle(Theme.text).padding(.top, 8)
                    Text("A quiet room, phone about a hand's width away, speaking the way \(target.isYou ? "you do" : "they do") on calls. About a minute is best.")
                        .font(Fonts.ui(12)).foregroundStyle(Theme.text3).padding(.top, 10)
                }
                Panel {
                    HStack(spacing: 16) {
                        Button { if recorder.recording { recorder.stop() } else { Task { await recorder.start() } } } label: {
                            Image(systemName: recorder.recording ? "stop.fill" : "mic.fill").font(.system(size: 22, weight: .semibold))
                                .foregroundStyle(recorder.recording ? Theme.danger : Theme.bg)
                                .frame(width: 64, height: 64)
                                .background(recorder.recording ? Theme.danger.opacity(0.16) : Theme.text, in: .circle)
                                .contentTransition(.symbolEffect(.replace))
                        }
                        .buttonStyle(Pressable())
                        .disabled(sending)
                        VStack(alignment: .leading, spacing: 6) {
                            Text(String(format: "%d:%02d", Int(recorder.seconds) / 60, Int(recorder.seconds) % 60))
                                .font(Fonts.mono(28)).foregroundStyle(Theme.text)
                            ProgressView(value: min(recorder.seconds, 60), total: 60).tint(recorder.seconds >= Self.minimum ? Theme.green : Theme.accent)
                            Text(recorder.seconds >= 60 ? "That's plenty." : recorder.seconds >= Self.minimum ? "Enough; a little more sounds better." : "At least 30 seconds")
                                .font(Fonts.ui(12)).foregroundStyle(Theme.text2)
                        }
                    }
                    if recorder.failed {
                        Text("Nothing was recorded: the microphone stopped. Try again. The iOS Simulator often loses the Mac's microphone; a real iPhone works, or record on the Mac and run python eleven.py clone \"\(target.name)\" recording.m4a")
                            .font(Fonts.ui(13)).foregroundStyle(Theme.danger).padding(.top, 10)
                    }
                    if recorder.denied {
                        Text("Weave needs the microphone: Settings > Weave > Microphone.").font(Fonts.ui(13)).foregroundStyle(Theme.danger).padding(.top, 10)
                    }
                }
                Panel {
                    Toggle(isOn: $consent) {
                        Text(target.isYou
                             ? "This is my voice. I agree to Weave making a copy of it with ElevenLabs to speak my translations on calls."
                             : "\(target.name) is here and agrees to Weave making a copy of their voice with ElevenLabs to speak their translations on calls.")
                            .font(Fonts.ui(13)).foregroundStyle(Theme.text)
                    }
                    .tint(Theme.accent)
                    Text("You can remove it any time in the Voice tab; that deletes it at ElevenLabs too.").font(Fonts.ui(12)).foregroundStyle(Theme.text3).padding(.top, 8)
                }
                Button(action: send) {
                    HStack(spacing: 8) {
                        if sending { ProgressView().tint(Theme.bg) }
                        Text(sending ? "Making the voice…" : "Make \(whose) voice").font(Fonts.ui(15, .medium))
                    }
                    .foregroundStyle(Theme.bg).frame(maxWidth: .infinity).frame(height: 46)
                    .background(Theme.text, in: .rect(cornerRadius: 10))
                }
                .buttonStyle(Pressable())
                .disabled(!ready)
                .opacity(ready ? 1 : 0.4)
                if let status { Text(status).font(Fonts.ui(13)).foregroundStyle(Theme.text2) }
            }
            .onDisappear { recorder.stop() }
    }

    private var ready: Bool { consent && !recorder.recording && !sending && recorder.seconds >= Self.minimum }

    private func send() {
        guard let audio = recorder.audio else { status = "The recording didn't save. Try again."; return }
        sending = true
        status = nil
        Task {
            let error = await GardenClient.makeVoice(name: target.name, audio: audio)
            sending = false
            if let error { status = error } else if embedded { onDone?() } else { onDone?(); dismiss() }
        }
    }

    private static let englishScript = """
    Hi! It's so good to hear your voice. I finally finished my exams this week, and I've been cooking a lot more. \
    Yesterday I tried making pappu and rice the way you showed me, but I think I added too much tamarind. \
    Tell me, what did you have for lunch today? Is it still raining there? I miss sitting on the porch with you \
    in the evenings, listening to the stories about when you were little. When I visit in December, will you teach \
    me how to make pulihora? I want to get it right this time.
    """

    private static let teluguScript = """
    నమస్కారం! ఈ రోజు ఎలా ఉన్నావు? ఇక్కడ వాన బాగా పడుతోంది. పొద్దున్నే పులిహోర చేశాను, అందరూ బాగుందన్నారు. \
    నీ చదువు ఎలా ఉంది? బాగా తింటున్నావా? డిసెంబర్‌లో వచ్చినప్పుడు నీకు ఇష్టమైనవన్నీ చేసి పెడతాను. \
    మా చిన్నప్పుడు మేము ఊర్లో పొలాల దగ్గర ఆడుకునేవాళ్ళం, ఆ కథలన్నీ నీకు చెప్పాలి.

    (Or just ask them about their day and let them talk.)
    """
}

/// "Who are you?": pick yourself from the family on the Mac (people.py), or add your name. Says whether you
/// already have a personalized voice.
struct PersonPicker: View {
    @Binding var name: String
    @EnvironmentObject var people: People
    @State private var loading = true
    @State private var typed = ""
    @State private var url = GardenClient.serverURL
    @FocusState private var typing: Bool

    private var chosen: Person? { people.family?.first { $0.id == Person.id(for: name) } }

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            if let family = people.family, !family.isEmpty {
                if family.count > 5 {  // a scroll view would otherwise take its whole height for a short list
                    ScrollView { list(family) }.scrollIndicators(.hidden).frame(maxHeight: 280)
                } else {
                    list(family)
                }
            } else if loading {
                HStack(spacing: 10) {
                    ProgressView().tint(Theme.text2)
                    Text("Finding your family on the Mac…").font(Fonts.ui(14)).foregroundStyle(Theme.text2)
                }
            } else {
                unreachable
            }
            TextField("", text: $typed, prompt: Text(people.family?.isEmpty == false ? "Not here? Add your name" : "Your name").foregroundColor(Theme.text3))
                .font(Fonts.ui(17, .medium)).foregroundStyle(Theme.text)
                .focused($typing)
                .textInputAutocapitalization(.words).autocorrectionDisabled()
                .padding(.horizontal, 16).frame(height: 52)
                .background(Theme.surface, in: .rect(cornerRadius: 14))
                .overlay(RoundedRectangle(cornerRadius: 14).strokeBorder(typing ? Theme.accent.opacity(0.6) : Theme.border2, lineWidth: 1))
                .onChange(of: typed) { _, t in if !t.trimmingCharacters(in: .whitespaces).isEmpty { name = t.trimmingCharacters(in: .whitespaces) } }
            if !name.isEmpty { voiceLine }
        }
        .task { await refresh() }
    }

    private func list(_ family: [Person]) -> some View {
        VStack(spacing: 0) {
            ForEach(Array(family.enumerated()), id: \.element.id) { i, p in
                if i > 0 { Rectangle().fill(Theme.border).frame(height: 1).padding(.leading, 16) }
                row(p)
            }
        }
        .background(Card())
        .clipShape(.rect(cornerRadius: Theme.radius))
    }

    private func row(_ p: Person) -> some View {
        let on = p.id == Person.id(for: name)
        return Button {
            withAnimation(.spring(response: 0.3, dampingFraction: 0.8)) { name = p.name; typed = ""; typing = false }
        } label: {
            HStack(spacing: 12) {
                Text(String(p.name.prefix(1)).uppercased()).font(Fonts.ui(14, .semibold)).foregroundStyle(Theme.text)
                    .frame(width: 32, height: 32).background(Theme.surface2, in: .circle)
                Text(p.name).font(Fonts.ui(17)).foregroundStyle(Theme.text)
                Spacer()
                if p.voice { Label("Own voice", systemImage: "waveform").font(Fonts.ui(12)).foregroundStyle(Theme.accent) }
                ZStack {
                    Circle().strokeBorder(on ? Theme.accent : Theme.border2, lineWidth: 1.5)
                    if on {
                        Circle().fill(Theme.accent)
                        Image(systemName: "checkmark").font(.system(size: 10, weight: .bold)).foregroundStyle(Theme.onAccent)
                    }
                }
                .frame(width: 20, height: 20)
            }
            .padding(.horizontal, 16).padding(.vertical, 12)
            .contentShape(Rectangle())
        }
        .buttonStyle(RowStyle())
        .sensoryFeedback(.selection, trigger: on)
    }

    private var voiceLine: some View {
        Group {
            if chosen?.voice == true {
                Label("Your personalized voice is ready: your translations sound like you.", systemImage: "waveform")
                    .foregroundStyle(Theme.accent)
            } else if chosen != nil {
                Label("No personalized voice yet. Record one any time in Settings.", systemImage: "mic")
                    .foregroundStyle(Theme.text2)
            } else {
                Label("New to Weave? We'll add \(name) to the family.", systemImage: "person.badge.plus")
                    .foregroundStyle(Theme.text2)
            }
        }
        .font(Fonts.ui(13))
    }

    /// No answer from the Mac: probably a real phone that doesn't know the Mac's address yet.
    private var unreachable: some View {
        VStack(alignment: .leading, spacing: 8) {
            Text("Couldn't reach Weave on your Mac, so type your name below, or enter the address python -m garden --lan prints.")
                .font(Fonts.ui(13)).foregroundStyle(Theme.text2)
            HStack(spacing: 8) {
                TextField("http://192.168.1.10:8770", text: $url)
                    .font(Fonts.mono(14, .regular)).foregroundStyle(Theme.text)
                    .keyboardType(.URL).textInputAutocapitalization(.never).autocorrectionDisabled()
                    .padding(.horizontal, 12).frame(height: 42)
                    .background(Theme.surface2, in: .rect(cornerRadius: 10))
                Button("Connect") { GardenClient.serverURL = url; Task { await refresh() } }
                    .font(Fonts.ui(14, .medium)).foregroundStyle(Theme.accent)
            }
        }
    }

    private func refresh() async {
        loading = true
        await people.loadFamily()
        loading = false
    }
}

/// Settings → "Not you?": pick someone else (or add yourself).
struct SwitchPersonView: View {
    @EnvironmentObject var people: People
    @Environment(\.dismiss) private var dismiss
    @State private var name = ""

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack {
                Text("Who are you?").font(Fonts.ui(24, .medium)).tracking(-0.6).foregroundStyle(Theme.lavender)
                Spacer()
                Button("Done") {
                    let clean = name.trimmingCharacters(in: .whitespaces)
                    if !clean.isEmpty { people.becomes(clean) }
                    dismiss()
                }
                .font(Fonts.ui(15, .medium)).foregroundStyle(Theme.accent)
            }
            .padding(.bottom, 8)
            PersonPicker(name: $name)
            Spacer()
        }
        .padding(20)
        .preferredColorScheme(.dark)
        .onAppear { name = people.profileName ?? "" }
    }
}

/// The Voice tab: record your personalized voice from a script, and everyone else's.
struct VoiceTab: View {
    @EnvironmentObject var people: People
    @State private var redo = false

    var body: some View {
        let name = people.profileName ?? "You"
        ScrollView {
            VStack(alignment: .leading, spacing: 12) {
                Text("Your voice").font(Fonts.display(34, .semibold)).tracking(-0.8).foregroundStyle(Theme.lavender).padding(.top, 20)
                Text("Read the script below for about a minute. Weave then speaks your translations in your own voice, in English and in Telugu.")
                    .font(Fonts.ui(15)).foregroundStyle(Theme.text2).padding(.bottom, 8)
                if people.family == nil {
                    Panel { Text("Connect to Weave on your Mac (avatar → Settings) to record your voice.").font(Fonts.ui(14)).foregroundStyle(Theme.text2) }
                } else if people.me?.voice == true && !redo {
                    Panel {
                        Label("Your voice is ready", systemImage: "checkmark.seal.fill").font(Fonts.ui(17, .medium)).foregroundStyle(Theme.accent)
                        Text("Calls where the Mac runs subtitles.py --me \(name) speak your translations in it.").font(Fonts.ui(13)).foregroundStyle(Theme.text2).padding(.top, 6)
                        HStack(spacing: 20) {
                            Button("Record again") { redo = true }.foregroundStyle(Theme.accent)
                            Button("Remove") { Task { _ = await GardenClient.removeVoice(name: name); await people.loadFamily() } }.foregroundStyle(Theme.danger)
                        }
                        .font(Fonts.ui(14, .medium)).padding(.top, 12)
                    }
                } else {
                    VoiceSetupView(target: VoiceTarget(name: name, isYou: true), embedded: true) {
                        redo = false
                        Task { await people.loadFamily() }
                    }
                    .id(name)
                }
                FamilyVoices().padding(.top, 12)
            }
            .padding(.horizontal, 20).padding(.bottom, 100)
        }
        .scrollIndicators(.hidden)
        .background(Backdrop())
        .task { await people.loadFamily() }
        .refreshable { await people.loadFamily() }
    }
}
