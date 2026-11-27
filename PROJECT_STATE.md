# Project state — 2026-11-27

Experimental public-caption retrieval: transcript.py, test_transcript.py. 14 local tests passed using synthetic fixtures; live request failed DNS. No credentials, browser or paid API. HTTPS limited to exact YouTube host and endpoints; redirects rejected. No release. Next: validate on public captioned video with permitted network, harden malformed player data and add public search parser. Real captions and search not yet proven. Do not bypass restrictions.

16h15 recovery: implemented first-page public video discovery, stable deduplication, query encoding, malformed player handling and six regression tests. CI required; real YouTube discovery and captions remain separate validation requirements. Next: live public probe without credentials or bypass.

20 synthetic tests pass on Python 3.10/3.12 (run 46059051484). Live diagnostic run 46059043835 failed: search returned zero results, caption returned playback_not_public. Additional structural diagnostic reports only renderer keys and playback status, never response contents. No release or access-control bypass.
