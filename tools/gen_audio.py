"""Generate Real Mogul's UI sound effects as small synthesized WAV files.

No external assets needed — we render simple tones/chimes with the stdlib so the
game ships with real audio (not silent stubs). Re-run after tweaking to refresh
``assets/audio/``:

    python -m tools.gen_audio
"""

from __future__ import annotations

import math
import os
import struct
import wave

SR = 22_050  # sample rate (small + mobile-friendly)
OUT = os.path.join("assets", "audio")


def _render(path: str, fn, duration: float, gain: float = 0.5) -> None:
    n = int(SR * duration)
    frames = bytearray()
    for i in range(n):
        t = i / SR
        v = max(-1.0, min(1.0, fn(t) * gain))
        frames += struct.pack("<h", int(v * 32767))
    with wave.open(path, "w") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(bytes(frames))


def _sine(freq: float, t: float) -> float:
    return math.sin(2 * math.pi * freq * t)


def _decay(t: float, rate: float) -> float:
    return math.exp(-t * rate)


def main() -> int:
    os.makedirs(OUT, exist_ok=True)

    # A crisp UI tick.
    _render(os.path.join(OUT, "tick.wav"), lambda t: _sine(1200, t) * _decay(t, 45), 0.06, 0.4)

    # A two-note coin chime (cash collected).
    def cash(t: float) -> float:
        f = 988 if t < 0.06 else 1319
        return _sine(f, t) * _decay(t, 7)

    _render(os.path.join(OUT, "cash.wav"), cash, 0.45)

    # A rising C-E-G arpeggio for build/upgrade complete.
    def build_done(t: float) -> float:
        notes = [523.25, 659.25, 783.99]
        idx = min(2, int(t / 0.12))
        return _sine(notes[idx], t) * _decay(t, 4)

    _render(os.path.join(OUT, "build_done.wav"), build_done, 0.5)

    # A bright major chord for a win.
    def win(t: float) -> float:
        chord = [523.25, 659.25, 783.99, 1046.5]
        return sum(_sine(f, t) for f in chord) / len(chord) * _decay(t, 2.2)

    _render(os.path.join(OUT, "win.wav"), win, 0.9, 0.6)

    # A descending tone for a loss.
    _render(
        os.path.join(OUT, "lose.wav"),
        lambda t: _sine(440 - 240 * t, t) * _decay(t, 3),
        0.6,
    )

    files = sorted(os.listdir(OUT))
    print(f"wrote {len(files)} sounds to {OUT}: {', '.join(files)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
