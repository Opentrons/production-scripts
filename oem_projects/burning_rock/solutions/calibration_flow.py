"""
@author: andy-hu
for calibration
"""
# from protocol.jog import jog as p_jog
from ot_type import Mount, Instrument, LabWare, Axis
from solutions.reconstruct_protocol import ProtocolContext
from protocol.session import Session
from ot_type import CalibrationType

information_str = """
                           Click  >>   i   << to move up
                           Click  >>   k   << to move down
                           Click  >>   a  << to move left
                           Click  >>   d  << to move right
                           Click  >>   w  << to move forward
                           Click  >>   s  << to move back
                           Click  >>   +   << to Increase the length of each step
                           Click  >>   -   << to decrease the length of each step
                           Click  >> Enter << to save position
                           Click  >> q << to quit the test script
                                       """

CalibrationDeckPositionDefinition = {
    "deck_calibration": {
        "tip_rack": "slot8"
    },
    "tip_length_calibration": {
        "left": {
            "calibration_block": "slot3",
            "tip_rack": "slot8"
        },
        "right": {
            "calibration_block": "slot10",
            "tip_rack": "slot8"
        }
    }
}


class CalibrationFlow:
    def __init__(self):
        self.session = Session()

    async def calibration_labware(self, labware_name: LabWare, pipette_name: Instrument, mount: Mount, slot_name):
        """
        main loop
        :return:
        """
        # await self.api.build_context()
        # await self.api.home()
        # labware_id = await self.api.load_labware(labware_name, slot_name=slot_name)
        # pipette_id = await self.api.load_pipette(pipette_name, mount)
        # await self.api.move_to_well(pipette_id, labware_id, offset={'x': 0, 'y': 0, 'z': 0})
        # get_raw_pos = await self.api.require_saved_pos(pipette_id)
        # await p_jog(self.api, pipette_id)
        # get_then_pos = await self.api.require_saved_pos(pipette_id)
        # print(get_raw_pos, get_then_pos)
        pass

    async def excuse_exit_calibration(self, _all=False):
        """
        exit calibration
        :_all: exit all calibration
        :return:
        """
        if _all is False:
            await self.session.calibration_exit()
        else:
            id_list = await self.session.get_sessions()
            for _id in id_list:
                try:
                    await self.session.calibration_exit(_id=_id)
                except:
                    pass

    async def jog(self):
        """
        jog when calibration
        :return:
        """
        input("ready to jog? (press enter and continue...)")
        step_idx = 0
        while True:
            step = [0.1, 1, 5, 10]
            if step_idx > 3:
                step_idx = 0
            print(information_str)
            get_jog_input = input("jog >")
            if get_jog_input == 'w':
                await self.session.do_jog(offset_y=step[step_idx])
            elif get_jog_input == 'a':
                await self.session.do_jog(offset_x=-step[step_idx])
            elif get_jog_input == 's':
                await self.session.do_jog(offset_y=-step[step_idx])
            elif get_jog_input == 'd':
                await self.session.do_jog(offset_x=step[step_idx])
            elif get_jog_input == 'k':
                await self.session.do_jog(offset_z=-step[step_idx])
            elif get_jog_input == 'i':
                await self.session.do_jog(offset_z=step[step_idx])
            elif get_jog_input == '+':
                step_idx = step_idx + 1
            elif get_jog_input == '-':
                step_idx = step_idx - 1
            elif get_jog_input == 'q':
                break
            else:
                print("get error input")
            print(f"step: {step[step_idx]}")

    async def deck_calibration(self):
        """
        deck calibration
        :return:
        """
        await self.session.create_session_id(CalibrationType.DECK_CALIBRATION)
        await self.session.load_labware()
        input("load lab-ware on slot8 (press enter and continue...)")  # Todo: tell which lab-ware should put on(上位机作业)
        await self.session.move_to_tiprack()
        await self.jog()
        input("ready to pick up? (press enter and continue...)")
        await self.session.do_pick_up()
        while True:
            get_input = input("y: pick up and continue? / n: try again (y/n ?)")
            if get_input.strip() == 'y':
                await self.session.deck_calibration_move_to_deck()
                break
            else:
                await self.session.try_pick_up_again()
        await self.jog()
        await self.session.save_offset()
        await self.session.deck_calibration_move_to_point_one()
        await self.jog()
        await self.session.save_offset()
        await self.session.deck_calibration_move_to_point_two()
        await self.jog()
        await self.session.save_offset()
        await self.session.deck_calibration_move_to_point_three()
        await self.jog()
        await self.session.save_offset()
        await self.session.move_to_tiprack()
        await self.session.calibration_exit()

    async def tip_length_calibration(self, mount: Mount):
        """
        tip len calibration
        :param mount: which mount you want to calibrate
        :return:
        """
        create_params = {
            "hasCalibrationBlock": True,
            "mount": mount.value,
            "tipRackDefinition": None
        }
        await self.session.create_session_id(CalibrationType.TIP_LENGTH_CALIBRATION, create_params=create_params)
        await self.session.load_labware()
        calibration_slot_position = CalibrationDeckPositionDefinition["tip_length_calibration"][mount.value][
            "calibration_block"]
        input(f"load calibration block on {calibration_slot_position} (press enter and continue...)")
        # Todo: tell which lab-ware should put on(上位机作业)

        await self.session.move_to_reference_point()
        await self.jog()
        await self.session.save_offset()

        await self.session.move_to_tiprack()
        await self.jog()
        input("ready to pick up? (press enter and continue...)")
        await self.session.do_pick_up()
        while True:
            get_input = input("y: pick up and continue? / n: try again (y/n ?)")
            if get_input.strip() == 'y':
                await self.session.move_to_reference_point()
                break
            else:
                await self.session.try_pick_up_again()
        await self.jog()
        await self.session.save_offset()
        await self.session.move_to_tiprack()

        input("please take calibration block away (press enter and continue...)")
        await self.excuse_exit_calibration()

    async def pipette_offset_calibration(self, mount: Mount):
        """
        pipette offset calibration
        :param mount:
        :return:
        """
        create_params = {
            "hasCalibrationBlock": True,
            "mount": mount.value,
            "tipRackDefinition": None,
            "shouldRecalibrateTipLength": False
        }
        await self.session.create_session_id(CalibrationType.PIPETTE_OFFSET_CALIBRATION, create_params=create_params)
        await self.session.load_labware()
        input("load tip rack on slot8 (press enter and continue...)")
        # Todo: tell which lab-ware should put on(上位机作业)
        await self.session.move_to_tiprack()
        await self.jog()
        input("ready to pick up? (press enter and continue...)")
        await self.session.do_pick_up()
        while True:
            get_input = input("y: pick up and continue? / n: try again (y/n ?)")
            if get_input.strip() == 'y':
                await self.session.deck_calibration_move_to_deck()
                break
            else:
                await self.session.try_pick_up_again()
        await self.jog()
        await self.session.save_offset()
        await self.session.deck_calibration_move_to_point_one()
        await self.jog()
        await self.session.save_offset()
        await self.session.calibration_exit()
