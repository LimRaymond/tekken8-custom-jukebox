"""Exact intro and loop fitting."""

import numpy as np
import pytest

from app.audio.fit import prepare_audio


def test_cut_uses_exact_intro_and_loop_lengths_without_stretching():
    source = np.arange(1000, dtype=np.float64)

    fitted = prepare_audio(
        source,
        48000,
        intro_samples=100,
        loop_samples=200,
        target_rate=48000,
        target_channels=1,
        crossfade_ms=0,
        boost=False,
    )

    assert fitted.sample_rate == 48000
    assert fitted.channels == 1
    assert fitted.intro.shape == (100, 1)
    assert fitted.loop.shape == (200, 1)
    np.testing.assert_allclose(fitted.intro[:, 0], source[:100])
    np.testing.assert_allclose(fitted.loop[:, 0], source[100:300])


def test_crossfade_keeps_loop_length_and_meets_the_start():
    source = np.linspace(-0.8, 0.8, 400, dtype=np.float64)

    fitted = prepare_audio(
        source,
        1000,
        intro_samples=50,
        loop_samples=100,
        target_rate=1000,
        target_channels=1,
        crossfade_ms=20,
        boost=False,
    )

    assert fitted.intro.shape == (50, 1)
    assert fitted.loop.shape == (100, 1)
    np.testing.assert_allclose(fitted.loop[-1], fitted.loop[0], atol=1e-6)
    assert not np.allclose(fitted.loop[-10:, 0], source[140:150])


def test_short_song_repeats_until_the_loop_is_full():
    source = np.arange(4, dtype=np.float64)

    fitted = prepare_audio(
        source,
        1000,
        intro_samples=4,
        loop_samples=10,
        target_rate=1000,
        target_channels=1,
        crossfade_ms=2,
        boost=False,
    )

    assert fitted.intro.shape == (4, 1)
    assert fitted.loop.shape == (10, 1)
    np.testing.assert_allclose(fitted.intro[:, 0], source)
    np.testing.assert_allclose(fitted.loop[:8, 0], np.tile(source, 3)[:8])


def test_resample_matches_slot_rate_and_channel_count():
    source = np.ones(10, dtype=np.float64)

    fitted = prepare_audio(
        source,
        24000,
        intro_samples=4,
        loop_samples=4,
        target_rate=48000,
        target_channels=2,
        crossfade_ms=0,
    )

    assert fitted.intro.shape == (4, 2)
    assert fitted.loop.shape == (4, 2)
    assert fitted.sample_rate == 48000
    assert fitted.channels == 2
    assert np.all(np.isfinite(fitted.intro))
    assert np.all(np.isfinite(fitted.loop))


def test_zero_length_intro_leaves_the_loop_at_the_start_of_the_song():
    source = np.arange(20, dtype=np.float64)

    fitted = prepare_audio(
        source,
        1000,
        intro_samples=0,
        loop_samples=10,
        target_rate=1000,
        target_channels=1,
        crossfade_ms=0,
        boost=False,
    )

    assert fitted.intro.shape == (0, 1)
    assert fitted.loop.shape == (10, 1)
    np.testing.assert_allclose(fitted.loop[:, 0], source[:10])


def test_quiet_music_is_raised_and_stays_inside_full_scale():
    source = np.full(2000, 0.1, dtype=np.float64)

    fitted = prepare_audio(
        source,
        48000,
        intro_samples=100,
        loop_samples=100,
        target_rate=48000,
        target_channels=1,
        crossfade_ms=0,
    )

    assert np.max(np.abs(fitted.intro)) <= 0.98 + 1e-6
    assert np.max(np.abs(fitted.loop)) <= 0.98 + 1e-6
    assert np.max(np.abs(fitted.loop)) > 0.3


def test_empty_audio_is_refused():
    with pytest.raises(ValueError, match="empty"):
        prepare_audio(
            np.zeros((0, 1)),
            48000,
            intro_samples=10,
            loop_samples=10,
            target_rate=48000,
            target_channels=1,
        )
