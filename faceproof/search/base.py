"""Search provider interface + cascade.

No single reverse-image service is reliable enough to bet a demo on, so the
pipeline defines one interface and tries providers in order until one returns
candidates.

IMPORTANT: a provider's output is a *claim*, never evidence. Everything it
returns is re-verified by rerank.py against the probe embedding before it can
become part of an evidence bundle.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from urllib.parse import urlparse

SOCIAL_DOMAINS = {
    "instagram.com", "x.com", "twitter.com", "linkedin.com", "facebook.com",
    "reddit.com", "threads.net", "mastodon.social", "bsky.app", "tumblr.com",
    "github.com", "youtube.com", "tiktok.com", "pinterest.com", "flickr.com",
    "vk.com", "weibo.com", "medium.com", "substack.com",
}


@dataclass
class Candidate:
    """One result from a search provider. Unverified by construction."""

    page_url: str
    image_url: str
    title: str = ""
    snippet: str = ""
    provider: str = ""
    raw: dict = field(default_factory=dict)

    @property
    def host(self) -> str:
        return urlparse(self.page_url).netloc.lower().removeprefix("www.")

    @property
    def is_social(self) -> bool:
        h = self.host
        return any(h == d or h.endswith("." + d) for d in SOCIAL_DOMAINS)

    @property
    def platform(self) -> str:
        h = self.host
        for d in SOCIAL_DOMAINS:
            if h == d or h.endswith("." + d):
                return d
        return h or "unknown"

    def to_dict(self) -> dict:
        return {
            "page_url": self.page_url,
            "image_url": self.image_url,
            "title": self.title,
            "snippet": self.snippet,
            "provider": self.provider,
            "platform": self.platform,
            "is_social": self.is_social,
        }


class SearchProvider(ABC):
    name: str = "abstract"
    requires_key: bool = False

    @abstractmethod
    def available(self) -> bool:
        """True when this provider can actually run right now."""

    @abstractmethod
    def search(self, image_path: str, limit: int = 25) -> list[Candidate]:
        """Run a live search. Must hit the network (except LocalCorpus)."""


def _registry() -> dict[str, type[SearchProvider]]:
    from .local_corpus import LocalCorpus
    from .playwright_lens import PlaywrightLens
    from .serpapi_lens import SerpApiLens
    from .serpapi_yandex import SerpApiYandex

    return {
        "serpapi": SerpApiLens,
        "yandex": SerpApiYandex,
        "playwright": PlaywrightLens,
        "local": LocalCorpus,
    }


#: Order matters. Yandex has the best face recall; Lens has the best social
#: coverage; Playwright is free but scrapes; LocalCorpus is the offline floor.
CASCADE_ORDER = ["serpapi", "yandex", "playwright", "local"]


def get_provider(name: str) -> SearchProvider:
    reg = _registry()
    if name not in reg:
        raise ValueError(f"unknown provider {name!r}; choose from {sorted(reg)}")
    return reg[name]()


def cascade(image_path: str, limit: int = 25, order: list[str] | None = None,
            on_event=None) -> tuple[list[Candidate], list[dict]]:
    """Try providers in order; return the first non-empty result set.

    Returns (candidates, trace) where trace records every provider attempt so
    the evidence bundle can show exactly how the search went.
    """
    trace: list[dict] = []
    for name in (order or CASCADE_ORDER):
        try:
            p = get_provider(name)
        except ValueError as e:
            trace.append({"provider": name, "status": "unknown", "detail": str(e)})
            continue
        if not p.available():
            trace.append({"provider": p.name, "status": "unavailable",
                          "detail": "missing key or dependency"})
            if on_event:
                on_event(p.name, "unavailable", 0)
            continue
        try:
            results = p.search(image_path, limit=limit)
        except Exception as e:  # a dead provider must not kill the run
            trace.append({"provider": p.name, "status": "error", "detail": repr(e)})
            if on_event:
                on_event(p.name, "error", 0)
            continue
        trace.append({"provider": p.name, "status": "ok", "count": len(results)})
        if on_event:
            on_event(p.name, "ok", len(results))
        if results:
            return results, trace
    return [], trace
