"""SerpApi -> Google Lens. Primary provider.

Best social-media coverage of the four. Free tier is ~100 searches/month.
Set SERPAPI_KEY in .env.
"""

from __future__ import annotations

import requests

from .. import config
from ._imagehost import host_temporarily
from .base import Candidate, SearchProvider


class SerpApiLens(SearchProvider):
    name = "serpapi_google_lens"
    requires_key = True

    def available(self) -> bool:
        return bool(config.SERPAPI_KEY)

    def search(self, image_path: str, limit: int = 25) -> list[Candidate]:
        public_url = host_temporarily(image_path)
        r = requests.get(
            "https://serpapi.com/search",
            params={
                "engine": "google_lens",
                "url": public_url,
                "api_key": config.SERPAPI_KEY,
            },
            timeout=config.HTTP_TIMEOUT * 3,
        )
        r.raise_for_status()
        data = r.json()
        if data.get("error"):
            raise RuntimeError(f"serpapi: {data['error']}")

        out: list[Candidate] = []
        for m in (data.get("visual_matches") or [])[:limit]:
            out.append(Candidate(
                page_url=m.get("link") or "",
                image_url=m.get("thumbnail") or m.get("image") or "",
                title=m.get("title") or "",
                snippet=m.get("source") or "",
                provider=self.name,
                raw=m,
            ))
        # keep the raw payload so the audit trail can prove the search happened
        self.last_raw = {"hosted_probe_url": public_url,
                         "search_metadata": data.get("search_metadata", {}),
                         "visual_match_count": len(data.get("visual_matches") or [])}
        return [c for c in out if c.page_url and c.image_url]
