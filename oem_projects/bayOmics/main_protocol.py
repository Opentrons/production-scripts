from opentrons import protocol_api
import json
import serial
import serial.tools.list_ports
import codecs
from enum import Enum
import hashlib

# metadata
metadata = {
    "protocolName": "__BayOmicsTemperatureModule__V1.4.8",
    "author": "Name <opentrons@example.com>",
    "description": "Simple protocol to get started using the OT-2",
}

# requirements
requirements = {"robotType": "OT-2", "apiLevel": "2.18"}

"""
customer labware
"""
USER_LABWARE_SLOT = '8'
LABWARE_DEF_JSON = """{"ordering":[["A1","B1","C1","D1","E1","F1","G1","H1"],["A2","B2","C2","D2","E2","F2","G2","H2"],["A3","B3","C3","D3","E3","F3","G3","H3"],["A4","B4","C4","D4","E4","F4","G4","H4"],["A5","B5","C5","D5","E5","F5","G5","H5"],["A6","B6","C6","D6","E6","F6","G6","H6"],["A7","B7","C7","D7","E7","F7","G7","H7"],["A8","B8","C8","D8","E8","F8","G8","H8"],["A9","B9","C9","D9","E9","F9","G9","H9"],["A10","B10","C10","D10","E10","F10","G10","H10"],["A11","B11","C11","D11","E11","F11","G11","H11"],["A12","B12","C12","D12","E12","F12","G12","H12"]],"brand":{"brand":"BayOmics2","brandId":["v2"]},"metadata":{"displayName":"BayOmics2 96 Well Plate 1000 µL","displayCategory":"wellPlate","displayVolumeUnits":"µL","tags":[]},"dimensions":{"xDimension":127.56,"yDimension":85.36,"zDimension":130.74},"wells":{"A1":{"depth":4.5,"totalLiquidVolume":1000,"shape":"circular","diameter":4.89,"x":14.28,"y":74.18,"z":126.24},"B1":{"depth":4.5,"totalLiquidVolume":1000,"shape":"circular","diameter":4.89,"x":14.28,"y":65.18,"z":126.24},"C1":{"depth":4.5,"totalLiquidVolume":1000,"shape":"circular","diameter":4.89,"x":14.28,"y":56.18,"z":126.24},"D1":{"depth":4.5,"totalLiquidVolume":1000,"shape":"circular","diameter":4.89,"x":14.28,"y":47.18,"z":126.24},"E1":{"depth":4.5,"totalLiquidVolume":1000,"shape":"circular","diameter":4.89,"x":14.28,"y":38.18,"z":126.24},"F1":{"depth":4.5,"totalLiquidVolume":1000,"shape":"circular","diameter":4.89,"x":14.28,"y":29.18,"z":126.24},"G1":{"depth":4.5,"totalLiquidVolume":1000,"shape":"circular","diameter":4.89,"x":14.28,"y":20.18,"z":126.24},"H1":{"depth":4.5,"totalLiquidVolume":1000,"shape":"circular","diameter":4.89,"x":14.28,"y":11.18,"z":126.24},"A2":{"depth":4.5,"totalLiquidVolume":1000,"shape":"circular","diameter":4.89,"x":23.28,"y":74.18,"z":126.24},"B2":{"depth":4.5,"totalLiquidVolume":1000,"shape":"circular","diameter":4.89,"x":23.28,"y":65.18,"z":126.24},"C2":{"depth":4.5,"totalLiquidVolume":1000,"shape":"circular","diameter":4.89,"x":23.28,"y":56.18,"z":126.24},"D2":{"depth":4.5,"totalLiquidVolume":1000,"shape":"circular","diameter":4.89,"x":23.28,"y":47.18,"z":126.24},"E2":{"depth":4.5,"totalLiquidVolume":1000,"shape":"circular","diameter":4.89,"x":23.28,"y":38.18,"z":126.24},"F2":{"depth":4.5,"totalLiquidVolume":1000,"shape":"circular","diameter":4.89,"x":23.28,"y":29.18,"z":126.24},"G2":{"depth":4.5,"totalLiquidVolume":1000,"shape":"circular","diameter":4.89,"x":23.28,"y":20.18,"z":126.24},"H2":{"depth":4.5,"totalLiquidVolume":1000,"shape":"circular","diameter":4.89,"x":23.28,"y":11.18,"z":126.24},"A3":{"depth":4.5,"totalLiquidVolume":1000,"shape":"circular","diameter":4.89,"x":32.28,"y":74.18,"z":126.24},"B3":{"depth":4.5,"totalLiquidVolume":1000,"shape":"circular","diameter":4.89,"x":32.28,"y":65.18,"z":126.24},"C3":{"depth":4.5,"totalLiquidVolume":1000,"shape":"circular","diameter":4.89,"x":32.28,"y":56.18,"z":126.24},"D3":{"depth":4.5,"totalLiquidVolume":1000,"shape":"circular","diameter":4.89,"x":32.28,"y":47.18,"z":126.24},"E3":{"depth":4.5,"totalLiquidVolume":1000,"shape":"circular","diameter":4.89,"x":32.28,"y":38.18,"z":126.24},"F3":{"depth":4.5,"totalLiquidVolume":1000,"shape":"circular","diameter":4.89,"x":32.28,"y":29.18,"z":126.24},"G3":{"depth":4.5,"totalLiquidVolume":1000,"shape":"circular","diameter":4.89,"x":32.28,"y":20.18,"z":126.24},"H3":{"depth":4.5,"totalLiquidVolume":1000,"shape":"circular","diameter":4.89,"x":32.28,"y":11.18,"z":126.24},"A4":{"depth":4.5,"totalLiquidVolume":1000,"shape":"circular","diameter":4.89,"x":41.28,"y":74.18,"z":126.24},"B4":{"depth":4.5,"totalLiquidVolume":1000,"shape":"circular","diameter":4.89,"x":41.28,"y":65.18,"z":126.24},"C4":{"depth":4.5,"totalLiquidVolume":1000,"shape":"circular","diameter":4.89,"x":41.28,"y":56.18,"z":126.24},"D4":{"depth":4.5,"totalLiquidVolume":1000,"shape":"circular","diameter":4.89,"x":41.28,"y":47.18,"z":126.24},"E4":{"depth":4.5,"totalLiquidVolume":1000,"shape":"circular","diameter":4.89,"x":41.28,"y":38.18,"z":126.24},"F4":{"depth":4.5,"totalLiquidVolume":1000,"shape":"circular","diameter":4.89,"x":41.28,"y":29.18,"z":126.24},"G4":{"depth":4.5,"totalLiquidVolume":1000,"shape":"circular","diameter":4.89,"x":41.28,"y":20.18,"z":126.24},"H4":{"depth":4.5,"totalLiquidVolume":1000,"shape":"circular","diameter":4.89,"x":41.28,"y":11.18,"z":126.24},"A5":{"depth":4.5,"totalLiquidVolume":1000,"shape":"circular","diameter":4.89,"x":50.28,"y":74.18,"z":126.24},"B5":{"depth":4.5,"totalLiquidVolume":1000,"shape":"circular","diameter":4.89,"x":50.28,"y":65.18,"z":126.24},"C5":{"depth":4.5,"totalLiquidVolume":1000,"shape":"circular","diameter":4.89,"x":50.28,"y":56.18,"z":126.24},"D5":{"depth":4.5,"totalLiquidVolume":1000,"shape":"circular","diameter":4.89,"x":50.28,"y":47.18,"z":126.24},"E5":{"depth":4.5,"totalLiquidVolume":1000,"shape":"circular","diameter":4.89,"x":50.28,"y":38.18,"z":126.24},"F5":{"depth":4.5,"totalLiquidVolume":1000,"shape":"circular","diameter":4.89,"x":50.28,"y":29.18,"z":126.24},"G5":{"depth":4.5,"totalLiquidVolume":1000,"shape":"circular","diameter":4.89,"x":50.28,"y":20.18,"z":126.24},"H5":{"depth":4.5,"totalLiquidVolume":1000,"shape":"circular","diameter":4.89,"x":50.28,"y":11.18,"z":126.24},"A6":{"depth":4.5,"totalLiquidVolume":1000,"shape":"circular","diameter":4.89,"x":59.28,"y":74.18,"z":126.24},"B6":{"depth":4.5,"totalLiquidVolume":1000,"shape":"circular","diameter":4.89,"x":59.28,"y":65.18,"z":126.24},"C6":{"depth":4.5,"totalLiquidVolume":1000,"shape":"circular","diameter":4.89,"x":59.28,"y":56.18,"z":126.24},"D6":{"depth":4.5,"totalLiquidVolume":1000,"shape":"circular","diameter":4.89,"x":59.28,"y":47.18,"z":126.24},"E6":{"depth":4.5,"totalLiquidVolume":1000,"shape":"circular","diameter":4.89,"x":59.28,"y":38.18,"z":126.24},"F6":{"depth":4.5,"totalLiquidVolume":1000,"shape":"circular","diameter":4.89,"x":59.28,"y":29.18,"z":126.24},"G6":{"depth":4.5,"totalLiquidVolume":1000,"shape":"circular","diameter":4.89,"x":59.28,"y":20.18,"z":126.24},"H6":{"depth":4.5,"totalLiquidVolume":1000,"shape":"circular","diameter":4.89,"x":59.28,"y":11.18,"z":126.24},"A7":{"depth":4.5,"totalLiquidVolume":1000,"shape":"circular","diameter":4.89,"x":68.28,"y":74.18,"z":126.24},"B7":{"depth":4.5,"totalLiquidVolume":1000,"shape":"circular","diameter":4.89,"x":68.28,"y":65.18,"z":126.24},"C7":{"depth":4.5,"totalLiquidVolume":1000,"shape":"circular","diameter":4.89,"x":68.28,"y":56.18,"z":126.24},"D7":{"depth":4.5,"totalLiquidVolume":1000,"shape":"circular","diameter":4.89,"x":68.28,"y":47.18,"z":126.24},"E7":{"depth":4.5,"totalLiquidVolume":1000,"shape":"circular","diameter":4.89,"x":68.28,"y":38.18,"z":126.24},"F7":{"depth":4.5,"totalLiquidVolume":1000,"shape":"circular","diameter":4.89,"x":68.28,"y":29.18,"z":126.24},"G7":{"depth":4.5,"totalLiquidVolume":1000,"shape":"circular","diameter":4.89,"x":68.28,"y":20.18,"z":126.24},"H7":{"depth":4.5,"totalLiquidVolume":1000,"shape":"circular","diameter":4.89,"x":68.28,"y":11.18,"z":126.24},"A8":{"depth":4.5,"totalLiquidVolume":1000,"shape":"circular","diameter":4.89,"x":77.28,"y":74.18,"z":126.24},"B8":{"depth":4.5,"totalLiquidVolume":1000,"shape":"circular","diameter":4.89,"x":77.28,"y":65.18,"z":126.24},"C8":{"depth":4.5,"totalLiquidVolume":1000,"shape":"circular","diameter":4.89,"x":77.28,"y":56.18,"z":126.24},"D8":{"depth":4.5,"totalLiquidVolume":1000,"shape":"circular","diameter":4.89,"x":77.28,"y":47.18,"z":126.24},"E8":{"depth":4.5,"totalLiquidVolume":1000,"shape":"circular","diameter":4.89,"x":77.28,"y":38.18,"z":126.24},"F8":{"depth":4.5,"totalLiquidVolume":1000,"shape":"circular","diameter":4.89,"x":77.28,"y":29.18,"z":126.24},"G8":{"depth":4.5,"totalLiquidVolume":1000,"shape":"circular","diameter":4.89,"x":77.28,"y":20.18,"z":126.24},"H8":{"depth":4.5,"totalLiquidVolume":1000,"shape":"circular","diameter":4.89,"x":77.28,"y":11.18,"z":126.24},"A9":{"depth":4.5,"totalLiquidVolume":1000,"shape":"circular","diameter":4.89,"x":86.28,"y":74.18,"z":126.24},"B9":{"depth":4.5,"totalLiquidVolume":1000,"shape":"circular","diameter":4.89,"x":86.28,"y":65.18,"z":126.24},"C9":{"depth":4.5,"totalLiquidVolume":1000,"shape":"circular","diameter":4.89,"x":86.28,"y":56.18,"z":126.24},"D9":{"depth":4.5,"totalLiquidVolume":1000,"shape":"circular","diameter":4.89,"x":86.28,"y":47.18,"z":126.24},"E9":{"depth":4.5,"totalLiquidVolume":1000,"shape":"circular","diameter":4.89,"x":86.28,"y":38.18,"z":126.24},"F9":{"depth":4.5,"totalLiquidVolume":1000,"shape":"circular","diameter":4.89,"x":86.28,"y":29.18,"z":126.24},"G9":{"depth":4.5,"totalLiquidVolume":1000,"shape":"circular","diameter":4.89,"x":86.28,"y":20.18,"z":126.24},"H9":{"depth":4.5,"totalLiquidVolume":1000,"shape":"circular","diameter":4.89,"x":86.28,"y":11.18,"z":126.24},"A10":{"depth":4.5,"totalLiquidVolume":1000,"shape":"circular","diameter":4.89,"x":95.28,"y":74.18,"z":126.24},"B10":{"depth":4.5,"totalLiquidVolume":1000,"shape":"circular","diameter":4.89,"x":95.28,"y":65.18,"z":126.24},"C10":{"depth":4.5,"totalLiquidVolume":1000,"shape":"circular","diameter":4.89,"x":95.28,"y":56.18,"z":126.24},"D10":{"depth":4.5,"totalLiquidVolume":1000,"shape":"circular","diameter":4.89,"x":95.28,"y":47.18,"z":126.24},"E10":{"depth":4.5,"totalLiquidVolume":1000,"shape":"circular","diameter":4.89,"x":95.28,"y":38.18,"z":126.24},"F10":{"depth":4.5,"totalLiquidVolume":1000,"shape":"circular","diameter":4.89,"x":95.28,"y":29.18,"z":126.24},"G10":{"depth":4.5,"totalLiquidVolume":1000,"shape":"circular","diameter":4.89,"x":95.28,"y":20.18,"z":126.24},"H10":{"depth":4.5,"totalLiquidVolume":1000,"shape":"circular","diameter":4.89,"x":95.28,"y":11.18,"z":126.24},"A11":{"depth":4.5,"totalLiquidVolume":1000,"shape":"circular","diameter":4.89,"x":104.28,"y":74.18,"z":126.24},"B11":{"depth":4.5,"totalLiquidVolume":1000,"shape":"circular","diameter":4.89,"x":104.28,"y":65.18,"z":126.24},"C11":{"depth":4.5,"totalLiquidVolume":1000,"shape":"circular","diameter":4.89,"x":104.28,"y":56.18,"z":126.24},"D11":{"depth":4.5,"totalLiquidVolume":1000,"shape":"circular","diameter":4.89,"x":104.28,"y":47.18,"z":126.24},"E11":{"depth":4.5,"totalLiquidVolume":1000,"shape":"circular","diameter":4.89,"x":104.28,"y":38.18,"z":126.24},"F11":{"depth":4.5,"totalLiquidVolume":1000,"shape":"circular","diameter":4.89,"x":104.28,"y":29.18,"z":126.24},"G11":{"depth":4.5,"totalLiquidVolume":1000,"shape":"circular","diameter":4.89,"x":104.28,"y":20.18,"z":126.24},"H11":{"depth":4.5,"totalLiquidVolume":1000,"shape":"circular","diameter":4.89,"x":104.28,"y":11.18,"z":126.24},"A12":{"depth":4.5,"totalLiquidVolume":1000,"shape":"circular","diameter":4.89,"x":113.28,"y":74.18,"z":126.24},"B12":{"depth":4.5,"totalLiquidVolume":1000,"shape":"circular","diameter":4.89,"x":113.28,"y":65.18,"z":126.24},"C12":{"depth":4.5,"totalLiquidVolume":1000,"shape":"circular","diameter":4.89,"x":113.28,"y":56.18,"z":126.24},"D12":{"depth":4.5,"totalLiquidVolume":1000,"shape":"circular","diameter":4.89,"x":113.28,"y":47.18,"z":126.24},"E12":{"depth":4.5,"totalLiquidVolume":1000,"shape":"circular","diameter":4.89,"x":113.28,"y":38.18,"z":126.24},"F12":{"depth":4.5,"totalLiquidVolume":1000,"shape":"circular","diameter":4.89,"x":113.28,"y":29.18,"z":126.24},"G12":{"depth":4.5,"totalLiquidVolume":1000,"shape":"circular","diameter":4.89,"x":113.28,"y":20.18,"z":126.24},"H12":{"depth":4.5,"totalLiquidVolume":1000,"shape":"circular","diameter":4.89,"x":113.28,"y":11.18,"z":126.24}},"groups":[{"metadata":{"wellBottomShape":"v"},"wells":["A1","B1","C1","D1","E1","F1","G1","H1","A2","B2","C2","D2","E2","F2","G2","H2","A3","B3","C3","D3","E3","F3","G3","H3","A4","B4","C4","D4","E4","F4","G4","H4","A5","B5","C5","D5","E5","F5","G5","H5","A6","B6","C6","D6","E6","F6","G6","H6","A7","B7","C7","D7","E7","F7","G7","H7","A8","B8","C8","D8","E8","F8","G8","H8","A9","B9","C9","D9","E9","F9","G9","H9","A10","B10","C10","D10","E10","F10","G10","H10","A11","B11","C11","D11","E11","F11","G11","H11","A12","B12","C12","D12","E12","F12","G12","H12"]}],"parameters":{"format":"irregular","quirks":[],"isTiprack":false,"isMagneticModuleCompatible":false,"loadName":"bayomics2_96_wellplate_1000ul"},"namespace":"custom_beta","version":1,"schemaVersion":2,"cornerOffsetFromSlot":{"x":0,"y":0,"z":0}}"""
LABWARE_DEF = json.loads(LABWARE_DEF_JSON)
LABWARE_LABEL = LABWARE_DEF.get('metadata', {}).get('displayName', 'test labware')
LABWARE_DIMENSIONS = LABWARE_DEF.get('wells', {}).get('A1', {}).get('yDimension')

