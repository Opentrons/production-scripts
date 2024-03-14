import asyncio
import time

from ot3_testing.hardware_control.hardware_control import HardwareControl
from ot3_testing.http_client import HttpClient
from ot3_testing.ot_type import LabWare, Instrument, ModuleName, Mount, Target, Axis, Point, LabwareResult, PipetteResult
from typing import Union, List


class ProtocolContext:

    def __init__(self, ip):
        self.http_client = HttpClient(ip)
        self.run_id = None

    async def _post_create_a_run(self) -> dict:
        """
        create a run and return a run_id
        :return:
        """
        ret = self.http_client.post("/runs")
        self.http_client.judge_state_code(ret)
        return ret[1]

    async def _del_clear_a_run(self, run_id):
        """
        clear a run by id
        :param run_id:
        :return:
        """
        _url = f"/runs/{run_id}"
        data = {}
        ret = self.http_client.delete(_url, data)
        self.http_client.judge_state_code(ret)

    async def _get_require_all_run(self):
        """
        get all created run
        :return:
        """
        ret = self.http_client.get("/runs")
        self.http_client.judge_state_code(ret)
        return ret[1]

    async def _post_apply_labware_offset(self, uri: str, location: dict, vector=None):
        """
        apply offset
        :return:
        """
        if self.run_id is None:
            raise ValueError("run id can't be None")
        _url = f"/runs/{self.run_id}/labware_offsets"
        if vector is None:
            vector = {'x': 0, 'y': 0, 'z': 0}
        _data = {
            "data": {
                "definitionUri": uri,
                "location": location,
                "vector": vector
            }
        }
        _params = {"waitUntilComplete": True}
        ret = self.http_client.post(_url, data=_data, params=_params)
        self.http_client.judge_state_code(ret)

    async def _get_run(self):
        """
        get run message
        :return:
        """
        if self.run_id is None:
            raise ValueError("run id can't be None")
        ret = self.http_client.get(f'/runs/{self.run_id}')
        self.http_client.judge_state_code(ret)
        return ret[1]

    async def _post_load_labware(self, labware_name: LabWare, slot_name="9", name_space="opentrons", module_id=None):
        """
        load labware
        :return:
        """
        _url = f"/runs/{self.run_id}/commands"
        labware_name = labware_name.value
        if module_id is None:
            location = {"slotName": slot_name}
        else:
            location = {"moduleId": module_id}
        _data = {
            "data": {
                "commandType": "loadLabware",
                "params": {
                    "location": location,
                    "loadName": labware_name,
                    "namespace": name_space,
                    "version": 1,
                },
                "intent": "setup",
            }
        }
        _params = {"waitUntilComplete": True}
        ret = self.http_client.post(_url, params=_params, data=_data)
        self.http_client.judge_state_code(ret)
        return ret[1]

    async def _post_load_liquid(self, labwareId, liquidId="waterId", volumeByWell=None):
        """
        load labware
        :return:
        """
        _url = f"/runs/{self.run_id}/commands"
        if volumeByWell is None:
            volumeByWell = {"A1": 200, "B1": 200}
        _data = {
            "data": {
                "commandType": "loadLiquid",
                "params": {
                    "liquidId": liquidId,
                    "labwareId": labwareId,
                    "volumeByWell": volumeByWell
                }
            }
        }
        ret = self.http_client.post(_url, data=_data)
        self.http_client.judge_state_code(ret)
        return ret[1]

    async def _post_load_pipette(self, pipette_name: Instrument, mount: Mount):
        """
        post load pipette
        :param run_id:
        :param pipette_name:
        :param mount:
        :return:
        """
        _url = f"/runs/{self.run_id}/commands"
        pipette_name = pipette_name.value
        mount = mount.value
        _data = {
            "data": {
                "commandType": "loadPipette",
                "params": {"pipetteName": pipette_name, "mount": mount},
                "intent": "setup",
            }
        }
        _params = {"waitUntilComplete": True}
        ret = self.http_client.post(_url, params=_params, data=_data)
        self.http_client.judge_state_code(ret)
        return ret[1]

    async def _post_pick_up(self, pipette_id, labware_id, well="A1", offset: dict = None):
        """
        post pick up
        :param pipette_id:
        :param labware_id:
        :param well:
        :param offset:
        :return:
        """
        if self.run_id is None:
            raise ValueError("run id can't be None")
        _url = f"/runs/{self.run_id}/commands"
        if offset is None:
            offset = {"x": 0, "y": 0, "z": 0}
        _data = {
            "data": {
                "commandType": "pickUpTip",
                "params": {
                    "pipetteId": pipette_id,
                    "labwareId": labware_id,
                    "wellName": well,
                    "wellLocation": {"origin": "top", "offset": offset},
                },
            }
        }
        _params = {"waitUntilComplete": True}
        ret = self.http_client.post(_url, params=_params, data=_data)
        self.http_client.judge_state_code(ret)
        return ret[1]

    async def _post_drop(self, pipette_id, labware_id="fixedTrash", well="A1", offset: dict = None):
        """
        post drop
        :param pipette_id:
        :param labware_id:
        :param well:
        :param offset:
        :return:
        """
        if self.run_id is None:
            raise ValueError("run id can't be None")
        if offset is None:
            offset = {"x": 0, "y": 0, "z": 0}
        _url = f"/runs/{self.run_id}/commands"
        _data = {
            "data": {
                "commandType": "dropTip",
                "params": {
                    "labwareId": labware_id,
                    "wellName": well,
                    "wellLocation": {"origin": "top", "offset": offset},
                    "pipetteId": pipette_id,
                },
            }
        }
        _params = {"waitUntilComplete": True}
        ret = self.http_client.post(_url, params=_params, data=_data)
        self.http_client.judge_state_code(ret)

    async def _post_run_protocol(self):
        """
        run protocol
        :return:
        """
        if self.run_id is None:
            raise ValueError("run id can't be None")
        _url = f"/runs/{self.run_id}/actions"
        _data = {"data": {"actionType": "play"}}
        ret = self.http_client.post(_url, data=_data)
        self.http_client.judge_state_code(ret)

    async def _post_pause_protocol(self):
        """
        pause protocol
        :return:
        """
        if self.run_id is None:
            raise ValueError("run id can't be None")
        _url = f"/runs/{self.run_id}/actions"
        _data = {"data": {"actionType": "pause"}}
        ret = self.http_client.post(_url, data=_data)
        self.http_client.judge_state_code(ret)

    def _judge_error(self, responds):
        """
        judge error type
        :return:
        """
        try:
            err = responds["data"]["error"]["errorType"]
        except:
            err = False
        return err

    async def _post_stop_protocol(self):
        """
        stop protocol
        :return:
        """
        if self.run_id is None:
            raise ValueError("run id can't be None")
        _url = f"/runs/{self.run_id}/actions"
        _data = {"data": {"actionType": "stop"}}
        ret = self.http_client.post(_url, data=_data)
        self.http_client.judge_state_code(ret)

    async def _post_save_position(self, pipetteId):
        """
        post saved position
        :param pipetteId:
        :return:
        """
        if self.run_id is None:
            raise ValueError("run id can't be None")
        _url = f"/runs/{self.run_id}/commands"
        _data = {
            "data": {
                "commandType": "savePosition",
                "params": {
                    "pipetteId": pipetteId
                }
            }
        }
        _params = {"waitUntilComplete": True}
        ret = self.http_client.post(_url, params=_params, data=_data)
        self.http_client.judge_state_code(ret)
        return ret[1]

    async def _post_home(self, axis: Union[None, List[Axis]]):
        """
        post home
        :param axis:
        :return:
        """
        if self.run_id is None:
            raise ValueError("run id can't be None")
        _url = f"/commands"
        if axis is not None:
            _data = {
                "data": {
                    "commandType": "home",
                    "params": {
                        "axes": axis
                    }
                }
            }
        else:
            _data = {
                "data": {
                    "commandType": "home",
                    "params": {}
                }
            }
        ret = self.http_client.post(_url, data=_data)
        self.http_client.judge_state_code(ret)

    async def _get_command(self, run_id, length):
        """
        get commands
        :param: run_id
        :param: len
        :return:
        """
        _url = f"/{run_id}/commands"
        _param = {"cursor": 0, "pageLength": length}
        ret = self.http_client.get(_url, params=_param)
        self.http_client.judge_state_code(ret)
        return ret[1]

    async def _post_load_module(self, module_name: ModuleName, slot="10"):
        """
        load module
        :param module_name:
        :param slot:
        :return:
        """
        if self.run_id is None:
            raise ValueError("run id can't be None")
        _url = f"/runs/{self.run_id}/commands"
        _data = {
            "data": {
                "commandType": "loadModule",
                "params": {
                    "model": module_name.value,
                    "location": {"slotName": slot}
                }
            }
        }
        _params = {"waitUntilComplete": True}
        ret = self.http_client.post(_url, data=_data, params=_params)
        self.http_client.judge_state_code(ret)
        responds = ret[1]
        error = self._judge_error(responds)
        if error is not False:
            raise ConnectionError(error)
        return responds

    async def _post_aspirate(self, pipetteId, labwareId, volume: float, flow_rate: float = 3, well="A1", offset=None,
                             origin="bottom"):
        """
        aspire
        :param pipetteId:
        :param labwareId:
        :param volume:
        :param flow_rate:
        :param well:
        :param offset:
        :param origin: locate to aspirate
        :return:
        """
        if self.run_id is None:
            raise ValueError("run id can't be None")
        _url = f"/runs/{self.run_id}/commands"
        if offset is None:
            offset = {"x": 0, "y": 0, "z": 0}
        _data = {
            "data": {
                "commandType": "aspirate",
                "params": {
                    "pipetteId": pipetteId,
                    "labwareId": labwareId,
                    "wellName": well,
                    "wellLocation": {
                        "origin": origin,
                        "offset": offset
                    },
                    "volume": volume,
                    "flowRate": flow_rate
                },
            }
        }
        _params = {"waitUntilComplete": True}
        ret = self.http_client.post(_url, params=_params, data=_data)
        self.http_client.judge_state_code(ret)
        return ret[1]

    async def _load_labware_by_definition(self, _data):
        """
        load labware
        :param _data:
        :return:
        """
        if self.run_id is None:
            raise ValueError("run id can't be None")
        _url = f"/runs/{self.run_id}/labware_definitions"
        _data = {
            "data": _data
        }
        ret = self.http_client.post(_url, data=_data)
        self.http_client.judge_state_code(ret)
        return ret[1]

    async def _post_wait_for_duration(self, seconds):
        """
        wait for complete an action
        :param seconds: delay time_s
        :return:
        """
        if self.run_id is None:
            raise ValueError("run id can't be None")
        _url = f"/runs/{self.run_id}/commands"
        _data = {
            "data": {
                "commandType": "waitForDuration",
                "params": {
                    "seconds": seconds
                },
                "intent": "protocol",
            }
        }
        ret = self.http_client.post(_url, data=_data)
        self.http_client.judge_state_code(ret)

    async def _post_dispense(self, pipetteId, labwareId, volume: float, flow_rate: float = 3, well="A1", offset=None,
                             origin="bottom"):
        """
        dispense
        :param pipetteId:
        :param labwareId:
        :param volume:
        :param flow_rate:
        :param well:
        :param offset:
        :param origin:
        :return:
        """
        if self.run_id is None:
            raise ValueError("run id can't be None")
        if offset is None:
            offset = {"x": 0, "y": 0, "z": 0}
        _url = f"/runs/{self.run_id}/commands"
        _data = {
            "data": {
                "commandType": "dispense",
                "params": {
                    "pipetteId": pipetteId,
                    "labwareId": labwareId,
                    "wellName": well,
                    "wellLocation": {
                        "origin": origin,
                        "offset": offset
                    },
                    "volume": volume,
                    "flowRate": flow_rate
                },
            }
        }
        _params = {"waitUntilComplete": True}
        ret = self.http_client.post(_url, params=_params, data=_data)
        self.http_client.judge_state_code(ret)

    async def _post_touch_tip(self, pipetteId, labwareId, radius=0.5, speed: float = 42.0, well="A1", offset=None):
        """
        touch tip
        :param pipetteId:
        :param labwareId:
        :param volume:
        :param flow_rate:
        :param well:
        :param offset:
        :return:
        """
        if self.run_id is None:
            raise ValueError("run id can't be None")
        if offset is None:
            offset = {"x": 0, "y": 0, "z": 0}
        _url = f"/runs/{self.run_id}/commands"
        _data = {
            "data": {
                "commandType": "touchTip",
                "params": {
                    "pipetteId": pipetteId,
                    "labwareId": labwareId,
                    "wellName": well,
                    "wellLocation": {
                        "origin": "bottom",
                        "offset": offset
                    },
                    "radius": radius,
                    "speed": speed
                },
                "intent": "protocol",
            }
        }
        ret = self.http_client.post(_url, data=_data)
        self.http_client.judge_state_code(ret)

    async def _post_blow_out(self, pipetteId, labwareId, flow_rate=2, well="A1", offset=None):
        """
        blow out
        :param pipetteId:
        :param labwareId:
        :param flow_rate:
        :param well:
        :param offset:
        :return:
        """
        if self.run_id is None:
            raise ValueError("run id can't be None")
        if offset is None:
            offset = {"x": 0, "y": 0, "z": 0}
        _url = f"/runs/{self.run_id}/commands"
        _data = {
            "data": {
                "commandType": "blowout",
                "params": {
                    "pipetteId": pipetteId,
                    "labwareId": labwareId,
                    "wellName": well,
                    "wellLocation": {
                        "origin": "bottom",
                        "offset": offset
                    },
                    "flowRate": flow_rate,
                },
            }
        }
        _params = {"waitUntilComplete": True}
        ret = self.http_client.post(_url, params=_params, data=_data)
        self.http_client.judge_state_code(ret)

    async def _post_move_to_well(self, pipetteId, labwareId, speed=12.3, forceDirect: bool = False, well="A1",
                                 offset=None):
        """
        move to well
        :param pipetteId:
        :param labwareId:
        :param forceDirect:
        :param well:
        :param offset:
        :return:
        """
        if self.run_id is None:
            raise ValueError("run id can't be None")
        _url = f"/runs/{self.run_id}/commands"
        if offset is None:
            offset = {"x": 0, "y": 0, "z": 0}
        _data = {
            "data": {
                "commandType": "moveToWell",
                "params": {
                    "pipetteId": pipetteId,
                    "labwareId": labwareId,
                    "wellName": well,
                    "wellLocation": {
                        "origin": "top",
                        "offset": offset
                    },
                    "forceDirect": forceDirect,
                    "speed": speed
                }
            }
        }
        _params = {"waitUntilComplete": True}
        ret = self.http_client.post(_url, data=_data, params=_params)
        self.http_client.judge_state_code(ret)

    async def _post_move_to_slot(self, pipetteId, slotName, offset=None):
        """
        move to slot
        :param pipetteId:
        :param slotName:
        :param offset:
        :return:
        """
        if self.run_id is None:
            raise ValueError("run id can't be None")
        _url = f"/runs/{self.run_id}/commands"
        if offset is None:
            offset = {"x": 0, "y": 0, "z": 0}
        _data = {
            "data": {
                "commandType": "moveToSlot",
                "params": {
                    "pipetteId": pipetteId,
                    "slotName": slotName,
                    "wellLocation": {
                        "origin": "bottom",
                        "offset": offset
                    }
                }
            }
        }
        _params = {"waitUntilComplete": True}
        ret = self.http_client.post(_url, data=_data, params=_params)
        self.http_client.judge_state_code(ret)
        return ret[1]

    async def _post_move_to(self, pipetteId, speed=12.3, position: Point = Point(400, 200, 100), mininumZ=35,
                            forceDirect=True):
        """
        move to a coordinates
        :param pipetteId: 
        :param speed: 
        :param position: 
        :param mininumZ: 
        :param forceDirect: if move to and  home z
        :return: 
        """
        if self.run_id is None:
            raise ValueError("run id can't be None")
        _url = f"/runs/{self.run_id}/commands"
        position = {"x": position[0], "y": position[1], "z": position[2]}
        _data = {
            "data": {
                "commandType": "moveToCoordinates",
                "params": {
                    "pipetteId": pipetteId,
                    "coordinates": position
                },
                "minimumZHeight": mininumZ,
                "speed": speed,
                "forceDirect": forceDirect
            }
        }
        _params = {"waitUntilComplete": True}
        ret = self.http_client.post(_url, data=_data, params=_params)
        self.http_client.judge_state_code(ret)
        return ret[1]

    async def _post_move_rel(self, pipetteId, axis: Axis, distance: float):
        """
        move relative
        :param pipetteId:
        :param axis:
        :param distance:
        :return:
        """
        if self.run_id is None:
            raise ValueError("run id can't be None")
        axis = axis.value
        _url = f"/runs/{self.run_id}/commands"
        _data = {
            "data": {
                "commandType": "moveRelative",
                "params": {
                    "pipetteId": pipetteId,
                    "axis": axis,
                    "distance": distance
                }
            }
        }
        _params = {"waitUntilComplete": True}
        ret = self.http_client.post(_url, data=_data, params=_params)
        self.http_client.judge_state_code(ret)
        return ret[1]

    async def get_run(self):
        """
        get run message
        :return:
        """
        responds = await self._get_run()
        return responds["data"]

    async def load_labware_by_definition(self, data):
        """
        load lab ware by definition
        :param data: describe file
        :return:
        """
        responds = await self._load_labware_by_definition(data)
        return responds["data"]["definitionUri"]

    async def require_saved_pos(self, pipette_id) -> Point:
        """
        require current pipette position
        :param pipette_id:
        :return:
        """
        responds = await self._post_save_position(pipette_id)
        position = responds["data"]["result"]["position"]
        _point = Point(x=position["x"], y=position["y"], z=position["z"])
        return _point

    async def move_to(self, pipetteId, speed=12.3, position: Point = Point(400, 200, 100), mininumZ=35,
                      forceDirect=True):
        """
        move to
        :param pipetteId:
        :param speed:
        :param position:
        :param mininumZ:
        :param forceDirect:
        :return:
        """
        print("move to")
        responds = await self._post_move_to(pipetteId, speed=speed, position=position, mininumZ=mininumZ,
                                            forceDirect=forceDirect)
        return responds["data"]["result"]["position"]

    async def move_rel(self, pipetteId, axis: Axis, distance: float):
        """
        move rel
        :param pipetteId:
        :param axis:
        :param distance:
        :return:
        """
        print("move rel")
        responds = await self._post_move_rel(pipetteId, axis, distance)
        return responds["data"]["result"]["position"]

    async def move_to_slot(self, pipette_id, slot_name):
        """
        move to slot
        :param pipette_id:
        :param slot_name:
        :return:
        """
        print("move to slot")
        responds = await self._post_move_to_slot(pipette_id, slot_name, offset=None)
        print(responds)

    async def move_to_well(self, pipetteId, labwareId, speed=12.3, forceDirect: bool = False, well="A1", offset=None):
        """
        move to well
        :param pipetteId:
        :param labwareId:
        :param speed:
        :param forceDirect:
        :param well:
        :param offset:
        :return:
        """
        print("move to well")
        await self._post_move_to_well(pipetteId, labwareId, speed=speed, forceDirect=forceDirect, well=well,
                                      offset=offset)

    async def require_last_run_status(self) -> str:
        """
        require protocol status
        :return:
        """
        run_list = await self.require_all_runs()
        last_run = run_list[-1]
        status = last_run["status"]
        return status

    async def require_all_runs(self) -> list:
        """
        require all created run
        :return:
        """
        responds = await self._get_require_all_run()
        return responds["data"]

    async def delete_run_by_id(self, id):
        """
        delete
        :param id:
        :return:
        """
        await self._del_clear_a_run(id)

    async def clear_runs(self, force=False):
        """
        clear all stopped and succeeded runs
        :param: force delete
        :return:
        """
        run_list = await self.require_all_runs()
        for run in run_list:
            status = run["status"]
            run_id = run["id"]
            if force:
                await self.delete_run_by_id(run_id)
            else:
                if status == "stopped" or status == "succeeded":
                    await self.delete_run_by_id(run_id)

    async def wait_for_protocol_stop(self):
        """
        wait until protocol done
        :return:
        """
        while True:
            status = await self.require_last_run_status()
            print(f"Protocol: {self.run_id} Is {status}...")
            if status == "stopped" or status == "succeeded":
                return
            time.sleep(3)

    async def load_module(self, module_name: ModuleName, slot="10"):
        """
        load module
        :param module_name:
        :param slot:
        :return:
        """
        print("load module")
        responds = await self._post_load_module(module_name, slot=slot)
        return responds["data"]["result"]["moduleId"]

    async def home(self, axis: Union[None, List[Axis]] = None):
        """
        home
        :param axis:
        :return:
        """
        print("home")
        await self._post_home(axis=axis)

    async def run_protocol(self):
        """
        run protocol
        :return:
        """
        if self.run_id is None:
            raise ValueError("run id can't be None")
        await self._post_run_protocol()
        await self.wait_for_protocol_stop()

    async def stop_protocol(self):
        """
        run protocol
        :return:
        """
        if self.run_id is None:
            raise ValueError("run id can't be None")
        await self._post_stop_protocol()

    async def pause_protocol(self):
        """
        run protocol
        :return:
        """
        if self.run_id is None:
            raise ValueError("run id can't be None")
        await self._post_pause_protocol()

    async def drop(self, pipette_id, labware_id="fixedTrash", well="A1", offset: dict = None):
        """
        drop
        :param pipette_id:
        :param labware_id:
        :param well:
        :param offset:
        :return:
        """
        print("drop")
        await self._post_drop(pipette_id, labware_id=labware_id, well=well, offset=offset)

    async def pick_up(self, pipette_id, labware_id, well="A1", offset: dict = None):
        """
        pick up
        :param pipette_id:
        :param labware_id:
        :param well:
        :param offset:
        :return:
        """
        print("pick up")
        await self._post_pick_up(pipette_id, labware_id, well=well, offset=offset)

    async def load_liquid(self, labware_id, liquid_id="waterId", volumeByWell=None):
        """
        load liquid
        :param labware_id:
        :param liquid_id:
        :param volumeByWell:
        :return:
        """
        await self._post_load_liquid(labware_id, liquidId=liquid_id, volumeByWell=volumeByWell)

    async def load_pipette(self, pipette_name: Instrument, mount: Mount):
        """
        load a pipette
        :param pipette_name:
        :param mount:
        :return: pipette id
        """
        response = await self._post_load_pipette(pipette_name, mount)
        pipette_id = response["data"]["result"]["pipetteId"]
        print(f"load pipette: {pipette_id}")
        pipette_result = PipetteResult(pipette_id, mount)
        return pipette_result

    async def load_labware(self, labware_name: LabWare, slot_name="9", name_space="opentrons",
                           module_id=None) -> LabwareResult:
        """
        load a labware
        :param labware_name:
        slot_name: slot location
        :param name_space: lab ware type, custom/opentrons
        :return: labware id
        """
        response = await self._post_load_labware(labware_name, slot_name=slot_name, name_space=name_space,
                                                 module_id=module_id)
        labware_id = response["data"]["result"]["labwareId"]
        try:
            slot = response["data"]["params"]["location"]["slotName"]
        except Exception as e:
            slot = "None"
        labware_name = response["data"]["params"]["loadName"]
        print(f"load labware: {labware_name}")
        return LabwareResult(labware_id, slot, labware_name)

    async def load_custom_labware(self, labware_name: LabWare, custom_definition, slot_name="9",
                                  name_space="custom_beta") -> LabwareResult:
        """
        load labware by definition
        :param labware_name:
        :param custom_definition:
        :param slot_name:
        :param name_space:
        :return:
        """
        await self.load_labware_by_definition(custom_definition)
        ret: LabwareResult = await self.load_labware(labware_name, slot_name=slot_name, name_space=name_space)
        return ret

    async def build_context(self, clear=False) -> str:
        """
        create a run
        :param clear: clear all runs
        :return:
        """
        if clear:
            await self.clear_runs()
        response = await self._post_create_a_run()
        run_id = response["data"]["id"]
        self.run_id = run_id
        return run_id

    async def get_commands(self, run_id, length):
        """
        get commands
        :return:
        """
        responds = await self._get_command(run_id, length)
        print(responds)

    async def blow_out(self, pipetteId, labwareId, flow_rate=2, well="A1", offset=None):
        """
        blow out
        :param pipetteId:
        :param labwareId:
        :param flow_rate:
        :param well:
        :param offset:
        :return:
        """
        print("blow_out")
        await self._post_blow_out(pipetteId, labwareId, flow_rate=flow_rate, well=well, offset=offset)

    async def touch_tip(self, pipette_id, labware_id, radius: float = 0.5, speed: float = 42, well: str = "A1",
                        offset=None):
        print("touch_tip")
        await self._post_touch_tip(pipette_id, labware_id, radius=radius, speed=speed, well=well, offset=offset)

    async def aspirate(self, pipette_id, labware_id, volume: float, flow_rate=3, well: str = "A1", offset=None,
                       leading_air_gap: float = 0, lagged_air_gap: float = 0):
        """
        aspire
        :param pipette_id:
        :param labware_id:
        :param volume:
        :param flow_rate:
        :param well:
        :param offset:
        :param leading_air_gap: aspirate air before liquid
        :param lagged_air_gap: aspirate air after liquid
        :return:
        """
        print("aspirate")
        if leading_air_gap > 0:
            responds = await self._post_aspirate(pipette_id, labware_id, leading_air_gap, flow_rate=1, well=well,
                                                 offset=offset, origin="top")
        responds = await self._post_aspirate(pipette_id, labware_id, volume, flow_rate=flow_rate, well=well,
                                             offset=offset)
        if lagged_air_gap > 0:
            responds = await self._post_aspirate(pipette_id, labware_id, lagged_air_gap, flow_rate=1, well=well,
                                                 offset=offset, origin="top")

    async def dispense(self, pipette_id, labware_id, volume: float, flow_rate=3, well: str = "A1", offset=None,
                       leading_air_gap: float = 0, lagged_air_gap: float = 0):
        """
        dispense
        :param pipette_id:
        :param labware_id:
        :param volume:
        :param flow_rate:
        :param well:
        :param offset:
        :param leading_air_gap:
        :param lagged_air_gap:
        :return:
        """
        print("dispense")
        if leading_air_gap > 0:
            await self._post_dispense(pipette_id, labware_id, leading_air_gap, flow_rate=1, well=well, offset=offset,
                                      origin="top")
        await self._post_dispense(pipette_id, labware_id, volume, flow_rate=flow_rate, well=well, offset=offset)
        if lagged_air_gap > 0:
            await self._post_dispense(pipette_id, labware_id, lagged_air_gap, flow_rate=1, well=well, offset=offset,
                                      origin="top")

    async def apply_labware_offset(self, uri: str, location: dict, vector=None):
        """
        load labware offset
        :param uri:
        :param location:
        :param vector:
        :return:
        """
        await self._post_apply_labware_offset(uri, location, vector=vector)

    async def return_tip(self, pipette_id, labware_id, well: str = "A1", offset: dict = None):
        """
        move to labware and return tip
        :param pipette_id:
        :param labware_id:
        :param well:
        :param offset:
        :return:
        """
        print("return tip")
        await self._post_drop(pipette_id, labware_id=labware_id, well=well, offset=offset)

    async def mix_liquid(self, pipette_id, labware_id, volume, times: int, well='A1'):
        """
        mix liquid
        supposed to do aspirate first
        :param pipette_id:
        :param labware_id:
        :param volume:
        :param times:
        :param well:
        :return:
        """
        for i in range(times):
            await self.aspirate(pipette_id, labware_id, volume, well=well, flow_rate=35)
            time.sleep(0.1)
            await self.dispense(pipette_id, labware_id, volume, well=well, flow_rate=35)

