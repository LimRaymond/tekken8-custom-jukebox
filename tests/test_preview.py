"""Local preview is the intro once, then the loop twice."""

import numpy as np

from app.audio.preview import build_preview


def test_preview_plays_intro_once_and_loop_twice():
    intro = np.array([[1.0], [2.0]])
    loop = np.array([[3.0], [4.0], [5.0]])

    preview = build_preview(intro, loop)

    assert preview.shape == (8, 1)
    np.testing.assert_array_equal(preview[:, 0], [1, 2, 3, 4, 5, 3, 4, 5])


def test_default_player_writes_a_wav_and_starts_it(tmp_path, monkeypatch):
    from app.audio.preview import default_player
    from app.audio.wavio import read_wav

    started = []
    monkeypatch.setattr("tempfile.gettempdir", lambda: str(tmp_path))
    default_player(np.array([[0.5], [-0.5]]), 8000, starter=started.append)

    audio, rate = read_wav(started[0])
    assert rate == 8000
    assert audio.shape == (2, 1)


def test_stop_playback_uses_the_given_stopper():
    from app.audio.preview import stop_playback

    stopped = []
    stop_playback(stopper=lambda: stopped.append(True))

    assert stopped == [True]
