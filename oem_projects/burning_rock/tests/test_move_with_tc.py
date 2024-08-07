from protocol.protocol_context import ProtocolContext
from ot_type import Instrument, LabWare, Mount, Point, Axis
import asyncio
import time


async def _main():
    api = ProtocolContext()
    mount = Mount.LEFT
    await api.build_context(clear=True)
    await api.home()
    # load
    pipette_p300_s = await api.load_pipette(Instrument.PIPETTE_P300_MULTI_GEN2, mount)
    tip_300ul_12 = await api.load_labware(LabWare.OPENTRONS_96_TIPRACK_300UL, slot_name="12")
    tip_300ul_2 = await api.load_labware(LabWare.OPENTRONS_96_TIPRACK_300UL, slot_name="2")

    tip_rack_300_4 = await api.load_labware(LabWare.NEST_12_RESERVOIR_15ML, slot_name="4")
    await api.pick_up(pipette_p300_s.pipette_id, tip_300ul_12.labware_id, offset={"x": 0, "y": 7, "z": 0})
    # run

    await api.aspirate(pipette_p300_s.pipette_id, tip_rack_300_4.labware_id, 20)
    await api.dispense(pipette_p300_s.pipette_id, tip_rack_300_4.labware_id, 20)

    await api.drop(pipette_p300_s.pipette_id)


if __name__ == '__main__':
    asyncio.run(_main())
