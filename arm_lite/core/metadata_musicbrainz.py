"""
MusicBrainz client for identifying audio CDs by disc TOC, plus Cover Art
Archive for album art. No API key required, but MusicBrainz asks for a
descriptive User-Agent and reasonable rate limiting (~1 req/sec).

Used when arm_config.yaml's GET_AUDIO_TITLE == "musicbrainz" (the other
options, "freecddb" and "none", aren't implemented here - see identify.py).
"""
import time

import requests

MB_URL = "https://musicbrainz.org/ws/2"
CAA_URL = "https://coverartarchive.org"
HEADERS = {"User-Agent": "ARM-Lite/1.0 (personal disc ripping tool)"}

_last_request = 0.0


def _throttled_get(url, params=None):
    global _last_request
    elapsed = time.time() - _last_request
    if elapsed < 1.0:
        time.sleep(1.0 - elapsed)
    resp = requests.get(url, params=params, headers=HEADERS, timeout=10)
    _last_request = time.time()
    return resp


def _parse_release(release: dict) -> dict:
    """Shared shape for a full release record, whether it came from a
    disc-id lookup or a release-id lookup."""
    artist = ""
    if release.get("artist-credit"):
        artist = release["artist-credit"][0].get("name", "")

    tracks = []
    media = release.get("media") or []
    for medium in media:
        for t in medium.get("tracks", []):
            tracks.append(
                {
                    "number": int(t.get("number", 0) or 0),
                    "title": t.get("title", f"Track {t.get('number')}"),
                    "length_sec": round((t.get("length") or 0) / 1000, 1),
                }
            )

    return {
        "release_id": release.get("id"),
        "title": release.get("title", "Unknown Album"),
        "artist": artist or "Unknown Artist",
        "date": release.get("date", ""),
        "tracks": tracks,
    }


def lookup_by_disc_id(disc_id: str):
    """
    Automatic identification from the disc's TOC hash. Returns a dict
    {release_id, title, artist, date, tracks:[{number,title,length_sec}]}
    for the best-matching release, or None if not found.
    """
    try:
        resp = _throttled_get(
            f"{MB_URL}/discid/{disc_id}",
            params={"fmt": "json", "inc": "recordings+artist-credits"},
        )
    except Exception as e:
        print(f"[metadata_musicbrainz] lookup failed: {e}")
        return None

    if resp.status_code != 200:
        return None
    data = resp.json()

    releases = data.get("releases") or []
    if not releases:
        return None
    return _parse_release(releases[0])


def lookup_release_by_id(release_id: str):
    """Full detail fetch for a release chosen from search_releases() - used
    by a manual 'wrong match? fix it' flow."""
    try:
        resp = _throttled_get(
            f"{MB_URL}/release/{release_id}",
            params={"fmt": "json", "inc": "recordings+artist-credits+media"},
        )
    except Exception as e:
        print(f"[metadata_musicbrainz] lookup_release_by_id failed: {e}")
        return None

    if resp.status_code != 200:
        return None
    return _parse_release(resp.json())


def search_releases(query: str, limit: int = 12):
    """
    Multi-result release search (MusicBrainz's text search, not a disc-id
    lookup) for a manual 'wrong match? fix it' flow. Returns a list of
    lightweight {id, title, artist, date, track_count} dicts - fetch full
    track details via lookup_release_by_id() once one is picked.
    """
    if not query.strip():
        return []
    try:
        resp = _throttled_get(
            f"{MB_URL}/release/",
            params={"query": query.strip(), "fmt": "json", "limit": limit},
        )
    except Exception as e:
        print(f"[metadata_musicbrainz] search_releases failed: {e}")
        return []

    if resp.status_code != 200:
        return []

    results = []
    for r in resp.json().get("releases", []):
        artist = ""
        if r.get("artist-credit"):
            artist = r["artist-credit"][0].get("name", "")
        results.append(
            {
                "id": r.get("id"),
                "title": r.get("title", "Unknown Album"),
                "artist": artist or "Unknown Artist",
                "date": r.get("date", ""),
                "track_count": r.get("track-count"),
            }
        )
    return results


def cover_art_url(release_id: str):
    """Returns a front-cover image URL, or None if none is registered."""
    try:
        resp = requests.get(f"{CAA_URL}/release/{release_id}", headers=HEADERS, timeout=8)
        if resp.status_code == 200:
            images = resp.json().get("images", [])
            for img in images:
                if img.get("front"):
                    return img.get("image")
    except Exception:
        pass
    return None
