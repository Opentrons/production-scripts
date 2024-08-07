from GPT import *
from time import sleep

if __name__ == '__main__':

    gpt = GptDevice()
    gpt.connect()


    while True:
        cond = input("请输入")
        if cond == '9':
            break
        
        cond = '1'

        res = gpt.query_command(Code.main_func)
        print(res)
        res = gpt.change_mode(MainFunc.MENU)
        print(res)

        res = gpt.query_command(Code.manu_step)
        print(res)
        res = gpt.set_manu_test_serial(int(cond))
        print(res)

        res = gpt.query_command(Code.system_buzzer_psound)
        print(res)
        res = gpt.send_setup_to_device(Code.system_buzzer_psound,PassSoundState.ON.value)
        print(res)

        res = gpt.query_command(Code.system_buzzer_fsound)
        print(res)
        res = gpt.send_setup_to_device(Code.system_buzzer_fsound, PassSoundState.ON.value)
        print(res)

        res = gpt.query_command(Code.system_buzzer_ptime)
        print(res)
        res = gpt.set_buzzer_time(Code.system_buzzer_ptime,5)
        print(res)

        res = gpt.query_command(Code.system_buzzer_ftime)
        print(res)
        res = gpt.set_buzzer_time(Code.system_buzzer_ftime, 5)
        print(res)

        # res = gpt._send_command(Code.manu_init.value)
        # print(res)

        res = gpt.query_command(Code.function_test)
        print(res)
        res = gpt.send_setup_to_device(Code.function_test, 'ON')
        print(res)
        res = gpt.query_command(Code.function_test)
        print(res)
        sleep(75)
        res = gpt.send_setup_to_device(Code.function_test, 'OFF')
        print(res)

        res = gpt.query_command(Code.measure)
        print(res)

        

    if gpt.simulate is False:
        gpt._send_command(Code.rmtoff.value)
        res = gpt._get_response()
        print("mmmm",res)
        gpt.device.close()