USER_LIQUID_SLOT = '1'
USER_LIQUID_LABWARE_DEF_JSON = """{"ordering":[["A1","B1","C1","D1","E1","F1","G1","H1"],["A2","B2","C2","D2","E2","F2","G2","H2"],["A3","B3","C3","D3","E3","F3","G3","H3"],["A4","B4","C4","D4","E4","F4","G4","H4"],["A5","B5","C5","D5","E5","F5","G5","H5"],["A6","B6","C6","D6","E6","F6","G6","H6"],["A7","B7","C7","D7","E7","F7","G7","H7"],["A8","B8","C8","D8","E8","F8","G8","H8"],["A9","B9","C9","D9","E9","F9","G9","H9"],["A10","B10","C10","D10","E10","F10","G10","H10"],["A11","B11","C11","D11","E11","F11","G11","H11"],["A12","B12","C12","D12","E12","F12","G12","H12"]],"brand":{"brand":"BayOmics","brandId":[]},"metadata":{"displayName":"BayOmics 96 Well Plate 1200 µL","displayCategory":"wellPlate","displayVolumeUnits":"µL","tags":[]},"dimensions":{"xDimension":127,"yDimension":85,"zDimension":24.6},"wells":{"A1":{"depth":21.7,"totalLiquidVolume":1200,"shape":"rectangular","xDimension":8,"yDimension":8,"x":14.3,"y":73.85,"z":2.9},"B1":{"depth":21.7,"totalLiquidVolume":1200,"shape":"rectangular","xDimension":8,"yDimension":8,"x":14.3,"y":64.85,"z":2.9},"C1":{"depth":21.7,"totalLiquidVolume":1200,"shape":"rectangular","xDimension":8,"yDimension":8,"x":14.3,"y":55.85,"z":2.9},"D1":{"depth":21.7,"totalLiquidVolume":1200,"shape":"rectangular","xDimension":8,"yDimension":8,"x":14.3,"y":46.85,"z":2.9},"E1":{"depth":21.7,"totalLiquidVolume":1200,"shape":"rectangular","xDimension":8,"yDimension":8,"x":14.3,"y":37.85,"z":2.9},"F1":{"depth":21.7,"totalLiquidVolume":1200,"shape":"rectangular","xDimension":8,"yDimension":8,"x":14.3,"y":28.85,"z":2.9},"G1":{"depth":21.7,"totalLiquidVolume":1200,"shape":"rectangular","xDimension":8,"yDimension":8,"x":14.3,"y":19.85,"z":2.9},"H1":{"depth":21.7,"totalLiquidVolume":1200,"shape":"rectangular","xDimension":8,"yDimension":8,"x":14.3,"y":10.85,"z":2.9},"A2":{"depth":21.7,"totalLiquidVolume":1200,"shape":"rectangular","xDimension":8,"yDimension":8,"x":23.3,"y":73.85,"z":2.9},"B2":{"depth":21.7,"totalLiquidVolume":1200,"shape":"rectangular","xDimension":8,"yDimension":8,"x":23.3,"y":64.85,"z":2.9},"C2":{"depth":21.7,"totalLiquidVolume":1200,"shape":"rectangular","xDimension":8,"yDimension":8,"x":23.3,"y":55.85,"z":2.9},"D2":{"depth":21.7,"totalLiquidVolume":1200,"shape":"rectangular","xDimension":8,"yDimension":8,"x":23.3,"y":46.85,"z":2.9},"E2":{"depth":21.7,"totalLiquidVolume":1200,"shape":"rectangular","xDimension":8,"yDimension":8,"x":23.3,"y":37.85,"z":2.9},"F2":{"depth":21.7,"totalLiquidVolume":1200,"shape":"rectangular","xDimension":8,"yDimension":8,"x":23.3,"y":28.85,"z":2.9},"G2":{"depth":21.7,"totalLiquidVolume":1200,"shape":"rectangular","xDimension":8,"yDimension":8,"x":23.3,"y":19.85,"z":2.9},"H2":{"depth":21.7,"totalLiquidVolume":1200,"shape":"rectangular","xDimension":8,"yDimension":8,"x":23.3,"y":10.85,"z":2.9},"A3":{"depth":21.7,"totalLiquidVolume":1200,"shape":"rectangular","xDimension":8,"yDimension":8,"x":32.3,"y":73.85,"z":2.9},"B3":{"depth":21.7,"totalLiquidVolume":1200,"shape":"rectangular","xDimension":8,"yDimension":8,"x":32.3,"y":64.85,"z":2.9},"C3":{"depth":21.7,"totalLiquidVolume":1200,"shape":"rectangular","xDimension":8,"yDimension":8,"x":32.3,"y":55.85,"z":2.9},"D3":{"depth":21.7,"totalLiquidVolume":1200,"shape":"rectangular","xDimension":8,"yDimension":8,"x":32.3,"y":46.85,"z":2.9},"E3":{"depth":21.7,"totalLiquidVolume":1200,"shape":"rectangular","xDimension":8,"yDimension":8,"x":32.3,"y":37.85,"z":2.9},"F3":{"depth":21.7,"totalLiquidVolume":1200,"shape":"rectangular","xDimension":8,"yDimension":8,"x":32.3,"y":28.85,"z":2.9},"G3":{"depth":21.7,"totalLiquidVolume":1200,"shape":"rectangular","xDimension":8,"yDimension":8,"x":32.3,"y":19.85,"z":2.9},"H3":{"depth":21.7,"totalLiquidVolume":1200,"shape":"rectangular","xDimension":8,"yDimension":8,"x":32.3,"y":10.85,"z":2.9},"A4":{"depth":21.7,"totalLiquidVolume":1200,"shape":"rectangular","xDimension":8,"yDimension":8,"x":41.3,"y":73.85,"z":2.9},"B4":{"depth":21.7,"totalLiquidVolume":1200,"shape":"rectangular","xDimension":8,"yDimension":8,"x":41.3,"y":64.85,"z":2.9},"C4":{"depth":21.7,"totalLiquidVolume":1200,"shape":"rectangular","xDimension":8,"yDimension":8,"x":41.3,"y":55.85,"z":2.9},"D4":{"depth":21.7,"totalLiquidVolume":1200,"shape":"rectangular","xDimension":8,"yDimension":8,"x":41.3,"y":46.85,"z":2.9},"E4":{"depth":21.7,"totalLiquidVolume":1200,"shape":"rectangular","xDimension":8,"yDimension":8,"x":41.3,"y":37.85,"z":2.9},"F4":{"depth":21.7,"totalLiquidVolume":1200,"shape":"rectangular","xDimension":8,"yDimension":8,"x":41.3,"y":28.85,"z":2.9},"G4":{"depth":21.7,"totalLiquidVolume":1200,"shape":"rectangular","xDimension":8,"yDimension":8,"x":41.3,"y":19.85,"z":2.9},"H4":{"depth":21.7,"totalLiquidVolume":1200,"shape":"rectangular","xDimension":8,"yDimension":8,"x":41.3,"y":10.85,"z":2.9},"A5":{"depth":21.7,"totalLiquidVolume":1200,"shape":"rectangular","xDimension":8,"yDimension":8,"x":50.3,"y":73.85,"z":2.9},"B5":{"depth":21.7,"totalLiquidVolume":1200,"shape":"rectangular","xDimension":8,"yDimension":8,"x":50.3,"y":64.85,"z":2.9},"C5":{"depth":21.7,"totalLiquidVolume":1200,"shape":"rectangular","xDimension":8,"yDimension":8,"x":50.3,"y":55.85,"z":2.9},"D5":{"depth":21.7,"totalLiquidVolume":1200,"shape":"rectangular","xDimension":8,"yDimension":8,"x":50.3,"y":46.85,"z":2.9},"E5":{"depth":21.7,"totalLiquidVolume":1200,"shape":"rectangular","xDimension":8,"yDimension":8,"x":50.3,"y":37.85,"z":2.9},"F5":{"depth":21.7,"totalLiquidVolume":1200,"shape":"rectangular","xDimension":8,"yDimension":8,"x":50.3,"y":28.85,"z":2.9},"G5":{"depth":21.7,"totalLiquidVolume":1200,"shape":"rectangular","xDimension":8,"yDimension":8,"x":50.3,"y":19.85,"z":2.9},"H5":{"depth":21.7,"totalLiquidVolume":1200,"shape":"rectangular","xDimension":8,"yDimension":8,"x":50.3,"y":10.85,"z":2.9},"A6":{"depth":21.7,"totalLiquidVolume":1200,"shape":"rectangular","xDimension":8,"yDimension":8,"x":59.3,"y":73.85,"z":2.9},"B6":{"depth":21.7,"totalLiquidVolume":1200,"shape":"rectangular","xDimension":8,"yDimension":8,"x":59.3,"y":64.85,"z":2.9},"C6":{"depth":21.7,"totalLiquidVolume":1200,"shape":"rectangular","xDimension":8,"yDimension":8,"x":59.3,"y":55.85,"z":2.9},"D6":{"depth":21.7,"totalLiquidVolume":1200,"shape":"rectangular","xDimension":8,"yDimension":8,"x":59.3,"y":46.85,"z":2.9},"E6":{"depth":21.7,"totalLiquidVolume":1200,"shape":"rectangular","xDimension":8,"yDimension":8,"x":59.3,"y":37.85,"z":2.9},"F6":{"depth":21.7,"totalLiquidVolume":1200,"shape":"rectangular","xDimension":8,"yDimension":8,"x":59.3,"y":28.85,"z":2.9},"G6":{"depth":21.7,"totalLiquidVolume":1200,"shape":"rectangular","xDimension":8,"yDimension":8,"x":59.3,"y":19.85,"z":2.9},"H6":{"depth":21.7,"totalLiquidVolume":1200,"shape":"rectangular","xDimension":8,"yDimension":8,"x":59.3,"y":10.85,"z":2.9},"A7":{"depth":21.7,"totalLiquidVolume":1200,"shape":"rectangular","xDimension":8,"yDimension":8,"x":68.3,"y":73.85,"z":2.9},"B7":{"depth":21.7,"totalLiquidVolume":1200,"shape":"rectangular","xDimension":8,"yDimension":8,"x":68.3,"y":64.85,"z":2.9},"C7":{"depth":21.7,"totalLiquidVolume":1200,"shape":"rectangular","xDimension":8,"yDimension":8,"x":68.3,"y":55.85,"z":2.9},"D7":{"depth":21.7,"totalLiquidVolume":1200,"shape":"rectangular","xDimension":8,"yDimension":8,"x":68.3,"y":46.85,"z":2.9},"E7":{"depth":21.7,"totalLiquidVolume":1200,"shape":"rectangular","xDimension":8,"yDimension":8,"x":68.3,"y":37.85,"z":2.9},"F7":{"depth":21.7,"totalLiquidVolume":1200,"shape":"rectangular","xDimension":8,"yDimension":8,"x":68.3,"y":28.85,"z":2.9},"G7":{"depth":21.7,"totalLiquidVolume":1200,"shape":"rectangular","xDimension":8,"yDimension":8,"x":68.3,"y":19.85,"z":2.9},"H7":{"depth":21.7,"totalLiquidVolume":1200,"shape":"rectangular","xDimension":8,"yDimension":8,"x":68.3,"y":10.85,"z":2.9},"A8":{"depth":21.7,"totalLiquidVolume":1200,"shape":"rectangular","xDimension":8,"yDimension":8,"x":77.3,"y":73.85,"z":2.9},"B8":{"depth":21.7,"totalLiquidVolume":1200,"shape":"rectangular","xDimension":8,"yDimension":8,"x":77.3,"y":64.85,"z":2.9},"C8":{"depth":21.7,"totalLiquidVolume":1200,"shape":"rectangular","xDimension":8,"yDimension":8,"x":77.3,"y":55.85,"z":2.9},"D8":{"depth":21.7,"totalLiquidVolume":1200,"shape":"rectangular","xDimension":8,"yDimension":8,"x":77.3,"y":46.85,"z":2.9},"E8":{"depth":21.7,"totalLiquidVolume":1200,"shape":"rectangular","xDimension":8,"yDimension":8,"x":77.3,"y":37.85,"z":2.9},"F8":{"depth":21.7,"totalLiquidVolume":1200,"shape":"rectangular","xDimension":8,"yDimension":8,"x":77.3,"y":28.85,"z":2.9},"G8":{"depth":21.7,"totalLiquidVolume":1200,"shape":"rectangular","xDimension":8,"yDimension":8,"x":77.3,"y":19.85,"z":2.9},"H8":{"depth":21.7,"totalLiquidVolume":1200,"shape":"rectangular","xDimension":8,"yDimension":8,"x":77.3,"y":10.85,"z":2.9},"A9":{"depth":21.7,"totalLiquidVolume":1200,"shape":"rectangular","xDimension":8,"yDimension":8,"x":86.3,"y":73.85,"z":2.9},"B9":{"depth":21.7,"totalLiquidVolume":1200,"shape":"rectangular","xDimension":8,"yDimension":8,"x":86.3,"y":64.85,"z":2.9},"C9":{"depth":21.7,"totalLiquidVolume":1200,"shape":"rectangular","xDimension":8,"yDimension":8,"x":86.3,"y":55.85,"z":2.9},"D9":{"depth":21.7,"totalLiquidVolume":1200,"shape":"rectangular","xDimension":8,"yDimension":8,"x":86.3,"y":46.85,"z":2.9},"E9":{"depth":21.7,"totalLiquidVolume":1200,"shape":"rectangular","xDimension":8,"yDimension":8,"x":86.3,"y":37.85,"z":2.9},"F9":{"depth":21.7,"totalLiquidVolume":1200,"shape":"rectangular","xDimension":8,"yDimension":8,"x":86.3,"y":28.85,"z":2.9},"G9":{"depth":21.7,"totalLiquidVolume":1200,"shape":"rectangular","xDimension":8,"yDimension":8,"x":86.3,"y":19.85,"z":2.9},"H9":{"depth":21.7,"totalLiquidVolume":1200,"shape":"rectangular","xDimension":8,"yDimension":8,"x":86.3,"y":10.85,"z":2.9},"A10":{"depth":21.7,"totalLiquidVolume":1200,"shape":"rectangular","xDimension":8,"yDimension":8,"x":95.3,"y":73.85,"z":2.9},"B10":{"depth":21.7,"totalLiquidVolume":1200,"shape":"rectangular","xDimension":8,"yDimension":8,"x":95.3,"y":64.85,"z":2.9},"C10":{"depth":21.7,"totalLiquidVolume":1200,"shape":"rectangular","xDimension":8,"yDimension":8,"x":95.3,"y":55.85,"z":2.9},"D10":{"depth":21.7,"totalLiquidVolume":1200,"shape":"rectangular","xDimension":8,"yDimension":8,"x":95.3,"y":46.85,"z":2.9},"E10":{"depth":21.7,"totalLiquidVolume":1200,"shape":"rectangular","xDimension":8,"yDimension":8,"x":95.3,"y":37.85,"z":2.9},"F10":{"depth":21.7,"totalLiquidVolume":1200,"shape":"rectangular","xDimension":8,"yDimension":8,"x":95.3,"y":28.85,"z":2.9},"G10":{"depth":21.7,"totalLiquidVolume":1200,"shape":"rectangular","xDimension":8,"yDimension":8,"x":95.3,"y":19.85,"z":2.9},"H10":{"depth":21.7,"totalLiquidVolume":1200,"shape":"rectangular","xDimension":8,"yDimension":8,"x":95.3,"y":10.85,"z":2.9},"A11":{"depth":21.7,"totalLiquidVolume":1200,"shape":"rectangular","xDimension":8,"yDimension":8,"x":104.3,"y":73.85,"z":2.9},"B11":{"depth":21.7,"totalLiquidVolume":1200,"shape":"rectangular","xDimension":8,"yDimension":8,"x":104.3,"y":64.85,"z":2.9},"C11":{"depth":21.7,"totalLiquidVolume":1200,"shape":"rectangular","xDimension":8,"yDimension":8,"x":104.3,"y":55.85,"z":2.9},"D11":{"depth":21.7,"totalLiquidVolume":1200,"shape":"rectangular","xDimension":8,"yDimension":8,"x":104.3,"y":46.85,"z":2.9},"E11":{"depth":21.7,"totalLiquidVolume":1200,"shape":"rectangular","xDimension":8,"yDimension":8,"x":104.3,"y":37.85,"z":2.9},"F11":{"depth":21.7,"totalLiquidVolume":1200,"shape":"rectangular","xDimension":8,"yDimension":8,"x":104.3,"y":28.85,"z":2.9},"G11":{"depth":21.7,"totalLiquidVolume":1200,"shape":"rectangular","xDimension":8,"yDimension":8,"x":104.3,"y":19.85,"z":2.9},"H11":{"depth":21.7,"totalLiquidVolume":1200,"shape":"rectangular","xDimension":8,"yDimension":8,"x":104.3,"y":10.85,"z":2.9},"A12":{"depth":21.7,"totalLiquidVolume":1200,"shape":"rectangular","xDimension":8,"yDimension":8,"x":113.3,"y":73.85,"z":2.9},"B12":{"depth":21.7,"totalLiquidVolume":1200,"shape":"rectangular","xDimension":8,"yDimension":8,"x":113.3,"y":64.85,"z":2.9},"C12":{"depth":21.7,"totalLiquidVolume":1200,"shape":"rectangular","xDimension":8,"yDimension":8,"x":113.3,"y":55.85,"z":2.9},"D12":{"depth":21.7,"totalLiquidVolume":1200,"shape":"rectangular","xDimension":8,"yDimension":8,"x":113.3,"y":46.85,"z":2.9},"E12":{"depth":21.7,"totalLiquidVolume":1200,"shape":"rectangular","xDimension":8,"yDimension":8,"x":113.3,"y":37.85,"z":2.9},"F12":{"depth":21.7,"totalLiquidVolume":1200,"shape":"rectangular","xDimension":8,"yDimension":8,"x":113.3,"y":28.85,"z":2.9},"G12":{"depth":21.7,"totalLiquidVolume":1200,"shape":"rectangular","xDimension":8,"yDimension":8,"x":113.3,"y":19.85,"z":2.9},"H12":{"depth":21.7,"totalLiquidVolume":1200,"shape":"rectangular","xDimension":8,"yDimension":8,"x":113.3,"y":10.85,"z":2.9}},"groups":[{"metadata":{"wellBottomShape":"u"},"wells":["A1","B1","C1","D1","E1","F1","G1","H1","A2","B2","C2","D2","E2","F2","G2","H2","A3","B3","C3","D3","E3","F3","G3","H3","A4","B4","C4","D4","E4","F4","G4","H4","A5","B5","C5","D5","E5","F5","G5","H5","A6","B6","C6","D6","E6","F6","G6","H6","A7","B7","C7","D7","E7","F7","G7","H7","A8","B8","C8","D8","E8","F8","G8","H8","A9","B9","C9","D9","E9","F9","G9","H9","A10","B10","C10","D10","E10","F10","G10","H10","A11","B11","C11","D11","E11","F11","G11","H11","A12","B12","C12","D12","E12","F12","G12","H12"]}],"parameters":{"format":"irregular","quirks":[],"isTiprack":false,"isMagneticModuleCompatible":false,"loadName":"bayomics_96_wellplate_1200ul"},"namespace":"custom_beta","version":1,"schemaVersion":2,"cornerOffsetFromSlot":{"x":0,"y":0,"z":0}}"""
USER_LIQUID_LABWARE_DEF = json.loads(USER_LIQUID_LABWARE_DEF_JSON)
USER_LIQUID_LABWARE_LABEL = LABWARE_DEF.get('metadata', {}).get('displayName', 'test labware')
USER_LIQUID_LABWARE_DIMENSIONS = LABWARE_DEF.get('wells', {}).get('A1', {}).get('yDimension')

