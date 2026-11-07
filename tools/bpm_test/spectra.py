"""Song -> WE-like 16-band spectrum frames (float32 [frames,16]) at a given fps, plus a reference
tempo from a fine-resolution onset autocorrelation over the whole song.
Usage: python tools/bpm_test/spectra.py <audio> <out.f32> <fps>
Then: node tools/bpm_test/run.mjs scripts/mandala_controller.js <out.f32> <fps> [repeat]
(repeat: each audio frame shown N times, i.e. audio refreshing slower than the frame rate)."""
import shutil
import subprocess
import sys

import numpy as np

FF = shutil.which("ffmpeg") or r"C:\Users\rockb\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-9.0.2-full_build\bin\ffmpeg.exe"
src, out, fps = sys.argv[1], sys.argv[2], float(sys.argv[3])
SR = 44100
pcm = subprocess.run([FF, "-v", "quiet", "-i", src, "-ac", "1", "-ar", str(SR), "-f", "f32le", "-"],
                     capture_output=True).stdout
x = np.frombuffer(pcm, np.float32)
N = 2048
win = np.hanning(N).astype(np.float32)
freqs = np.fft.rfftfreq(N, 1 / SR)
edges = np.geomspace(30, 16000, 17)
band = [np.where((freqs >= edges[i]) & (freqs < edges[i + 1]))[0] for i in range(16)]
band = [b if len(b) else np.array([np.argmin(abs(freqs - edges[i]))]) for i, b in enumerate(band)]


def frames_at(rate):
    hop = SR / rate
    n = int((len(x) - N) / hop)
    S = np.empty((n, 16), np.float32)
    for k in range(n):
        s = int(k * hop)
        m = np.abs(np.fft.rfft(x[s:s + N] * win))
        S[k] = [m[b].mean() for b in band]
    return S


S = frames_at(fps)
S /= np.percentile(S, 99, axis=0, keepdims=True) + 1e-9        # each band peaks near 1, like WE's
# WE smooths its bars (fast rise, slower fall)
for k in range(1, len(S)):
    S[k] = np.maximum(S[k], S[k - 1] * 0.75)
S.astype(np.float32).tofile(out)

# reference: 200 Hz onset envelope over the whole song, ACF 70..180 BPM with the same octave prior
R = frames_at(200.0)
L = np.log1p(100 * R / (np.percentile(R, 99, axis=0, keepdims=True) + 1e-9))
o = np.maximum(0, np.diff(L, axis=0)).sum(1)
o = o - np.convolve(o, np.ones(41) / 41, "same")
o = np.maximum(o, 0)
lags = np.arange(int(200 * 60 / 180), int(200 * 60 / 70) + 1)
r = np.array([np.dot(o[l:], o[:-l]) / (len(o) - l) for l in range(1, 3 * lags[-1] + 2)])
sc = [(r[l - 1] + 0.5 * r[2 * l - 1] + 0.33 * r[3 * l - 1]) * np.exp(-0.5 * (np.log2(12000 / l / 120) / 0.9) ** 2) for l in lags]
print(f"{len(S)} frames @ {fps:g} fps, {len(x) / SR:.0f} s; reference {12000 / lags[int(np.argmax(sc))]:.1f} BPM")
