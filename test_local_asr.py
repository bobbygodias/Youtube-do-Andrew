import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import wave

from local_asr import local_asr, parse_whisper_json
from transcript import CaptionError


class LocalASRTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        root = Path(self.folder.name)
        self.audio = root / 'audio.wav'
        self.model = root / 'model.bin'
        self.model.write_bytes(b'fixture, not a speech model')
        with wave.open(str(self.audio), 'wb') as wav:
            wav.setparams((1, 2, 16000, 0, 'NONE', 'not compressed'))
            wav.writeframes(b'\0\0' * 160)
        self.payload = {'transcription': [
            {'offsets': {'from': 100, 'to': 500}, 'text': ' Olá mundo '}]}

    def test_parse_offsets(self):
        self.assertEqual(parse_whisper_json(json.dumps(self.payload)),
                         [{'start_ms': 100, 'duration_ms': 400, 'text': 'Olá mundo'}])

    def test_invalid_response(self):
        for payload in ({}, {'transcription': {}}, {'transcription': [
            {'offsets': {'from': True, 'to': 2}, 'text': 'x'}]},
            {'transcription': [{'offsets': {'from': 3, 'to': 2}, 'text': 'x'}]}):
            with self.subTest(payload=payload), self.assertRaisesRegex(CaptionError, 'invalid_asr_response'):
                parse_whisper_json(json.dumps(payload))

    def test_empty_response(self):
        with self.assertRaisesRegex(CaptionError, 'empty_asr_response'):
            parse_whisper_json('{"transcription":[]}')

    def test_process_contract(self):
        def engine(args, **kwargs):
            self.assertEqual(args[1:5], ['-m', str(self.model), '-f', str(self.audio)])
            self.assertEqual(args[5:8], ['-l', 'pt', '-oj'])
            self.assertEqual(kwargs['timeout'], 10)
            self.assertEqual(kwargs['stdin'], subprocess.DEVNULL)
            self.assertNotIn('shell', kwargs)
            Path(args[-1] + '.json').write_text(json.dumps(self.payload), encoding='utf-8')
            return subprocess.CompletedProcess(args, 0)
        with patch('local_asr.subprocess.run', side_effect=engine):
            result = local_asr(self.audio, self.model, sys.executable, 'pt', 'abcDEF12345', 10)
        self.assertEqual(result['source'], 'local_audio')
        self.assertEqual(result['user_supplied_video_id'], 'abcDEF12345')
        self.assertEqual(result['segments'][0]['text'], 'Olá mundo')

    def test_timeout(self):
        with patch('local_asr.subprocess.run', side_effect=subprocess.TimeoutExpired([], 1)):
            with self.assertRaisesRegex(CaptionError, 'asr_timeout'):
                local_asr(self.audio, self.model, sys.executable, timeout=1)

    def test_nonzero_exit(self):
        with patch('local_asr.subprocess.run', return_value=subprocess.CompletedProcess([], 2)):
            with self.assertRaisesRegex(CaptionError, 'asr_failed'):
                local_asr(self.audio, self.model, sys.executable)

    def test_missing_output(self):
        with patch('local_asr.subprocess.run', return_value=subprocess.CompletedProcess([], 0)):
            with self.assertRaisesRegex(CaptionError, 'asr_output_unreadable'):
                local_asr(self.audio, self.model, sys.executable)

    def test_input_validation(self):
        with patch('local_asr.subprocess.run') as run:
            for kwargs, error in [({'language': '--bad'}, 'invalid_asr_language'),
                                  ({'timeout': 0}, 'invalid_asr_timeout')]:
                with self.assertRaisesRegex(CaptionError, error):
                    local_asr(self.audio, self.model, sys.executable, **kwargs)
            with self.assertRaisesRegex(CaptionError, 'asr_model_missing'):
                local_asr(self.audio, self.model.with_suffix('.missing'), sys.executable)
            with self.assertRaisesRegex(CaptionError, 'asr_executable_missing'):
                local_asr(self.audio, self.model, self.model.with_suffix('.missing'))
            self.audio.write_bytes(b'not a WAV')
            with self.assertRaisesRegex(CaptionError, 'invalid_audio_file'):
                local_asr(self.audio, self.model, sys.executable)
            run.assert_not_called()


if __name__ == '__main__':
    unittest.main()
