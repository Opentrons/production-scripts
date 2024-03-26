import os.path

from playsound import playsound
from utils import Utils
root_path = Utils.get_root_path()

Dog_Barking = '../sounds/mixkit-dog-barking-twice-1.wav'

Alarm_1 = '../sounds/mixkit-classic-alarm-995.wav'
Alarm_2 = os.path.join(root_path, 'ot3_testing', 'sounds', 'mixkit-alarm-tone-996.wav')


def play_dog_barking():
    """
    voice1
    :return:
    """
    playsound(Dog_Barking)


def play_alarm_1():
    """
    voice2
    :return:
    """
    playsound(Alarm_1)


def play_alarm_2():
    """
    voice2
    :return:
    """
    playsound(Alarm_2)


if __name__ == '__main__':
    # play_dog_barking()
    play_alarm_2()
