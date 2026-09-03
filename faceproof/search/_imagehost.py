"""Temporary public image hosting.

SerpApi's Lens/Yandex engines need a URL they can fetch, not a file upload, so
the probe crop is pushed to a throwaway host for the duration of the search.

Two hosts are tried; both are anonymous and short-lived. The URL that was
actually used is recorded in the evidence audit trail.
"""

from __future__ import annotations

import requests

from .. import config


def host_temporarily(path: str) -> str:
    errors = []
    for fn in (_tmpfiles, _catbox):
        try:
            url = fn(path)
            if url:
                return url
        except Exception as e:
            errors.append(f"{fn.__name__}: {e!r}")
    raise RuntimeError("could not host probe image publicly: " + "; ".join(errors))


def _tmpfiles(path: str) -> str:
    with open(path, "rb") as fh:
        r = requests.post(
            "https://tmpfiles.org/api/v1/upload",
            files={"file": fh},
            timeout=config.HTTP_TIMEOUT * 2,
            headers={"User-Agent": config.USER_AGENT},
        )
    r.raise_for_status()
    url = r.json()["data"]["url"]
    # the API returns a viewer URL; /dl/ serves the raw bytes
    return url.replace("tmpfiles.org/", "tmpfiles.org/dl/")


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
