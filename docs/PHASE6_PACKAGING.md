# Phase 6 — Mobile packaging & native bridges

This is **scaffolding**: the configuration and bridge stubs are in place, but the
builds themselves cannot run in a headless dev box — they need an Android SDK/NDK,
a macOS machine with Xcode for iOS, and signing keys. The brief flags this as the
project's #1 risk, so the strategy is: containerize the Android build, keep native
code minimal and isolated, and wire the real purchase flows on-device.

## Where native code lives

`nativebridge/` (not `platform/` — that name shadows Python's stdlib `platform`
module and breaks Kivy). Everything there implements an interface declared in a
pure layer:

| Bridge | Interface | Native dep | Status |
|---|---|---|---|
| `billing_android.py` | `monetization.billing.BillingProvider` | pyjnius → Play Billing | stub |
| `billing_ios.py` | `monetization.billing.BillingProvider` | pyobjus → StoreKit | stub |
| `ads.py` | `RewardedAdProvider` | AdMob/mediation | stub + desktop no-op |
| `analytics.py` | `AnalyticsSink` | HTTPS endpoint | NoOp + in-memory |

The provider is **injected at startup** (`nativebridge.provider_for_platform`),
so `engine/` and `ui/` never import device code. On desktop/web you get
`MockBillingProvider`; the whole purchase → verify → entitle flow already works
there and is covered by tests.

## Feasibility — verified

`buildozer` **1.6.0 installs fine**, but on Windows its Android target is
unavailable (`buildozer android debug` → "Unknown command/target android") — the
Android target requires a POSIX/Linux environment with the SDK/NDK/Java toolchain.
This is expected and is why the build runs in a Linux container (or WSL / a Linux
CI runner), never on the dev box directly. The `buildozer.spec` is in place and
bundles the engine/ui/education/monetization/nativebridge layers plus the
synthesized audio (`assets/audio/*.wav` via the `wav` ext + `assets/*` pattern).

## Android (Dockerized buildozer)

```bash
docker build -f docker/Dockerfile.buildozer -t realmogul-buildozer .
docker run --rm -v "$PWD":/home/user/app realmogul-buildozer buildozer -v android debug
# -> bin/realmogul-0.0.0-debug.apk
```

Config is `buildozer.spec`: landscape, `INTERNET` + Play `BILLING` permissions,
Play Billing gradle dep, and only the shippable layers bundled (tests/tools/spikes
excluded). A signed release/AAB needs a keystore in CI secrets.

## iOS (kivy-ios)

Requires macOS + Xcode (CI: a `macos` runner).

```bash
pip install kivy-ios
toolchain build python3 kivy
toolchain create RealMogul .
# open the generated Xcode project, set signing, archive.
```

StoreKit is reached through pyobjus in `nativebridge/billing_ios.py`.

## The verification server is mandatory

Both stores' purchases are confirmed **server-side** before entitling
(`monetization/verify_service.py`). Deploy it (FastAPI/uvicorn) and point the
client's verify URL at it; the `REALMOGUL_MOCK_SECRET` env var holds the dev
secret (real store verification uses the Play/App Store APIs, added here in
Phase 6).

## What's left to actually ship mobile

1. Fill in the four `TODO(phase6)` purchase/restore flows on real devices.
2. Add Play/App Store receipt validation to `verify.py` (the `google`/`apple`
   branches currently return "not implemented").
3. Stand up the verify service and set the client's endpoint.
4. CI: provision signing secrets; the Android job (`.github/workflows/android.yml`)
   builds an unsigned debug APK today and is the place to add signing.
5. Store readiness: privacy labels, data-safety form, age rating, COPPA.
