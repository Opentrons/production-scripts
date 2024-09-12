import json
from opentrons import protocol_api, types
import time
import serial
import serial.tools.list_ports
import codecs

LABWARE_DEF_JSON = """{"ordering":[["A1","B1","C1","D1","E1","F1","G1","H1"],["A2","B2","C2","D2"],["A3","B3","C3"]],
    "brand":{"brand":"Fluorescence","brandId":["Fluorescence"]},
    "metadata":{"displayName":"Fluorescence_tuberack_2ul","displayCategory":"tubeRack","displayVolumeUnits":"µL","tags":[]},
    "dimensions":{"xDimension":143.9,"yDimension":105.8,"zDimension":97.69},
    "wells":{"A1":{"depth":15.9,"totalLiquidVolume":2000,"shape":"circular","diameter":5.3,"x":60.2,"y":74.33,"z":82.76},
    "B1":{"depth":15.9,"totalLiquidVolume":2,"shape":"circular","diameter":5.3,"x":60.2,"y":65.33,"z":79.1},
    "C1":{"depth":15.9,"totalLiquidVolume":2,"shape":"circular","diameter":5.3,"x":60.2,"y":56.33,"z":79.1},
    "D1":{"depth":15.9,"totalLiquidVolume":2,"shape":"circular","diameter":5.3,"x":60.2,"y":47.33,"z":79.1},
    "E1":{"depth":15.9,"totalLiquidVolume":2,"shape":"circular","diameter":5.3,"x":60.2,"y":38.33,"z":79.1},
    "F1":{"depth":15.9,"totalLiquidVolume":2,"shape":"circular","diameter":5.3,"x":60.2,"y":29.33,"z":79.1},
    "G1":{"depth":15.9,"totalLiquidVolume":2,"shape":"circular","diameter":5.3,"x":60.2,"y":20.33,"z":79.1},
    "H1":{"depth":15.9,"totalLiquidVolume":2,"shape":"circular","diameter":5.3,"x":60.2,"y":11.33,"z":79.1},
    "A2":{"depth":42.14,"totalLiquidVolume":2,"shape":"circular","diameter":8.7,"x":90.7,"y":69.75,"z":52.86},
    "B2":{"depth":42.14,"totalLiquidVolume":2,"shape":"circular","diameter":8.7,"x":90.7,"y":52.02,"z":52.86},
    "C2":{"depth":42.14,"totalLiquidVolume":2,"shape":"circular","diameter":8.7,"x":90.7,"y":34.29,"z":52.86},
    "D2":{"depth":42.14,"totalLiquidVolume":2,"shape":"circular","diameter":8.7,"x":90.7,"y":16.56,"z":52.86},
    "A3":{"depth":59,"totalLiquidVolume":2,"shape":"circular","diameter":14.9,"x":122.3,"y":64.78,"z":61},
    "B3":{"depth":95,"totalLiquidVolume":2,"shape":"circular","diameter":14.9,"x":122.3,"y":41.78,"z":25},
    "C3":{"depth":95,"totalLiquidVolume":2,"shape":"circular","diameter":14.9,"x":122.3,"y":18.78,"z":25}},
    "groups":[{"brand":{"brand":"Fluorescence","brandId":["Fluorescence"]},
    "metadata":{"wellBottomShape":"u","displayCategory":"tubeRack"},
    "wells":["A1","B1","C1","D1","E1","F1","G1","H1","A2","B2","C2","D2","A3","B3","C3"]}],
    "parameters":{"format":"irregular","quirks":[],"isTiprack":false,"isMagneticModuleCompatible":false,"loadName":"fluorescence_24_tuberack_2ul"},
    "namespace":"custom_beta","version":1,"schemaVersion":2,"cornerOffsetFromSlot":{"x":0,"y":0,"z":0}}"""

