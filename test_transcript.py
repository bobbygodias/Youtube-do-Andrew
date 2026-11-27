import json
import unittest
from unittest.mock import patch
import urllib.error
import socket
import transcript as t

VID = 'abcDEF12345'
URL = 'https://www.youtube.com/api/timedtext?v=' + VID + '&lang=pt'


def page(tracks=None, status='OK', identifier=VID):
    player = {'playabilityStatus': {'status': status}, 'videoDetails': {'videoId': identifier},
              'captions': {'playerCaptionsTracklistRenderer': {'captionTracks': tracks or []}}}
    return '<script>var ytInitialPlayerResponse = ' + json.dumps(player) + ';</script>'


def track(**kwargs):
    return dict({'languageCode': 'pt', 'baseUrl': URL}, **kwargs)


class Tests(unittest.TestCase):
    def test_end_to_end_fixture(self):
        responses = [page([track(kind='asr'), track()]), json.dumps({'events': [
            {'tStartMs': 123, 'dDurationMs': 456, 'segs': [{'utf8': 'Olá '}, {'utf8': 'mundo'}]}]})]
        calls = []
        def transport(url):
            calls.append(url)
            return responses.pop(0)
        out = t.transcript(VID, 'pt', transport)
        self.assertEqual(out['segments'], [{'start_ms': 123, 'duration_ms': 456, 'text': 'Olá mundo'}])
        self.assertFalse(out['automatic'])
        self.assertTrue(calls[1].endswith('fmt=json3'))

    def test_reject_nonpublic(self):
        with self.assertRaisesRegex(t.CaptionError, 'playback_not_public'):
            t.player_response(page(status='LOGIN_REQUIRED'), VID)

    def test_wrong_video(self):
        with self.assertRaisesRegex(t.CaptionError, 'video_mismatch'):
            t.player_response(page(identifier='xxxxxxxxxxx'), VID)

    def test_no_player(self):
        with self.assertRaisesRegex(t.CaptionError, 'player_response_missing'):
            t.player_response('<html>consent</html>', VID)

    def test_no_tracks(self):
        with self.assertRaisesRegex(t.CaptionError, 'no_caption_tracks'):
            t.choose_track(t.player_response(page(), VID), 'pt')

    def test_wrong_language(self):
        with self.assertRaisesRegex(t.CaptionError, 'language_unavailable'):
            t.choose_track(t.player_response(page([track()]), VID), 'en')

    def test_unsafe_endpoints(self):
        for url in ('http://www.youtube.com/watch', 'https://www.youtube.com.evil/watch',
                    'https://www.youtube.com@127.0.0.1/watch', 'https://www.youtube.com:443/watch',
                    'https://www.youtube.com/watch\n', 'https://www.youtube.com/other'):
            with self.subTest(url=url), self.assertRaises(t.CaptionError):
                t.checked_url(url)

    def test_caption_wrong_video(self):
        with self.assertRaisesRegex(t.CaptionError, 'caption_video_mismatch'):
            t.caption_url(track(baseUrl=URL + '&v=other'), VID)

    def test_invalid_response(self):
        for body in ('<html>', '{"events": {}}', '{"events":[{"segs":[{"utf8":"x"}],"tStartMs":-1}]}'):
            with self.subTest(body=body), self.assertRaisesRegex(t.CaptionError, 'invalid_caption_response'):
                t.parse_captions(body)

    def test_empty_caption(self):
        with self.assertRaisesRegex(t.CaptionError, 'empty_caption_response'):
            t.parse_captions('{"events": []}')

    def test_invalid_id(self):
        with self.assertRaisesRegex(t.CaptionError, 'invalid_video_id'):
            t.video_id('abc&x=12345')

    def test_dns_failure(self):
        with patch('urllib.request.OpenerDirector.open', side_effect=urllib.error.URLError(socket.gaierror(-2, 'DNS'))):
            with self.assertRaisesRegex(t.CaptionError, 'dns_failure'):
                t.fetch('https://www.youtube.com/watch?v=' + VID)

    def test_http_error(self):
        error = urllib.error.HTTPError(URL, 429, 'rate limit', {}, None)
        with patch('urllib.request.OpenerDirector.open', side_effect=error):
            with self.assertRaisesRegex(t.CaptionError, 'http_429'):
                t.fetch(URL)

    def test_redirect_denied(self):
        self.assertIsNone(t.NoRedirect().redirect_request(None, None, 302, '', {}, 'https://other.invalid/'))


