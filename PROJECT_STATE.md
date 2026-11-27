# Project state — 2026-11-27

Experimental public-caption retrieval: transcript.py, test_transcript.py. 14 local tests passed using synthetic fixtures; live request failed DNS. No credentials, browser or paid API. HTTPS limited to exact YouTube host and endpoints; redirects rejected. No release. Next: validate on public captioned video with permitted network, harden malformed player data and add public search parser. Real captions and search not yet proven. Do not bypass restrictions.

16h15 recovery: implemented first-page public video discovery, stable deduplication, query encoding, malformed player handling and six regression tests. CI required; real YouTube discovery and captions remain separate validation requirements. Next: live public probe without credentials or bypass.

20 synthetic tests pass on Python 3.10/3.12 (run 46059051484). Live diagnostic run 46059043835 failed: search returned zero results, caption returned playback_not_public. Additional structural diagnostic reports only renderer keys and playback status, never response contents. No release or access-control bypass.

Live follow-up run 46059156052: search returned 3 videos; caption probe returned LOGIN_REQUIRED, videoDetails absent. Search validated once on public network; repeatability not established (prior run returned zero). Caption retrieval is not validated; no credentials or bypass. Keep PR draft. Next authorized public-network validation: use another openly captioned video in an ordinary permitted environment and inspect response status before parsing.

Offline import implemented for user-provided WebVTT and SRT (UTF-8/BOM, CRLF, multi-line text, timestamps, validation and 8 MB limit); five new regression tests. This offers a working independent path when online captions are unavailable, not an online bypass or ASR. Next: validate live caption retrieval on permitted public videos and extend supported VTT constructs as needed.
