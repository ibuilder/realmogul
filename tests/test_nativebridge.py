"""Native bridges must import cleanly on desktop/CI and only fail when a real
device-bound provider is actually instantiated."""

import pytest

from monetization.billing import BillingProvider
from nativebridge import provider_for_platform
from nativebridge.ads import NoRewardedAds, RewardedAdProvider
from nativebridge.analytics import Event, InMemoryAnalytics, NoOpAnalytics


def test_provider_factory_falls_back_to_mock_off_device():
    provider = provider_for_platform(mock_secret="x")
    assert isinstance(provider, BillingProvider)
    # The mock provider can actually transact (proves the desktop flow works).
    assert provider.purchase("keys_small").success


def test_native_billing_modules_import_but_raise_when_instantiated():
    # Modules import fine (lazy native deps); constructing off-device raises.
    from nativebridge.billing_android import AndroidBillingProvider
    from nativebridge.billing_ios import IosBillingProvider

    with pytest.raises(RuntimeError):
        AndroidBillingProvider()
    with pytest.raises(RuntimeError):
        IosBillingProvider()


def test_desktop_ads_are_unavailable_and_dismiss():
    ads: RewardedAdProvider = NoRewardedAds()
    assert not ads.is_available()
    dismissed = []
    ads.show(
        on_reward=lambda: dismissed.append("reward"), on_dismiss=lambda: dismissed.append("dismiss")
    )
    assert dismissed == ["dismiss"]  # no reward without inventory


def test_analytics_sinks():
    assert NoOpAnalytics().emit(Event("session_start")) is None
    mem = InMemoryAnalytics()
    mem.emit(Event("deal_closed", {"asset": "sfr"}))
    mem.emit(Event("deal_closed", {"asset": "retail"}))
    assert mem.count("deal_closed") == 2
