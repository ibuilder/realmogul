"""Native platform bridges — the ONLY place device-specific code lives.

This is the brief's "platform/" layer, renamed to ``nativebridge`` because a
top-level package literally named ``platform`` would shadow Python's stdlib
``platform`` module (which Kivy and others import) and break the app.

Everything here implements an interface declared elsewhere (e.g.
``monetization.billing.BillingProvider``) so the engine/UI never import device
code directly — they depend on the interface and a provider is injected at
startup (see ``provider_for_platform``). Native imports (pyjnius/pyobjus) are
done lazily inside constructors so these modules import fine on desktop/CI; only
*instantiating* a real bridge off-device raises.
"""

from __future__ import annotations


def provider_for_platform(*, mock_secret: str = "dev-secret-change-me"):
    """Return the right BillingProvider for the current device.

    Android -> Play Billing (pyjnius); iOS -> StoreKit (pyobjus); everything else
    (desktop/web/CI) -> the MockBillingProvider so the full flow is exercisable.
    """
    try:
        from kivy.utils import platform as kivy_platform
    except Exception:  # pragma: no cover - kivy not present in pure CI
        kivy_platform = "unknown"

    if kivy_platform == "android":
        from nativebridge.billing_android import AndroidBillingProvider

        return AndroidBillingProvider()
    if kivy_platform == "ios":
        from nativebridge.billing_ios import IosBillingProvider

        return IosBillingProvider()

    from monetization import MockBillingProvider

    return MockBillingProvider(mock_secret)
