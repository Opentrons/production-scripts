from enum import Enum


class Query(Enum):
    NO_SPACE = '?'
    SPACE = " ?"

# 用于设置屏幕对比度亮度
class LCD_CONTRASH(Enum):
    _1 = ' 1'
    _2 = ' 2'
    _3 = ' 3'
    _4 = ' 4'
    _5 = ' 5'
    _6 = ' 6'
    _7 = ' 7'
    _8 = ' 8'


class LCD_BRIGHT(Enum):
    DARK = ' 1'  # dark
    BRIGHT = ' 2'  # bright

class PassSoundState(Enum):
    ON = ' ON'
    OFF = ' OFF'


class MainFunc(Enum):
    MENU = 'MANU'
    AUTO = 'AUTO'



class ManuMode(Enum):
    ACW = 'ACW'
    DCW = 'DCW'


class Step(Enum):
    _1 = '1'
    _2 = '2'
    _3 = '3'
    _4 = '4'
    _5 = '5'
    _6 = '6'
    _7 = '7'
    _8 = '8'
    _9 = '9'
    _10 = '10'
    _11 = '11'
    _12 = '12'
    _13 = '13'
    _14 = '14'
    _15 = '15'
    _16 = '16'
