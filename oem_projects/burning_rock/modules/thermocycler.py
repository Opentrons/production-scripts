from oem_projects.burning_rock.modules.module import ModuleBuilder
from oem_projects.burning_rock.http_client import HttpClient
import time


class ThermocyclerModule(ModuleBuilder):
    def __init__(self, with_run_id=None):
        super(ThermocyclerModule, self).__init__()
        if with_run_id is None:
            self._url = "/commands"
        else:
            self._url = f"/runs/{with_run_id}/commands"

    async def _post_open_lid(self, module_id):
        """
        open lid
        :param module_id:
        :return:
        """
        _url = self._url
        _data = {
            "data": {
                "commandType": "thermocycler/openLid",
                "params": {
                    "moduleId": module_id
                }
            }
        }
        _params = {"waitUntilComplete": True}
        ret = HttpClient.post(_url, data=_data, params=_params)
        HttpClient.judge_state_code(ret)
        return ret[1]

    async def _post_close_lid(self, module_id):
        """
        close lid
        :param module_id:
        :return:
        """
        _url = self._url
        _data = {
            "data": {
                "commandType": "thermocycler/closeLid",
                "params": {
                    "moduleId": module_id
                }
            }
        }
        _params = {"waitUntilComplete": True}
        ret = HttpClient.post(_url, data=_data, params=_params)
        HttpClient.judge_state_code(ret)
        return ret[1]

    async def _post_set_lid_temperature(self, module_id, celsius):
        """
        set lid tem
        :param module_id:
        :return:
        """
        _url = self._url
        _data = {
            "data": {
                "commandType": "thermocycler/setTargetLidTemperature",
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

    async def _post_deactivate_lid(self, module_id):
        """
        deactivate lid
        :param module_id:
        :return:
        """
        _url = self._url
        _data = {
            "data": {
                "commandType": "thermocycler/deactivateLid",
                "params": {
                    "moduleId": module_id
                }
            }
        }
        _params = {"waitUntilComplete": True}
        ret = HttpClient.post(_url, data=_data, params=_params)
        HttpClient.judge_state_code(ret)
        return ret[1]

    async def _post_deactivate_block(self, module_id):
        """
        deactivate block
        :param module_id:
        :return:
        """
        _url = self._url
        _data = {
            "data": {
                "commandType": "thermocycler/deactivateBlock",
                "params": {
                    "moduleId": module_id
                }
            }
        }
        _params = {"waitUntilComplete": True}
        ret = HttpClient.post(_url, data=_data, params=_params)
        HttpClient.judge_state_code(ret)
        return ret[1]

    async def _post_deactivate_all(self, module_id):
        """
        deactivate block
        :param module_id:
        :return:
        """
        _url = self._url
        _data = {
            "data": {
                "commandType": "thermocycler/awaitProfileComplete",
                "params": {
                    "moduleId": module_id
                }
            }
        }
        _params = {"waitUntilComplete": True}
        ret = HttpClient.post(_url, data=_data, params=_params)
        HttpClient.judge_state_code(ret)
        return ret[1]

    async def _post_set_block_temperature(self, module_id, celsius):
        """
        set block tem
        :param module_id:
        :return:
        """
        _url = self._url
        _data = {
            "data": {
                "commandType": "thermocycler/setTargetBlockTemperature",
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

    async def _post_run_profile(self, module_id, profile: list = None):
        """
        run profile
        :param module_id:
        :param profile:
        :return:
        """
        if profile is None:
            profile = [
                {"holdSeconds": 10, "celsius": 30},
                {"holdSeconds": 10, "celsius": 30},
                {"holdSeconds": 10, "celsius": 30},
                {"holdSeconds": 10, "celsius": 30}
            ]

        _url = self._url
        _data = {
            "data": {
                "commandType": "thermocycler/runProfile",
                "params": {
                    "moduleId": module_id,
                    "profile": profile
                }
            }
        }
        _params = {"waitUntilComplete": True}
        ret = HttpClient.post(_url, data=_data, params=_params)
        HttpClient.judge_state_code(ret)
        return ret[1]

    async def run_profile(self, module_id, profile=None):
        """
        run profile
        :param module_id:
        :param profile:
        :return:
        """
        print("run profile")
        await self._post_run_profile(module_id, profile)

    async def open_lid(self, module_id):
        """
        open lid
        :param module_id:
        :return:
        """
        print("open lid")
        await self._post_open_lid(module_id)

    async def close_lid(self, module_id):
        """
        close lid
        :param module_id:
        :return:
        """
        print("close lid")
        await self._post_close_lid(module_id)

    async def set_lid_temperature(self, module_id, celsius):
        """
        set lid tem
        :param module_id:
        :param celsius: 37~101
        :return:
        """
        await self._post_set_lid_temperature(module_id, celsius)

    async def wait_for_lid_temperature(self, module_id, time_out=300):
        """
        wait lid tem
        :param module_id:
        :param time_out:
        :return:
        """
        wait_times = 0
        print("waiting for temperature...")
        while True:
            _data = await self.get_status_by_id(module_id)
            status = _data["lidTemperatureStatus"]
            if "holding" not in status:
                pass
            else:
                print("end..")
                break
            time.sleep(1)
            wait_times += 1
            if wait_times > time_out:
                raise RuntimeError("wait timeout...")

    async def deactivate_lid(self, module_id):
        """
        deactivate lid
        :param module_id:
        :return:
        """
        await self._post_deactivate_lid(module_id)

    async def deactivate_block(self, module_id):
        """
        deactivate block
        :param module_id:
        :return:
        """
        print("deactivate block")
        await self._post_deactivate_block(module_id)

    async def deactivate_all(self, module_id):
        print("deactivate all")
        await self._post_deactivate_all(module_id)

    async def wait_for_block_temperature(self, module_id, time_out=300):
        """
        wait block tem
        :param module_id:
        :param time_out:
        :return:
        """
        wait_times = 0
        print("waiting for temperature...")
        while True:
            _data = await self.get_status_by_id(module_id)
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

    async def get_block_temperature(self, module_id):
        """
        get block temperature
        :param module_id:
        :return:
        """
        _data = await self.get_status_by_id(module_id)
        return _data["currentTemperature"]

    async def get_lid_temperature(self, module_id):
        """
        get lid temperature
        :param module_id:
        :return:
        """
        _data = await self.get_status_by_id(module_id)
        return _data["lidTemperature"]

    async def get_lid_status(self, module_id):
        """
        get module status
        :param module_id:
        :return:
        """
        _data = await self.get_status_by_id(module_id)
        return _data["lidStatus"]

    async def set_block_temperature(self, module_id, celsius):
        """
        set block tem
        :param module_id:
        :return:
        """
        await self._post_set_block_temperature(module_id, celsius)
