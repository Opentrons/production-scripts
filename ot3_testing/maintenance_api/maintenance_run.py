from ot3_testing.http_client import HttpClient
from ot3_testing.leveling_test.type import Mount, Point
from tools.download_data_testing.testing_data_files import key_str


class MaintenanceApi(HttpClient):
    def __init__(self, ip_address: str):
        super().__init__(ip_address)
        self.run_id = None

    def __del__(self):
        pass

    async def delete_run(self):
        """
        release run id
        :return:
        """
        assert self.run_id is not None, "run_id must be set"
        url = f"/maintenance_runs/{self.run_id}"
        _data = {
            "data": {

            }
        }
        status_code, data = self.delete(url, _data)
        print("Released the API")
        if status_code != 200:
            raise Exception("Failed to move to coordinate")


    async def create_run(self):
        status_code, data = self.post('/maintenance_runs')
        if status_code == 201:
            if self.run_id is None:
                self.run_id = data['data']['id']
        else:
            raise Exception("Failed to create run")

    async def move_to(self, coordinate: dict[str, float], mount:Mount, speed=567.8):
        """
        coordinate: ex: {"x": 115, "y": 100, "leftZ": 342}
        """
        assert self.run_id is not None, "run_id must be set"
        url = f"/maintenance_runs/{self.run_id}/commands?waitUntilComplete=true"
        if mount is Mount.LEFT:
            _key = 'leftZ'
        elif mount is Mount.RIGHT:
            _key = 'rightZ'
        else:
            raise Exception("Unknown mount type")
        key_value = coordinate['z']
        del coordinate['z']
        coordinate[_key] = key_value
        _data = {
            "data": {
                "commandType": "robot/moveAxesTo",
                "params": {
                    "axis_map": coordinate,

                    "speed": speed,
                }
            }

        }
        status_code, data = self.post(url, _data)
        if status_code != 201:
            raise Exception("Failed to move to coordinate")

    async def home(self):
        assert self.run_id is not None, "run_id must be set"
        url = f"/maintenance_runs/{self.run_id}/commands?waitUntilComplete=true"
        _data = {
            "data": {
                "commandType": "robot/home",
                "params": {

                }
            }

        }
        status_code, data = self.post(url, _data)
        if status_code != 201:
            raise Exception("Failed to move to coordinate")

    async def home_z(self, mount:Mount, current_position: Point):
        assert self.run_id is not None, "run_id must be set"
        await self.move_to(current_position.replace({'z': 505})._asdict(), mount=mount)



if __name__ == '__main__':
    import time
    async def _run():
        m_api = MaintenanceApi('192.168.6.15')
        await m_api.create_run()
        # await m_api.home()
        await m_api.move_to({"x": 115, "y": 100, "z": 400}, mount=Mount.RIGHT)
        time.sleep(1)
        await m_api.move_to({"x": 115, "y": 100, "z": 370}, mount=Mount.RIGHT)
        time.sleep(1)
        await m_api.move_to({"x": 115, "y": 100, "z": 342}, mount=Mount.RIGHT)
        time.sleep(1)
        await m_api.home_z(mount=Mount.RIGHT, current_position=Point(115, 100, 342))
        await m_api.delete_run()
    import asyncio
    asyncio.run(_run())
