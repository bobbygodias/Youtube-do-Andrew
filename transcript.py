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
                and u.path in ('/watch', '/api/timedtext', '/results') and not u.fragment
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
            status = obj(value.get('playabilityStatus')).get('status')
            if status != 'OK':
                raise CaptionError('playback_not_public')
            if obj(value.get('videoDetails')).get('videoId') != expected_id:
                raise CaptionError('video_mismatch')
            return value
    raise CaptionError('player_response_missing')


def obj(value):
    return value if isinstance(value, dict) else {}


def choose_track(player, language):
    tracks = obj(obj(obj(player).get('captions')).get('playerCaptionsTracklistRenderer')).get('captionTracks', [])
    if not isinstance(tracks, list):
        raise CaptionError('invalid_caption_tracks')
    tracks = [t for t in tracks if isinstance(t, dict)]
    if not tracks:
        raise CaptionError('no_caption_tracks')
    matches = [t for t in tracks if t.get('languageCode') == language]
    if not matches:
        raise CaptionError('language_unavailable')
    return min(matches, key=lambda t: t.get('kind') == 'asr')


def caption_url(track, expected_id):
    raw = obj(track).get('baseUrl')
    if not isinstance(raw, str):
        raise CaptionError('unsupported_endpoint')
    url = checked_url(raw)
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



def renderer_text(value):
    value = obj(value)
    if isinstance(value.get('simpleText'), str):
        return value['simpleText']
    runs = value.get('runs')
    if not isinstance(runs, list):
        return ''
    return ''.join(r['text'] for r in runs if isinstance(r, dict) and isinstance(r.get('text'), str))


def parse_search(page, limit=10):
    if type(limit) is not int or not 1 <= limit <= 50:
        raise CaptionError('invalid_search_limit')
    data = None
    for match in re.finditer(r'\bytInitialData\s*=\s*', page):
        try:
            candidate, _ = json.JSONDecoder().raw_decode(page, match.end())
        except ValueError:
            continue
        if isinstance(candidate, dict):
            data = candidate
            break
    if data is None:
        raise CaptionError('search_response_missing')
    # Restrict discovery to primary search-result sections; no recommendations.
    primary = obj(obj(obj(obj(data.get('contents')).get('twoColumnSearchResultsRenderer')).get('primaryContents')).get('sectionListRenderer'))
    sections = primary.get('contents')
    if not isinstance(sections, list):
        raise CaptionError('invalid_search_response')
    result, seen = [], set()
    for section in sections:
        items = obj(obj(section).get('itemSectionRenderer')).get('contents', [])
        if not isinstance(items, list):
            continue
        for item in items:
            v = obj(obj(item).get('videoRenderer'))
            identifier = v.get('videoId')
            title = renderer_text(v.get('title')).strip()
            if not isinstance(identifier, str) or not re.fullmatch(r'[A-Za-z0-9_-]{11}', identifier) or not title or identifier in seen:
                continue
            seen.add(identifier)
            result.append({'video_id': identifier, 'title': title,
                           'channel': renderer_text(v.get('ownerText')),
                           'source': 'https://www.youtube.com/watch?v=' + identifier})
            if len(result) == limit:
                return result
    return result


def search_videos(query, limit=10, transport=fetch):
    if not isinstance(query, str) or not query.strip() or len(query) > 300:
        raise CaptionError('invalid_search_query')
    if type(limit) is not int or not 1 <= limit <= 50:
        raise CaptionError('invalid_search_limit')
    url = 'https://www.youtube.com/results?' + urllib.parse.urlencode({'search_query': query})
    return {'query': query, 'source': url, 'videos': parse_search(transport(url), limit)}



def timestamp_ms(value):
    match = re.fullmatch(r'(?:(\d{2,}):)?([0-5]\d):([0-5]\d)[.,](\d{3})', value)
    if not match:
        raise CaptionError('invalid_caption_timestamp')
    hours, minutes, seconds, ms = (int(x or 0) for x in match.groups())
    return ((hours * 60 + minutes) * 60 + seconds) * 1000 + ms


def parse_timed_text(body, fmt):
    """Import a user-provided WebVTT or SRT subtitle file, no network."""
    if fmt not in ('vtt', 'srt'):
        raise CaptionError('unsupported_caption_format')
    body = body.lstrip('\ufeff').replace('\r\n', '\n').replace('\r', '\n')
    blocks = re.split(r'\n[ \t]*\n', body.strip())
    if fmt == 'vtt':
        if not blocks or not re.fullmatch(r'WEBVTT(?:[ \t].*)?', blocks[0].split('\n')[0]):
            raise CaptionError('invalid_vtt_header')
        blocks = blocks[1:]
    results = []
    for block in blocks:
        lines = block.split('\n')
        if fmt == 'vtt' and (re.match(r'^(NOTE(?:[ \t]|$)|STYLE$|REGION$)', lines[0])):
            continue
        if len(lines) >= 2 and '-->' not in lines[0]:
            if fmt == 'srt' and not lines[0].isdigit():
                raise CaptionError('invalid_caption_block')
            lines = lines[1:]
        if len(lines) < 2 or '-->' not in lines[0]:
            raise CaptionError('invalid_caption_block')
        parts = lines[0].split('-->')
        if len(parts) != 2 or not parts[1].strip():
            raise CaptionError('invalid_caption_block')
        start = timestamp_ms(parts[0].strip())
        end = timestamp_ms(parts[1].strip().split()[0])
        if end < start:
            raise CaptionError('invalid_caption_interval')
        text = '\n'.join(lines[1:]).strip()
        if text:
            results.append({'start_ms': start, 'duration_ms': end-start, 'text': text})
    if not results:
        raise CaptionError('empty_caption_response')
    return results


def import_captions(path, fmt):
    try:
        with open(path, 'rb') as handle:
            raw = handle.read(8_000_001)
        if len(raw) > 8_000_000:
            raise CaptionError('response_too_large')
        body = raw.decode('utf-8-sig')
    except (OSError, UnicodeError):
        raise CaptionError('caption_file_unreadable') from None
    return {'source': 'local_file', 'format': fmt, 'segments': parse_timed_text(body, fmt)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('video_id', nargs='?')
    parser.add_argument('--language')
    parser.add_argument('--search')
    parser.add_argument('--limit', type=int, default=10)
    parser.add_argument('--caption-file')
    parser.add_argument('--format', choices=['vtt', 'srt'])
    args = parser.parse_args()
    try:
        if args.caption_file is not None:
            if args.format is None or any(x is not None for x in (args.video_id, args.search, args.language)):
                raise CaptionError('invalid_arguments')
            result = import_captions(args.caption_file, args.format)
        elif args.format is not None:
            raise CaptionError('invalid_arguments')
        elif args.search is not None and args.video_id is None and args.language is None:
            result = search_videos(args.search, args.limit)
        elif args.search is None and args.video_id is not None and args.language is not None:
            result = transcript(args.video_id, args.language)
        else:
            raise CaptionError('invalid_arguments')
    except CaptionError as exc:
        print(json.dumps({'error': exc.code}))
        return 1
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