TIP_8_DEF_JSON = """{"ordering": [["A1", "B1", "C1", "D1", "E1", "F1", "G1", "H1"], ["A2", "B2", "C2", "D2", "E2", "F2", "G2", "H2"],
              ["A3", "B3", "C3", "D3", "E3", "F3", "G3", "H3"], ["A4", "B4", "C4", "D4", "E4", "F4", "G4", "H4"],
              ["A5", "B5", "C5", "D5", "E5", "F5", "G5", "H5"]], "brand": {"brand": "8Tip", "brandId": ["xx"]},
 "metadata": {"displayName": "8Tip 40 Well Plate 200 µL", "displayCategory": "wellPlate", "displayVolumeUnits": "µL",
              "tags": []}, "dimensions": {"xDimension": 150, "yDimension": 85.48, "zDimension": 82.5}, "wells": {
    "A1": {"depth": 15, "totalLiquidVolume": 200, "shape": "circular", "diameter": 5.3, "x": 26, "y": 74, "z": 67.5},
    "B1": {"depth": 15, "totalLiquidVolume": 200, "shape": "circular", "diameter": 5.3, "x": 26, "y": 65, "z": 67.5},
    "C1": {"depth": 15, "totalLiquidVolume": 200, "shape": "circular", "diameter": 5.3, "x": 26, "y": 56, "z": 67.5},
    "D1": {"depth": 15, "totalLiquidVolume": 200, "shape": "circular", "diameter": 5.3, "x": 26, "y": 47, "z": 67.5},
    "E1": {"depth": 15, "totalLiquidVolume": 200, "shape": "circular", "diameter": 5.3, "x": 26, "y": 38, "z": 67.5},
    "F1": {"depth": 15, "totalLiquidVolume": 200, "shape": "circular", "diameter": 5.3, "x": 26, "y": 29, "z": 67.5},
    "G1": {"depth": 15, "totalLiquidVolume": 200, "shape": "circular", "diameter": 5.3, "x": 26, "y": 20, "z": 67.5},
    "H1": {"depth": 15, "totalLiquidVolume": 200, "shape": "circular", "diameter": 5.3, "x": 26, "y": 11, "z": 67.5},
    "A2": {"depth": 15, "totalLiquidVolume": 200, "shape": "circular", "diameter": 5.3, "x": 54, "y": 74, "z": 67.5},
    "B2": {"depth": 15, "totalLiquidVolume": 200, "shape": "circular", "diameter": 5.3, "x": 54, "y": 65, "z": 67.5},
    "C2": {"depth": 15, "totalLiquidVolume": 200, "shape": "circular", "diameter": 5.3, "x": 54, "y": 56, "z": 67.5},
    "D2": {"depth": 15, "totalLiquidVolume": 200, "shape": "circular", "diameter": 5.3, "x": 54, "y": 47, "z": 67.5},
    "E2": {"depth": 15, "totalLiquidVolume": 200, "shape": "circular", "diameter": 5.3, "x": 54, "y": 38, "z": 67.5},
    "F2": {"depth": 15, "totalLiquidVolume": 200, "shape": "circular", "diameter": 5.3, "x": 54, "y": 29, "z": 67.5},
    "G2": {"depth": 15, "totalLiquidVolume": 200, "shape": "circular", "diameter": 5.3, "x": 54, "y": 20, "z": 67.5},
    "H2": {"depth": 15, "totalLiquidVolume": 200, "shape": "circular", "diameter": 5.3, "x": 54, "y": 11, "z": 67.5},
    "A3": {"depth": 15, "totalLiquidVolume": 200, "shape": "circular", "diameter": 5.3, "x": 82, "y": 74, "z": 67.5},
    "B3": {"depth": 15, "totalLiquidVolume": 200, "shape": "circular", "diameter": 5.3, "x": 82, "y": 65, "z": 67.5},
    "C3": {"depth": 15, "totalLiquidVolume": 200, "shape": "circular", "diameter": 5.3, "x": 82, "y": 56, "z": 67.5},
    "D3": {"depth": 15, "totalLiquidVolume": 200, "shape": "circular", "diameter": 5.3, "x": 82, "y": 47, "z": 67.5},
    "E3": {"depth": 15, "totalLiquidVolume": 200, "shape": "circular", "diameter": 5.3, "x": 82, "y": 38, "z": 67.5},
    "F3": {"depth": 15, "totalLiquidVolume": 200, "shape": "circular", "diameter": 5.3, "x": 82, "y": 29, "z": 67.5},
    "G3": {"depth": 15, "totalLiquidVolume": 200, "shape": "circular", "diameter": 5.3, "x": 82, "y": 20, "z": 67.5},
    "H3": {"depth": 15, "totalLiquidVolume": 200, "shape": "circular", "diameter": 5.3, "x": 82, "y": 11, "z": 67.5},
    "A4": {"depth": 15, "totalLiquidVolume": 200, "shape": "circular", "diameter": 5.3, "x": 110, "y": 74, "z": 67.5},
    "B4": {"depth": 15, "totalLiquidVolume": 200, "shape": "circular", "diameter": 5.3, "x": 110, "y": 65, "z": 67.5},
    "C4": {"depth": 15, "totalLiquidVolume": 200, "shape": "circular", "diameter": 5.3, "x": 110, "y": 56, "z": 67.5},
    "D4": {"depth": 15, "totalLiquidVolume": 200, "shape": "circular", "diameter": 5.3, "x": 110, "y": 47, "z": 67.5},
    "E4": {"depth": 15, "totalLiquidVolume": 200, "shape": "circular", "diameter": 5.3, "x": 110, "y": 38, "z": 67.5},
    "F4": {"depth": 15, "totalLiquidVolume": 200, "shape": "circular", "diameter": 5.3, "x": 110, "y": 29, "z": 67.5},
    "G4": {"depth": 15, "totalLiquidVolume": 200, "shape": "circular", "diameter": 5.3, "x": 110, "y": 20, "z": 67.5},
    "H4": {"depth": 15, "totalLiquidVolume": 200, "shape": "circular", "diameter": 5.3, "x": 110, "y": 11, "z": 67.5},
    "A5": {"depth": 15, "totalLiquidVolume": 200, "shape": "circular", "diameter": 5.3, "x": 138, "y": 74, "z": 67.5},
    "B5": {"depth": 15, "totalLiquidVolume": 200, "shape": "circular", "diameter": 5.3, "x": 138, "y": 65, "z": 67.5},
    "C5": {"depth": 15, "totalLiquidVolume": 200, "shape": "circular", "diameter": 5.3, "x": 138, "y": 56, "z": 67.5},
    "D5": {"depth": 15, "totalLiquidVolume": 200, "shape": "circular", "diameter": 5.3, "x": 138, "y": 47, "z": 67.5},
    "E5": {"depth": 15, "totalLiquidVolume": 200, "shape": "circular", "diameter": 5.3, "x": 138, "y": 38, "z": 67.5},
    "F5": {"depth": 15, "totalLiquidVolume": 200, "shape": "circular", "diameter": 5.3, "x": 138, "y": 29, "z": 67.5},
    "G5": {"depth": 15, "totalLiquidVolume": 200, "shape": "circular", "diameter": 5.3, "x": 138, "y": 20, "z": 67.5},
    "H5": {"depth": 15, "totalLiquidVolume": 200, "shape": "circular", "diameter": 5.3, "x": 138, "y": 11, "z": 67.5}},
 "groups": [{"metadata": {"wellBottomShape": "v"},
             "wells": ["A1", "B1", "C1", "D1", "E1", "F1", "G1", "H1", "A2", "B2", "C2", "D2", "E2", "F2", "G2", "H2",
                       "A3", "B3", "C3", "D3", "E3", "F3", "G3", "H3", "A4", "B4", "C4", "D4", "E4", "F4", "G4", "H4",
                       "A5", "B5", "C5", "D5", "E5", "F5", "G5", "H5"]}],
 "parameters": {"format": "irregular", "quirks": [], "isTiprack": false, "isMagneticModuleCompatible": false,
                "loadName": "8tip_40_wellplate_200ul"}, "namespace": "custom_beta", "version": 1, "schemaVersion": 2,
 "cornerOffsetFromSlot": {"x": 0, "y": 0, "z": 0}}"""

