"""
@description: TC Diagnostic Test
@date: 20230601
@author: andy-hu
@email: andy.hu@opentrons.com
"""

# encoding:utf-8

import os.path

from modules_testing.thermocycle_diagnostic.report import Report
from modules_testing.thermocycle_diagnostic.driver import SerialDriver
import time

DisplaySymbol = "#"
IfAskDutState = False
ReportName = "TC-DiagnosticTest"


class TC:
    def __init__(self):
        self.report = Report(ReportName)
        self.serail = SerialDriver()
        self.test_result = []

    def write_csv(self):
        """
        write test result
        :return:
        """
        self.report.write_row(self.test_result)

    def init_report(self):
        """
        init csv
        :return:
        """

        head1 = ["Test: Barcode Scan", "Test: Get System Info", "Test: Get System Info", "Test: Get Board HW Revision",
                 "Test: UI LED Test", "Test: Front Button LED", "Test: Seal Retracted Switch Test",
                 "Test: Seal Retracted Switch Test",
                 "Test: Plate Lift Test", "Test: Lid Open Switch Test", "Test: Lid Open Switch Test",
                 "Test: Front Button Press", "Test: Front Button Press", "Test: Close Lid Extend Seal Switch Test",
                 "Test: Close Lid Extend Seal Switch Test",
                 "Test: Lid Thermistor Test", "Test: Lid Thermistor Test", "Test: Plate Thermistor Test",
                 "Test: Plate Thermistor Test",
                 "Test: Heatsink Fan Test", "Test: Heatsink Fan Test", "Test: Lid Heater Test", "Test: Lid Heater Test",
                 "Test: Cold Peltier Test", "Test: Cold Peltier Test", "Test: Hot Peltier Test",
                 "Test: Hot Peltier Test"]

        head2 = ["Unit Barcode Number", "Unit Firmware Serial Number", "Unit Firmware Revision",
                 "Unit Board HW Revision",
                 "RESULT", "RESULT", "M901.D Response", "RESULT", "RESULT", "M901.D Response", "RESULT",
                 "M901.D Response", "RESULT", "M901.D Response", "RESULT", "Lid Thermistor M141 Response", "RESULT",
                 "Plate Thermistor M105.D Response", "RESULT", "Heatsink Fan M103.D Response", "RESULT",
                 "M141 Response",
                 "RESULT", "Cold Peltier Test M105.D Response", "RESULT", "Hot Peltier Test M105.D Response", "RESULT"
                 ]
        csv = ReportName + "-" + time.strftime("%Y%m%d") + '.csv'
        if os.path.exists(csv):
            pass
        else:
            self.report.write_row(head1)
            self.report.write_row(head2)

    def init_serial(self):
        """
        init serial port connect
        :return:
        """
        self.serail.init()

    def load_test_specification(self):
        """
        load test guide
        :return:
        """
        import json
        with open("tc_test_specificaition.json", "r", encoding='utf-8') as f:
            dict_res = json.load(f)
            f.close()
            return dict_res

    def get_barcode_number(self):
        """
        get bar code
        :return:
        """
        # board code
        get_board_code = input("input barcode number: ")
        self.test_result.append(get_board_code)

    def repair_to_start(self):
        """
        repair to get started
        :return:
        """
        input("close lid and type any key...（盖子是否关闭，清空机器内的孔板，可以开始测试，按任意键继续...）")

    def get_sn_by_system_info(self, info):
        """
        get serial number
        :param info:
        :return:
        """
        idx = info.find("SerialNo:")
        serial_number = info[idx:].split(' ')[0].strip()
        if ":" in serial_number:
            serial_number = serial_number.split(':')[-1]
        return serial_number

    def get_fw_by_system_info(self, info):
        """
        get serial number
        :param info:
        :return:
        """
        idx = info.find("FW:")
        fw = info[idx:].split(' ')[0].strip()
        if ":" in fw:
            fw = fw.split(':')[-1]
        return fw

    def lift_plate(self):
        """
        lift instrument
        :return:
        """
        ret = self.serail.write_and_get_buffer("M128", delay=3)
        print("Responds: ", ret)

    def get_error_message(self):
        """
        send M14 for debug error
        """
        ret = self.serail.write_and_get_buffer("M14")
        print("Responds: ", ret)

    def get_spec(self):
        """
        get test spec
        :return:
        """
        _ = {
            "step16": ["above", 35],
            "step19": ["above", 35],
            "step18": ["below", 15],
            "step14": ["above", 15000],
        }
        return _

    def analyze_result(self, result, answer, expect, idx: str):
        """
        get final result
        :param result:
        :param answer:
        :param expect:
        :param idx:
        :return:
        """
        _spec = self.get_spec()
        if idx in _spec:
            _spec = _spec[idx]
        else:
            _spec = None

        if result == "FAIL":
            return False

        if expect == "None":
            return True
        else:
            judge_spec = ["M103", "M105", "M106", "M140"]
            if expect in judge_spec:
                if _spec is None:
                    raise ValueError("can't find spec")
                answer_list = answer.split(' ')
                for item in answer_list:
                    if "HST" in item:
                        continue
                    dir_ = _spec[0]
                    spec = float(_spec[1])
                    if dir_ == "above":
                        if float(item.split(':')[-1]) < spec:
                            return False
                    else:
                        if float(item.split(':')[-1]) > spec:
                            return False
                return True
            elif "M901" in expect:
                if answer == expect.split(',')[-1].strip():
                    return True
                else:
                    return False
            else:
                if expect in answer:
                    return True
                else:
                    return False

    def analyze_answer(self):
        """
        get real answer from responds for write in csv
        :return:
        """

        def get_hw_version(answer):
            if ":" in answer:
                answer = answer.split(":")[-1]
                if " " in answer:
                    answer = answer.split(" ")[0]
                    return answer
                else:
                    return answer
            else:
                return answer

        def get_real_responds(answer, start_word=""):
            if start_word in answer:
                start_idx = answer.find(start_word)
                answer = answer[(len(start_word) + start_idx):]
                if "OK" in answer:
                    answer = answer[:-3].strip()
                elif "HSA" in answer:
                    end_idx = answer.find("HSA")
                    answer = answer[:-int(len(answer) - end_idx)].strip()
            return answer

        _ = {
            "step3": {"fun": get_hw_version},
            "step7": {"fun": get_real_responds, "start_word": "M901.D"},
            "step9": {"fun": get_real_responds, "start_word": "M901.D"},
            "step10": {"fun": get_real_responds, "start_word": "M901.D"},
            "step11": {"fun": get_real_responds, "start_word": "M901.D"},
            "step12": {"fun": get_real_responds, "start_word": "M141"},
            "step13": {"fun": get_real_responds, "start_word": "M105.D"},
            "step14": {"fun": get_real_responds, "start_word": "F:1.00"},
            "step16": {"fun": get_real_responds, "start_word": "M141"},
            "step18": {"fun": get_real_responds, "start_word": "M105.D"},
            "step19": {"fun": get_real_responds, "start_word": "M105.D"},
        }
        return _

    def test_result_handel(self, idx, answer, add_result, expect, result):
        """
        record test result
        :param answer:
        :param add_result:
        :param result:
        :return:
        """
        analyze_answer = self.analyze_answer()
        if idx in analyze_answer:
            item = analyze_answer[idx]
            if "start_word" in item:
                answer = item["fun"](answer, start_word=item["start_word"])
            else:
                answer = item["fun"](answer)

        if self.analyze_result(result, answer, expect, idx):
            result = "PASS"
        else:
            result = "FAIL"

        if add_result == "ByPass":  # don't need to add anything to csv
            pass
        elif add_result == "response":  # only add response to csv
            self.test_result.append(answer)
        elif add_result == "response_result":  # add response and result to csv
            self.test_result.append(answer)
            self.test_result.append(result)
        elif add_result == "result":  # only add result to csv
            self.test_result.append(result)
        else:
            pass
        return result

    def delay_s(self, second: int):
        """
        delay
        :param second:
        :return:
        """
        print(f"wait {second} s...")
        for i in range(second):
            print(f"wait: {i + 1}")
            time.sleep(1)
        print("\n")

    def ask(self, content: str):
        """
        ask content
        :param content:
        :return:
        """
        answer = input(f"{content} confirm(y/n)?")
        if "y" or "Y" in answer:
            return True
        else:
            return False

    def request_dut_state(self, dut_state: str):
        """
        ask dut state is ok
        :param dut_state:
        :return:
        """
        if "Lid Closed" in dut_state and "No Labware" in dut_state:
            # close lid
            self.ask("Lid Closed, No Labware （是否盖子关闭，没有实验器具）")
        elif "Lid Open" in dut_state and "Labware on plate" in dut_state:
            # open lid, labware on plate
            self.ask("Lid Open, Labware on plate （是否盖子打开，放置了实验器具）")
        else:
            pass

    def judge_wait_and_send(self, send: str, expect: str):
        """
        judge wait, and delay
        :param send:
        :param expect:
        :return:
        """
        # judge wait
        if "wait" in send:
            s = send.split(',')
            send = s[0].strip()
            wait_time = int(s[1].split(' ')[-1].strip())
            self.serail.write_and_get_buffer(send, only_write=True)
            self.delay_s(wait_time)
            answer = self.serail.read_buffer()
            print("response: ", answer)
        else:
            answer = self.serail.write_and_get_buffer(send)
            print("response: ", answer)
        if "ERR" not in answer:
            result = "PASS"
        else:
            result = "FAIL"
        return answer, result

    def open_lid(self):
        """
        open lid
        """
        self.serail.write_and_get_buffer("M126")

    def flash_sn(self):
        """
        flash serial number
        :return:
        """
        flash_g_code = "M996"
        read_g_code = "M115"
        get_char = input("type serial number（输入条码:）>")
        send = flash_g_code + " " + get_char
        ret = self.serail.write_and_get_buffer(send)
        print("Responds: " + ret)
        ret = self.serail.write_and_get_buffer(read_g_code)
        print("Versions:\n" + ret)
        sn = self.get_sn_by_system_info(ret)
        if str(sn.strip()) != str(get_char.strip()):
            print("FAIL")
        else:
            print("PASS")

    def test_unit(self):
        """
        v-for test unit and write csv
        :return:
        """
        self.repair_to_start()
        specification_dict: dict = self.load_test_specification()
        self.get_barcode_number()
        result = ""
        for k, v in specification_dict.items():
            idx = k
            description = v["description"]
            send = v["send"]
            expect = v["response"]
            request = v["request"]
            add_result = v["add_result"]
            dut_state = v["dut_state"]
            test_tag = DisplaySymbol + k + ": " + description + DisplaySymbol
            print("\n" + DisplaySymbol * len(test_tag))
            print(test_tag)
            print(DisplaySymbol * len(test_tag) + "\n")
            # check dut state
            if IfAskDutState:
                self.request_dut_state(dut_state)
            # ask request
            if request == "None":
                pass
            elif "Before" in request:
                confirm_ret = input(request + " confirm?(y/n)")
                if "y" in confirm_ret and result != "FAIL":
                    result = "PASS"
                else:
                    result = "FAIL"
            else:
                pass
            # send command
            if send != "None" and "&&" not in send:
                answer, result = self.judge_wait_and_send(send, expect)
            elif send != "None" and "&&" in send:
                answer = []
                send = send.split('&&')
                for item in send:
                    if "delay" in item:
                        self.delay_s(int(item.split(' ')[-1]))
                    else:
                        # judge wait
                        ret, result = self.judge_wait_and_send(item, expect)
                        answer.append(ret)
                answer = answer[-1]

            else:
                answer = ""
            # ask request
            if request == "None":
                pass
            elif "After" in request:
                confirm_ret = input(request + " confirm?(y/n)")
                if "y" in confirm_ret and result != "FAIL":
                    result = "PASS"
                else:
                    result = "FAIL"
            else:
                pass
            """
            answer: if answer is "", we don't need to write responds
            add_result: judge how to add result to csv
            result: test result
            """
            if type(answer) is list:
                answer = answer[-1]
            if "get_system" in description:
                # confirm fw version by operator
                fw_version = self.get_fw_by_system_info(answer)
                print("FIRMWARE VERSION \n"
                      f"{fw_version}")
                judge_fw_version = input("Is this firmware version right? (当前的固件版本是否正确)？ (y/n)")
                if judge_fw_version.strip() != 'y':
                    return
                self.test_result.append(self.get_sn_by_system_info(answer))
                self.test_result.append(fw_version)
            else:
                result = self.test_result_handel(idx, answer, add_result, expect, result)
            print("Result: " + result)

        # add end action
        print("wait for ending")
        self.open_lid()
        self.lift_plate()

        self.serail.close()
        self.write_csv()


if __name__ == '__main__':
    while True:
        get_type = input("=====================\n"
                         "TC Diagnostic Test\n\n"
                         "type 1 to start(输入1开始测试)\n"
                         "type 2 to lift plate(输入2取96孔板)\n"
                         "type 3 to flash serial number(输入3开始烧录条码)\n"
                         "type 4 to get error message(输入4查看当前错误信息)\n")
        start_time = time.time()
        tc = TC()
        tc.init_serial()
        if str(get_type) == "1":
            tc.init_report()
            tc.test_unit()
        elif str(get_type) == "2":
            tc.lift_plate()
        elif str(get_type) == "3":
            tc.flash_sn()
        elif str(get_type) == "4":
            tc.get_error_message()
        else:
            pass
        end_time = time.time()
        f = float((end_time - start_time) / 60)
        print("Time: " + '%.2f' % f + "Min(分钟)")  # 程序的运行时间，单位为分
        get_input = input("Test Complete, type 'q' to exit, others to continue...(测试结束, 输入‘q’退出，其它键继续...)")
        if get_input.strip().lower() == 'q':
            break