"""
User Arguments, 定义用户参数
1. USER_LIQUID - slot1 试剂所有列及配比容量(ul)
2. SERIAL_DEVICE_INDEX 设备端口号所在索引 (一般不需要变，假如机器连接多个串口设备可能需要改动)
4. LIQUID_CAL_VALUE 每个孔板试剂的安全液体容量警戒值（ul）
4. LIQUID_REAL_VALUE 每个孔板试剂的真实值（ul）
5. SINGLE_VOLUME 每次吸取的固定容量 (ul)
6. DARK_DURATION 遮光孵化时间 (min)
7. HEAT_TEMP_GAP 加热设备真实与预期的差值 （摄氏度）
8. USE_MODE 运行模式 调试模式会缩短运行时间
9. WORK_POSITION_FOR_Z Z 轴到达的工作位置
10. WORK_POSITION_FOR_Y Y 轴到达工作位置
"""
LIQUID_CAL_RANGE = 880
LIQUID_REAL_RANGE = 1000

USER_LIQUID = {
    "Ac": {1: LIQUID_REAL_RANGE, 2: LIQUID_REAL_RANGE},
    "Rd": {3: LIQUID_REAL_RANGE},
    "Tf": {4: LIQUID_REAL_RANGE},
    "Et": {5: LIQUID_REAL_RANGE},
    "Ds": {6: LIQUID_REAL_RANGE},
    "Wa": {7: LIQUID_REAL_RANGE, 8: LIQUID_REAL_RANGE, 9: LIQUID_REAL_RANGE},
    "Sample": {1: LIQUID_REAL_RANGE},  # 35
    "Enzyme": {1: LIQUID_REAL_RANGE}  # 20
}  # BayOmics Liquid loaded on slot1, 每种液体定义所在列及孔板容量(Ul)