LABWARE_DEF = json.loads(LABWARE_DEF_JSON)
LABWARE_LABEL = LABWARE_DEF.get('metadata', {}).get('displayName', 'test labware')
LABWARE_DIMENSIONS = LABWARE_DEF.get('wells', {}).get('A1', {}).get('yDimension')

TIP_8_DEF = json.loads(TIP_8_DEF_JSON)
TIP_8_LABEL = LABWARE_DEF.get('metadata', {}).get('displayName', 'test labware')
TIP_8_DIMENSIONS = LABWARE_DEF.get('wells', {}).get('A1', {}).get('yDimension')

# requirements
requirements = {"robotType": "Flex", "apiLevel": "2.18"}
metadata = {
    "protocolName": "__Fluorescence_15_Tuberack__V1.1.4",
    "author": "Name <opentrons@example.com>",
    "description": "Simple protocol to get started using the OT-2",
}


class SerialDriver:
    @classmethod
    def get_com_list(cls):
        port_list = serial.tools.list_ports.comports()
        return port_list

    def __init__(self, baud, simulating=False):
        self.baud = baud
        self.port = None
        self.device = None
        self.simulating = simulating

    def build_connection(self):
        if not self.simulating:
            res = SerialDriver.get_com_list()
            print("=" * 5 + "PORT LIST" + "=" * 5)
            for index, p in enumerate(res):
                print(f"{index + 1} >>{p.device}")
            # select = input("Select Port Number(输入串口号对应的数字):")
            select = '1'
            if self.port is None:
                self.port = res[int(select.strip()) - 1].device
            self.device = serial.Serial(self.port, self.baud, parity=serial.PARITY_NONE, stopbits=serial.STOPBITS_ONE,
                                        bytesize=serial.EIGHTBITS, timeout=1)
            if self.device.isOpen():
                print(f"{self.port} Opened! \n")
            # settings
            self.device.bytesize = serial.EIGHTBITS  # 数据位 8
            self.device.parity = serial.PARITY_NONE  # 无校验
            self.device.stopbits = serial.STOPBITS_ONE  # 停止位 1
        else:
            print("Connect Device...")

    def close_device(self):
        """
        close com
        :return:
        """
        if not self.simulating:
            self.device.close()
            print(f"{self.port} Closed! \n")
        else:
            print("Close Device")

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
        time.sleep(delay)
        data = self.device.read(ReceiveBuffer)
        data = codecs.encode(data, "hex")
        return data.decode('utf-8')

    def format_code(self, code):
        return code.replace(" ", "").strip()

    def get_data(self, code: str, delay=0.1, buffer=100):
        """
        get buffer
        :param code:
        :param delay:
        :param buffer:
        :return:
        """
        # byte_array = codecs.decode(code.encode(), 'hex')

        byte_array = bytes.fromhex(code)
        data = self.send_and_read(byte_array, delay=delay, ReceiveBuffer=buffer)
        return data.upper()

    def check_connection(self):
        """
        检查连接状态
        """
        result = self.get_data('5E 01 00 05 64')
        if self.format_code(result) == self.format_code('5E 81 00 06 00 E5'):
            print("Connect Successfully")
            return True
        else:
            raise ConnectionError("Connection fail")

    def get_fluorescence_data(self):
        """
        获取荧光原始数据
        """
        if not self.simulating:
            length = ''
            status = ''
            result = ''
            for _ in range(4):
                if length == '1E' and status == '00':
                    channels = [int(result[8:14], 16), int(result[14:20], 16), int(result[20:26], 16),
                                int(result[26:32], 16),
                                int(result[32:38], 16), int(result[38:44], 16), int(result[44:50], 16),
                                int(result[50:56], 16)]
                    return channels
                else:
                    result = self.get_data('5E 17 00 06 01 7C', delay=5, buffer=200)
                    length = result[6:8]
                    status = result[-4:-2]
            raise ValueError('Check received data error !')
        else:
            return [0, 0, 0, 0, 0, 0, 0, 0]

    def get_concentration(self, fluorescence: list) -> list:
        """
        获取浓度
        """
        k = 0.000198
        b = -0.049392
        return [round(i * k + b, 3) for i in fluorescence]


