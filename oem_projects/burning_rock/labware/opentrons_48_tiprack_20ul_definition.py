import json

DEFINITION = """{"ordering": [["A1", "B1", "C1", "D1", "E1", "F1", "G1", "H1"], ["A2", "B2", "C2", "D2", "E2", "F2", "G2", "H2"],
              ["A3", "B3", "C3", "D3", "E3", "F3", "G3", "H3"], ["A4", "B4", "C4", "D4", "E4", "F4", "G4", "H4"],
              ["A5", "B5", "C5", "D5", "E5", "F5", "G5", "H5"], ["A6", "B6", "C6", "D6", "E6", "F6", "G6", "H6"]],
 "brand": {"brand": "Opentrons", "brandId": []},
 "metadata": {"displayName": "Opentrons 48 Tip Rack 20 µL", "displayCategory": "tipRack", "displayVolumeUnits": "µL",
              "tags": []}, "dimensions": {"xDimension": 127.76, "yDimension": 85.48, "zDimension": 64.69}, "wells": {
    "A1": {"depth": 39.2, "totalLiquidVolume": 20, "shape": "circular", "diameter": 3.27, "x": 71.9, "y": 74.24,
           "z": 25.49},
    "B1": {"depth": 39.2, "totalLiquidVolume": 20, "shape": "circular", "diameter": 3.27, "x": 71.9, "y": 65.24,
           "z": 25.49},
    "C1": {"depth": 39.2, "totalLiquidVolume": 20, "shape": "circular", "diameter": 3.27, "x": 71.9, "y": 56.24,
           "z": 25.49},
    "D1": {"depth": 39.2, "totalLiquidVolume": 20, "shape": "circular", "diameter": 3.27, "x": 71.9, "y": 47.24,
           "z": 25.49},
    "E1": {"depth": 39.2, "totalLiquidVolume": 20, "shape": "circular", "diameter": 3.27, "x": 71.9, "y": 38.24,
           "z": 25.49},
    "F1": {"depth": 39.2, "totalLiquidVolume": 20, "shape": "circular", "diameter": 3.27, "x": 71.9, "y": 29.24,
           "z": 25.49},
    "G1": {"depth": 39.2, "totalLiquidVolume": 20, "shape": "circular", "diameter": 3.27, "x": 71.9, "y": 20.24,
           "z": 25.49},
    "H1": {"depth": 39.2, "totalLiquidVolume": 20, "shape": "circular", "diameter": 3.27, "x": 71.9, "y": 11.24,
           "z": 25.49},
    "A2": {"depth": 39.2, "totalLiquidVolume": 20, "shape": "circular", "diameter": 3.27, "x": 80.9, "y": 74.24,
           "z": 25.49},
    "B2": {"depth": 39.2, "totalLiquidVolume": 20, "shape": "circular", "diameter": 3.27, "x": 80.9, "y": 65.24,
           "z": 25.49},
    "C2": {"depth": 39.2, "totalLiquidVolume": 20, "shape": "circular", "diameter": 3.27, "x": 80.9, "y": 56.24,
           "z": 25.49},
    "D2": {"depth": 39.2, "totalLiquidVolume": 20, "shape": "circular", "diameter": 3.27, "x": 80.9, "y": 47.24,
           "z": 25.49},
    "E2": {"depth": 39.2, "totalLiquidVolume": 20, "shape": "circular", "diameter": 3.27, "x": 80.9, "y": 38.24,
           "z": 25.49},
    "F2": {"depth": 39.2, "totalLiquidVolume": 20, "shape": "circular", "diameter": 3.27, "x": 80.9, "y": 29.24,
           "z": 25.49},
    "G2": {"depth": 39.2, "totalLiquidVolume": 20, "shape": "circular", "diameter": 3.27, "x": 80.9, "y": 20.24,
           "z": 25.49},
    "H2": {"depth": 39.2, "totalLiquidVolume": 20, "shape": "circular", "diameter": 3.27, "x": 80.9, "y": 11.24,
           "z": 25.49},
    "A3": {"depth": 39.2, "totalLiquidVolume": 20, "shape": "circular", "diameter": 3.27, "x": 89.9, "y": 74.24,
           "z": 25.49},
    "B3": {"depth": 39.2, "totalLiquidVolume": 20, "shape": "circular", "diameter": 3.27, "x": 89.9, "y": 65.24,
           "z": 25.49},
    "C3": {"depth": 39.2, "totalLiquidVolume": 20, "shape": "circular", "diameter": 3.27, "x": 89.9, "y": 56.24,
           "z": 25.49},
    "D3": {"depth": 39.2, "totalLiquidVolume": 20, "shape": "circular", "diameter": 3.27, "x": 89.9, "y": 47.24,
           "z": 25.49},
    "E3": {"depth": 39.2, "totalLiquidVolume": 20, "shape": "circular", "diameter": 3.27, "x": 89.9, "y": 38.24,
           "z": 25.49},
    "F3": {"depth": 39.2, "totalLiquidVolume": 20, "shape": "circular", "diameter": 3.27, "x": 89.9, "y": 29.24,
           "z": 25.49},
    "G3": {"depth": 39.2, "totalLiquidVolume": 20, "shape": "circular", "diameter": 3.27, "x": 89.9, "y": 20.24,
           "z": 25.49},
    "H3": {"depth": 39.2, "totalLiquidVolume": 20, "shape": "circular", "diameter": 3.27, "x": 89.9, "y": 11.24,
           "z": 25.49},
    "A4": {"depth": 39.2, "totalLiquidVolume": 20, "shape": "circular", "diameter": 3.27, "x": 98.9, "y": 74.24,
           "z": 25.49},
    "B4": {"depth": 39.2, "totalLiquidVolume": 20, "shape": "circular", "diameter": 3.27, "x": 98.9, "y": 65.24,
           "z": 25.49},
    "C4": {"depth": 39.2, "totalLiquidVolume": 20, "shape": "circular", "diameter": 3.27, "x": 98.9, "y": 56.24,
           "z": 25.49},
    "D4": {"depth": 39.2, "totalLiquidVolume": 20, "shape": "circular", "diameter": 3.27, "x": 98.9, "y": 47.24,
           "z": 25.49},
    "E4": {"depth": 39.2, "totalLiquidVolume": 20, "shape": "circular", "diameter": 3.27, "x": 98.9, "y": 38.24,
           "z": 25.49},
    "F4": {"depth": 39.2, "totalLiquidVolume": 20, "shape": "circular", "diameter": 3.27, "x": 98.9, "y": 29.24,
           "z": 25.49},
    "G4": {"depth": 39.2, "totalLiquidVolume": 20, "shape": "circular", "diameter": 3.27, "x": 98.9, "y": 20.24,
           "z": 25.49},
    "H4": {"depth": 39.2, "totalLiquidVolume": 20, "shape": "circular", "diameter": 3.27, "x": 98.9, "y": 11.24,
           "z": 25.49},
    "A5": {"depth": 39.2, "totalLiquidVolume": 20, "shape": "circular", "diameter": 3.27, "x": 107.9, "y": 74.24,
           "z": 25.49},
    "B5": {"depth": 39.2, "totalLiquidVolume": 20, "shape": "circular", "diameter": 3.27, "x": 107.9, "y": 65.24,
           "z": 25.49},
    "C5": {"depth": 39.2, "totalLiquidVolume": 20, "shape": "circular", "diameter": 3.27, "x": 107.9, "y": 56.24,
           "z": 25.49},
    "D5": {"depth": 39.2, "totalLiquidVolume": 20, "shape": "circular", "diameter": 3.27, "x": 107.9, "y": 47.24,
           "z": 25.49},
    "E5": {"depth": 39.2, "totalLiquidVolume": 20, "shape": "circular", "diameter": 3.27, "x": 107.9, "y": 38.24,
           "z": 25.49},
    "F5": {"depth": 39.2, "totalLiquidVolume": 20, "shape": "circular", "diameter": 3.27, "x": 107.9, "y": 29.24,
           "z": 25.49},
    "G5": {"depth": 39.2, "totalLiquidVolume": 20, "shape": "circular", "diameter": 3.27, "x": 107.9, "y": 20.24,
           "z": 25.49},
    "H5": {"depth": 39.2, "totalLiquidVolume": 20, "shape": "circular", "diameter": 3.27, "x": 107.9, "y": 11.24,
           "z": 25.49},
    "A6": {"depth": 39.2, "totalLiquidVolume": 20, "shape": "circular", "diameter": 3.27, "x": 116.9, "y": 74.24,
           "z": 25.49},
    "B6": {"depth": 39.2, "totalLiquidVolume": 20, "shape": "circular", "diameter": 3.27, "x": 116.9, "y": 65.24,
           "z": 25.49},
    "C6": {"depth": 39.2, "totalLiquidVolume": 20, "shape": "circular", "diameter": 3.27, "x": 116.9, "y": 56.24,
           "z": 25.49},
    "D6": {"depth": 39.2, "totalLiquidVolume": 20, "shape": "circular", "diameter": 3.27, "x": 116.9, "y": 47.24,
           "z": 25.49},
    "E6": {"depth": 39.2, "totalLiquidVolume": 20, "shape": "circular", "diameter": 3.27, "x": 116.9, "y": 38.24,
           "z": 25.49},
    "F6": {"depth": 39.2, "totalLiquidVolume": 20, "shape": "circular", "diameter": 3.27, "x": 116.9, "y": 29.24,
           "z": 25.49},
    "G6": {"depth": 39.2, "totalLiquidVolume": 20, "shape": "circular", "diameter": 3.27, "x": 116.9, "y": 20.24,
           "z": 25.49},
    "H6": {"depth": 39.2, "totalLiquidVolume": 20, "shape": "circular", "diameter": 3.27, "x": 116.9, "y": 11.24,
           "z": 25.49}}, "groups": [{"metadata": {},
                                     "wells": ["A1", "B1", "C1", "D1", "E1", "F1", "G1", "H1", "A2", "B2", "C2", "D2",
                                               "E2", "F2", "G2", "H2", "A3", "B3", "C3", "D3", "E3", "F3", "G3", "H3",
                                               "A4", "B4", "C4", "D4", "E4", "F4", "G4", "H4", "A5", "B5", "C5", "D5",
                                               "E5", "F5", "G5", "H5", "A6", "B6", "C6", "D6", "E6", "F6", "G6",
                                               "H6"]}],
 "parameters": {"format": "irregular", "quirks": [], "isTiprack": true, "tipLength": 39.2,
                "isMagneticModuleCompatible": false, "loadName": "opentrons_48_tiprack_20ul"},
 "namespace": "custom_beta", "version": 1, "schemaVersion": 2, "cornerOffsetFromSlot": {"x": 0, "y": 0, "z": 0}}"""

TIPRACK_DEF = json.loads(DEFINITION)