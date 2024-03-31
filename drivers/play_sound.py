import os.path

from playsound import playsound
from utils import Utils

root_path = Utils.get_root_path()

Dog_Barking = 'assets/sounds/mixkit-dog-barking-twice-1.wav'
Alarm_1 = 'assets/sounds/mixkit-classic-alarm-995.wav'
Alarm_2 = os.path.join('assets', 'sounds', 'mixkit-alarm-tone-996.wav')
voice = 'assets/'


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


def play_alarm_2(project_path):
    """
    voice2
    :return:
    """
    voice = os.path.join(project_path, Alarm_2)
    playsound(voice)


if __name__ == '__main__':
    # play_dog_barking()
    # play_alarm_2(
    pass
