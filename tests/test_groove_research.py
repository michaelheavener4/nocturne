import types
import pytest

from nocturne.grooves import (
    GM_PERCUSSION,
    GROOVE_PRESETS,
    GENRE_SWING,
    BASS_GRIDS,
    MONO_SUB_HZ,
    ghost_velocity,
    apply_swing,
    sidechain_release_ms,
)

ALL_16 = list(range(16))


# 1. GM map exact
def test_gm_peruccion_exact():
    expected = {
        "kick": 36,
        "rim": 37,
        "snare": 38,
        "clap": 39,
        "closed_hat": 42,
        "open_hat": 46,
        "crash": 49,
        "ride": 51,
        "maracas": 70,
        "shaker": 82,
    }
    assert GM_PERCUSSION == expected
    assert GM_PERCUSSION["shaker"] == 82
    assert GM_PERCUSSION["maracas"] == 70


# 2. Every preset's exact step lists
def test_preset_house():
    p = GROOVE_PRESETS["house"]
    assert p["kick"] == [0, 4, 8, 12]
    assert p["snare"] == [4, 12]
    assert p["hat"] == ALL_16
    assert p["open_hat"] == [2, 6, 10, 14]
    assert p["ghost"] is False


def test_preset_backbeat():
    p = GROOVE_PRESETS["backbeat"]
    assert p["kick"] == [0, 8]
    assert p["snare"] == [4, 12]
    assert p["hat"] == [0, 2, 4, 6, 8, 10, 12, 14]
    assert p["open_hat"] == []
    assert p["ghost"] is False


def test_preset_trap():
    p = GROOVE_PRESETS["trap"]
    assert p["kick"] == [0, 10]
    assert p["snare"] == [8]
    assert p["hat"] == ALL_16
    assert p["open_hat"] == []
    assert p["ghost"] is True


def test_preset_dubstep():
    p = GROOVE_PRESETS["dubstep"]
    assert p["kick"] == [0]
    assert p["snare"] == [8]
    assert p["hat"] == [0, 2, 4, 6, 8, 10, 12, 14]
    assert p["open_hat"] == []
    assert p["ghost"] is False


def test_preset_dnb():
    p = GROOVE_PRESETS["dnb"]
    assert p["kick"] == [0, 10]
    assert p["snare"] == [4, 12]
    assert p["hat"] == ALL_16
    assert p["open_hat"] == []
    assert p["ghost"] is True


def test_preset_dembow():
    p = GROOVE_PRESETS["dembow"]
    assert p["kick"] == [0, 8]
    assert p["snare"] == [3, 6, 11, 14]
    assert p["hat"] == [0, 2, 4, 6, 8, 10, 12, 14]
    assert p["open_hat"] == []
    assert p["ghost"] is False


def test_preset_dembow_b():
    p = GROOVE_PRESETS["dembow_b"]
    assert p["kick"] == [0, 8]
    assert p["snare"] == [0, 3, 6, 8, 11, 14]
    assert p["hat"] == [0, 2, 4, 6, 8, 10, 12, 14]
    assert p["open_hat"] == []
    assert p["ghost"] is False


def test_all_expected_presets_present():
    expected = {"house", "backbeat", "trap", "dubstep", "dnb", "dembow", "dembow_b"}
    assert expected <= set(GROOVE_PRESETS)


# 3. BASS_GRIDS
def test_bass_grids_offbeat_exact():
    assert BASS_GRIDS["offbeat"] == [2, 6, 10, 14]


def test_bass_grids_rolling_length():
    assert len(BASS_GRIDS["rolling"]) == 16


def test_bass_grids_double_offbeat_superset_of_offbeat():
    assert set(BASS_GRIDS["offbeat"]) <= set(BASS_GRIDS["double_offbeat"])


# 4. ghost_velocity
def test_ghost_velocity_100_range():
    v = ghost_velocity(100)
    assert 25 <= v <= 40


def test_ghost_velocity_monotonic():
    assert ghost_velocity(50) < ghost_velocity(100)


def test_ghost_velocity_floor():
    assert ghost_velocity(1) >= 1


def test_ghost_velocity_exact_formula():
    for v in (1, 10, 50, 100, 127):
        assert ghost_velocity(v) == max(1, int(v * 0.32))


# 5. apply_swing
def test_apply_swing_50_is_identity():
    notes = [
        types.SimpleNamespace(start=s, pitch=38) for s in (0.0, 0.25, 0.5, 1.25)
    ]
    out = apply_swing(notes, 50)
    assert len(out) == len(notes)
    for orig, swung in zip(notes, out):
        assert swung is not orig
        assert swung.start == pytest.approx(orig.start, abs=1e-12)
    # input unmodified
    assert [n.start for n in notes] == [0.0, 0.25, 0.5, 1.25]


def test_apply_swing_58_delays_odd_step():
    odd = types.SimpleNamespace(start=0.25, pitch=38)
    even = types.SimpleNamespace(start=0.5, pitch=38)
    orig_odd_start = odd.start
    orig_even_start = even.start

    out = apply_swing([odd, even], 58)
    assert len(out) == 2

    # odd step (start 0.25 -> step 1) delayed by 0.04 beats
    expected_delay = (58 - 50) / 100 * 0.5
    assert expected_delay == pytest.approx(0.04)
    assert out[0].start - orig_odd_start == pytest.approx(0.04, abs=1e-9)

    # even step unchanged
    assert out[1].start == pytest.approx(orig_even_start, abs=1e-12)

    # original objects unmodified
    assert odd.start == pytest.approx(orig_odd_start, abs=1e-12)
    assert even.start == pytest.approx(orig_even_start, abs=1e-12)


def test_apply_swing_input_list_unmodified():
    notes = [types.SimpleNamespace(start=0.25, pitch=38)]
    snapshot = [n.start for n in notes]
    out = apply_swing(notes, 58)
    assert [n.start for n in notes] == snapshot
    assert out is not notes


# 6. sidechain_release_ms
def test_sidechain_release_ms_high_bpm_capped_by_period():
    # A request above the period cap is clamped to 0.9 * quarter-note period.
    result = sidechain_release_ms(128, 500)
    assert result == pytest.approx(0.9 * 60000 / 128)
    assert result < 469
    # A request under the cap passes through unchanged (min, not the cap).
    assert sidechain_release_ms(128, 300) == pytest.approx(300)


def test_sidechain_release_ms_low_bpm_capped_by_request():
    result = sidechain_release_ms(60, 300)
    assert result == pytest.approx(300)


def test_sidechain_release_ms_default_request():
    # Default request is 300 ms, which is under the 128 BPM cap (421.875 ms).
    result = sidechain_release_ms(128)
    assert result == pytest.approx(300)


# 7. MONO_SUB_HZ
def test_mono_sub_hz():
    assert MONO_SUB_HZ == 120


# 8. GENRE_SWING covers the six non-variant presets, values in 50..58
def test_genre_swing_keys_and_range():
    expected_keys = {"house", "backbeat", "trap", "dubstep", "dnb", "dembow"}
    assert set(GENRE_SWING) == expected_keys
    for genre, swing in GENRE_SWING.items():
        assert 50 <= swing <= 58, f"{genre} swing {swing} out of 50..58"
