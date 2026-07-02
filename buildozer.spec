[app]

# --- identity ---
title = real mogul
package.name = realmogul
package.domain = com.realmogul
version = 0.0.0

# --- sources ---
source.dir = .
# Bundle the pure layers + the UI and native bridges; leave tests/tools/spikes out.
source.include_patterns = engine/*,ui/*,education/*,monetization/*,nativebridge/*,assets/*,main.py
source.include_exts = py,png,jpg,jpeg,kv,atlas,ttf,otf,wav,ogg,json
source.exclude_dirs = tests,tools,spikes,docs,.github,.claude,assets_src

# --- python / kivy requirements ---
# pyjnius is pulled in automatically by python-for-android for the billing bridge.
requirements = python3,kivy==2.3.1,certifi,urllib3

# Landscape: the board + deal panel sit side by side.
orientation = landscape
fullscreen = 0

# --- android ---
android.api = 34
android.minapi = 24
android.ndk_api = 24
android.archs = arm64-v8a,armeabi-v7a
# INTERNET for receipt verification; BILLING for Play purchases.
android.permissions = android.permission.INTERNET,com.android.vending.BILLING
# Play Billing Library is added via a gradle dependency at build time.
android.gradle_dependencies = com.android.billingclient:billing:6.2.0

[buildozer]
log_level = 2
warn_on_root = 1

# iOS is built separately with kivy-ios (see docs/PHASE6_PACKAGING.md); StoreKit
# is reached through pyobjus in nativebridge/billing_ios.py.
