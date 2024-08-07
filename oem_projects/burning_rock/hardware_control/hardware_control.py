from http_client import HttpClient
from ot_type import PositionSel, Mount, Point, Target, Axis, LabWare, Instrument
from typing import Union, List
import asyncio


class HardwareControl:
    def __init__(self):
        self.pipette_left_saved_position = Point(100.00, 100.00, 100.00)
        self.pipette_right_saved_position = Point(100.00, 100.00, 100.00)

    async def _get_robot_position(self):
        """
        get robot position
        :return:
        """
        ret = HttpClient.get("/robot/positions")
        HttpClient.judge_state_code(ret)
        return ret[1]

    async def _post_robot_move(self, mount: str, position: tuple, target="pipette"):
        """
        post pipette move
        :param mount:
        :param position:
        :param target:
        :return:
        """
        datas = {
            "target": target,
            "point": position,
            "mount": mount,
            "model": "string"
        }
        ret = HttpClient.post("/robot/move", data=datas)
        HttpClient.judge_state_code(ret)
        return ret

    async def _post_home(self, target, mount: Union[None, Mount] = None):
        """
        post home
        :param target:
        :param mount:
        :return:
        """
        target = target.value
        if mount is None:
            # home robot
            ret = HttpClient.post("/robot/home", data={"target": target})
        else:
            # home pipette
            ret = HttpClient.post("/robot/home", data={"target": target, "mount": mount.value})
        HttpClient.judge_state_code(ret)

    async def _get_calibration_status(self):
        """
        get calibration status
        :return:
        """
        ret = HttpClient.get("/calibration/status")
        HttpClient.judge_state_code(ret)

    async def _get_pipette_attached(self, refresh: Union[bool, None] = None):
        """
        get attached pipette message
        :param refresh: scan and fresh
        :return:
        """
        ret = HttpClient.get("/pipettes", params=refresh)
        HttpClient.judge_state_code(ret)
        return ret[1]

    async def _get_pipette_offset_calibration(self, pipette_id=None, mount=None):
        """
        get all pipette_offset
        :param pipette_id:
        :param mount:
        :return:
        """
        if pipette_id is None:
            ret = HttpClient.get("/calibration/pipette_offset")
        else:
            ret = HttpClient.get("/calibration/pipette_offset", params={"pipette_id": pipette_id, "mount": mount})
        HttpClient.judge_state_code(ret)
        return ret[1]

    async def _get_engaged_motor(self):
        """
        get engaged motor
        :return:
        """
        ret = HttpClient.get("/motors/engaged")
        HttpClient.judge_state_code(ret)
        return ret[1]

    async def _post_disengaged_motor(self, axis: List[Axis]):
        """
        disengage motor
        :param axis: [Axis.X, Axis.Y]
        :return:
        """

        ret = HttpClient.post("/motors/disengage", data={"axes": axis})
        HttpClient.judge_state_code(ret)
        return ret[1]

    def _get_point(self, message, mount: Mount):
        """
        move to and get response message
        :param message:
        :return:
        """
        idx = message.find('(')
        message = message[idx:]
        message = message.replace('(', "")
        message = message.replace(')', "")
        message_list = message.strip().split(',')
        saved_point = Point.converse_to_point(message_list)
        if mount == Mount.LEFT:
            self.pipette_left_saved_position = saved_point
        elif mount == Mount.RIGHT:
            self.pipette_right_saved_position = saved_point
        else:
            raise ValueError("mount err")

    async def home(self, target: Union[None, Target] = Target.ROBOT, mount: Union[None, Mount] = Mount.LEFT):
        """
        home
        :param target:
        :param mount:
        :return:
        """
        await self._post_home(target, mount=mount)

    async def move_to(self, mount: Mount, point: Point):
        """
        move to a position
        :param mount: mount
        :param point: point(x, y, z)
        :return:
        """
        response = await self._post_robot_move(mount.value, point)
        self._get_point(response[1]["message"], mount)

    async def move_rel(self, mount: Mount, position: Point):
        """
        move to a relative positions
        :param mount:
        :param position: Point(x, y, z)
        :return:
        """
        if mount == Mount.LEFT:
            pos = self.pipette_left_saved_position
        elif mount == Mount.RIGHT:
            pos = self.pipette_right_saved_position
        else:
            raise ValueError("parameter err")
        await self.move_to(mount, (pos + position))

    async def require_useful_pos(self, selector: PositionSel) -> Point:
        """
        require a useful position for equip instrument
        :param selector:
        :return:
        """
        pos = await self._get_robot_position()
        pos = pos["positions"]
        if "change_pipette" not in pos:
            raise AttributeError("unexpected parameter")
        change_pipette = pos["change_pipette"]
        if selector == PositionSel.MOUNT_LEFT:
            if "left" not in change_pipette:
                raise AttributeError("unexpected parameter")
            pos = change_pipette["left"]
            point = Point.converse_to_point(pos)
            return point
        if selector == PositionSel.MOUNT_RIGHT:
            if "right" not in change_pipette:
                raise AttributeError("unexpected parameter")
            pos = change_pipette["right"]
            point = Point.converse_to_point(pos)
            return point
        if "attach_tip" not in pos:
            raise AttributeError("unexpected parameter")
        attach_tip = pos["attach_tip"]
        if selector == PositionSel.TIP:
            pos = attach_tip["point"]
            point = Point.converse_to_point(pos)
            return point

    async def identify_robot(self, blink_time: int):
        """
        blink light for identify which robot
        :param blink_time: blink times
        :return:
        """
        ret = HttpClient.post("/identify", params={"seconds": blink_time})
        HttpClient.judge_state_code(ret)


if __name__ == '__main__':
    hc = HardwareControl()
    asyncio.run(hc.home())
