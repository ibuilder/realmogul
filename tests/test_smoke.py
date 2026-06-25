"""Phase 0 smoke test: the package imports and the toolchain runs green."""

import engine


def test_engine_package_imports():
    assert engine is not None


def test_arithmetic_sanity():
    # Trivial guard so `pytest` has something to be green on from day one.
    assert 2 + 2 == 4
