# samples/corpus/ — offline fallback index

Used only by the `local` search provider, which exists so the demo still runs
when the venue Wi-Fi dies or the SerpApi quota is exhausted.

**Be honest about this one.** The *matching* is genuine — every image here is
face-embedded and compared to the probe with the same threshold as the live
path — but the *discovery* is local. If you demo with `--provider local`, say
so out loud and in your README.

## Layout

One image plus an optional sidecar describing the real post it came from:

```
samples/corpus/
    post_001.jpg
    post_001.json
    post_002.png
    post_002.json
```

`post_001.json`:

```json
{
  "page_url": "https://www.instagram.com/p/REAL_POST_ID/",
  "title": "caption text as it appeared",
  "captured_at": "2026-09-05T14:20:00+00:00"
}
```

Build one with:

```bash
python scripts/make_corpus.py --url https://www.instagram.com/p/... --image downloaded.jpg
```

Contents are gitignored — the images are other people's photographs.
