"""
@description: test load module and do labware calibration
"""
from modules.thermocycler import ThermocyclerModule
from ot_type import ModuleName, Mount, Instrument, LabWare
import asyncio
from solutions.reconstruct_protocol import ReconstructProtocolContext

Init_Labaware = {
    "left": [
             {"labware_name": LabWare.OPENTRONS_PCR_PLATE, "slot_name": 'None'},
             ]

}


async def _main():
    # initial api & lab-ware
    api = ReconstructProtocolContext()
    await api.build_context(clear=True)
    p300m = await api.load_pipette(Instrument.PIPETTE_P300_MULTI_GEN2, Mount.LEFT)

    # initial module
    _thermo_module = ThermocyclerModule(with_run_id=api.run_id)

    # load module
    tc = await api.load_module(ModuleName.TC_V2, slot='7')
    pcr = await api.load_labware(LabWare.OPENTRONS_PCR_PLATE, module_id=tc)
    # home
    await api.home()
    await _thermo_module.open_lid(tc)

    # labware calibration
    await api.move_to_well(p300m.pipette_id, pcr.labware_id, speed=55)
    _vector = {'x': 15.0, 'y': 0, 'z': 2}
    responds = await api.get_run()

    module = responds["modules"][0]
    module_location = module["location"]

    labware = responds["labware"][1]
    labware_uri = labware["definitionUri"]
    module_location.update({"moduleModel": ModuleName.TC_V2.value})
    print(module_location)

    await api.apply_labware_offset(labware_uri, module_location, _vector)

    # load module

    pcr = await api.load_labware(LabWare.OPENTRONS_PCR_PLATE, module_id=tc)

    await api.move_to_well(p300m.pipette_id, pcr.labware_id, speed=55)


if __name__ == '__main__':
    asyncio.run(_main())



