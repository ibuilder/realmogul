"""Mobile/desktop entrypoint used by buildozer (Android) and kivy-ios.

Selects the right native billing provider for the device and launches the Kivy
app. On desktop this is equivalent to ``python -m ui`` but with the
platform-aware provider injection wired in.
"""

from __future__ import annotations

from nativebridge import provider_for_platform
from ui.app import RealMogulApp


def main() -> int:
    RealMogulApp(billing_provider=provider_for_platform()).run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
