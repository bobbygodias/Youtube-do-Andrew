"""Public YouTube caption retrieval; no credentials or browser required."""
import argparse
import json
import re
import socket
import urllib.error
import urllib.parse
import urllib.request


class CaptionError(Exception):
    def __init__(self, code):
        self.code = code
        super().__init__(code)


def video_id(value):
    if re.fullmatch(r'[A-Za-z0-9_-]{11}', value):
        return value
    raise CaptionError('invalid_video_id')


def checked_url(url):
    try:
        u = urllib.parse.urlsplit(url)
        if (u.scheme == 'https' and u.netloc == 'www.youtube.com'
                and u.path in ('/watch', '/api/timedtext') and not u.fragment
                and not any(ord(c) < 33 or ord(c) == 127 for c in url)):
            return url
    except ValueError:
        pass
    raise CaptionError('unsupported_endpoint')


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def fetch(url):
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())
    try:
        with opener.open(checked_url(url), timeout=15) as response:
            data = response.read(8_000_001)
    except urllib.error.HTTPError as exc:
        raise CaptionError('http_' + str(exc.code)) from None
    except (urllib.error.URLError, TimeoutError, socket.timeout, OSError) as exc:
        reason = getattr(exc, 'reason', exc)
        raise CaptionError('dns_failure' if isinstance(reason, socket.gaierror) else 'network_failure') from None
    if len(data) > 8_000_000:
        raise CaptionError('response_too_large')
    return data.decode('utf-8', errors='replace')


def player_response(page, expected_id):
    for match in re.finditer(r'\bytInitialPlayerResponse\s*=\s*', page):
        try:
            value, _ = json.JSONDecoder().raw_decode(page, match.end())
        except ValueError:
            continue
        if isinstance(value, dict):
            status = value.get('playabilityStatus', {}).get('status')
            if status != 'OK':
                raise CaptionError('playback_not_public')
            if value.get('videoDetails', {}).get('videoId') != expected_id:
                raise CaptionError('video_mismatch')
            return value
    raise CaptionError('player_response_missing')


def choose_track(player, language):
    tracks = player.get('captions', {}).get('playerCaptionsTracklistRenderer', {}).get('captionTracks', [])
    if not tracks:
        raise CaptionError('no_caption_tracks')
    matches = [t for t in tracks if t.get('languageCode') == language]
    if not matches:
        raise CaptionError('language_unavailable')
    return min(matches, key=lambda t: t.get('kind') == 'asr')


def caption_url(track, expected_id):
    url = checked_url(track.get('baseUrl', ''))
    u = urllib.parse.urlsplit(url)
    params = urllib.parse.parse_qsl(u.query, keep_blank_values=True)
    if u.path != '/api/timedtext' or [v for k, v in params if k == 'v'] != [expected_id]:
        raise CaptionError('caption_video_mismatch')
    params = [(k, v) for k, v in params if k != 'fmt'] + [('fmt', 'json3')]
    return urllib.parse.urlunsplit(u._replace(query=urllib.parse.urlencode(params)))


def parse_captions(body):
    try:
        events = json.loads(body)['events']
        if not isinstance(events, list):
            raise TypeError
        result = []
        for event in events:
            if not event.get('segs'):
                continue
            text = ''.join(s.get('utf8', '') for s in event['segs']).strip()
            if not text:
                continue
            start = event['tStartMs']
            duration = event.get('dDurationMs')
            if type(start) is not int or start < 0 or (duration is not None and (type(duration) is not int or duration < 0)):
                raise ValueError
            result.append({'start_ms': start, 'duration_ms': duration, 'text': text})
    except (ValueError, TypeError, KeyError, AttributeError):
        raise CaptionError('invalid_caption_response') from None
    if not result:
        raise CaptionError('empty_caption_response')
    return result


def transcript(identifier, language, transport=fetch):
    identifier = video_id(identifier)
    source = 'https://www.youtube.com/watch?v=' + identifier
    player = player_response(transport(source), identifier)
    track = choose_track(player, language)
    segments = parse_captions(transport(caption_url(track, identifier)))
    return {'video_id': identifier, 'source': source, 'language': language,
            'automatic': track.get('kind') == 'asr', 'segments': segments}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('video_id')
    parser.add_argument('--language', required=True)
    args = parser.parse_args()
    try:
        result = transcript(args.video_id, args.language)
    except CaptionError as exc:
        print(json.dumps({'error': exc.code}))
        return 1
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
