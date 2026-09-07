"""Temporary public image hosting.

SerpApi's Lens/Yandex engines need a URL they can fetch, not a file upload, so
the probe crop is pushed to a throwaway host for the duration of the search.

Hosts are tried in order and **the returned URL is verified to actually serve
image bytes** before it is handed to a search engine. That check is not
paranoia: tmpfiles.org changed its scheme so that the documented `/dl/<id>/`
path now returns an HTML viewer page rather than the file. Without the check
the pipeline uploads fine, hands the engine an HTML document, and the engine
either errors ("the URL does not refer to an image") or -- worse -- silently
returns zero matches, which is indistinguishable from "this face is not on the
web". A false negative there discredits the whole run.

The URL that was actually used is recorded in the evidence audit trail.
"""

from __future__ import annotations

import re

import requests

from .. import config

# tmpfiles' viewer page embeds the real, signed direct link:
#   https://tmpfiles.org/dl/<unix_ts>.<sig>/<id>/<filename>
_TMPFILES_DIRECT = re.compile(
    r'https://tmpfiles\.org/dl/[0-9]+\.[0-9a-f]+/[^"\'\s]+'
)


def host_temporarily(path: str) -> str:
    """Upload `path` to a throwaway public host and return a verified image URL."""
    errors = []
    # catbox first: it serves image/* directly and has proven stable.
    for fn in (_catbox, _tmpfiles):
        try:
            url = fn(path)
            if not url:
                errors.append(f"{fn.__name__}: returned no url")
                continue
            ok, detail = _serves_an_image(url)
            if ok:
                return url
            errors.append(f"{fn.__name__}: {url} -> {detail}")
        except Exception as e:
            errors.append(f"{fn.__name__}: {e!r}")
    raise RuntimeError("could not host probe image publicly: " + "; ".join(errors))


def _serves_an_image(url: str) -> tuple[bool, str]:
    """Fetch the URL the way a search engine would and confirm it is an image."""
    try:
        r = requests.get(
            url,
            timeout=config.HTTP_TIMEOUT,
            headers={"User-Agent": config.USER_AGENT},
            stream=True,
        )
    except Exception as e:
        return False, f"unfetchable: {e!r}"

    ctype = (r.headers.get("content-type") or "").split(";")[0].strip().lower()
    head = r.raw.read(12, decode_content=True) or b""
    r.close()

    if r.status_code != 200:
        return False, f"HTTP {r.status_code}"
    if not ctype.startswith("image/"):
        return False, f"content-type {ctype or '<none>'}, not image/*"
    if not _magic_is_image(head):
        return False, "content-type claims image but the bytes are not one"
    return True, ctype


def _magic_is_image(head: bytes) -> bool:
    return (
        head.startswith(b"\xff\xd8\xff")            # jpeg
        or head.startswith(b"\x89PNG\r\n\x1a\n")    # png
        or head.startswith(b"GIF87a")
        or head.startswith(b"GIF89a")
        or (head[:4] == b"RIFF" and head[8:12] == b"WEBP")
    )


def _tmpfiles(path: str) -> str:
    with open(path, "rb") as fh:
        r = requests.post(
            "https://tmpfiles.org/api/v1/upload",
            files={"file": fh},
            timeout=config.HTTP_TIMEOUT * 2,
            headers={"User-Agent": config.USER_AGENT},
        )
    r.raise_for_status()
    viewer = r.json()["data"]["url"]

    # The documented transform. It used to serve raw bytes; it now returns an
    # HTML page, so treat it as a candidate rather than an answer.
    candidate = viewer.replace("tmpfiles.org/", "tmpfiles.org/dl/")
    ok, _ = _serves_an_image(candidate)
    if ok:
        return candidate

    # Scrape the signed direct link out of the viewer page.
    page = requests.get(
        candidate,
        timeout=config.HTTP_TIMEOUT,
        headers={"User-Agent": config.USER_AGENT},
    )
    m = _TMPFILES_DIRECT.search(page.text)
    if not m:
        raise RuntimeError("tmpfiles: no direct image link in the viewer page")
    return m.group(0)


def _catbox(path: str) -> str:
    with open(path, "rb") as fh:
        r = requests.post(
            "https://catbox.moe/user/api.php",
            data={"reqtype": "fileupload"},
            files={"fileToUpload": fh},
            timeout=config.HTTP_TIMEOUT * 2,
            headers={"User-Agent": config.USER_AGENT},
        )
    r.raise_for_status()
    url = r.text.strip()
    if not url.startswith("http"):
        raise RuntimeError(f"catbox returned: {url[:120]}")
    return url
