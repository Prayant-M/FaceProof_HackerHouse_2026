"""SerpApi -> Yandex reverse image. Secondary provider.

Yandex has materially better *face* recall than Google Lens, which is tuned for
objects and products. Uses the same SERPAPI_KEY.
"""

from __future__ import annotations

import requests

from .. import config
from ._imagehost import host_temporarily
from .base import Candidate, SearchProvider


class SerpApiYandex(SearchProvider):
    name = "serpapi_yandex_images"
    requires_key = True

    def available(self) -> bool:
        return bool(config.SERPAPI_KEY)

    def search(self, image_path: str, limit: int = 25) -> list[Candidate]:
        public_url = host_temporarily(image_path)
        r = requests.get(
            "https://serpapi.com/search",
            params={
                "engine": "yandex_images",
                "url": public_url,
                "api_key": config.SERPAPI_KEY,
            },
            timeout=config.HTTP_TIMEOUT * 3,
        )
        r.raise_for_status()
        data = r.json()
        if data.get("error"):
            raise RuntimeError(f"serpapi yandex: {data['error']}")

        rows = (data.get("image_results")
                or data.get("similar_images")
                or data.get("organic_results")
                or [])
        out: list[Candidate] = []
        for m in rows[:limit]:
            out.append(Candidate(
                page_url=m.get("link") or m.get("source") or "",
                image_url=(m.get("original") or m.get("thumbnail")
                           or m.get("original_image") or ""),
                title=m.get("title") or "",
                snippet=m.get("source_name") or m.get("source") or "",
                provider=self.name,
                raw=m,
            ))
        self.last_raw = {"hosted_probe_url": public_url,
                         "search_metadata": data.get("search_metadata", {}),
                         "row_count": len(rows)}
        return [c for c in out if c.page_url and c.image_url]
