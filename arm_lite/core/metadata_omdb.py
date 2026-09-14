"""
OMDB (omdbapi.com) client for movie & TV series metadata, including poster
art. Requires arm_config.yaml's OMDB_KEY.

METADATA_PROVIDER in arm_config.yaml can also be set to "tmdb" - that
provider isn't implemented here (see identify.py, which checks the
setting and logs a warning rather than silently doing nothing if it's
set to something other than "omdb").
"""
import re

import requests

import arm_lite.config.config as cfg

OMDB_URL = "https://www.omdbapi.com/"

# Strings commonly found in disc volume labels that we should strip before
# guessing a title, e.g. "THE_MATRIX_1999_1080P_BLURAY" -> "The Matrix" 1999
_JUNK_TOKENS = [
    r"\b(1080p|720p|2160p|4k|bluray|blu-ray|dvdrip|brrip|webrip|remux|hdr|x264|x265|h264|h265)\b",
    r"\b(disc|disk|cd)\s*\d+\b",
    r"\b(dts|ac3|aac|truehd|atmos)\b",
]


def clean_label(label: str):
    """Turn a volume label into (guessed_title, guessed_year)."""
    text = (label or "").replace(".", " ").replace("_", " ").strip()
    year_match = re.search(r"(19|20)\d{2}", text)
    year = year_match.group(0) if year_match else None
    if year:
        text = text[: year_match.start()] + text[year_match.end():]
    for pattern in _JUNK_TOKENS:
        text = re.sub(pattern, "", text, flags=re.IGNORECASE)
    text = re.sub(r"\s+", " ", text).strip(" -_")
    return text.title(), year


def search(title: str, year: str = None, content_type: str = None):
    """
    content_type: None | 'movie' | 'series'. If None, tries movie then series.
    Returns an OMDB result dict (Title, Year, Poster, Plot, imdbID, Type, ...)
    or None if nothing found.
    """
    api_key = cfg.arm_config.get("OMDB_KEY")
    if not api_key:
        return None

    types_to_try = [content_type] if content_type else ["movie", "series"]
    for t in types_to_try:
        params = {"apikey": api_key, "t": title, "type": t}
        if year:
            params["y"] = year
        try:
            resp = requests.get(OMDB_URL, params=params, timeout=10)
            data = resp.json()
        except Exception as e:
            print(f"[metadata_omdb] request failed: {e}")
            continue
        if data.get("Response") == "True":
            return data

    # Fall back to a fuzzy search endpoint and take the top hit
    try:
        resp = requests.get(OMDB_URL, params={"apikey": api_key, "s": title}, timeout=10)
        data = resp.json()
        if data.get("Response") == "True" and data.get("Search"):
            top = data["Search"][0]
            return search(top["Title"], top.get("Year"), top.get("Type"))
    except Exception as e:
        print(f"[metadata_omdb] fallback search failed: {e}")

    return None


def get_by_imdb_id(imdb_id: str):
    api_key = cfg.arm_config.get("OMDB_KEY")
    if not api_key:
        return None
    resp = requests.get(OMDB_URL, params={"apikey": api_key, "i": imdb_id, "plot": "full"}, timeout=10)
    data = resp.json()
    return data if data.get("Response") == "True" else None


def search_candidates(query: str, content_type: str = None):
    """Multi-result search for a manual re-identify/fix-metadata flow."""
    api_key = cfg.arm_config.get("OMDB_KEY")
    if not api_key or not query.strip():
        return []
    params = {"apikey": api_key, "s": query.strip()}
    if content_type:
        params["type"] = content_type
    try:
        resp = requests.get(OMDB_URL, params=params, timeout=10)
        data = resp.json()
    except Exception as e:
        print(f"[metadata_omdb] search_candidates failed: {e}")
        return []
    if data.get("Response") != "True":
        return []
    return data.get("Search", [])
