import os.path
import time
import winsound

from playsound import playsound
from utils import Utils

root_path = Utils.get_root_path()

Dog_Barking = 'shared_data/sounds/mixkit-dog-barking-twice-1.wav'
Alarm_1 = 'shared_data/sounds/mixkit-classic-alarm-995.wav'
Alarm_2 = os.path.join('shared_data', 'sounds', 'mixkit-alarm-tone-996.wav')
voice = 'shared_data/'

value = 1


def play_dog_barking():
    """
    voice1
    :return:
    """
    playsound(Dog_Barking)


def play_alarm_1(project_path=None):
    """
    voice2
    :return:
    """
    if project_path is not None:
        voice = os.path.join(project_path, Alarm_1)
    else:
        voice = Alarm_1
    playsound(voice)


def play_alarm_2(project_path=None):
    """
    voice2
    :return:
    """
    if project_path is not None:
        voice = os.path.join(project_path, Alarm_2)
    else:
        voice = Alarm_2
    playsound(voice)


def play_alarm_3(frequency, duration):
    pass
    winsound.Beep(frequency, duration)


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
