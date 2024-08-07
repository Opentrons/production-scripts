NEW_SERIAL_NUMBER ="OT2RS20240523003"


from opentrons import protocol_api
import os

requirements = {"robotType": "OT-2", "apiLevel": "2.14"}


def run(protocol: protocol_api.ProtocolContext):


    protocol.comment(f"Run this protocol to set your OT-2's serial number to {NEW_SERIAL_NUMBER}")

    with open("/var/serial", "w") as serial_number_file:
        serial_number_file.write(NEW_SERIAL_NUMBER + "\n")
    with open("/etc/machine-info", "w") as serial_number_file:
        serial_number_file.write(f"PRETTY_HOSTNAME={NEW_SERIAL_NUMBER}\n")
    with open("/etc/hostname", "w") as serial_number_file:
        serial_number_file.write(NEW_SERIAL_NUMBER + "\n")
    os.sync()

    protocol.comment("Serial number reset complete.  Please restart your OT-2.")
