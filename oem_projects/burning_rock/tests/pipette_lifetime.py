"""
transfer liquid demo
"""

from protocol.protocol_context import ProtocolContext
from ot_type import Instrument, LabWare, Mount
import asyncio
from utils import Utils

Init_Instrument = {
    "left": Instrument.PIPETTE_P300_MULTI_GEN2,
    "right": Instrument.PIPETTE_P300_MULTI_GEN2
}


async def _main():
    api = ProtocolContext()
    await api.build_context(clear=True)
    await api.home()
    # init load
    tip_rack_300ul_left = await api.load_labware(LabWare.OPENTRONS_96_TIPRACK_300UL, slot_name="7")
    tip_rack_300ul_right = await api.load_labware(LabWare.OPENTRONS_96_TIPRACK_300UL, slot_name="8")
    reservoir_15ml = await api.load_labware(LabWare.NEST_12_RESERVOIR_15ML, slot_name="2")
    plate_200ul = await api.load_labware(LabWare.NEST_96_WELLPLATE_200UL_FLAT, slot_name="9")
    pipette_left = await api.load_pipette(Init_Instrument["left"], Mount.LEFT)
    pipette_right = await api.load_pipette(Init_Instrument["right"], Mount.RIGHT)
    # main loop
    await api.pick_up(pipette_left.pipette_id, tip_rack_300ul_left.labware_id, well="A1",
                      offset={"x": 0, "y": 0, "z": -2})
    await api.pick_up(pipette_right.pipette_id, tip_rack_300ul_right.labware_id, well="A1",
                      offset={"x": 0, "y": 0, "z": -2})
    for i in range(3000):
        await api.aspirate(pipette_left.pipette_id, reservoir_15ml.labware_id, 200, flow_rate=80, well="A1",
                           offset={"x": 0, "y": 0, "z": 5}, leading_air_gap=5)
        await api.dispense(pipette_left.pipette_id, reservoir_15ml.labware_id, 200, flow_rate=80, well="A1",
                           offset={"x": 0, "y": 0, "z": 5}, leading_air_gap=5)

        await api.aspirate(pipette_right.pipette_id, reservoir_15ml.labware_id, 200, flow_rate=80, well="A1",
                           offset={"x": 0, "y": 0, "z": 5}, leading_air_gap=5)
        await api.dispense(pipette_right.pipette_id, reservoir_15ml.labware_id, 200, flow_rate=80, well="A1",
                           offset={"x": 0, "y": 0, "z": 5}, leading_air_gap=5)
        print(f"times: {i + 1}")
    await api.home()


if __name__ == '__main__':
    asyncio.run(_main())
