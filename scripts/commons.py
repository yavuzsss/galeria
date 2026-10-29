"""Minimal, polite Wikimedia Commons API client (stdlib only).

Wikimedia asks API clients to send a descriptive User-Agent, keep requests sequential and back
off when told to; this client does all three.
"""

import html
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request

API = "https://commons.wikimedia.org/w/api.php"
USER_AGENT = "GaleriaEval/0.1 (portfolio project; builds a small eval set)"
MIN_INTERVAL = 1.0  # seconds between API calls

_last_call = 0.0


def _throttle() -> None:
    global _last_call
    wait = MIN_INTERVAL - (time.monotonic() - _last_call)
    if wait > 0:
        time.sleep(wait)
    _last_call = time.monotonic()


def open_url(url: str, method: str = "GET", timeout: float = 60):
    request = urllib.request.Request(url, method=method, headers={"User-Agent": USER_AGENT})
    for attempt in range(6):
        try:
            return urllib.request.urlopen(request, timeout=timeout)
        except urllib.error.HTTPError as exc:
            if exc.code not in (429, 503) or attempt == 5:
                raise
            time.sleep(int(exc.headers.get("Retry-After") or 5 * (attempt + 1)))
    raise AssertionError("unreachable")


def api(**params) -> dict:
    params.update(format="json", formatversion="2", maxlag="5")
    url = f"{API}?{urllib.parse.urlencode(params)}"
    for attempt in range(6):
        _throttle()
        with open_url(url) as response:
            data = json.load(response)
        error = data.get("error")
        if not error:
            return data
        if error.get("code") not in ("maxlag", "ratelimited", "cirrussearch-too-busy-error"):
            raise RuntimeError(f"Commons API error: {error}")
        time.sleep(5 * (attempt + 1))
    raise RuntimeError("Commons API kept refusing the request")


def category_files(category: str) -> list[str]:
    """File titles directly in a category, in the category's own sort order."""
    titles: list[str] = []
    params = {
        "action": "query",
        "list": "categorymembers",
        "cmtitle": f"Category:{category}",
        "cmtype": "file",
        "cmlimit": "500",
    }
    while True:
        data = api(**params)
        titles += [m["title"] for m in data["query"]["categorymembers"]]
        if "continue" not in data or len(titles) >= 1000:
            return titles
        params.update(data["continue"])


def file_info(titles: list[str], thumb_width: int) -> dict[str, dict]:
    """imageinfo for up to 50 titles per request, keyed by title."""
    out: dict[str, dict] = {}
    for i in range(0, len(titles), 50):
        data = api(
            action="query",
            prop="imageinfo",
            titles="|".join(titles[i : i + 50]),
            iiprop="url|size|mime|extmetadata|metadata",
            iiurlwidth=str(thumb_width),
            iiextmetadatafilter="LicenseShortName|LicenseUrl|Artist|Credit",
        )
        for page in data["query"]["pages"]:
            if page.get("imageinfo"):
                out[page["title"]] = page["imageinfo"][0]
    return out


def video_derivatives(title: str) -> list[dict]:
    """Transcoded renditions of a video (e.g. 360p VP9 WebM), smallest first."""
    data = api(action="query", prop="videoinfo", titles=title, viprop="derivatives")
    pages = data["query"]["pages"]
    derivatives = pages[0].get("videoinfo", [{}])[0].get("derivatives", []) if pages else []
    return sorted(derivatives, key=lambda d: d.get("height") or 0)


def plain_text(value: str | None) -> str:
    """Commons metadata fields are HTML snippets; reduce them to readable text."""
    if not value:
        return ""
    text = re.sub(r"<[^>]+>", "", value)
    return re.sub(r"\s+", " ", html.unescape(text)).strip()
