from modules.module import ModuleBuilder
from http_client import HttpClient


class MagneticModule(ModuleBuilder):
    def __init__(self):
        super(MagneticModule, self).__init__()

    async def engage_magnetic(self, module_id, height: float):
        """
        engage
        :param module_id:
        :param height:
        :return:
        """
        responds = await self._post_engage_magnetic(module_id, height)
        return responds["data"]["params"]["height"]

    async def disengage(self, module_id):
        """
        disengage
        :param module_id:
        :return:
        """
        await self._post_disengage_magnetic(module_id)

    async def _post_engage_magnetic(self, module_id, height):
        """
        engage
        :param module_id:
        :param height:
        :return:
        """
        if height > 20:
            raise ValueError("height supposed to lower 20")
        _url = "/commands"
        _data = {
            "data": {
                "commandType": "magneticModule/engage",
                "params": {
                    "moduleId": module_id,
                    "height": height
                }
            }
        }
        _params = {"waitUntilComplete": True}
        ret = HttpClient.post(_url, data=_data, params=_params)
        HttpClient.judge_state_code(ret)
        return ret[1]

    async def _post_disengage_magnetic(self, module_id):
        """
        engage
        :param module_id:
        :return:
        """
        _url = "/commands"
        _params = {"waitUntilComplete": True}
        _data = {"data":
            {
                "commandType": "magneticModule/disengage",
                "params": {
                    "moduleId": module_id
                }
            }
        }
        ret = HttpClient.post(_url, data=_data, params=_params)
        HttpClient.judge_state_code(ret)
        return ret[1]
