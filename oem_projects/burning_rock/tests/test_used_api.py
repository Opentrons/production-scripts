"""
transfer liquid demo
"""

from solutions.reconstruct_protocol import ProtocolContext
from ot_type import Instrument, LabWare, Mount
from solutions.version import get_version
import asyncio
from utils import Utils

Init_Instrument = {
    "left": Instrument.PIPETTE_P20_MULTI_GEN2,
    "right": Instrument.PIPETTE_P20_SIGNAL_GEN2
}

Domain = "http://OT2RS20240523002:31950"


class TestUsedApi:
    def __init__(self):
        self.api = ProtocolContext()
        await self.api.build_context(clear=True)
        await self.api.home()
        # init load
        pipette_left = await self.api.load_pipette(Init_Instrument["left"], Mount.LEFT)
        pipette_right = await self.api.load_pipette(Init_Instrument["right"], Mount.RIGHT)

    def test_version(self):
        res = get_version(Domain)
        return res
