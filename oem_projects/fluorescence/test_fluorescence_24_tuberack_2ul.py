import json
from opentrons import protocol_api, types

TEST_LABWARE_SLOT = '5'

RATE = 0.25  # % of default speeds

PIPETTE_MOUNT = 'left'
PIPETTE_NAME = 'flex_8channel_1000'

TIPRACK_SLOT = '11'
TIPRACK_LOADNAME = 'opentrons_96_tiprack_1000ul'
LABWARE_DEF_JSON = """{"ordering":[["A1","B1","C1","D1","E1","F1","G1","H1"],["A2","B2","C2","D2"],["A3","B3","C3"]],
    "brand":{"brand":"Fluorescence","brandId":["Fluorescence"]},
    "metadata":{"displayName":"Fluorescence_tuberack_2ul","displayCategory":"tubeRack","displayVolumeUnits":"µL","tags":[]},
    "dimensions":{"xDimension":127.75,"yDimension":85.5,"zDimension":124.35},
    "wells":{"A1":{"depth":117.5,"totalLiquidVolume":2,"shape":"circular","diameter":9,"x":69,"y":77.6,"z":6.85},
    "B1":{"depth":117.5,"totalLiquidVolume":2,"shape":"circular","diameter":9,"x":69,"y":67.6,"z":6.85},
    "C1":{"depth":117.5,"totalLiquidVolume":2,"shape":"circular","diameter":9,"x":69,"y":57.6,"z":6.85},
    "D1":{"depth":117.5,"totalLiquidVolume":2,"shape":"circular","diameter":9,"x":69,"y":47.6,"z":6.85},
    "E1":{"depth":117.5,"totalLiquidVolume":2,"shape":"circular","diameter":9,"x":69,"y":37.6,"z":6.85},
    "F1":{"depth":117.5,"totalLiquidVolume":2,"shape":"circular","diameter":9,"x":69,"y":27.6,"z":6.85},
    "G1":{"depth":117.5,"totalLiquidVolume":2,"shape":"circular","diameter":9,"x":69,"y":17.6,"z":6.85},
    "H1":{"depth":117.5,"totalLiquidVolume":2,"shape":"circular","diameter":9,"x":69,"y":7.6,"z":6.85},
    "A2":{"depth":117.5,"totalLiquidVolume":2,"shape":"circular","diameter":8.7,"x":84,"y":67.84,"z":6.85},
    "B2":{"depth":117.5,"totalLiquidVolume":2,"shape":"circular","diameter":8.7,"x":84,"y":48.56,"z":6.85},
    "C2":{"depth":117.5,"totalLiquidVolume":2,"shape":"circular","diameter":8.7,"x":84,"y":29.28,"z":6.85},
    "D2":{"depth":117.5,"totalLiquidVolume":2,"shape":"circular","diameter":8.7,"x":84,"y":10,"z":6.85},
    "A3":{"depth":117.5,"totalLiquidVolume":2,"shape":"circular","diameter":14.9,"x":109,"y":70,"z":6.85},
    "B3":{"depth":117.5,"totalLiquidVolume":2,"shape":"circular","diameter":14.9,"x":109,"y":45,"z":6.85},
    "C3":{"depth":117.5,"totalLiquidVolume":2,"shape":"circular","diameter":14.9,"x":109,"y":20,"z":6.85}},
    "groups":[{"brand":{"brand":"Fluorescence","brandId":["Fluorescence"]},
    "metadata":{"wellBottomShape":"u","displayCategory":"tubeRack"},
    "wells":["A1","B1","C1","D1","E1","F1","G1","H1","A2","B2","C2","D2","A3","B3","C3"]}],
    "parameters":{"format":"irregular","quirks":[],"isTiprack":false,"isMagneticModuleCompatible":false,"loadName":"fluorescence_24_tuberack_2ul"},
    "namespace":"custom_beta","version":1,"schemaVersion":2,"cornerOffsetFromSlot":{"x":0,"y":0,"z":0}}"""



LABWARE_DEF = json.loads(LABWARE_DEF_JSON)
LABWARE_LABEL = LABWARE_DEF.get('metadata', {}).get(
    'displayName', 'test labware')
LABWARE_DIMENSIONS = LABWARE_DEF.get('wells', {}).get('A1', {}).get('yDimension')

# requirements
requirements = {"robotType": "Flex", "apiLevel": "2.18"}


def run(protocol: protocol_api.ProtocolContext):
    tiprack = protocol.load_labware(TIPRACK_LOADNAME, TIPRACK_SLOT)
    pipette = protocol.load_instrument(
        PIPETTE_NAME, PIPETTE_MOUNT, tip_racks=[tiprack])

    reservoir = protocol.load_labware("nest_12_reservoir_15ml", "D2")

    test_labware = protocol.load_labware_from_definition(
        LABWARE_DEF,
        TEST_LABWARE_SLOT,
        LABWARE_LABEL,
    )

    pipette.pick_up_tip()

    pipette.aspirate(20, reservoir['A1'])
    pipette.dispense(20, test_labware['A1'])

    pipette.aspirate(20, reservoir['A1'])
    pipette.dispense(20, test_labware['B2'])

    pipette.aspirate(20, reservoir['A1'])
    pipette.dispense(20, test_labware['C3'])

    pipette.home()

    pipette.return_tip()
