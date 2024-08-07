from modules.thermocycler import ThermocyclerModule
from ot_type import ModuleName, Mount, Instrument, LabWare
import asyncio
from solutions.reconstruct_protocol import ReconstructProtocolContext
import time

Init_Labaware = {
    "left": [{"labware_name": LabWare.TRASH_1100ML_FIXED, "slot_name": '1'},
             {"labware_name": LabWare.OPENTRONS_96_TIPRACK_300UL, "slot_name": '11'},
             {"labware_name": LabWare.OPENTRONS_PCR_PLATE, "slot_name": 'None'},
             ]

}


async def _main():
    # initial api & lab-ware
    api = ReconstructProtocolContext()
    mount_r = Mount.RIGHT
    mount_l = Mount.LEFT
    await api.build_context(clear=True)

    # initial module
    _thermo_module = ThermocyclerModule(with_run_id=api.run_id)

    # load module
    tc = await api.load_module(ModuleName.TC_V2, slot='7')
    pcr = await api.load_labware(LabWare.OPENTRONS_PCR_PLATE, module_id=tc)

    # open lid
    """
    you have to open lid for the first step, otherwise, the further HTTP API for moving to TC will raise error
    """
    await _thermo_module.open_lid(tc)

    p20s = await api.load_pipette(Instrument.PIPETTE_P20_SIGNAL_GEN2, mount_r)
    p300m = await api.load_pipette(Instrument.PIPETTE_P300_MULTI_GEN2, mount_l)
    tip_20ul = await api.load_labware(LabWare.OPENTRONS_96_TIPRACK_20UL, slot_name="8")
    tip_300ul = await api.load_labware(LabWare.OPENTRONS_96_TIPRACK_300UL, slot_name="11")
    reservoir = await api.load_labware(LabWare.NEST_12_RESERVOIR_15ML, slot_name="3")

    # run process
    await api.home()

    # labware - calibration
    await api.labware_calibration(Init_Labaware)

    await api.pick_up(p300m.pipette_id, tip_300ul.labware_id)
    await api.aspirate(p300m.pipette_id, reservoir.labware_id, 10)
    await api.dispense(p300m.pipette_id, pcr.labware_id, 10)
    await api.drop(p300m.pipette_id)
    await api.home()
    await _thermo_module.close_lid(tc)

    # run profile
    # await _thermo_module.run_profile(tc)  # using default profile setting
    # time.sleep(5)
    # await _thermo_module.deactivate_block(tc)


if __name__ == '__main__':
    asyncio.run(_main())