class SearchTests(unittest.TestCase):
    def fixture(self, items):
        data = {'contents': {'twoColumnSearchResultsRenderer': {'primaryContents':
            {'sectionListRenderer': {'contents': [{'itemSectionRenderer': {'contents': items}}]}}}}}
        return '<script>var ytInitialData = ' + json.dumps(data) + ';</script>'

    def video(self, identifier=VID):
        return {'videoRenderer': {'videoId': identifier, 'title': {'runs': [{'text': 'A '}, {'text': 'video'}]},
                                 'ownerText': {'simpleText': 'Channel'}}}

    def test_search_order_dedup_and_filter(self):
        page = self.fixture([self.video(), self.video(), {'channelRenderer': {}},
                             self.video('invalid'), self.video('12345678901')])
        result = t.parse_search(page)
        self.assertEqual([x['video_id'] for x in result], [VID, '12345678901'])
        self.assertEqual(result[0]['title'], 'A video')
        self.assertEqual(result[0]['channel'], 'Channel')
        self.assertEqual(len(t.parse_search(page, 1)), 1)

    def test_search_transport_encoding(self):
        calls = []
        def transport(url):
            calls.append(url)
            return self.fixture([self.video()])
        out = t.search_videos('a & b', transport=transport)
        self.assertEqual(calls, ['https://www.youtube.com/results?search_query=a+%26+b'])
        self.assertEqual(len(out['videos']), 1)

    def test_search_bad_response(self):
        for page in ('consent', 'ytInitialData = {}'):
            with self.assertRaises(t.CaptionError):
                t.parse_search(page)

    def test_search_empty_results(self):
        self.assertEqual(t.parse_search(self.fixture([])), [])

    def test_search_invalid_parameters(self):
        for query, limit in [('', 10), ('a', 0), ('a', 51), ('a', True)]:
            with self.assertRaises(t.CaptionError):
                t.search_videos(query, limit, transport=lambda _: self.fail('network invoked'))

    def test_malformed_player_and_track(self):
        with self.assertRaisesRegex(t.CaptionError, 'playback_not_public'):
            t.player_response('ytInitialPlayerResponse = {"playabilityStatus":null}', VID)
        with self.assertRaisesRegex(t.CaptionError, 'no_caption_tracks'):
            t.choose_track({'captions': None}, 'pt')
        with self.assertRaisesRegex(t.CaptionError, 'unsupported_endpoint'):
            t.caption_url({'baseUrl': None}, VID)


class LocalCaptionTests(unittest.TestCase):
    def test_vtt_multiline_and_settings(self):
        raw = 'WEBVTT\n\nNOTE metadata\nignored\n\ncue-one\n00:01.100 --> 00:03.200 align:start\nOlá\nmundo\n\n00:03.200 --> 00:04.000\nnext'
        result = t.parse_timed_text(raw, 'vtt')
        self.assertEqual(result[0], {'start_ms':1100,'duration_ms':2100,'text':'Olá\nmundo'})
        self.assertEqual(result[1]['start_ms'],3200)

    def test_srt_crlf_and_hours(self):
        result = t.parse_timed_text('1\r\n01:02:03,004 --> 01:02:04,005\r\nText\r\n','srt')
        self.assertEqual(result,[{'start_ms':3723004,'duration_ms':1001,'text':'Text'}])

    def test_invalid_timestamp_and_interval(self):
        for stamp in ['00:60.000','nope','00:00.00']:
            with self.assertRaises(t.CaptionError):
                t.timestamp_ms(stamp)
        with self.assertRaisesRegex(t.CaptionError,'invalid_caption_interval'):
            t.parse_timed_text('WEBVTT\n\n00:02.000 --> 00:01.000\nx','vtt')

    def test_file_import_and_missing(self):
        import tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/'example.vtt'
            path.write_text('WEBVTT\n\n00:00.000 --> 00:01.000\nabc',encoding='utf-8-sig')
            self.assertEqual(t.import_captions(path,'vtt')['segments'][0]['text'],'abc')
            with self.assertRaisesRegex(t.CaptionError,'caption_file_unreadable'):
                t.import_captions(Path(folder)/'missing','srt')

    def test_empty_invalid_header_and_format(self):
        for body,fmt in [('WEBVTT','vtt'),('bad','vtt'),('hello','txt')]:
            with self.assertRaises(t.CaptionError):
                t.parse_timed_text(body,fmt)


if __name__ == '__main__':
    unittest.main()
