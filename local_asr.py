"""Offline speech transcription of an authorized local WAV using whisper.cpp."""
import argparse
import json
from pathlib import Path
import re
import subprocess
import tempfile
import wave

from transcript import CaptionError, video_id


def parse_whisper_json(body):
    try:
        value = json.loads(body)
        items = value['transcription']
        if not isinstance(items, list):
            raise ValueError
        segments = []
        for item in items:
            start, end = item['offsets']['from'], item['offsets']['to']
            text = item['text']
            if type(start) is not int or type(end) is not int or not 0 <= start <= end or not isinstance(text, str):
                raise ValueError
            if text.strip():
                segments.append({'start_ms': start, 'duration_ms': end-start, 'text': text.strip()})
    except (ValueError, TypeError, KeyError, AttributeError):
        raise CaptionError('invalid_asr_response') from None
    if not segments:
        raise CaptionError('empty_asr_response')
    return segments


def validate_audio(path):
    try:
        with wave.open(str(path), 'rb') as wav:
            if (wav.getnchannels(), wav.getsampwidth(), wav.getframerate(), wav.getcomptype()) != (1, 2, 16000, 'NONE'):
                raise CaptionError('unsupported_audio_format')
            frames = wav.getnframes()
            if not 0 < frames <= 16000 * 3600:
                raise CaptionError('invalid_audio_duration')
            # Detect a truncated data chunk rather than trusting only the header.
            wav.setpos(frames-1)
            if len(wav.readframes(1)) != 2:
                raise CaptionError('invalid_audio_file')
    except (OSError, EOFError, wave.Error):
        raise CaptionError('invalid_audio_file') from None


def local_asr(audio, model, executable, language='auto', identifier=None, timeout=1800):
    """No downloads, network transport, shell, or implicit model selection."""
    if not isinstance(language, str) or not re.fullmatch(r'auto|[a-z]{2,3}', language):
        raise CaptionError('invalid_asr_language')
    if type(timeout) is not int or not 1 <= timeout <= 7200:
        raise CaptionError('invalid_asr_timeout')
    if identifier is not None:
        identifier = video_id(identifier)
    audio, model, executable = (Path(p).expanduser().resolve() for p in (audio, model, executable))
    validate_audio(audio)
    if not model.is_file():
        raise CaptionError('asr_model_missing')
    if not executable.is_file():
        raise CaptionError('asr_executable_missing')
    with tempfile.TemporaryDirectory(prefix='andrew-asr-') as folder:
        output = Path(folder) / 'result'
        command = [str(executable), '-m', str(model), '-f', str(audio),
                   '-l', language, '-oj', '-of', str(output)]
        try:
            proc = subprocess.run(command, stdin=subprocess.DEVNULL,
                                  stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                  timeout=timeout, check=False)
        except subprocess.TimeoutExpired:
            raise CaptionError('asr_timeout') from None
        except OSError:
            raise CaptionError('asr_launch_failed') from None
        if proc.returncode != 0:
            raise CaptionError('asr_failed')
        try:
            with output.with_suffix('.json').open('rb') as handle:
                raw = handle.read(8_000_001)
            if len(raw) > 8_000_000:
                raise CaptionError('response_too_large')
            body = raw.decode('utf-8')
        except (OSError, UnicodeError):
            raise CaptionError('asr_output_unreadable') from None
        segments = parse_whisper_json(body)
    result = {'source': 'local_audio', 'engine': 'whisper.cpp',
              'language_requested': language, 'automatic': True, 'segments': segments}
    if identifier is not None:
        result['user_supplied_video_id'] = identifier
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('audio')
    parser.add_argument('--model', required=True)
    parser.add_argument('--executable', required=True)
    parser.add_argument('--language', default='auto')
    parser.add_argument('--video-id')
    parser.add_argument('--timeout', type=int, default=1800)
    args = parser.parse_args()
    try:
        result = local_asr(args.audio, args.model, args.executable,
                           args.language, args.video_id, args.timeout)
    except CaptionError as exc:
        print(json.dumps({'error': exc.code}))
        return 1
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
