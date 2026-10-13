"""Parse the public jukebox sheet into catalog slots."""

from app.jukebox_sheet import parse_jukebox_sheet

SHEET = """\
Sheets by hnzwayora,,,,,,
No,Title,Intro ID,Loop ID,Intro Length,Loop Length,Total Length
1,Character Select (Arcade ver.) / TEKKEN,58037268,754605713,00:01,00:07,00:08
7,"Acropolis, Greece (Arcade ver.) / TEKKEN",832991567,1021491991,00:00,00:52,00:52
,Ancient Powers (Normal) / TEKKEN 8,966353609,145043262,00:16,01:39,01:55
99,Staff Roll (Arcade ver.) / TEKKEN TAG,-,868018058,-,01:34,01:34
"""


def test_parse_jukebox_sheet_records_ids_lengths_and_media_paths():
    catalog = parse_jukebox_sheet(SHEET)

    assert catalog.game_version is None
    assert [slot.id for slot in catalog.slots] == [
        "1",
        "7",
        "ancient-powers-normal-tekken-8",
        "99",
    ]
    first, silent_intro, ancient, loop_only = catalog.slots
    assert first.name == "Character Select (Arcade ver.) / TEKKEN"
    assert first.sample_rate == 48000
    assert first.channels == 2
    assert first.codec == "vorbis"
    assert first.intro_samples == 48000
    assert first.loop_samples == 7 * 48000
    assert first.intro_asset == "Polaris/Content/WwiseAudio/Media/58037268.wem"
    assert first.loop_asset == "Polaris/Content/WwiseAudio/Media/754605713.wem"
    assert silent_intro.intro_samples == 0
    assert silent_intro.loop_samples == 52 * 48000
    assert ancient.intro_samples == 16 * 48000
    assert ancient.loop_samples == (1 * 60 + 39) * 48000
    assert loop_only.intro_samples == 0
    assert loop_only.loop_samples == (1 * 60 + 34) * 48000
    assert loop_only.intro_asset == loop_only.loop_asset
    assert loop_only.loop_asset.endswith("/868018058.wem")
