from PyInquirer import prompt

test_choices = ['leveling-8ch', 'leveling-96ch', 'leveling-gantry', 'leveling-z-stage', 'leveling-gripper',
                'leveling-reading-sensor', 'heat-96ch', 'grav-openweb']

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
    ret = prompt(question_flex)
    return ret['flex'].strip()


def prompt_raspNo():
    ret = prompt(question_gravname)
    return ret['raspNo'].strip()


def prompt_ip():
    ret = prompt(question_ip)
    return ret['ip'].strip()


def prompt_test_name():
    ret = prompt(question_test)
    return ret['test'].strip()


def prompt_connect_method():
    ret = prompt(question_ssh_connection)
    return ret['connection'].strip()


def prompt_exit():
    ret = prompt(question_exit)
    return ret['exit'].strip()


def prompt_openweb():
    ret = prompt(question_openweb)
    return ret['openweb'].strip()
