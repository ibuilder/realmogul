"""Sound effects — load the synthesized WAVs and play them by name.

Best-effort and defensive: audio is loaded lazily and every call is wrapped, so a
missing backend (headless CI), a missing file, or a device with no audio simply
makes the game silent rather than crashing. The ad-free/subscription state never
gates audio — this is game feel, not monetization.
"""

from __future__ import annotations

import os

_NAMES = ("tick", "cash", "build_done", "win", "lose")


class SoundBank:
    def __init__(self, enabled: bool = True) -> None:
        self.enabled = enabled
        self._sounds: dict[str, object] = {}
        self._loaded = False

    def _load(self) -> None:
        self._loaded = True
        try:
            from kivy.core.audio import SoundLoader
        except Exception:  # pragma: no cover - no audio backend
            self.enabled = False
            return
        base = os.path.join("assets", "audio")
        for name in _NAMES:
            try:
                snd = SoundLoader.load(os.path.join(base, f"{name}.wav"))
                if snd is not None:
                    self._sounds[name] = snd
            except Exception:  # pragma: no cover - per-file load failure
                pass

    def play(self, name: str) -> None:
        if not self.enabled:
            return
        if not self._loaded:
            self._load()
        snd = self._sounds.get(name)
        if snd is None:
            return
        try:  # pragma: no cover - device audio
            snd.stop()
            snd.play()
        except Exception:
            pass
