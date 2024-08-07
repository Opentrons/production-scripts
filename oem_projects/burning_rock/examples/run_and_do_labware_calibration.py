from solutions.reconstruct_protocol import ReconstructProtocolContext
from ot_type import Instrument, Mount, LabWare
import asyncio
import utils
from labware.opentrons_48_tiprack_20ul_definition import TIPRACK_DEF

Init_Instrument = {
    "left": Instrument.PIPETTE_P20_SIGNAL_GEN2,
    "right": Instrument.PIPETTE_P300_MULTI_GEN2
}

Init_Labaware = {
    "left": [{"labware_name": LabWare.TRASH_1100ML_FIXED, "slot_name": '1'},
             {"labware_name": LabWare.OPENTRONS_48_TIPRACK_20UL, "slot_name": '1'}
             ],
    "right": [{"labware_name": LabWare.TRASH_1100ML_FIXED, "slot_name": '1'},
              {"labware_name": LabWare.OPENTRONS_96_TIPRACK_300UL, "slot_name": '12'}
              ]
}


# init which labware that this mount will move to
# TODO: app should supposed to analyse this process through custom protocol


async def _main():
    re_api = ReconstructProtocolContext()
    await re_api.build_context()
    pipette_left = await re_api.load_pipette(Init_Instrument["left"], mount=Mount.LEFT)
    pipette_right = await re_api.load_pipette(Init_Instrument["right"], mount=Mount.RIGHT)
    tip_rack_20ul = await re_api.load_custom_labware(LabWare.OPENTRONS_48_TIPRACK_20UL, TIPRACK_DEF, slot_name="1")
    tip_rack_300ul = await re_api.load_labware(LabWare.OPENTRONS_96_TIPRACK_300UL, slot_name="12")

    await re_api.home()

    await re_api.labware_calibration(Init_Labaware)
    for i in range(5):
        well = utils.Utils.get_well_by_num(i)
        # left
        await re_api.fixed_pick_up(pipette_left.pipette_id, tip_rack_20ul, well=well, mount=pipette_left.mount)
        await re_api.fixed_drop(pipette_left.pipette_id, mount=pipette_left.mount)

        # right
        await re_api.fixed_pick_up(pipette_right.pipette_id, tip_rack_300ul, well=well, mount=pipette_right.mount)
        await re_api.fixed_drop(pipette_right.pipette_id, mount=pipette_right.mount)


if __name__ == '__main__':
    asyncio.run(_main())