# FIXME: 当前通过tip-rack存放盖子
def remove_lid(protocol: protocol_api.ProtocolContext, labware: protocol_api.Labware, new_lid_slot: str = 'D3',
               re_load="nest_96_wellplate_200ul_flat", labware_slot='A2', labware_def=LABWARE_DEF,
               labware_lab=LABWARE_LABEL):
    # 删除位置
    del protocol.deck[new_lid_slot]
    # 夹取盖子
    protocol.move_labware(
        labware=labware,
        new_location=new_lid_slot,
        use_gripper=True,
        pick_up_offset={"x": -14, "y": 0, "z": 46},
        drop_offset={"x": 0, "y": 0, "z": -23}
    )
    # 恢复原来位置labware
    del protocol.deck[new_lid_slot]
    pcr = protocol.load_labware(re_load, new_lid_slot)
    fluorescence = protocol.load_labware_from_definition(labware_def, labware_slot, labware_lab, )
    return pcr, fluorescence


def cover_lid(protocol: protocol_api.ProtocolContext, labware: protocol_api.Labware, old_lid_slot='C1',
              new_lid_slot='A2', labware_def=LABWARE_DEF, labware_lab=LABWARE_LABEL,
              pcr='nest_96_wellplate_200ul_flat'):
    # 删除位置
    del protocol.deck[new_lid_slot]
    # 夹取盖子
    protocol.move_labware(
        labware=labware,
        new_location=new_lid_slot,
        use_gripper=True,
        pick_up_offset={"x": 0, "y": 0, "z": 15},
        drop_offset={"x": -14, "y": 0, "z": 80}
    )
    # 恢复原来位置labware
    del protocol.deck[new_lid_slot]
    pcr = protocol.load_labware(pcr, old_lid_slot)
    fluorescence = protocol.load_labware_from_definition(labware_def, new_lid_slot, labware_lab)
    return fluorescence, pcr


