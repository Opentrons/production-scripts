from solutions.reconstruct_protocol import ReconstructProtocolContext
from ot_type import Instrument, Mount, LabWare
import asyncio
import utils
from labware.opentrons_48_tiprack_20ul_definition import TIPRACK_DEF

Init_Instrument = {
    "left": Instrument.PIPETTE_P300_MULTI_GEN2,
    "right": Instrument.PIPETTE_P20_SIGNAL_GEN2
}


async def _main():
    re_api = ReconstructProtocolContext()
    await re_api.build_context()
    pipette_left = await re_api.load_pipette(Init_Instrument["left"], mount=Mount.LEFT)
    pipette_right = await re_api.load_pipette(Init_Instrument["right"], mount=Mount.RIGHT)
    tip_rack_300ul = await re_api.load_labware(LabWare.OPENTRONS_96_TIPRACK_300UL, slot_name="5")

    tip_rack_20ul = await re_api.load_custom_labware(LabWare.OPENTRONS_48_TIPRACK_20UL, TIPRACK_DEF, slot_name="1")

    reservoir_15ml = await re_api.load_labware(LabWare.NEST_12_RESERVOIR_15ML, slot_name="2")
    plate_200ul = await re_api.load_labware(LabWare.NEST_96_WELLPLATE_200UL_FLAT, slot_name="3")

    await re_api.home()

    for i in range(1):
        well = utils.Utils.get_well_by_num(i)
        # left
        await re_api.pick_up(pipette_left.pipette_id, tip_rack_20ul.labware_id, well=well)
        await re_api.aspirate(pipette_left.pipette_id, reservoir_15ml.labware_id, 10, flow_rate=92.86, well="A1",
                              offset={"x": 0, "y": 0, "z": 10})
        await re_api.dispense(pipette_left.pipette_id, plate_200ul.labware_id, 10, flow_rate=92.86, well=well)
        await re_api.blow_out(pipette_left.pipette_id, plate_200ul.labware_id, well=well)
        await re_api.fixed_drop(pipette_left.pipette_id)
        # right
        await re_api.pick_up(pipette_right.pipette_id, tip_rack_300ul.labware_id, well=well,
                             offset={'x': 1, 'y': 2, 'z': 0})
        await re_api.aspirate(pipette_right.pipette_id, reservoir_15ml.labware_id, 50, flow_rate=92.86, well="A1",
                              offset={"x": 0, "y": 0, "z": 10})
        await re_api.dispense(pipette_right.pipette_id, plate_200ul.labware_id, 50, flow_rate=92.86, well=well)
        await re_api.blow_out(pipette_right.pipette_id, plate_200ul.labware_id, well=well)
        await re_api.fixed_drop(pipette_right)


if __name__ == '__main__':
    asyncio.run(_main())
