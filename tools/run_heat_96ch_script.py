from ot3_testing.devices.ssh import SSHClient
import time
from ot3_testing.devices.play_sound import play_alarm_2


def heat_96ch(client: SSHClient, device_name):
    """
    client, 机器条码
    """
    started_time_h = input("请输入多少小时后开始加热(/h): ")
    started_time_s = float(started_time_h.strip()) * 3600
    init_time = time.time()  # 记录开始时间

    while True:
        end_time = time.time()  # 判断时间
        judge_time = end_time - init_time
        if judge_time > float(started_time_s):
            # 开始加热
            print("开始加热...")
            client.connect(with_key=True)
            channel = client.channel
            channel.send(f"ot3repl \n")
            time.sleep(3)
            line = ""
            while True:
                result = channel.recv(1).decode()  # 循环检查每一个返回值
                line = line + result
                # print(line)
                if str(line).find("Call methods on api like api.move_to(Mount.RIGHT, Point(400, 400, 500))") != -1:
                    break
            print(line)

            channel.send(
                f"m = OT3Mount.LEFT; api.reset(); api.cache_instruments(); api.home(); api.add_tip(m, 1); api.prepare_for_aspirate(m); api.set_pipette_speed(m, 0.5, 0.5, 0.5);[api.aspirate(m) is api.dispense(m, push_out=0) for _ in range(200)] \n")
            time.sleep(5)
            result = channel.recv(1024000).decode()
            print(result)
            break
        print(f"running...{judge_time / 3600} h")
        time.sleep(1)

    # 计算加热时间
    heat_start = time.time()
    while True:
        heat_time = time.time()
        during_time = heat_time - heat_start
        if during_time < (3 * 3600):
            pass
        else:
            play_alarm_2()
            print(
                f"{device_name} -> 加热时间已完成，关闭程序则结束加热，如果要继续加热，不关闭程序即可，加热时间请自己计算")


if __name__ == '__main__':
    pass
