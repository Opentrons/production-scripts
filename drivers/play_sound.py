import os.path
import math
import shutil
import struct
import subprocess
import tempfile
import time
import sys
import wave

from utils import Utils

if sys.platform == 'win32':
    import winsound
else:
    winsound = None

root_path = Utils.get_root_path()

Dog_Barking = 'shared_data/sounds/mixkit-dog-barking-twice-1.wav'
Alarm_1 = 'shared_data/sounds/mixkit-classic-alarm-995.wav'
Alarm_2 = os.path.join('shared_data', 'sounds', 'mixkit-alarm-tone-996.wav')
voice = 'shared_data/'

value = 1


def _resolve_sound_path(path: str, project_path=None) -> str:
    if project_path is not None:
        return os.path.join(project_path, path)
    if os.path.isabs(path):
        return path
    return os.path.join(root_path, path)


def _play_file(path: str) -> None:
    if winsound:
        winsound.PlaySound(path, winsound.SND_FILENAME | winsound.SND_ASYNC)
        return
    if sys.platform == 'darwin' and shutil.which('afplay'):
        subprocess.Popen(
            ['afplay', path],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return
    print('\a', end='', flush=True)


def _write_tone(path: str, frequency: int, duration_ms: int) -> None:
    sample_rate = 44100
    samples = max(1, int(sample_rate * duration_ms / 1000))
    amplitude = 12000
    with wave.open(path, 'wb') as audio:
        audio.setnchannels(1)
        audio.setsampwidth(2)
        audio.setframerate(sample_rate)
        frames = bytearray()
        for index in range(samples):
            value = int(amplitude * math.sin(2 * math.pi * frequency * index / sample_rate))
            frames.extend(struct.pack('<h', value))
        audio.writeframes(frames)


def _play_tone_with_afplay(frequency: int, duration_ms: int) -> None:
    tone_file = tempfile.NamedTemporaryFile(prefix='test-cli-tone-', suffix='.wav', delete=False)
    tone_path = tone_file.name
    tone_file.close()
    _write_tone(tone_path, frequency, duration_ms)
    process = subprocess.Popen(
        ['afplay', tone_path],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    def cleanup():
        try:
            process.wait(timeout=max(1, duration_ms / 1000 + 1))
        finally:
            try:
                os.remove(tone_path)
            except OSError:
                pass

    import threading

    threading.Thread(target=cleanup, daemon=True).start()


def play_dog_barking():
    """
    voice1
    :return:
    """
    _play_file(_resolve_sound_path(Dog_Barking))


def play_alarm_1(project_path=None):
    """
    voice2
    :return:
    """
    if project_path is not None:
        voice = _resolve_sound_path(Alarm_1, project_path)
    else:
        voice = _resolve_sound_path(Alarm_1)
    _play_file(voice)


def play_alarm_2(project_path=None):
    """
    voice2
    :return:
    """
    if project_path is not None:
        voice = _resolve_sound_path(Alarm_2, project_path)
    else:
        voice = _resolve_sound_path(Alarm_2)
    _play_file(voice)


def play_alarm_3(frequency, duration):
    if winsound:
        winsound.Beep(frequency, duration)
        return
    if sys.platform == 'darwin' and shutil.which('afplay'):
        _play_tone_with_afplay(frequency, duration)
        return
    print('\a', end='', flush=True)


if __name__ == '__main__':
    print(root_path)
    play_alarm_3(3000, 500)

    import threading


    def play_value(f, d):
        play_alarm_3(f, d)


    def judge_value():
        while True:
            # if value > 0.2:
            #     play_value(500, 1000)
            # elif 0.1 <value<= 0.2:
            #     play_value(500, 1000)
            # elif value
            # elif 0.05 <= value <= 0.1:
            #     play_value(500, 500)
            # elif 0.03 < value < 0.05:
            #     play_value(1000, 500)
            # else:
            #     play_value(1000, 300)
            _value = int(-value * 1500 + 1000)
            if _value < 0:
                _value = 1500
            play_alarm_3(_value, 500)



    th = threading.Thread(target=judge_value)
    th.start()
    # th.join()
    while True:
        value = float(input("value:"))
