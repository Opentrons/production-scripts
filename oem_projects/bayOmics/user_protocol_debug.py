from opentrons import protocol_api
import json

# metadata
metadata = {
    "protocolName": "__BayOmicsTemperatureModuleUserDebug__V1.5.0",
    "author": "Andy <opentrons@example.com>",
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
    # parameters
    simulating = protocol.is_simulating()
    sample_counts = protocol.params.sample_number
    led_virtual = protocol.params.led_virtual
    user_pwd = protocol.params.user_pwd
    pause_selection = protocol.params.pause_selection

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
    if not simulating:
        from BayOmicsLib import BayOmicsLib
        from BayOmicsLib import UserMode, DropMethod, transform_round, USER_PRESSURE, DARK_DURATION, HEAT_SETTING

    """
    检查参数
    """
    verificaiton_value = sample_counts % 8
    assert verificaiton_value == 0, 'sample counts should be multiples of 8 (样本数不是8的倍数)'

    """一、连接串口
    1. 建立设备连接
    2. 初始化LED屏幕
    """
    # if not simulating:

    def _pick_up():
        left_pipette.move_to(enzyme_liquid['A1'].top(z=50))
        left_pipette.pick_up_tip()
    _pick_up()
    left_pipette.aspirate(20, customer_liquid['A1'])
    left_pipette.dispense(20, sample_liquid['A1'])
    left_pipette.drop_tip()
    _pick_up()
    left_pipette.aspirate(20, customer_liquid['A1'])
    left_pipette.dispense(20, enzyme_liquid['A1'])
    left_pipette.drop_tip()
    _pick_up()
    left_pipette.aspirate(20, customer_liquid['A1'])
    left_pipette.dispense(20, user_labware['A1'])
    left_pipette.drop_tip()
    # else:
    #     # fake process 示例流程为了初始化校准,保存校准位置
    #     left_pipette.pick_up_tip()
    #     left_pipette.aspirate(20, customer_liquid['A1'])
    #     left_pipette.dispense(20, sample_liquid['A1'])
    #     left_pipette.drop_tip()
    #     left_pipette.pick_up_tip()
    #     left_pipette.aspirate(20, customer_liquid['A1'])
    #     left_pipette.dispense(20, enzyme_liquid['A1'])
    #     left_pipette.drop_tip()
    #     left_pipette.pick_up_tip()
    #     left_pipette.aspirate(20, customer_liquid['A1'])
    #     left_pipette.dispense(20, user_labware['A1'])
    #     left_pipette.drop_tip()
