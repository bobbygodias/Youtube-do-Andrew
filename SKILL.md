---
name: youtube-do-andrew
description: Experimental local CLI for retrieving publicly accessible YouTube captions by video ID; not yet live-validated.
---

Run `python transcript.py VIDEO_ID --language pt` from repository root. Choose the exact language code. JSON success contains source, video_id, language, automatic and timestamped segments. JSON error and nonzero exit mean no transcript was retrieved; do not fabricate or infer one. No credentials, login, paid API or browser needed. Do not circumvent access restrictions. Search by topic is not yet implemented. Test via `python -m unittest -v`.
