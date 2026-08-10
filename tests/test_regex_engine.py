"""
Tests for FilenameParser — verified against the sample table in ARCHITECTURE.md §4.3.
"""
from __future__ import annotations

import pytest

from bot.utils.regex_engine import FilenameParser, ParsedFilename


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def parse(filename: str) -> ParsedFilename:
    return FilenameParser.parse(filename)


# ---------------------------------------------------------------------------
# §4.3 Verified Example Outputs
# ---------------------------------------------------------------------------

class TestArchitectureSampleTable:
    """All 5 rows from the spec's verified example table must pass."""

    def test_breaking_bad_standard_sxxexx(self):
        r = parse("Breaking.Bad.S01E05.1080p.WEB-DL.Hindi-English.mkv")
        assert r.series_name == "Breaking Bad"
        assert r.season == 1
        assert r.episode == 5
        assert r.quality == "1080p"
        assert r.languages == ["Hindi", "English"]

    def test_money_heist_verbose(self):
        r = parse("Money Heist Season 3 Episode 08 720p HDRip Dual Audio.mkv")
        assert r.series_name == "Money Heist"
        assert r.season == 3
        assert r.episode == 8
        assert r.quality == "720p"
        assert r.languages == ["Dual Audio"]

    def test_stranger_things_complete_season_4k(self):
        r = parse("Stranger.Things.S04.COMPLETE.2160p.NF.WEB-DL.x265-HDR.mkv")
        assert r.series_name == "Stranger Things"
        assert r.season == 4
        assert r.episode == 0
        assert r.quality == "4K"
        assert r.languages == []

    def test_the_boys_numeric_nx(self):
        r = parse("The.Boys.1x05.480p.WEBRip.mkv")
        assert r.series_name == "The Boys"
        assert r.season == 1
        assert r.episode == 5
        assert r.quality == "480p"
        assert r.languages == []

    def test_vikings_valhalla_complete_with_language(self):
        r = parse("Vikings.Valhalla.S02.COMPLETE.720p.NF.WEBRip.Hindi.zip")
        assert r.series_name == "Vikings Valhalla"
        assert r.season == 2
        assert r.episode == 0
        assert r.quality == "720p"
        assert r.languages == ["Hindi"]


class TestMultiPartBatch:
    """Ensure multi-part batch files parse correctly into episode ranges."""

    def test_batch_part_01(self):
        r = parse("Money Heist S01 Part-01 E01-E06 720p.mkv")
        assert r.series_name == "Money Heist"
        assert r.season == 1
        assert r.start_ep == 1
        assert r.end_ep == 6
        assert r.quality == "720p"

    def test_batch_part_02(self):
        r = parse("Money Heist S01 Part-02 E07-E13 720p.mkv")
        assert r.series_name == "Money Heist"
        assert r.season == 1
        assert r.start_ep == 7
        assert r.end_ep == 13
        assert r.quality == "720p"

    def test_batch_no_part(self):
        r = parse("Money Heist S01 E01-E06 720p 10Bit WEBRip x265.mkv")
        assert r.series_name == "Money Heist"
        assert r.season == 1
        assert r.start_ep == 1
        assert r.end_ep == 6
        assert r.quality == "720p"

    def test_single_episode_fallback(self):
        r = parse("Money Heist S01E05 720p.mkv")
        assert r.series_name == "Money Heist"
        assert r.season == 1
        assert r.start_ep == 5
        assert r.end_ep == 5
        assert r.episode == 5
        assert r.quality == "720p"


# ---------------------------------------------------------------------------
# Edge cases & additional coverage
# ---------------------------------------------------------------------------

class TestEdgeCases:
    def test_quality_4k_normalized_from_2160p(self):
        r = parse("SomeShow.S01E01.2160p.mkv")
        assert r.quality == "4K"

    def test_quality_fallback_to_source_tag(self):
        r = parse("OldShow.S02E03.BluRay.mkv")
        assert r.quality == "BLURAY"

    def test_no_match_returns_none_season_episode(self):
        r = parse("Random File Without Any Pattern.mkv")
        assert r.season is None
        assert r.episode is None

    def test_language_case_insensitive(self):
        r = parse("ShowName.S01E01.hindi.mkv")
        assert "Hindi" in r.languages

    def test_multiple_languages_sorted(self):
        r = parse("Show.S01E01.Tamil.Telugu.mkv")
        assert r.languages == ["Tamil", "Telugu"]

    def test_is_complete_season_flag(self):
        r = parse("Stranger.Things.S04.COMPLETE.mkv")
        assert r.is_complete_season is True

    def test_season_only_without_complete_flag(self):
        r = parse("SomeShow.S03.mkv")
        # Season matches but is_complete_season is False (no complete/zip/pack keyword)
        assert r.season == 3
        assert r.episode == 0
        assert r.is_complete_season is False

    def test_language_display_empty(self):
        r = parse("Show.S01E01.720p.mkv")
        assert r.language_display == "Unknown"

    def test_language_display_with_languages(self):
        r = parse("Show.S01E01.720p.Hindi.mkv")
        assert r.language_display == "Hindi"

    def test_year_stripped_from_title(self):
        r = parse("The.Office.(2005).S03E12.720p.mkv")
        assert "2005" not in (r.series_name or "")

    def test_s_dot_e_notation(self):
        r = parse("Show.S01.E05.720p.mkv")
        assert r.season == 1
        assert r.episode == 5
