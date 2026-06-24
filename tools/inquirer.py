from typing import Any

from test_cli.cli.prompts import select, text

test_choices = ['1.leveling-8ch', '2.leveling-96ch', '3.leveling-gantry', '4.leveling-z-stage', '5.leveling-gripper',
                '6.leveling-reading-sensor', '7.heat-96ch', '8.grav-openweb', '9.start-server', '10.high-voltage-test',
                '11.thermocycle-diagnostic-test','12.getlifetime']

leveling_choices = ['1.ch8_leveling_test', '2.ch96_leveling_test', '3.gantry_leveling_test', '4.z_leveling_test',
                    '5.gripper_leveling_test', "6.read-sensor", "7.exit."]

question_flex = {
    'type': 'input',
    'name': 'flex',
    'message': 'Please input flex SN (请输入机器条码):'
}

question_gravname = {
    'type': 'input',
    'name': 'raspNo',
    'message': 'Please input raspberry pie No (请输入树莓派编号(GRAV1)):'
}

question_openweb = {
    'type': 'list',
    'name': 'openweb',
    'message': 'open (是否打开称数据网站):',
    'choices': ['yes(打开)', 'no(关闭)']

}

question_ip = {
    'type': 'input',
    'name': 'ip',
    'message': 'Please input IP Address (请输入机器IP地址):'
}

question_test = {
    'type': 'list',
    'name': 'test',
    'message': 'Please select test name (请选择开始测试内容):',
    'choices': test_choices
}

question_leveling = {
    'type': 'list',
    'name': 'test',
    'message': 'Please select test name (请选择开始测试内容):',
    'choices': leveling_choices
}

question_exit = {
    'type': 'list',
    'name': 'exit',
    'message': 'exit (是否退出):',
    'choices': ['yes(是)', 'no(否)']
}

question_ssh_connection = {
    'type': 'list',
    'name': 'connection',
    'message': 'use key (是否使用密钥连接):',
    'choices': ['yes(是)', 'no(否)']
}


def prompt_flex_name():
    return text(question_flex["message"]).strip()


def prompt_raspNo():
    return text(question_gravname["message"]).strip()


def prompt_ip():
    return text(question_ip["message"]).strip()


def prompt_test_name():
    return select(question_test["message"], question_test["choices"]).strip()


def prompt_leveling() -> str:
    return select(question_leveling["message"], question_leveling["choices"]).strip()


def prompt_connect_method():
    return select(question_ssh_connection["message"], question_ssh_connection["choices"]).strip()


def prompt_exit():
    return select(question_exit["message"], question_exit["choices"]).strip()


def prompt_openweb():
    return select(question_openweb["message"], question_openweb["choices"]).strip()

def input_with_default(note_text: str, default_value: Any):
    return text(note_text, default=str(default_value))