SERIAL_DEVICE_INDEX = 1
SINGLE_VOLUME = 20
DARK_DURATION = 1

USER_PRESSURE = {
    "step1": {"pressure": 0.02, "duration": 60},
    "step2": {"pressure": 0.06, "duration": 60},
    "step3": {"pressure": 0.02, "duration": 180},
    "step4": {"pressure": 0.03, "duration": 60},
    "step5": {"pressure": 0.03, "duration": 60},
    "step6_1": {"pressure": 0.04, "duration": 20},
    "step6_2": {"pressure": 0.04, "duration": 20},
    "step6_3": {"pressure": 0.04, "duration": 60},
    "step7": {"pressure": 0.05, "duration": 40},
    "step8_1": {"pressure": 0.04, "duration": 16},
    "step8_2": {"pressure": 0.02, "duration": 5},
    "step9": {"pressure": 0.04, "duration": 100},
    "step10": {"pressure": 0.07, "duration": 60},
    "step11": {"pressure": 0.07, "duration": 60},
    "step12": {"pressure": 0.03, "duration": 60},

}

HEAT_SETTING = [{"temperature": 70, "time": 10 * 60}, {"temperature": 52, "time": 60 * 60}]

"""
import serial driver
"""


class DropMethod(Enum):
    DoNotDrop = 1  # 不丢针管
    DropAtLast = 2  # 最后再丢针管
    DoNotPickUp = 5
    DropForAColumn = 3  # 完成一列移液后丢针管
    DropOnceUse = 4  # 一旦使用就丢针管


