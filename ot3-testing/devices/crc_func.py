from binascii import unhexlify
from crcmod import mkCrcFun


# common func
def get_crc_value(s, crc16):
    data = s.replace(' ', '')
    crc_out = hex(crc16(unhexlify(data))).upper()
    str_list = list(crc_out)
    if len(str_list) == 5:
        str_list.insert(2, '0')  # 位数不足补0
    crc_data = ''.join(str_list[2:])
    return crc_data[:2] + ' ' + crc_data[2:]


# CRC16/MODBUS
def crc16_modbus(s):
    crc16 = mkCrcFun(0x18005, rev=True, initCrc=0xFFFF, xorOut=0x0000)
    ret = get_crc_value(s, crc16)
    ret_list = ret.split(' ')
    ret_list.reverse()
    return ''.join(ret_list)


if __name__ == '__main__':
    s3 = crc16_modbus("020400000008")
    print('crc16_modbus: ' + s3)
    print(type(s3))
