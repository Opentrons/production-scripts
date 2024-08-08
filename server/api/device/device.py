from fastapi import Depends, FastAPI, HTTPException, APIRouter
from typing import List
from api.device.models import *
from ot_type import Mount, Point
from utils import write_local_json, read_local_json

router = APIRouter()

database_path = 'database/device_status.json'


def judge_ipaddress_repeat(device: list, target: dict) -> bool:
    """
    judge
    :param device:
    :param target:
    :return:
    """
    for item in device:
        if item["device_address"] == target["device_address"]:
            return False
    return True

def get_target_ip_device(device: list, target_ip):
    """
    get target
    :param device:
    :param target_ip:
    :return:
    """
    for index, item in enumerate(device):
        if item["device_address"] == target_ip:
            return index
    return -1



@router.get('/status', status_code=200)
async def get_device_status():
    """
    get devices
    :return:
    """
    ret: dict = read_local_json(database_path)
    return {
        "success": True,
        "device": ret["device"]
    }


@router.post('/add/device', status_code=200)
async def add_device(deviceParamDetail: addDeviceParam):
    """
    add devices
    :return:
    """
    deviceDetail = deviceParamDetail.params
    detail = {
        "date": deviceDetail.date,
        "auth": deviceDetail.auth,
        "device_name": deviceDetail.device_name,
        "device_address": deviceDetail.device_address,
        "device_tag": deviceDetail.device_tag,
        "online": deviceDetail.online
    }
    ret = read_local_json(database_path)
    status = judge_ipaddress_repeat(ret["device"], detail)
    if status is False:
        return {
            "success": False,
            "message": "IP 地址重复"
        }
    ret["device"].append(detail)
    write_local_json(database_path, ret)
    return {
        "success": True,
        "device": ret,
        "message": "Add Successful"
    }


@router.post('/remove/device', status_code=200)
async def remove_device(deviceParamDetail: removeDeviceParam):
    """
    add devices
    :return:
    """
    deviceDetail = deviceParamDetail.params
    target_ip = deviceDetail.device_address
    ret = read_local_json(database_path)
    result = get_target_ip_device(ret["device"], target_ip)
    if result == -1:
        return {
            "success": False,
            "message": "当前目标未找到"
        }
    del ret["device"][result]
    write_local_json(database_path, ret)
    return {
        "success": True,
        "device": ret,
        "message": "Remove Successful"
    }