class UserMode(Enum):
    Debugging = 1
    Running = 2


class BayOmicsLib:
    @classmethod
    def get_com_list(cls):
        port_list = serial.tools.list_ports.comports()
        return port_list

    def __init__(self, baud, protocol):
        self.baud = baud
        self.port = None
        self.device = None
        self.protocol: protocol_api.ProtocolContext = protocol
        self.simulate = True
        self.led_virtual = True
        self.verify = True
        self.explain_flag = True
        self.WORK_POSITION_FOR_Z = "8E3EFFFF"
        self.WORK_POSITION_FOR_Y = "BAD0FFFF"
        self.user_mode = UserMode.Running
        self.HEAT_TEMP_GAP = 2

    def opentrons_delay(self, times):
        self.protocol.delay(times)

    def print_f(self, msg):
        self.protocol.comment(msg)

    def build_connection(self, simulating, led_virtual, user_pwd):
        res = BayOmicsLib.get_com_list()
        self.simulate = simulating
        self.print_f("=" * 5 + "PORT LIST" + "=" * 5)
        for index, p in enumerate(res):
            self.print_f(f"{index + 1} >>{p.device}")
        # select = input("Select Port Number(输入串口号对应的数字):")
        select = str(SERIAL_DEVICE_INDEX)
        if self.port is None:
            if len(res) == 0 or self.simulate is True:
                self.port = "None"
                self.device = None
                return
            else:
                self.port = res[int(select.strip()) - 1].device
        self.device = serial.Serial(self.port, self.baud, parity=serial.PARITY_NONE, stopbits=serial.STOPBITS_ONE,
                                    bytesize=serial.EIGHTBITS, timeout=1)
        if self.device.isOpen():
            self.print_f(f"{self.port} Opened! \n")
        # settings
        self.device.bytesize = serial.EIGHTBITS  # 数据位 8
        self.device.parity = serial.PARITY_NONE  # 无校验
        self.device.stopbits = serial.STOPBITS_ONE  # 停止位 1
        # init

        auth = _auth(user_pwd)
        if auth:
            self.led_virtual = led_virtual
        else:
            self.led_virtual = True

    def close_device(self):
        """
        close com
        :return:
        """
        self.device.close()
        self.print_f(f"{self.port} Closed! \n")

    def calc_crc(self, string):
        data = bytearray.fromhex(string)
        crc = 0xFFFF
        for pos in data:
            crc ^= pos
            for i in range(8):
                if ((crc & 1) != 0):
                    crc >>= 1
                    crc ^= 0xA001
                else:
                    crc >>= 1
        crc_data = hex(((crc & 0xFF) << 8) + (crc >> 8))[2:]
        for i in range(4 - len(crc_data)):
            crc_data = '0' + crc_data
        return crc_data.upper()

    def send_and_read(self, send, delay=0.1, ReceiveBuffer=100):
        """
        send code and read buffer
        :param send:
        :param delay:
        :param ReceiveBuffer:
        :return:
        """
        if self.device is None:
            return
        if type(send) is not bytes:
            send = (send + "\r\n").encode('utf-8')
        self.device.flushInput()
        self.device.flushOutput()
        self.device.write(send)
        self.opentrons_delay(delay)
        data = self.device.read(ReceiveBuffer)
        data = codecs.encode(data, "hex")
        return data.decode('utf-8')

    def get_tm_data(self, code: str, is_without_crc=False):
        """
        get buffer
        :param code:
        :return:
        """
        # byte_array = codecs.decode(code.encode(), 'hex')
        if is_without_crc:
            code = code + self.calc_crc(code)
        byte_array = bytes.fromhex(code)
        data = self.send_and_read(byte_array)
        return data.upper()

    def _format_hex(self, value: int):
        value = hex(value)[2:]
        for i in range(4 - len(value)):
            value = '0' + value
        return value

    def _verify_responds(self, responds, words):
        """
        验证返回值
         :param responds: 返回值
        :param words: words in responds ?
        :return:
        """
        if not self.verify:
            return
        if responds == "":
            result = False
        else:
            if words.upper() in responds.upper():
                result = True
            else:
                result = False
        assert result, f"{words} don't in {responds}"

    def send_to_device(self, _send: str, label, verify=None, is_without_crc=True):
        """
        send code
        :param _send:
        :param label:  explain
        :param verify:
        :param is_without_crc:
        :return:
        """
        _send = _send.replace(" ", "").strip()
        if self.simulate:
            ret = ""
        else:
            ret = self.get_tm_data(_send, is_without_crc=is_without_crc)
        verify = _send if verify is None else verify
        if not self.simulate:
            self._verify_responds(ret, verify)
        if self.explain_flag:
            self.print_f(label + f": {ret}")
        return ret

    def set_led_rounds(self, _round: int, initial_point=True):
        """
        :param _round:
        :param initial_point:
        display screen number
        :return:
        """
        if _round > 9999:
            _round = 9999
        self.print_f(f"Setting Round {_round}...")
        # 设置小数点 - 0
        if initial_point:
            self.send_to_device("010600100000", "Set Led Point")
        # set round
        set_number = self._format_hex(_round)
        self.send_to_device(f"01060007{set_number}", "Set Led Value")

    def set_led_virtual_value(self):
        """
        设置虚拟值
        :return:
        """
        self.send_to_device("01 06 00 00 00 5F", "Set Virtual 1")
        self.send_to_device("01 06 00 01 00 5F", "Set Virtual 2")
        self.send_to_device("01 06 00 02 00 5F", "Set Virtual 3")
        self.send_to_device("01 06 00 03 00 5F", "Set Virtual 4")

    def set_pressure_off(self):
        """
        正压不加载，两通阀门闭合
        :return:
        """
        self.send_to_device("0406000A0000", "Set Pressure 0")
        self.send_to_device("030500410000", "Set Pressure Off")
        if not self.led_virtual:
            self.set_led_pressure_value(0)

    def read_pressure(self):
        """
        读取气压值
        """
        data = self.send_to_device("04 04 00 00 00 01", "Read Pressure", verify="")
        value = data[6:10]
        value = int(value, 16) / 1000
        value_mpa = 0.125 * value - 0.124
        return value_mpa

    def set_motor_enable(self, y=True, z=True, r=True):
        """
        set motor enable
        :param y:
        :param z:
        :param r:
        :return:
        """
        if y:
            self.send_to_device("060600000101", "Set Y Axis Enable")
        if z:
            self.send_to_device("070600000101", "Set Z Axis Enable")
        if r:
            self.send_to_device("050600000101", "Set R Axis Enable")

    def judge_pos(self, run_times: int, axis: str, target_pos: str, judge_method="Interrupt"):
        """
        判断是否到达指定位置
        :param run_times:
        :param axis:
        :param target_pos:
        :param judge_method:
        :return:
        """
        if not self.simulate:
            for i in range(run_times):
                self.opentrons_delay(1)
                current_pos = self.get_axis_position(axis)
                if current_pos == target_pos:
                    return True
                if i == run_times - 1:
                    if judge_method == "Interrupt":
                        raise RuntimeError("Move timeout")
                    else:
                        return False
        else:
            pass

    def set_axis_speed(self, axis: str):
        """
        设置速度
        :param axis:
        :return:
        """
        if "y" in axis:
            self.send_to_device("06 10 00 03 00 02 04 00 00 44 FA", "Set Y Axis Speed", verify="061000030002")  # 44 7A
        elif 'z' in axis:
            self.send_to_device("071000030002048000463B", "Set Z Axis Speed", verify="071000030002")  # 8000463B
        elif "r" in axis:
            pass

    def home(self, y=True, z=True, r=True):
        """
        home motor, move axis to the default position
        :param y:
        :param z:
        :param r:
        :return:
        """
        if r:
            self.send_to_device("05 10 00 03 00 02 04 00 00 42 48", "Set Speed 192000", verify="")
            self.send_to_device("05 10 00 01 00 02 04 FD 9C FF FF", "Move Relative", verify="")
            self.send_to_device("050600000302", "Set R Axis Relative Position Mode", verify="")
            self.opentrons_delay(5)
            self.send_to_device("050600000300", "Set R Axis Speed Mode", verify="")
            self.judge_pos(60, 'r', "00000000")
        if z:
            self.set_axis_speed('z')
            self.send_to_device("07 10 00 01 00 02 04 AC FF FF FF", "move relative", verify="")
            self.send_to_device("070600000302", "Set Z Axis Relative Position Mode", verify="")
            self.opentrons_delay(0.5)
            self.send_to_device("070600000300", "Set Z Axis Speed Mode", verify="")
            self.judge_pos(30, 'z', "00000000")
        if y:
            self.set_axis_speed('y')
            self.send_to_device("06 10 00 01 00 02 04 BA 24 FF FF", "Move Relative", verify="061000010002")
            self.send_to_device("060600000302", "Set Y Axis Relative Position Mode", verify="")
            self.opentrons_delay(1)
            self.send_to_device("060600000300", "Set Y Axis Speed Mode", verify="")
            self.judge_pos(30, 'y', "00000000")

    def init_motors(self, y=True, z=True, r=True):
        """
        初始话电机速度，各轴初始化工作位置
        :param y:
        :param z:
        :param r:
        :return:
        """
        self.set_motor_enable()
        self.set_axis_speed("y")
        self.set_axis_speed("z")

    def set_temperature_controller_off(self):
        """
        关闭温控器
        :return:
        """
        self.send_to_device("0206001B0001", "Set Temperature Controller Off")

    def set_lights(self, light):
        """
        开启等带
        :param light:
        :return:
        """
        self.print_f("Set rail lights ON" if light else "Set rail lights OFF")
        self.protocol.set_rail_lights(light)

    def init_device(self):
        """
        init device, ready for work
        :return:
        """
        self.init_led()
        self.set_pressure_off()
        self.init_motors()
        self.set_temperature_controller_off()
        self.home()
        self.protocol.comment("Set rail lights ON")
        self.set_lights(True)

    def close_lid(self):
        """
        close_lid
        :return:
        """
        self.send_to_device("050600000301", "Set R Axis Speed Mode", verify="")  # 位置模式
        self.send_to_device("05 10 00 01 00 02 04 F7 D4 FF FF", "close lid", verify="051000010002")
        self.judge_pos(60, "r", "F7D4FFFF")

    def dark_incubation(self, dark_time: int, pressure=None, duration=None, pressure_setting=None):
        """
        遮光
        """
        self.set_lights(False)
        self.close_lid()
        self.opentrons_delay(dark_time)
        self.home(y=False, z=False)
        self.set_lights(True)
        if pressure_setting is None and pressure:
            if self.user_mode == UserMode.Debugging:
                duration = 1
            self.set_pressure(pressure, duration)
        elif pressure_setting is not None:
            pressure = pressure_setting["pressure"]
            duration = pressure_setting["duration"]
            if self.user_mode == UserMode.Debugging:
                duration = 1
            self.set_pressure(pressure, duration)
        else:
            assert False, 'Can not find pressure setting'

    def heat_device(self, temp: float):
        """
        heat
        :param temp: 浮点，一位小数
        :return:
        """
        temp = int(temp * 10)
        temp = self._format_hex(temp)
        self.send_to_device(f"02060000{temp}", f"Set Temperature {temp}")
        # 开始加热
        self.send_to_device("02 06 00 1B 00 00", "Start to heat")

    def stop_heat(self):
        """
        停止加热
        :return:
        """
        self.send_to_device("02 06 00 1B 00 01", "Stop heating")

    def read_setting_temperature(self):
        """
        获取设定的温度
        :return:
        """
        data = self.send_to_device("02 03 00 4B 00 01", "Read Setting Temperature", verify="0203")
        if not self.simulate:
            data_value = data[6:10]
            temp = int(data_value, 16)
            return float(int(temp) / 10)
        else:
            return 0

    def read_real_temperature(self):
        """
        获取真实的温度
        :return:
        """
        data = self.send_to_device("02 03 00 4A 00 01", "Read Real Temperature", verify="0203")
        if not self.simulate:
            data_value = data[6:10]
            temp = int(data_value, 16)
            return float(int(temp) / 10)
        else:
            return 0

    def compare_temperature(self, tolerance):
        """
        compare difference between temp
        :param tolerance: 允许的差异
        :return:
        """
        for i in range(600):
            self.opentrons_delay(1)
            setting_temp = self.read_setting_temperature()
            real_temp = self.read_real_temperature()
            if abs(setting_temp - real_temp) < tolerance:
                break
        raise TimeoutError("reach time out")

    def read_heat_status(self):
        """
        读取加温状态
        :return:
        """
        data = self.send_to_device("02 03 00 4D 00 01", "Read Heat Controller Status", verify="0203")
        return data

    def heat_incubation(self, heat_list: list):
        """
        加温孵化
        1. 关盖
        2. 根据heat_list配置加温曲线
        :param heat_list:
        :return:
        """
        self.close_lid()
        for heat_setting in heat_list:
            temp = heat_setting["temperature"]
            keep_times = heat_setting["time"]
            if temp == 0:
                self.stop_heat()
            else:
                self.heat_device(temp)
            for i in range(keep_times):
                self.opentrons_delay(0.3)
                self.set_led_rounds(i + 1)
            # compare temp
            if temp != 0:
                set_temp = self.read_setting_temperature()
                real_temp = self.read_real_temperature()
                assert abs(set_temp - real_temp) < self.HEAT_TEMP_GAP, "heat device fail"
        self.stop_heat()
        self.home(y=False, z=False)

    def move_y(self, position: str):
        """
        移动y
        :param position:
        :return:
        """
        for i in range(3):
            self.send_to_device("060600000301", "Set Y Axis Position Mode", verify="")
            self.send_to_device(f"06100001000204{position}", f"Move Y To {position}", verify="061000010002")
            ret = self.judge_pos(30, 'y', position, judge_method="others")
            if ret:
                return 0
        if not self.simulate:
            raise TimeoutError("Move Y Time Out")

    def move_z(self, position: str):
        """
        移动z
        :param position:
        :return:
        """
        for i in range(3):
            self.send_to_device("070600000301", "Set Z Axis Position Mode", verify="")
            self.send_to_device(f"07100001000204{position}", f"Move Z To {position}", verify="071000010002")
            ret = self.judge_pos(30, 'z', position, judge_method="others")
            if ret:
                return 0
        if not self.simulate:
            raise TimeoutError("Move Z Time Out")

    def get_axis_position(self, axis: str):
        """
        get position
        :param axis: x, y, z
        :return:
        """
        if 'R' in axis.upper():
            data = self.send_to_device("05 04 00 02 00 02", "Get R Axis Position", verify="")
        elif "Z" in axis.upper():
            data = self.send_to_device("07 04 00 02 00 02", "Get Z Axis Position", verify="")
        elif "Y" in axis.upper():
            data = self.send_to_device("06 04 00 02 00 02", "Get Y Axis Position", verify="")
        else:
            raise ValueError("Can't find Axis")
        return (data[6:14].upper())

    def set_led_pressure_value(self, value: int):
        """
        set display pressure value
        :param value: pressure (Kpa)
        :return:
        """
        print(f"Setting Led Display")
        # 设置小数点 - 0
        if not self.led_virtual:
            self.send_to_device("010600100003", "Set Led Point")
            # set round
            set_number = self._format_hex(value)
            self.send_to_device(f"01060007{set_number}", "Set Led Value")

    def set_pressure(self, pressure, duration):
        """
        施加压力过程
        :param pressure: 压力值（MPa）
        :param duration: 持续时间 （s）
        :return:
        """
        self.move_to_work_position()
        if self.user_mode == UserMode.Debugging:
            pressure_kpa = 0
        else:
            pressure_kpa = pressure * 1000
        # voltage_mv = int(((pressure_kpa + 123.75) / 124.75) * 1000)  # * 10000
        voltage_mv = int(pressure_kpa * 10)
        voltage_mv_string = self._format_hex(voltage_mv)
        self.send_to_device("03 05 00 41 FF 00", "Pressure Open")  # 阀门开启
        self.send_to_device(f"0406000A{voltage_mv_string}", f"Set Pressure {pressure} Mpa", verify="")  # 设置正压
        self.opentrons_delay(1)
        pressure = self.read_pressure()

        # 显示压力值
        _pressure = int(pressure * 1000)
        if _pressure <= 0:
            _pressure = 0
        self.set_led_pressure_value(_pressure)
        self.opentrons_delay(duration)
        # 关闭压力
        self.set_pressure_off()
        # 释放work position
        self.release_work_position()

    def move_to_work_position(self, home=False):
        """
        y轴和z轴移动到工作点
        :return:
        """
        if home:
            self.home()
        self.move_y(self.WORK_POSITION_FOR_Y)
        self.move_z(self.WORK_POSITION_FOR_Z)

    def release_work_position(self):
        """
        释放work position, ready home
        :return:
        """
        self.move_z("00000000")
        self.home(r=False)

    def init_led(self):
        """
        set led
        :return:
        """
        if self.led_virtual:
            self.set_led_virtual_value()

    def release_device(self):
        """
        释放设备
        :return:
        """
        self.print_f("实验完成，正在关闭设备...")
        self.home()
        self.set_pressure_off()
        self.set_temperature_controller_off()
        self.set_led_rounds(0)
        self.close_device()
        self.set_lights(False)


