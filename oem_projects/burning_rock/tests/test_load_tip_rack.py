"""
@description: test load tip-rack and do labware calibration
"""
from modules.thermocycler import ThermocyclerModule
from ot_type import ModuleName, Mount, Instrument, LabWare
import asyncio
from solutions.reconstruct_protocol import ReconstructProtocolContext

Init_Labaware = {
    "left": [
             {"labware_name": LabWare.OPENTRONS_96_TIPRACK_300UL, "slot_name": 'None'},
             ]

}


async def _main():
    # initial api & lab-ware
    api = ReconstructProtocolContext()
    await api.build_context(clear=True)
    p300m = await api.load_pipette(Instrument.PIPETTE_P300_MULTI_GEN2, Mount.LEFT)
    tip300 = await api.load_labware(LabWare.OPENTRONS_96_TIPRACK_300UL, slot_name="3")

    # home
    await api.home()

    # labware calibration
    await api.move_to_well(p300m.pipette_id, tip300.labware_id, speed=55)
    _vector = {'x': 30.0, 'y': 0, 'z': 25}
    responds = await api.get_run()

    labware = responds["labware"][1]
    labware_uri = labware["definitionUri"]
    labware_location = labware["location"]

    print(labware_location)

    await api.apply_labware_offset(labware_uri, labware_location, _vector)

    # load tip-rack
    tip300 = await api.load_labware(LabWare.OPENTRONS_96_TIPRACK_300UL, slot_name="3")

    await api.move_to_well(p300m.pipette_id, tip300.labware_id, speed=55)


if __name__ == '__main__':
    asyncio.run(_main())



