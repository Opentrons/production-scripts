import json
from opentrons import protocol_api, types

# requirements
requirements = {"robotType": "Flex", "apiLevel": "2.18"}

TEST_VALUE = {"value": 5}


def update_value(protocol: protocol_api.protocol_context):
    TEST_VALUE['value'] = TEST_VALUE['value'] + 1
    protocol.comment(TEST_VALUE['value'])


def run(protocol: protocol_api.ProtocolContext):
    update_value(protocol)