def transfer_user_liquid(pipette: protocol_api.InstrumentContext, liquid_labware: protocol_api.Labware,
                         customer_labware: protocol_api.labware, customer_labware_pos: str, liquid_name: str,
                         volume: float, move_location: protocol_api.Labware, pick_up_location: protocol_api.Labware,
                         pick_up=False, drop=False):
    """
    移液&加压
    :param pipette:
    :param liquid_labware:
    :param customer_labware:
    :param customer_labware_pos:
    :param liquid_name:
    :param volume:
    :param move_location:
    :param pick_up_location:
    :param drop:
    :param pick_up:
    :return:
    """

    def _drop_tip():
        if not drop:
            pass
        else:
            pipette.move_to(move_location['A1'].top(z=50))
            pipette.drop_tip()

    def _pick_up():
        pipette.move_to(pick_up_location['A1'].top(z=50))
        pipette.pick_up_tip()

    aspirate_flag = False
    if pick_up:
        _pick_up()
    liquid: dict = USER_LIQUID[liquid_name]
    _trans_times = int(volume / SINGLE_VOLUME)
    _trans_last_volume = (volume % SINGLE_VOLUME)

    for i in range(_trans_times):
        if liquid_name != "Sample" and liquid_name != "Enzyme":
            for key, value in liquid.items():
                if value > (LIQUID_REAL_RANGE - LIQUID_CAL_RANGE):
                    pipette.aspirate(SINGLE_VOLUME, liquid_labware[f"A{key}"])
                    USER_LIQUID[liquid_name][key] -= SINGLE_VOLUME
                    aspirate_flag = True
                    break
        else:
            pipette.aspirate(SINGLE_VOLUME, liquid_labware[customer_labware_pos])
            aspirate_flag = True
        assert aspirate_flag, "Aspirate liquid fail"
        pipette.dispense(SINGLE_VOLUME, customer_labware[customer_labware_pos])
        pipette.blow_out(customer_labware[customer_labware_pos])
        if liquid_name == 'Ac' or liquid_name == 'Et':
            pipette.touch_tip(speed=30)

    if _trans_last_volume > 0:
        if liquid_name != "Sample" and liquid_name != "Enzyme":
            for key, value in liquid.items():
                if value > (LIQUID_REAL_RANGE - LIQUID_CAL_RANGE):
                    pipette.aspirate(_trans_last_volume, liquid_labware[f"A{key}"])
                    USER_LIQUID[liquid_name][key] -= _trans_last_volume
                    aspirate_flag = True
                    break
        else:
            pipette.aspirate(_trans_last_volume, liquid_labware[customer_labware_pos])
            aspirate_flag = True
        assert aspirate_flag, "Aspirate liquid fail"
        pipette.dispense(_trans_last_volume, customer_labware[customer_labware_pos])
        pipette.blow_out(customer_labware[customer_labware_pos])
        if liquid_name == 'Ac' or liquid_name == 'Et':
            pipette.touch_tip(speed=30)
    _drop_tip()


