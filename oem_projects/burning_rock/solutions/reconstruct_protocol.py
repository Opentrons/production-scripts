from protocol.protocol_context import ProtocolContext
from ot_type import LabWare, LabwareResult, Axis, Mount, get_labware_name_by_value
import utils

FixedTrashSlot = 1
FixedTrashOffset = {'x': -70, 'y': -39, 'z': 30}
FixedOffsetNumber = 6
FixedOffset = {'x': 9 * FixedOffsetNumber, 'y': 0, 'z': 0}

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


class ReconstructProtocolContext(ProtocolContext):

    def __init__(self):
        super(ProtocolContext, self).__init__()
        self.loaded_number = 0
        self.labware_offset = {
            "left": [],
            "right": []
        }

    async def _find_labware_offset(self, labware_name, slot_name, mount: Mount):
        """
        load offset
        :param labware_name:
        :param slot_name:
        :return:
        """
        for item in self.labware_offset[mount.value]:
            if str(labware_name) in str(item["labware_name"]) and str(slot_name) in str(item["slot_name"]):
                return item["offset"]
        return None

    async def fixed_drop(self, pipette_id: str, default=False, mount: Mount = Mount.LEFT):
        """
        drop to trash by slot1
        :return:
        """
        if default is False:
            ret = await self._find_labware_offset("trash", FixedTrashSlot, mount)
            if ret is not None:
                offset = ret
            else:
                offset = FixedTrashOffset
        else:
            offset = FixedTrashOffset
        await self.drop(pipette_id, offset=offset)

    async def fixed_pick_up(self, pipette_id, labware_result: LabwareResult, well: str = "A1", offset=None,
                            mount: Mount = Mount.LEFT):
        """
        pick up without conflict by slot1
        :return:
        """
        slot = labware_result.slot_name
        labware_id = labware_result.labware_id
        labware_name = labware_result.labware_name
        ret = await self._find_labware_offset(labware_name, slot, mount)
        if ret is not None and offset is None:
            offset = ret
        await self.pick_up(pipette_id, labware_id, well=well, offset=offset)

    async def fixed_move_to_well(self, pipetteId, labware_result: LabwareResult, speed=12.3, forceDirect: bool = False,
                                 well="A1", offset=None, mount: Mount = Mount.LEFT):
        """
        move to well
        :param pipetteId:
        :param labware_result:
        :param speed:
        :param forceDirect:
        :param well:
        :param offset:
        :return:
        """
        slot = labware_result.slot_name
        labware_id = labware_result.labware_id
        labware_name = labware_result.labware_name
        ret = await self._find_labware_offset(labware_name, slot, mount)
        if ret is not None and offset is None:
            offset = ret
        await self.move_to_well(pipetteId, labware_id, speed=speed, forceDirect=forceDirect, well=well,
                                offset=offset)

    async def fixed_blow_out(self, pipetteId, labware_result: LabwareResult, flow_rate=2, well="A1", offset=None):
        """
        blow out
        :param pipetteId:
        :param labwareId:
        :param flow_rate:
        :param well:
        :param offset:
        :return:
        """
        slot = labware_result.slot_name
        labware_id = labware_result.labware_id
        await self.blow_out(pipetteId, labware_id, flow_rate=flow_rate, well=well,
                            offset=FixedOffset if slot in FixedSlot else offset)

    async def fixed_touch_tip(self, pipette_id, labware_result: LabwareResult, radius: float = 0.5, speed: float = 42,
                              well: str = "A1",
                              offset=None):
        """
        touch tip
        :param pipette_id:
        :param labware_result:
        :param radius:
        :param speed:
        :param well:
        :param offset:
        :return:
        """
        slot = labware_result.slot_name
        labware_id = labware_result.labware_id
        await self.touch_tip(pipette_id, labware_id, radius=radius, speed=speed, well=well,
                             offset=FixedOffset if slot in FixedSlot else offset)

    async def fixed_aspirate(self, pipette_id, labware_result, volume: float, flow_rate=3, well: str = "A1",
                             offset=None):
        """
        aspirate
        :param pipette_id:
        :param labware_result:
        :param volume:
        :param flow_rate:
        :param well:
        :param offset:
        :return:
        """
        slot = labware_result.slot_name
        labware_id = labware_result.labware_id
        await self.aspirate(pipette_id, labware_id, volume, flow_rate=flow_rate, well=well,
                            offset=FixedOffset if slot in FixedSlot else offset)

    async def fixed_dispense(self, pipette_id, labware_result, volume: float, flow_rate=3, well: str = "A1",
                             offset=None):
        """
        dispense
        :param pipette_id:
        :param labware_result:
        :param volume:
        :param flow_rate:
        :param well:
        :param offset:
        :return:
        """
        slot = labware_result.slot_name
        labware_id = labware_result.labware_id
        await self.dispense(pipette_id, labware_id, volume, flow_rate=flow_rate, well=well,
                            offset=FixedOffset if slot in FixedSlot else offset)

    async def _jog(self, pipette_id):
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
                await self.move_rel(pipette_id, Axis.Y, step[step_idx])
            elif get_jog_input == 'a':
                await self.move_rel(pipette_id, Axis.X, -step[step_idx])
            elif get_jog_input == 's':
                await self.move_rel(pipette_id, Axis.Y, -step[step_idx])
            elif get_jog_input == 'd':
                await self.move_rel(pipette_id, Axis.X, step[step_idx])
            elif get_jog_input == 'k':
                await self.move_rel(pipette_id, Axis.Z, -step[step_idx])
            elif get_jog_input == 'i':
                await self.move_rel(pipette_id, Axis.Z, step[step_idx])
            elif get_jog_input == '+':
                step_idx = step_idx + 1
            elif get_jog_input == '-':
                step_idx = step_idx - 1
            elif get_jog_input == 'q':
                break
            else:
                print("get error input")
            print(f"step: {step[step_idx]}")

    async def _print_load_message(self, responds: dict, only_labware_offset=False):
        """
        print loaded fixture
        :param respond:
        :return:
        """
        pipettes = responds["pipettes"]
        labwares = responds["labware"]
        modules = responds["modules"]
        labware_offsets = responds["labwareOffsets"]
        print("find run message: \n"
              "====================\n"
              )
        if only_labware_offset is not True:
            for pipette in pipettes:
                pipette_name = pipette["pipetteName"]
                mount = pipette["mount"]
                print(f"{mount} pipette: {pipette_name}\n")
            for labware in labwares:
                labware_name = labware["loadName"]
                definition_url = labware["definitionUri"]
                try:
                    location = labware["location"]["slotName"]
                except:
                    location = labware["location"]["moduleId"]
                print(f"labware: {labware_name}\n"
                      f"url: {definition_url}\n"
                      f"slot: {location}\n")
            for module in modules:
                print(f"module: {module}")
        for labware_offset in labware_offsets:
            _offset = labware_offset["vector"]
            print(f"labware offset: {_offset}")

    async def _calibrate_labware_unit(self, labware, pipette_id, modules, mount='left'):
        """
        calibrate a labware unit
        :param labware:
        :param pipette_id:
        :param modules:
        :param mount:
        :return:
        """
        labware_name = labware["loadName"]
        labware_id = labware["id"]
        definition_url = labware["definitionUri"]

        if "slotName" in labware["location"]:
            slot_location = labware["location"]["slotName"]
            location = labware["location"]
        else:
            slot_location = labware["location"]["moduleId"]
            for module in modules:
                if slot_location == module["id"]:
                    location = module["location"]

        print(f"get started to calibrate {labware_name} on slot {slot_location}")

        # calibrate
        await self.move_to_well(pipette_id, labware_id, speed=72.5,
                                offset=FixedTrashOffset if "trash" in labware_name else None)
        current_pos = await self.require_saved_pos(pipette_id)
        await self._jog(pipette_id)
        calibrate_pos = await self.require_saved_pos(pipette_id)
        offset = calibrate_pos - current_pos

        # apply offset
        _vector = {'x': offset.x, 'y': offset.y, 'z': offset.z}
        _input = input(f"apply this offset: {_vector} ? (y/n)")
        if _input == 'y':
            _vector = {'x': _vector['x'] + FixedTrashOffset['x'], 'y': _vector['y'] + FixedTrashOffset['y'],
                       'z': _vector['z'] + FixedTrashOffset['z']} if "trash" in labware_name else _vector
            await self.apply_labware_offset(definition_url, location, _vector)
            # re-load labware
            if "slotName" in labware["location"]:
                await self.load_labware(get_labware_name_by_value(labware_name), slot_location)
            else:
                await self.load_labware(get_labware_name_by_value(labware_name), module_id=slot_location)

    async def _init_labware_offset(self, mount: Mount, _labware_offsets):
        """
        init labware-calibration offset
        :param _labware_offset: get labware offset responds
        :return:
        """
        labware_offset = []
        for item in (_labware_offsets[self.loaded_number:]):
            labware_name = item["definitionUri"]
            slot_name = item["location"]["slotName"]
            offset = item["vector"]

            labware_offset.append({"labware_name": labware_name, "slot_name": slot_name, "offset": offset})

        self.labware_offset[mount.value] = labware_offset

    async def _judge_is_calibrated_labware(self, inside_labwares: list, judged_labware_name: str,
                                           labware_location: dict):
        """
        if we need to calibrate
        :param inside_labwares:
        :param judged_labware_name:
        :param labware_location:
        :return:
        """
        for _labware in inside_labwares:
            if _labware["slot_name"] == "None" or "module_id" in labware_location:
                return True
            if _labware["labware_name"].value in judged_labware_name and str(_labware["slot_name"]) in str(
                    _labware["slot_name"]):
                return True
        return False

    async def _loaded_labware(self, responds, mount):
        """
        record loaded labware
        :param responds:
        :param mount:
        :return:
        """
        loaded = []
        for item in responds["labwareOffsets"]:
            labware_name = item["definitionUri"]
            slot_name = item["location"]["slotName"]
            loaded.append({"labware_name": labware_name, "slot_name": slot_name, "mount": mount})
        return loaded

    async def labware_calibration(self, init_labaware: dict):
        """
        do labware calibration through run
        :return:
        """
        # get run message
        responds = await self.get_run()
        await self._print_load_message(responds, only_labware_offset=False)
        # calibration process
        pipettes = responds["pipettes"]
        labwares = responds["labware"]
        modules = responds["modules"]

        _temp_labware_loaded = []
        for pipette in pipettes:
            pipette_id = pipette["id"]
            pipette_name = pipette["pipetteName"]
            mount = pipette["mount"]
            _input = input(f"do calibrate {mount} pipette -> {pipette_name} ? (y/n)")
            if _input != 'y':
                continue
            for labware in labwares:
                # judge should calibrate this labware
                inside_labwares = init_labaware[mount]
                ret = await self._judge_is_calibrated_labware(inside_labwares, labware["loadName"], labware["location"])
                if ret:
                    await self._calibrate_labware_unit(labware, pipette_id, modules, mount=mount)

            responds = await self.get_run()

            await self._init_labware_offset(utils.Utils.get_mount_from_value(mount), responds["labwareOffsets"])
            self.loaded_number = len(responds["labwareOffsets"])

        input("calibration complete, press any key to continue...")
        await self._print_load_message(responds, only_labware_offset=True)
