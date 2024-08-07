from solutions.calibration_flow import CalibrationFlow
from protocol.protocol_context import ProtocolContext
import asyncio
from ot_type import Mount, Instrument, LabWare, Axis

deck_status = {
    'instrument': [Instrument.PIPETTE_P20_SIGNAL_GEN2, Instrument.PIPETTE_P300_MULTI_GEN2],
    "labware": {
        "2": LabWare.OPENTRONS_96_TIPRACK_20UL,
        "5": LabWare.OPENTRONS_96_TIPRACK_300UL,
    }
}


async def _run(deck: dict):
    api = ProtocolContext()
    cf = CalibrationFlow()
    instrments = deck["instrument"]
    labwares = deck["labware"]
    mount = Mount.LEFT
    for instrment in instrments:
        for slot, labware_name in labwares.items():
            await cf.calibration_labware(labware_name, instrment, mount,
                                         slot_name=slot)
        mount = Mount.RIGHT


if __name__ == '__main__':
    asyncio.run(_run(deck_status))