def transform_round(pipette: protocol_api.InstrumentContext, liquid_labware: protocol_api.Labware,
                    customer_labware: protocol_api.labware, liquid_name: str, sample_counts: int,
                    volume: float, move_location: protocol_api.Labware, serial_device: BayOmicsLib,
                    pick_up_location: protocol_api.Labware,
                    pressure=None, duration=30, drop_method: DropMethod = DropMethod.DropAtLast, protocol=None,
                    pressure_setting: dict = None):
    """
    执行加液，正压，一个流程
    :param pipette:
    :param liquid_labware:
    :param customer_labware:
    :param liquid_name:
    :param sample_counts:
    :param volume:
    :param move_location:
    :param serial_device:
    :param pressure:
    :param duration:
    :param drop_method:
    :param protocol:
    :param pressure_setting:
    :param pick_up_location:
    :return:
    """
    for i in range(int(sample_counts / 8)):
        if drop_method == DropMethod.DropAtLast:
            drop = True if i == (int(sample_counts / 8) - 1) else False
            pick_up = True if i == 0 else False
        elif drop_method == DropMethod.DropForAColumn:
            drop = True
            pick_up = True
        elif drop_method == DropMethod.DoNotDrop:
            pick_up = True if i == 0 else False
            drop = False
        elif drop_method == DropMethod.DoNotPickUp:
            pick_up = False
            drop = True if i == (int(sample_counts / 8) - 1) else False
        else:
            drop = True
            pick_up = True
        transfer_user_liquid(pipette, liquid_labware, customer_labware, f'A{i + 1}', liquid_name, volume, move_location,
                             pick_up_location, pick_up=pick_up, drop=drop)
    if drop_method == DropMethod.DoNotDrop:
        pipette.move_to(move_location['A1'].top(z=50))
    if pressure_setting is None and pressure:
        if serial_device.user_mode == UserMode.Debugging:
            duration = 1
        serial_device.set_pressure(pressure, duration)
    elif pressure_setting is not None:
        pressure = pressure_setting["pressure"]
        duration = pressure_setting["duration"]
        if serial_device.user_mode == UserMode.Debugging:
            duration = 1
        serial_device.set_pressure(pressure, duration)
    else:
        assert False, 'Can not find pressure setting'

    if protocol is not None:
        protocol.pause(f"USER_LIQUID: {USER_LIQUID}")


"""
用户密码
"""


def _auth(pwd: int):
    """
    用户鉴权
    :param pwd: 0 ~ 999999
    :return:
    """
    md5_object = hashlib.md5()  # 创建MD5对象
    saved_pwd = "2a123be7c92297bf4ebf9eeeb69d3e98"  # 当前临时密码 342566
    user_pwd = str(pwd).strip().encode('utf-8')
    md5_object.update(user_pwd)
    user_pwd = md5_object.hexdigest()
    if user_pwd == saved_pwd:
        return True
    else:
        return False


"""
增加用户参数
"""


