"""The seeded RNG must be deterministic — this is a load-bearing guarantee."""

from engine.rng import GameRNG


def test_same_seed_same_sequence():
    a = GameRNG(1234)
    b = GameRNG(1234)
    seq_a = [a.randint(0, 1000) for _ in range(50)]
    seq_b = [b.randint(0, 1000) for _ in range(50)]
    assert seq_a == seq_b


def test_different_seed_diverges():
    a = GameRNG(1)
    b = GameRNG(2)
    seq_a = [a.random() for _ in range(50)]
    seq_b = [b.random() for _ in range(50)]
    assert seq_a != seq_b


def test_fork_is_deterministic_and_isolated():
    parent_one = GameRNG(99)
    parent_two = GameRNG(99)
    child_one = parent_one.fork("market")
    child_two = parent_two.fork("market")
    assert [child_one.random() for _ in range(20)] == [child_two.random() for _ in range(20)]

    # A different label yields a different stream.
    events = GameRNG(99).fork("events")
    market = GameRNG(99).fork("market")
    assert [events.random() for _ in range(20)] != [market.random() for _ in range(20)]


def test_chance_is_clamped():
    rng = GameRNG(7)
    assert all(rng.chance(1.0) for _ in range(20))
    assert not any(rng.chance(0.0) for _ in range(20))