def move_tips(col, protocol: protocol_api.ProtocolContext, labware: protocol_api.Labware, new_slot='A2',
              labware_def=LABWARE_DEF, labware_lab=LABWARE_LABEL):
    """
    移动8连管
    """
    del protocol.deck[new_slot]

    protocol.move_labware(
        labware=labware,
        new_location=new_slot,
        use_gripper=True,
        pick_up_offset={"x": -35 + (col - 1) * 28, "y": 0, "z": 50},
        drop_offset={"x": -36, "y": 0, "z": 56}
    )

    del protocol.deck[new_slot]
    fluorescence = protocol.load_labware_from_definition(labware_def, new_slot, labware_lab, )
    return fluorescence


def remove_tips(col, protocol: protocol_api.ProtocolContext, labware: protocol_api.Labware, new_slot='A2',
                labware_def=TIP_8_DEF, labware_lab=TIP_8_LABEL):
    del protocol.deck[new_slot]

    protocol.move_labware(
        labware=labware,
        new_location=new_slot,
        use_gripper=True,
        pick_up_offset={"x": -36, "y": 0, "z": 46},
        drop_offset={"x": -35 + (col - 1) * 28, "y": 0, "z": 50}
    )

    del protocol.deck[new_slot]
    tip_8 = protocol.load_labware_from_definition(labware_def, new_slot, labware_lab, )
    return tip_8


def fluorescence_round(protocol, col, fluorescence_labware, tip_8_labware, pcr_labware, fluorescence_slot, tip_8_slot,
                       pcr_slot, serial_device, remove_lid_flag=True, recover_lid_flag=False):

    # 移除盖子
    if remove_lid_flag:
        pcr_labware, fluorescence_labware = remove_lid(protocol, fluorescence_labware, new_lid_slot=pcr_slot,
                                                       labware_slot=fluorescence_slot)
    # 夹取样本
    fluorescence_labware = move_tips(col, protocol, tip_8_labware, new_slot=fluorescence_slot)
    # 盖上盖子
    fluorescence_labware, pcr_labware = cover_lid(protocol, pcr_labware, old_lid_slot=pcr_slot,
                                                  new_lid_slot=fluorescence_slot)
    # 读取浓度
    result = serial_device.get_fluorescence_data()
    result = serial_device.get_concentration(result)
    protocol.pause(f"8 CHANNELS VALUES: {result}")
    # 移掉盖子
    pcr_labware, fluorescence_labware = remove_lid(protocol, fluorescence_labware, new_lid_slot=pcr_slot,
                                                   labware_slot=fluorescence_slot)
    # 移掉8连管
    tip_8_labware = remove_tips(col, protocol, fluorescence_labware, new_slot=tip_8_slot)
    if recover_lid_flag:
        # 盖上盖子
        fluorescence_labware, pcr_labware = cover_lid(protocol, pcr_labware, old_lid_slot=pcr_slot,
                                                      new_lid_slot=fluorescence_slot)

    return fluorescence_labware, tip_8_labware, pcr_labware


def run(protocol: protocol_api.ProtocolContext):
    """
    Load labware & instrument
    """
    tiprack = protocol.load_labware('opentrons_flex_96_tiprack_50ul', 'D2')
    pipette = protocol.load_instrument(
        'flex_1channel_50', 'left', tip_racks=[tiprack])

    reservoir = protocol.load_labware("nest_12_reservoir_15ml", "D1")
    pcr_96_well = protocol.load_labware('nest_96_wellplate_200ul_flat', 'C1')
    fluorescence_labware = protocol.load_labware_from_definition(
        LABWARE_DEF,
        'C2',
        LABWARE_LABEL,
    )
    tip_8 = protocol.load_labware_from_definition(
        TIP_8_DEF,
        'C3',
        TIP_8_LABEL,
    )
    protocol.load_trash_bin('A3')
    simulating = protocol.is_simulating()

    """
    Init Serial Device
    """
    device = SerialDriver(9600, simulating)
    device.build_connection()

    Total_Cols = 2
    for i in range(Total_Cols):
        remove_lid = True if i == 0 else False
        recover_lid = True if i == Total_Cols - 1 else False
        fluorescence_labware, tip_8_labware, pcr_96_labware = fluorescence_round(protocol, i + 1, fluorescence_labware,
                                                                      tip_8, pcr_96_well, 'C2', 'C3', 'C1',
                                                                      device,
                                                                      remove_lid_flag=remove_lid,
                                                                      recover_lid_flag=recover_lid)
        fluorescence_labware = fluorescence_labware
        tip_8 = tip_8_labware
        pcr_96_well = pcr_96_labware

