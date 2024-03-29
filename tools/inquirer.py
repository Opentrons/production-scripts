from PyInquirer import prompt

test_choices = ['leveling-8ch', 'leveling-96ch', 'leveling-gantry', 'heat-96ch']

question_flex = {
    'type': 'input',
    'name': 'flex',
    'message': 'Please input flex SN (请输入机器条码):'
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


def prompt_flex_name():
    ret = prompt(question_flex)
    return ret['flex'].strip()


def prompt_ip():
    ret = prompt(question_ip)
    return ret['ip'].strip()


def prompt_test_name():
    ret = prompt(question_test)
    return ret['test'].strip()


def prompt_exit():
    ret = prompt(question_exit)
    return ret['exit'].strip()
