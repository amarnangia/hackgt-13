// Listens to a captured tab's sound and sends its frequency bands (0..1) to the overlay about 30 times a second.
// Capturing a tab silences it, so the sound is played straight back out.
const BANDS = 48;
const running = new Map();

chrome.runtime.onMessage.addListener(async (m) => {
  if (m?.target !== "offscreen" || m.type !== "start" || running.has(m.tabId)) return;
  let stream;
  try {
    stream = await navigator.mediaDevices.getUserMedia({ audio: { mandatory: { chromeMediaSource: "tab", chromeMediaSourceId: m.streamId } } });
  } catch {
    chrome.runtime.sendMessage({ target: "background", type: "stopped", tabId: m.tabId });
    return;
  }
  const ctx = new AudioContext();
  const source = ctx.createMediaStreamSource(stream);
  source.connect(ctx.destination);                     // keep hearing the call
  const analyser = ctx.createAnalyser();
  analyser.fftSize = 1024;
  analyser.smoothingTimeConstant = 0.72;
  analyser.minDecibels = -88;
  analyser.maxDecibels = -22;
  source.connect(analyser);
  const bins = new Uint8Array(analyser.frequencyBinCount);
  // Voice lives roughly between 80 Hz and 5 kHz: spread the bands over that range on a log scale.
  const hz = ctx.sampleRate / analyser.fftSize;
  const edges = Array.from({ length: BANDS + 1 }, (_, i) => Math.round((80 * Math.pow(5000 / 80, i / BANDS)) / hz));
  const timer = setInterval(() => {
    analyser.getByteFrequencyData(bins);
    const bands = [];
    for (let b = 0; b < BANDS; b++) {
      let sum = 0, n = 0;
      for (let k = edges[b]; k <= Math.max(edges[b], edges[b + 1] - 1); k++) { sum += bins[k] || 0; n++; }
      bands.push(Math.round((sum / n / 255) * 1000) / 1000);
    }
    chrome.runtime.sendMessage({ target: "background", type: "bands", tabId: m.tabId, bands });
  }, 33);
  running.set(m.tabId, { stream, ctx, timer });
  stream.getAudioTracks()[0].addEventListener("ended", () => {
    clearInterval(timer); ctx.close(); running.delete(m.tabId);
    chrome.runtime.sendMessage({ target: "background", type: "stopped", tabId: m.tabId });
  });
});
