from solutions.reconstruct_protocol import ReconstructProtocolContext
from ot_type import Instrument, Mount, LabWare
import asyncio
import utils

Init_Instrument = {
    "left": Instrument.PIPETTE_P300_MULTI_GEN2,
    "right": Instrument.PIPETTE_P20_SIGNAL_GEN2
}

# define offset setting

offset_vector = {'x': 50, 'y': 50, 'z': 10}
Is_Apply_Offset = True


async def _main():
    re_api = ReconstructProtocolContext()
    await re_api.build_context()
    p_300 = await re_api.load_pipette(Init_Instrument["left"], mount=Mount.LEFT)
    p20 = await re_api.load_pipette(Init_Instrument["right"], mount=Mount.RIGHT)
    tip_rack_300ul = await re_api.load_labware(LabWare.OPENTRONS_96_TIPRACK_300UL, slot_name="3")

    await re_api.home()

    if Is_Apply_Offset:
        responds = await re_api.get_run()
        labware = responds["labware"]
        tip_300 = labware[1]
        tip_300_uri = tip_300["definitionUri"]
        tip_300_location = tip_300["location"]
        await re_api.apply_labware_offset(tip_300_uri, tip_300_location, offset_vector)

    tip_rack_300ul = await re_api.load_labware(LabWare.OPENTRONS_96_TIPRACK_300UL, slot_name="3")

    await re_api.move_to_well(p_300.pipette_id, tip_rack_300ul.labware_id, speed=120)

    # demo - move_to tip_rack_300
    # responds = await re_api.get_run()
    # offsets = responds["labwareOffsets"]
    # move_to_location = tip_rack_300ul
    # if len(offsets) == 0:
    #     await re_api.move_to_well(p_300.pipette_id, move_to_location.labware_id, speed=120)
    # else:
    #     for offset in offsets:
    #         if move_to_location.slot_name == offset["location"]["slotName"]:
    #             vector = offset["vector"]
    #             await re_api.move_to_well(p_300.pipette_id, move_to_location.labware_id, speed=120, offset=vector)


if __name__ == '__main__':
    asyncio.run(_main())