def add_parameters(parameters: protocol_api.Parameters):
    """
    :param parameters:
    :return:
    """
    parameters.add_int(
        variable_name="user_pwd",
        display_name="管理员密码",
        description="部分功能需要管理员密码才能生效",
        default=999999,
        minimum=0,
        maximum=999999,
        unit=""
    )

    parameters.add_bool(
        variable_name="led_virtual",
        display_name="LED虚拟值显示",
        description="是否按虚拟值显示当前LED",
        default=True
    )

    parameters.add_bool(
        variable_name="pause_selection",
        display_name="暂停观察",
        description="是否运行过程中等待操作员操作",
        default=True
    )

    parameters.add_int(
        variable_name="sample_number",
        display_name="样品数量",
        description="实验的样品数量，最大不能超过96",
        default=8,
        minimum=8,
        maximum=96,
        unit="个"
    )


# protocol run function
def run(protocol: protocol_api.ProtocolContext):
    """
    :param protocol:
    :return:
    """
    """Opentrons 加载移液器，耗材
    1. load pipette
    2. load labware
    3. loda module
    4. 定义中间move to location
    """
    # labware
    tiprack_1 = protocol.load_labware(
        "opentrons_96_tiprack_20ul", location="4"
    )
    tiprack_2 = protocol.load_labware(
        "opentrons_96_tiprack_20ul", location="5"
    )
    # tiprack_3 = protocol.load_labware(
    #     "opentrons_96_tiprack_20ul", location="6"
    # )

    move_to_location = tiprack_2

    # pipettes
    left_pipette = protocol.load_instrument("p20_multi_gen2", mount="left",
                                            tip_racks=[tiprack_1, tiprack_2])
    sample_liquid = protocol.load_labware('armadillo_96_wellplate_200ul_pcr_full_skirt', location='2')  # 样本

    # customer labware
    customer_liquid = protocol.load_labware_from_definition(USER_LIQUID_LABWARE_DEF, USER_LIQUID_SLOT,
                                                            USER_LIQUID_LABWARE_LABEL)  # 试剂
    user_labware = protocol.load_labware_from_definition(
        LABWARE_DEF,
        USER_LABWARE_SLOT,
        LABWARE_LABEL,
    )
    # TD module
    temp_mod = protocol.load_module(
        module_name="temperature module gen2", location="3"
    )
    temp_adapter = temp_mod.load_adapter("opentrons_96_well_aluminum_block")
    enzyme_liquid = temp_adapter.load_labware("armadillo_96_wellplate_200ul_pcr_full_skirt")
    # parameters
    simulating = protocol.is_simulating()
    sample_counts = protocol.params.sample_number
    led_virtual = protocol.params.led_virtual
    user_pwd = protocol.params.user_pwd
    pause_selection = protocol.params.pause_selection
    """
    检查参数
    """
    verificaiton_value = sample_counts % 8
    assert verificaiton_value == 0, 'sample counts should be multiples of 8 (样本数不是8的倍数)'

    """一、连接串口
    1. 建立设备连接
    2. 初始化LED屏幕
    """
    protocol.comment(">>>>>1.连接串口<<<<<")
    serial_module = BayOmicsLib(19200, protocol)
    serial_module.build_connection(simulating, led_virtual, user_pwd)
    serial_module.user_mode = UserMode.Debugging

    if serial_module.device is not None:
        protocol.comment(">>>>>2.初始化设备<<<<<")
        """二、初始化
        1. 使能电机，初始化速度和复位
        2. 关闭加压
        3. 关闭温度控制器
        4. 开启灯带
        5. 开启TD
        """
        serial_module.init_device()
        if serial_module.user_mode == UserMode.Debugging:
            pass
        else:
            temp_mod.start_set_temperature(celsius=4)

        protocol.comment(">>>>>3.开始实验<<<<<")
        _protocol = None
        """三、执行实验步骤(移液&正压)
        1. 向样本处理器中加入60ul试剂 Ac
        """
        transform_round(left_pipette, customer_liquid, user_labware, "Ac", sample_counts, 60, move_to_location,
                        serial_module, enzyme_liquid, protocol=_protocol, pressure_setting=USER_PRESSURE['step1'])
        """三、执行实验步骤(移液&正压)
        2. 向样本处理器中加入60ul试剂 Wa
        """
        transform_round(left_pipette, customer_liquid, user_labware, "Wa", sample_counts, 60, move_to_location,
                        serial_module, enzyme_liquid, protocol=_protocol, pressure_setting=USER_PRESSURE['step2'])
        if pause_selection:
            protocol.pause("观察试剂过柱情况")
        """三、执行实验步骤(移液&正压)
        3. 向样本处理器中加入30ul样本
        """
        transform_round(left_pipette, sample_liquid, user_labware, "Sample", sample_counts, 30, move_to_location,
                        serial_module, enzyme_liquid, drop_method=DropMethod.DropForAColumn, protocol=_protocol,
                        pressure_setting=USER_PRESSURE['step3'])
        """三、执行实验步骤(移液&正压)
        4. 向样本处理器中加入30ul试剂 Wa
        """
        transform_round(left_pipette, customer_liquid, user_labware, "Wa", sample_counts, 30, move_to_location,
                        serial_module, enzyme_liquid, protocol=_protocol, pressure_setting=USER_PRESSURE['step4'])
        """三、执行实验步骤(移液&正压)
        5. 向样本处理器中加入30ul试剂 Ac
        """
        transform_round(left_pipette, customer_liquid, user_labware, "Ac", sample_counts, 30, move_to_location,
                        serial_module, enzyme_liquid, protocol=_protocol, pressure_setting=USER_PRESSURE['step5'])
        """三、执行实验步骤(移液&正压)
        6. 向样本处理器中加入30ul试剂 Rd - 再加入30ul Rd -  遮光孵化 - 正压
        """
        transform_round(left_pipette, customer_liquid, user_labware, "Rd", sample_counts, 30, move_to_location,
                        serial_module, enzyme_liquid, protocol=_protocol, drop_method=DropMethod.DoNotDrop,
                        pressure_setting=USER_PRESSURE['step6_1'])
        transform_round(left_pipette, customer_liquid, user_labware, "Rd", sample_counts, 30, move_to_location,
                        serial_module, enzyme_liquid, protocol=_protocol, drop_method=DropMethod.DoNotPickUp,
                        pressure_setting=USER_PRESSURE['step6_2'])
        if pause_selection:
            protocol.pause("开始做避光孵化，请确认...")
        if serial_module.user_mode == UserMode.Debugging:
            serial_module.dark_incubation(1, pressure_setting=USER_PRESSURE['step6_3'])
        else:
            serial_module.dark_incubation(DARK_DURATION * 60, pressure_setting=USER_PRESSURE['step6_3'])
        """三、执行实验步骤(移液&正压)
        7. 向样本处理器中加入30ul试剂 Ds
        """
        transform_round(left_pipette, customer_liquid, user_labware, "Ds", sample_counts, 30, move_to_location,
                        serial_module, enzyme_liquid, protocol=_protocol, pressure_setting=USER_PRESSURE['step7'])
        """三、执行实验步骤(移液&正压)
        8. 向样本处理器中加入13ul + 5ul酶
        """
        transform_round(left_pipette, enzyme_liquid, user_labware, "Enzyme", sample_counts, 13, move_to_location,
                        serial_module, enzyme_liquid, protocol=_protocol, drop_method=DropMethod.DoNotDrop,
                        pressure_setting=USER_PRESSURE['step8_1'])
        transform_round(left_pipette, enzyme_liquid, user_labware, "Enzyme", sample_counts, 5, move_to_location,
                        serial_module, enzyme_liquid, protocol=_protocol, drop_method=DropMethod.DoNotPickUp,
                        pressure_setting=USER_PRESSURE['step8_2'])
        # close td
        if serial_module.user_mode == UserMode.Debugging:
            pass
        else:
            temp_mod.deactivate()
        # 保温
        if serial_module.user_mode == UserMode.Debugging:
            serial_module.heat_incubation([{"temperature": 52, "time": 120}])
        else:
            serial_module.heat_incubation(HEAT_SETTING)
        """三、执行实验步骤(移液&正压)
        9. 向样本处理器中加入60ul试剂 Tf
        """
        transform_round(left_pipette, customer_liquid, user_labware, "Tf", sample_counts, 60, move_to_location,
                        serial_module, enzyme_liquid, pressure_setting=USER_PRESSURE['step9'])
        """三、执行实验步骤(移液&正压)
        10. 向样本处理器中加入60ul试剂 Wa
        """
        transform_round(left_pipette, customer_liquid, user_labware, "Wa", sample_counts, 60, move_to_location,
                        serial_module, enzyme_liquid, drop_method=DropMethod.DoNotDrop, pressure_setting=USER_PRESSURE['step10'])
        """三、执行实验步骤(移液&正压)
        11. 向样本处理器中加入60ul试剂 Wa
        """
        transform_round(left_pipette, customer_liquid, user_labware, "Wa", sample_counts, 60, move_to_location,
                        serial_module, enzyme_liquid, drop_method=DropMethod.DoNotPickUp, pressure_setting=USER_PRESSURE['step11'])
        protocol.pause("请更换收集板...")
        """三、执行实验步骤(移液&正压)
        12. 向样本处理器中加入60ul试剂 Et
        """
        transform_round(left_pipette, customer_liquid, user_labware, "Et", sample_counts, 60, move_to_location,
                        serial_module, enzyme_liquid, pressure_setting=USER_PRESSURE['step12'])
        protocol.pause("实验结束...恢复即将复位设备...")

        protocol.comment(">>>>>4.实验结束<<<<<")
        serial_module.release_device()
