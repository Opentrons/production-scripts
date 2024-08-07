"""
move opentrons flex with protocol
"""

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
    pipette_p300_s = await api.load_pipette(Instrument.PIPETTE_P20_SIGNAL_GEN2, mount)
    tip_20ul = await api.load_labware(LabWare.OPENTRONS_96_TIPRACK_20UL, slot_name="2")
    pipette_p300_s = pipette_p300_s.pipette_id
    tip_20ul = tip_20ul.labware_id
    # excuse
    home_pos = await api.require_saved_pos(pipette_p300_s)
    print(f"Home Position: {home_pos}")
    # move to well
    # await api.move_to_well(pipette_p300_s, tip_20ul, well='A2', offset={"x": 0, "y": 0, "z": 20})
    # move to
    await api.move_to(pipette_p300_s, position=Point(100, 100, 100))
    # move relative
    await api.move_rel(pipette_p300_s, Axis.X, 50)
    time.sleep(0.5)
    await api.move_rel(pipette_p300_s, Axis.Y, 50)
    time.sleep(0.5)
    rel_pos = await api.move_rel(pipette_p300_s, Axis.Z, -50)
    print(f"Current Position: {rel_pos}")
    # home
    await api.run_protocol()


if __name__ == '__main__':
    input("clean deck for move...")
    asyncio.run(_main())
