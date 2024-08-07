from modules.module import ModuleBuilder
from http_client import HttpClient
import time


class HeaterShakerModule(ModuleBuilder):
    def __init__(self):
        super(HeaterShakerModule, self).__init__()

    async def _post_open_labware_latch(self, module_id):
        """
        post open labware latch
        :param module_id:
        :return:
        """
        _url = "/commands"
        _data = {
            "data": {
                "commandType": "heaterShaker/openLabwareLatch",
                "params": {
                    "moduleId": module_id
                }
            }
        }
        _params = {"waitUntilComplete": True}
        ret = HttpClient.post(_url, data=_data, params=_params)
        HttpClient.judge_state_code(ret)
        return ret[1]

    async def _post_close_labware_latch(self, module_id):
        """
        post close labware latch
        :param module_id:
        :return:
        """
        _url = "/commands"
        _data = {
            "data": {
                "commandType": "heaterShaker/closeLabwareLatch",
                "params": {
                    "moduleId": module_id
                }
            }
        }
        _params = {"waitUntilComplete": True}
        ret = HttpClient.post(_url, data=_data, params=_params)
        HttpClient.judge_state_code(ret)
        return ret[1]

    async def _post_set_target_temperature(self, module_id, celsius):
        """
        set temperature
        :param module_id:
        :param celsius:
        :return:
        """
        _url = "/commands"
        _data = {
            "data": {
                "commandType": "heaterShaker/setTargetTemperature",
                "params": {
                    "moduleId": module_id,
                    "celsius": celsius
                }
            }
        }
        _params = {"waitUntilComplete": True}
        ret = HttpClient.post(_url, data=_data, params=_params)
        HttpClient.judge_state_code(ret)
        return ret[1]

    async def _post_wait_for_temperature(self, module_id, celsius):
        """
        wait for temperature
        :param module_id:
        :param celsius:
        :return:
        """
        _url = "/commands"
        _data = {
            "data": {
                "commandType": "heaterShaker/waitForTemperature",
                "params": {
                    "moduleId": module_id,
                    "celsius": celsius
                }
            }
        }
        _params = {"waitUntilComplete": True}
        ret = HttpClient.post(_url, data=_data, params=_params)
        HttpClient.judge_state_code(ret)
        return ret[1]

    async def _post_deactivate_shaker(self, module_id):
        """
        deactivate shaker
        :param module_id:
        :param celsius:
        :return:
        """
        _url = "/commands"
        _data = {
            "data": {
                "commandType": "heaterShaker/deactivateShaker",
                "params": {
                    "moduleId": module_id
                }
            }
        }
        _params = {"waitUntilComplete": True}
        ret = HttpClient.post(_url, data=_data, params=_params)
        HttpClient.judge_state_code(ret)
        return ret[1]

    async def _post_deactivate_heater(self, module_id):
        """
        deactivate shaker
        :param module_id:
        :param celsius:
        :return:
        """
        _url = "/commands"
        _data = {
            "data": {
                "commandType": "heaterShaker/deactivateHeater",
                "params": {
                    "moduleId": module_id
                }
            }
        }
        _params = {"waitUntilComplete": True}
        ret = HttpClient.post(_url, data=_data, params=_params)
        HttpClient.judge_state_code(ret)
        return ret[1]

    async def _post_set_wait_shaker_speed(self, module_id, rpm: int):
        """
        deactivate shaker
        :param module_id:
        :param celsius:
        :return:
        """
        _url = "/commands"
        _data = {
            "data": {
                "commandType": "heaterShaker/setAndWaitForShakeSpeed",
                "params": {
                    "moduleId": module_id,
                    "rpm": rpm
                }
            }
        }
        _params = {"waitUntilComplete": True}
        ret = HttpClient.post(_url, data=_data, params=_params)
        HttpClient.judge_state_code(ret)
        return ret[1]

    async def open_labware_latch(self, module_id):
        """
        post open labware latch
        :param module_id:
        :return:
        """
        await self._post_open_labware_latch(module_id)

    async def close_labware_latch(self, module_id):
        """
        post close labware latch
        :param module_id:
        :return:
        """
        await self._post_close_labware_latch(module_id)

    async def set_target_temperature(self, module_id, celsius):
        """
        set temperature
        :param module_id:
        :param celsius:
        :return:
        """
        await self._post_set_target_temperature(module_id, celsius)

    async def wait_for_temperature(self, module_id, time_out=300):
        """
        wait for temperature
        :param module_id:
        :param time_out:
        :return:
        """
        wait_times = 0
        print("waiting for temperature...")
        while True:
            _data = await self.get_status_by_id(module_id)
            status = _data["temperatureStatus"]
            if "holding" not in status:
                pass
            else:
                print("end..")
                break
            time.sleep(1)
            wait_times += 1
            if wait_times > time_out:
                raise RuntimeError("wait timeout...")

    async def get_target_temperature(self, module_id):
        """
        get target temperature
        :param module_id:
        :return:
        """
        _data = await self.get_status_by_id(module_id)
        temp = _data["currentTemperature"]
        return temp

    async def get_target_speed(self, module_id):
        """
        get target speed
        :param module_id:
        :return:
        """
        _data = await self.get_status_by_id(module_id)
        speed = _data["currentSpeed"]
        return speed

    async def get_latch_status(self, module_id):
        """
        get latch status
        :param module_id:
        :return:
        """
        _data = await self.get_status_by_id(module_id)
        latch = _data["labwareLatchStatus"]
        return latch

    async def deactivate_shaker(self, module_id):
        """
        deactivate shaker
        :param module_id:
        :param celsius:
        :return:
        """
        await self._post_deactivate_shaker(module_id)

    async def deactivate_heater(self, module_id):
        """
        deactivate heater
        :param module_id:
        :param celsius:
        :return:
        """
        await self._post_deactivate_heater(module_id)

    async def set_wait_shaker_speed(self, module_id, rpm: int):
        """
        deactivate shaker
        :param module_id:
        :param celsius:
        :return:
        """
        await self._post_set_wait_shaker_speed(module_id, rpm)
