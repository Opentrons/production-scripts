from oem_projects.burning_rock.hardware_control.hardware_control import HttpClient
from oem_projects.burning_rock.ot_type import ModuleName


class ModuleBuilder:
    def __init__(self):
        pass

    async def _get_modules(self):
        """
        get attached modules, response module id
        :return:
        """
        ret = HttpClient.get("/modules")
        HttpClient.judge_state_code(ret)
        return ret[1]

    async def get_modules(self):
        """
        get modules
        :return:
        """
        responds = await self._get_modules()
        return responds["data"]

    async def get_module_id_by_name(self, name: ModuleName):
        """
        get available module id
        :param name:
        :return:
        """
        id_list = []
        name = name.value
        ret = await self.get_modules()
        for item in ret:
            try:
                if item["moduleModel"] == name:
                    id_list.append(item['id'])
            except Exception as e:
                print(f"can't find module {name}")
                print(e)
        if len(id_list) == 0:
            raise ValueError(f"can't find module {name}")
        return id_list

    async def get_status_by_id(self, module_id):
        """
        get module's status
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

    async def _get_command_by_id(self, engage_id):
        """
        get command
        :param engage_id:
        :return:
        """
        ret = HttpClient.get(f"/commands/{engage_id}")
        HttpClient.judge_state_code(ret)
