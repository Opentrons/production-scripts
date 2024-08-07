"""
transfer liquid demo
"""

from protocol.protocol_context import ProtocolContext
from ot_type import Instrument, LabWare, Mount
import asyncio
from utils import Utils

Init_Instrument = {
    "left": Instrument.PIPETTE_P300_MULTI_GEN2,
    "right": Instrument.PIPETTE_P20_SIGNAL_GEN2
}


async def _main():
    api = ProtocolContext()
    await api.build_context(clear=True)
    # init load
    tip_rack_300ul = await api.load_labware(LabWare.OPENTRONS_96_TIPRACK_20UL, slot_name="12")
    reservoir_15ml = await api.load_labware(LabWare.NEST_12_RESERVOIR_15ML, slot_name="2")
    plate_200ul = await api.load_labware(LabWare.NEST_96_WELLPLATE_200UL_FLAT, slot_name="3")
    pipette_left = await api.load_pipette(Init_Instrument["left"], Mount.LEFT)
    # main loop
    for i in range(1):
        well = Utils.get_well_by_num(i)
        await api.pick_up(pipette_left.pipette_id, tip_rack_300ul.labware_id, well=well)
        await api.aspirate(pipette_left.pipette_id, reservoir_15ml.labware_id, 50, flow_rate=92.86, well="A1",
                           offset={"x": 0, "y": 0, "z": 5}, leading_air_gap=5)
        await api.dispense(pipette_left.pipette_id, plate_200ul.labware_id, 50, flow_rate=92.86, well=well,
                           leading_air_gap=6)
        await api.blow_out(pipette_left.pipette_id, plate_200ul.labware_id, well=well)
        await api.drop(pipette_left.pipette_id)
    await api.home()


if __name__ == '__main__':
    asyncio.run(_main())
