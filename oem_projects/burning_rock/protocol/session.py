"""
do some workflow procedure, for example
1. deck calibration
2. tip length calibration
3. pipette offset calibration
"""
from ot_type import CalibrationType, ExcuseNameWithCalibrationDeck
from http_client import HttpClient


class Session:
    def __init__(self):
        self.current_session_id = None

    async def _get_sessions(self):
        """
        get all session id
        :return:
        """
        _url = "/sessions"
        ret = HttpClient.get(_url)
        HttpClient.judge_state_code(ret)
        return ret[1]

    async def _post_get_calibration_status(self):
        """
        get calibration status
        :return:
        """
        _url = "/calibration/status"
        ret = HttpClient.get(_url)
        HttpClient.judge_state_code(ret[0])
        return ret[1]

    async def _post_create_session_id(self, session_type, create_params=None):
        """
        post create a session id
        :return:
        """
        _url = "/sessions"
        if create_params is None:
            create_params = {
                "hasCalibrationBlock": False,
                "tipRacks": []
            }
        _data = {
            "data": {
                "sessionType": session_type,
                "createParams": create_params
            }
        }
        ret = HttpClient.post(_url, data=_data)
        HttpClient.judge_state_code(ret)
        return ret[1]["data"]["id"]

    async def _post_session_excuse(self, excuse_name: ExcuseNameWithCalibrationDeck, data=None, _id=None):
        """
        excuse command with calibration
        :param excuse_name:
        :param data:
        :param id: session id
        :return:
        """
        if _id is None:
            _id = self.current_session_id
        excuse_type = excuse_name.value
        if data is None:
            data = {}
        if _id is None:
            raise AssertionError("no session id for this")
        _url = f"/sessions/{_id}/commands/execute"
        _data = {
            "data":
                {
                    "command": excuse_type,
                    "data": data
                }
        }
        ret = HttpClient.post(_url, data=_data)
        HttpClient.judge_state_code(ret)

    async def _get_session_id(self, session_id):
        """
        get session status
        :param session_id:
        :return:
        """
        _url = f"/sessions/{session_id}"
        ret = HttpClient.get(_url)
        HttpClient.judge_state_code(ret)
        return ret[1]

    async def _del_session_id(self, session_id):
        """
        del session
        :param session_id:
        :return:
        """
        _url = f"/sessions/{session_id}"
        ret = HttpClient.delete(_url)
        HttpClient.judge_state_code(ret)

    async def get_sessions(self):
        """
        get all sessions
        :return:
        """
        responds = await self._get_sessions()
        _data = responds["data"]
        _id_list = []
        for item in _data:
            _id = item["id"]
            _id_list.append(_id)
        return _id_list

    async def get_status(self):
        """
        get calibration status
        :return:
        """
        responds = await self._post_get_calibration_status()
        deck_calibration_status = responds["deckCalibration"]["status"]
        instrument_calibration = responds["instrumentCalibration"]
        return deck_calibration_status, instrument_calibration

    async def create_session_id(self, calibration_type: CalibrationType, create_params=None):
        """
        init session id
        :param calibration_type:
        :param create_params:
        :return:
        """
        calibration_type = calibration_type.value
        self.current_session_id = await self._post_create_session_id(calibration_type, create_params=create_params)

    async def load_labware(self):
        """
        excuse load lab-ware
        :return:
        """
        await self._post_session_excuse(ExcuseNameWithCalibrationDeck.LOAD_LABWARE)

    async def move_to_tiprack(self):
        """
        excuse move to tip rack
        :return:
        """
        await self._post_session_excuse(ExcuseNameWithCalibrationDeck.MOVE_TO_TIP_RACK)

    async def do_jog(self, offset_x=0, offset_y=0, offset_z=0):
        """
        excuse jog
        :return:
        """
        offset = [offset_x, offset_y, offset_z]
        await self._post_session_excuse(ExcuseNameWithCalibrationDeck.CALIBRATION_JOG, data={"vector": offset})

    async def do_pick_up(self):
        """
        excuse pick up
        :return:
        """
        await self._post_session_excuse(ExcuseNameWithCalibrationDeck.PICK_UP)

    async def try_pick_up_again(self):
        """
        excuse try again
        :return:
        """
        await self._post_session_excuse(ExcuseNameWithCalibrationDeck.TRY_AGAIN)

    async def calibration_exit(self, _id=None):
        """
        exit 
        :return: 
        """
        if _id is None:
            _id = self.current_session_id
        print(f"exit current {_id} session")
        try:
            await self._post_session_excuse(ExcuseNameWithCalibrationDeck.EXIT, _id=_id)
        except:
            print(f"{_id} is not activity")
        await self._get_session_id(_id)
        await self._del_session_id(_id)

    async def deck_calibration_move_to_deck(self):
        """
        move to deck
        :return:
        """
        await self._post_session_excuse(ExcuseNameWithCalibrationDeck.MOVE_TO_DECK)

    async def save_offset(self):
        """
        exit
        :return:
        """
        await self._post_session_excuse(ExcuseNameWithCalibrationDeck.SAVE_OFFSET)

    async def deck_calibration_move_to_point_one(self):
        """
        move point one
        :return:
        """
        await self._post_session_excuse(ExcuseNameWithCalibrationDeck.MOVE_TO_POINT_ONE)

    async def deck_calibration_move_to_point_two(self):
        """
        move point two
        :return:
        """
        await self._post_session_excuse(ExcuseNameWithCalibrationDeck.DECK_MOVE_TO_POINT_TWO)

    async def deck_calibration_move_to_point_three(self):
        """
        move point three
        :return:
        """
        await self._post_session_excuse(ExcuseNameWithCalibrationDeck.DECK_MOVE_TO_POINT_THREE)

    async def move_to_reference_point(self):
        """
        tip len calibration and move to tip rack
        :return:
        """
        await self._post_session_excuse(ExcuseNameWithCalibrationDeck.MOVE_TO_REFERENCE_POINT)
