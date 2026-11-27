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


if __name__ == '__main__':
    unittest.main()
