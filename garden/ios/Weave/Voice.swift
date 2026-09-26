import AVFoundation
import SwiftUI

/// Plays her real voice: clips the story keeper cut from the call, fetched from the Mac.
@MainActor
final class VoicePlayer: NSObject, ObservableObject, AVAudioPlayerDelegate {
    static let shared = VoicePlayer()
    @Published private(set) var playing: String?     // path of the clip that's playing
    @Published private(set) var loading: String?
    private var player: AVAudioPlayer?
    private var cache: [String: Data] = [:]

    /// `path` as the Mac serves it, e.g. "calls/2026-09-26-1830/clips/3.m4a".
    func toggle(_ path: String) {
        if playing == path { stop(); return }
        stop()
        loading = path
        Task {
            defer { if loading == path { loading = nil } }
            let data: Data
            if let d = cache[path] { data = d } else {
                guard let url = GardenClient.url(path), let (d, r) = try? await URLSession.shared.data(from: url),
                      (r as? HTTPURLResponse)?.statusCode == 200 else { return }
                cache[path] = d; data = d
            }
            guard loading == path else { return }
            try? AVAudioSession.sharedInstance().setCategory(.playback)
            try? AVAudioSession.sharedInstance().setActive(true)
            player = try? AVAudioPlayer(data: data)
            player?.delegate = self
            player?.play()
            playing = player?.isPlaying == true ? path : nil
        }
    }

    func stop() {
        player?.stop(); player = nil; playing = nil; loading = nil
    }

    nonisolated func audioPlayerDidFinishPlaying(_ p: AVAudioPlayer, successfully flag: Bool) {
        Task { @MainActor in self.playing = nil }
    }
}

/// Round play button for a clip of her voice.
struct VoiceButton: View {
    let path: String
    var size: CGFloat = 34
    @ObservedObject private var voice = VoicePlayer.shared
    var body: some View {
        let on = voice.playing == path
        Button { voice.toggle(path) } label: {
            ZStack {
                if voice.loading == path { ProgressView().controlSize(.mini).tint(Theme.text2) }
                else { Image(systemName: on ? "stop.fill" : "play.fill").font(.system(size: size * 0.32, weight: .semibold)) }
            }
            .foregroundStyle(on ? Theme.accent : Theme.text)
            .frame(width: size, height: size)
            .background(on ? Theme.accent.opacity(0.14) : Theme.surface2, in: .circle)
            .overlay(Circle().strokeBorder(on ? Theme.accent.opacity(0.5) : Theme.border2, lineWidth: 1))
            .contentTransition(.symbolEffect(.replace))
        }
        .buttonStyle(Pressable())
        .accessibilityLabel(on ? "Stop" : "Play her voice")
    }
}
