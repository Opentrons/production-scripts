from protocol.protocol_context import ProtocolContext
from ot_type import Instrument, LabWare, Mount, Point, Axis
import asyncio
import time

Life_Time = 2  # Hours


async def _main():
    api = ProtocolContext()
    mount = Mount.LEFT
    await api.build_context(clear=True)
    await api.home()
    # load
    pipette_p300_s = await api.load_pipette(Instrument.PIPETTE_P300_MULTI_GEN2, mount)

    tip_300ul_2 = await api.load_labware(LabWare.OPENTRONS_96_TIPRACK_300UL, slot_name="2")

    reservoir_4 = await api.load_labware(LabWare.NEST_12_RESERVOIR_15ML, slot_name="4")
    await api.pick_up(pipette_p300_s.pipette_id, tip_300ul_2.labware_id, offset={"x": 0, "y": 2, "z": 0})
    # run
    init_time = time.time()
    while True:
        await api.aspirate(pipette_p300_s.pipette_id, reservoir_4.labware_id, 100, flow_rate=50)
        await api.dispense(pipette_p300_s.pipette_id, reservoir_4.labware_id, 100, flow_rate=50)
        curr_time = time.time()
        if (curr_time - init_time) > (Life_Time * 60 * 60):
            break

    await api.drop(pipette_p300_s.pipette_id)


if __name__ == '__main__':
    asyncio.run(_main())
