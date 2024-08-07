from drivers.ssh import SSHClient
from typing import Union
from ot3_testing.test_config.lifetime_test_config import Z_STAGE_LIFETIME_TEST
from utils import Utils


class LifeTime:

    def __init__(self):
        self.ssh_client: Union[SSHClient, None] = None

    def init_ssh_connect(self, robot_ip: str, with_key=True):
        """
        initial connection
        :param robot_ip:
        :param with_key:
        :return:
        """
        self.ssh_client = SSHClient(robot_ip)
        self.ssh_client.connect(with_key=with_key)

    def start_96ch_pick_up_lifetime_test(self, pick_up_number: int):
        """
        96ch pick up lifetime test
        :param pick_up_number:
        :return:
        """
        pass

    def start_1_8ch_pick_up_lifetime_test(self, pick_up_number: int):
        """
        1/8 ch pick up lifetime test
        :param pick_up_number:
        :return:
        """
        pass

    def start_z_stage_lifetime_test(self, current: float, speed: float, cycles: int, slack_token,
                                    robot_name="", update="update"):
        """
        z stage force lifetime test
        :param current:
        :param speed:
        :param cycles:
        :param robot_name:
        :param slack_token:
        :param update:
        :return:
        """
        print(f"start {robot_name} for z_stage lifetime test, cycles: {cycles} ...")
        cmd = f"cd /opt/opentrons-robot-server/ && nohup python3 -m hardware_testing.scripts.force_pick_up_test " \
              f"--cycles {cycles} --speed {speed} --current {current} --target {robot_name}" \
              f" --slack_token {slack_token} --update {update}  &"
        ret = self.ssh_client.exec_command(cmd)
        return ret

    def disconnect(self):
        self.ssh_client.close()

    def _test_z_stage_lifetime_robots(self, ip_list: list, robot_names: list, current_speeds_cycles: list,
                                      with_key: list, slack_token: str):
        """
        test a serial robots
        :param ip_list:
        :param robot_names:
        :param current_speeds_cycles:
        :param slack_token:
        :return:
        """
        for _ip, _robot_name, _current_speed_cycle, _with_key, in zip(ip_list, robot_names,
                                                                      current_speeds_cycles, with_key):
            ret = Utils.test_online(_ip)
            if not ret:
                continue
            try:
                self.init_ssh_connect(_ip, _with_key)
                self.start_z_stage_lifetime_test(_current_speed_cycle["current"], _current_speed_cycle["speed"],
                                                 _current_speed_cycle["cycle"], slack_token, robot_name=_robot_name)
                self.disconnect()
            except Exception as e:
                print(f"{_robot_name} test failed:\n {e}\n")

    def test_z_stage_lifetime_robots(self, z_stage_life_test_config: list, slack_token: str):
        """
        test a serial robots
        :param z_stage_life_test_config:
        :param slack_token:
        :return:
        """
        ip_list = [item["ip"] for item in z_stage_life_test_config]
        robot_names = [item["robot_name"] for item in z_stage_life_test_config]
        current_speed_cycles = [item["current_speed_cycle"] for item in z_stage_life_test_config]
        with_key = [item["with_key"] for item in z_stage_life_test_config]
        self._test_z_stage_lifetime_robots(ip_list, robot_names, current_speed_cycles, with_key, slack_token)

    def test_z_stage_device_online(self, z_stage_life_test_config):
        """
        test online
        :param z_stage_life_test_config:
        :return:
        """
        ip_list = [item["ip"] for item in z_stage_life_test_config]
        Utils.test_devices_online(ip_list)


if __name__ == '__main__':
    slack_token = input("slack_token ?")
    lifetime_test = LifeTime()
    lifetime_test.test_z_stage_device_online(Z_STAGE_LIFETIME_TEST)
    lifetime_test.test_z_stage_lifetime_robots(Z_STAGE_LIFETIME_TEST, slack_token)  # start z stage?
