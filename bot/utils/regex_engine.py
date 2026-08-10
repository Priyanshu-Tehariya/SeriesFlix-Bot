from __future__ import annotations

import re
from dataclasses import dataclass, field

# ---------------------------------------------------------------------------
# Pattern Library (compiled once at import time)
# ---------------------------------------------------------------------------

# 1. Batch SxxExx-Exx -> "Money Heist S01 Part-01 E01-E06" or "S01E01-E06"
RE_BATCH_SXXEXX = re.compile(r"[Ss](\d{1,2})[\s._-]?(?:(?:Part|Pt\.?|Vol\.?)[\s._-]?\d{1,2}[\s._-]?)?[Ee](\d{1,3})[\s._]*(?:-|–|—|to|~)[\s._]*(?:[Ee]?)(\d{1,3})", re.IGNORECASE)

# 2. Standard SxxExx -> "Breaking.Bad.S01E05..."
RE_STANDARD_SXXEXX = re.compile(r"[Ss](\d{1,2})[\s._-]?[Ee](\d{1,3})")

# 2. Numeric NxN -> "The.Boys.1x05..."
RE_NUMERIC_X = re.compile(r"(?<!\d)(\d{1,2})x(\d{2,3})(?!\d)")

# 3. Verbose -> "Money Heist Season 3 Episode 08"
RE_VERBOSE = re.compile(r"Season\s*(\d{1,2}).{0,15}?Episode\s*(\d{1,3})", re.IGNORECASE)

# 4. Season-only (paired with a completeness keyword) -> "S04.COMPLETE", "Season 2 Zip"
RE_SEASON_ONLY = re.compile(r"[Ss](?:eason)?[\s._-]?(\d{1,2})(?![Ee\d])", re.IGNORECASE)
RE_COMPLETE_FLAG = re.compile(r"\b(VOL\s*\d+|VOLUME\s*\d+|PART\s*\d+|COMBINED|COMPLETE|FULL\s*SEASON|BATCH|ZIP|PACK)\b", re.IGNORECASE)

# 5. Resolution / quality
RE_QUALITY = re.compile(r"(2160p|4k|1440p|1080p|720p|480p|360p)", re.IGNORECASE)

# 6. Source / rip tag — fallback quality descriptor when no resolution is present
RE_SOURCE = re.compile(
    r"(WEB[- ]?DL|WEBRip|BluRay|BRRip|HDRip|HDCAM|HDTS|DVDRip|HDTV)",
    re.IGNORECASE,
)

# 7. Known language tokens (extend freely)
LANGUAGE_TOKENS = [
    "Hindi", "English", "Tamil", "Telugu", "Kannada", "Malayalam",
    "Punjabi", "Bengali", "Marathi", "Urdu", "Korean", "Japanese",
    "Spanish", "French", "German", "Multi", "Dual Audio",
]
RE_LANGUAGE = re.compile(
    r"\b(" + "|".join(re.escape(tok) for tok in LANGUAGE_TOKENS) + r")\b",
    re.IGNORECASE,
)

# Cleanup helpers for reconstructing a readable series title
RE_TITLE_CLEANUP = re.compile(r"[._]+")
RE_YEAR = re.compile(r"\((?:19|20)\d{2}\)|\b(?:19|20)\d{2}\b")


@dataclass
class ParsedFilename:
    raw: str
    series_name: str | None = None
    season: int | None = None
    episode: int | None = None          # 0 == complete-season record
    start_ep: int | None = None
    end_ep: int | None = None
    is_complete_season: bool = False
    quality: str = "Unknown"
    languages: list[str] = field(default_factory=list)

    @property
    def language_display(self) -> str:
        return ", ".join(self.languages) if self.languages else "Unknown"


class FilenameParser:
    """Stateless parser. Pattern application order is significant — see §4.1."""

    @classmethod
    def parse(cls, filename: str) -> ParsedFilename:
        cleaned = filename.strip()
        result = ParsedFilename(raw=cleaned)
        match_pos = len(cleaned)

        if m := RE_BATCH_SXXEXX.search(cleaned):
            result.season = int(m.group(1))
            result.start_ep = int(m.group(2))
            result.end_ep = int(m.group(3))
            result.episode = result.start_ep
            match_pos = m.start()
        elif m := RE_STANDARD_SXXEXX.search(cleaned):
            result.season, result.episode = int(m.group(1)), int(m.group(2))
            result.start_ep = result.end_ep = result.episode
            match_pos = m.start()
        elif m := RE_NUMERIC_X.search(cleaned):
            result.season, result.episode = int(m.group(1)), int(m.group(2))
            result.start_ep = result.end_ep = result.episode
            match_pos = m.start()
        elif m := RE_VERBOSE.search(cleaned):
            result.season, result.episode = int(m.group(1)), int(m.group(2))
            result.start_ep = result.end_ep = result.episode
            match_pos = m.start()
        elif m := RE_SEASON_ONLY.search(cleaned):
            result.season = int(m.group(1))
            result.is_complete_season = bool(RE_COMPLETE_FLAG.search(cleaned))
            if result.is_complete_season:
                result.episode = 0
            else:
                result.episode = 1
                result.start_ep = result.end_ep = 1
            match_pos = m.start()

        if m := RE_QUALITY.search(cleaned):
            q = m.group(1).lower()
            result.quality = "4K" if q in ("4k", "2160p") else q
        elif m := RE_SOURCE.search(cleaned):
            result.quality = m.group(1).upper()

        # Extract unique languages preserving order of appearance
        found_langs = []
        for m in RE_LANGUAGE.finditer(cleaned):
            lang = m.group(1).title()
            if lang not in found_langs:
                found_langs.append(lang)
        result.languages = found_langs

        title_fragment = cleaned[:match_pos]
        title_fragment = RE_YEAR.sub("", title_fragment)
        title_fragment = RE_TITLE_CLEANUP.sub(" ", title_fragment)
        title_fragment = re.sub(r"\s{2,}", " ", title_fragment).strip(" -_.")
        result.series_name = title_fragment.title() if title_fragment else None

        return result



def safe_regex_escape(user_input: str) -> str:
    """Escape user-supplied search text before embedding in an ILIKE / regex pattern."""
    return re.escape(user_input.strip())
