import time

from modules.module import ModuleBuilder
from http_client import HttpClient


class TemperatureModule(ModuleBuilder):
    def __init__(self):
        super(TemperatureModule, self).__init__()

    async def _post_set_temperature(self, module_id, celsius):
        """
        engage
        :param module_id:
        :param celsius:
        :return:
        """
        _url = "/commands"
        _params = {"waitUntilComplete": True}
        _data = {"data": {
            "commandType": "temperatureModule/setTargetTemperature",
            "params": {
                "moduleId": module_id,
                "celsius": celsius
            }
        }}
        ret = HttpClient.post(_url, data=_data, params=_params)
        HttpClient.judge_state_code(ret)
        return ret[1]

    async def _post_deactivate_temperature(self, module_id):
        """
        deactivate
        :param module_id:
        :return:
        """
        _url = "/commands"
        _params = {"waitUntilComplete": True}
        _data = {"data": {
            "commandType": "temperatureModule/deactivate",
            "params": {
                "moduleId": module_id
            }
        }}
        ret = HttpClient.post(_url, data=_data, params=_params)
        HttpClient.judge_state_code(ret)

    async def _require_temperature_status_by_id(self, module_id):
        """
        wait for temperature
        :param module_id:
        :return:
        """
        response = await self.get_modules()
        try:
            for item in response:
                if item["id"] == module_id:
                    return item["data"]
        except Exception as e:
            print(f"can't find {module_id}")
            raise ValueError(e)

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
            _data = await self._require_temperature_status_by_id(module_id)
            status = _data["status"]
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
        get temperature
        :return:
        """
        _data = await self._require_temperature_status_by_id(module_id)
        temp = _data["currentTemperature"]
        return temp

    async def set_temperature(self, module_id, value: float):
        """
        set module temperature
        :param module_id:
        :param value:
        :return:
        """
        await self._post_set_temperature(module_id, value)

    async def deactivate(self, module_id):
        """
        disable module
        :param module_id:
        :return:
        """
        await self._post_deactivate_temperature(module_id)
