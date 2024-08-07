def calc_crc(string):
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
    return hex(((crc & 0xFF) << 8) + (crc >> 8))[2:]


def format_hex(value: int):
    value = hex(value)[2:]
    for i in range(4 - len(value)):
        value = '0' + value
    print(value)


# crc = calc_crc('010600070009')
# print(type(crc))

# format_hex(700)
ret = calc_crc("070400020002")
print(ret)
