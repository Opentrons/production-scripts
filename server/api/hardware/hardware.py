from server.hardware_control.hardware_control import HardwareControl
from server.protocol_control.protocol_control import ProtocolContext
from fastapi import Depends, FastAPI, HTTPException, APIRouter
from typing import List
from server.api.hardware.models import *
from server.ot_type import Mount, Point
from utils import Utils


class DeviceHardware:
    def __init__(self, ip_addr: str):
        self.hardware_control: HardwareControl = HardwareControl(ip_addr)
        self.protocol_control: ProtocolContext = None


DeviceList: List[DeviceHardware] = []

router = APIRouter()


@router.post("/hardware/build", status_code=201)
def build_hardware(device_detail: BuilderParam):
    """
    build handler
    :return:
    """
    # try:
    device_detail = device_detail.params
    device = DeviceHardware(device_detail.ip)
    DeviceList.append(device)
    return {"message": f"成功！连接流ID: {(len(DeviceList) - 1)}",
            "success": True,
            "device_id": (len(DeviceList) - 1)}
    # except Exception as e:
    #     raise HTTPException(status_code=400, detail='can not build\n')


@router.post("/hardware/home", status_code=200)
async def hardware_home(home_detail: HomeParam):
    """
    home
    :return:
    """
    try:
        home_detail = home_detail.params
        device: int = home_detail.device
        axis = home_detail.axis
        if axis.lower() == "all":
            await DeviceList[device].hardware_control.home()
        return {"success": True, "message": "Home " + axis}
    except Exception as e:
        pass


@router.post("/hardware/move_to", status_code=200)
async def move_to(move_to_detail: MoveToParam):
    """
    move to
    :param move_to_detail:
    :return:
    """
    move_to_detail = move_to_detail.params
    device: int = move_to_detail.device
    mount: str = move_to_detail.mount
    point: dict = move_to_detail.point
    if mount.lower() == "left":
        _mount = Mount.LEFT
    else:
        _mount = Mount.RIGHT
    _point = Point(point["x"], point["y"], point["z"])
    await DeviceList[device].hardware_control.move_to(_mount, _point)
    return {"message": "OK",
            "success": True}


@router.post("/hardware/move_rel", status_code=200)
async def move_rel(move_rel_detail: MoveRelParam):
    """
    move rel
    :param move_rel_detail:
    :return:
    """
    move_rel_detail = move_rel_detail.params
    device: int = move_rel_detail.device
    mount: str = move_rel_detail.mount
    point: dict = move_rel_detail.point
    if mount.lower() == "left":
        _mount = Mount.LEFT
    else:
        _mount = Mount.RIGHT
    _point = Point(point["x"], point["y"], point["z"])
    await DeviceList[device].hardware_control.move_rel(_mount, _point)


@router.post('/hardware/test/online', status_code=200)
async def test_device_online(test_online: TestOnlineParam):
    """
    test online
    :param test_online:
    :return:
    """
    test_online_detail = test_online.params
    ipaddress = test_online_detail.ipaddress
    ret = Utils.test_online3(ipaddress)
    if ret:
        return {"message": "online", "success": True}
    else:
        return {"message": "offline", "success": True}
