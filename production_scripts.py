from ot3_testing.tests.pipette_leveling import PipetteLeveling
from ot3_testing.tests.test_type import SlotLocationCH96, ChannelDefinitionCH96, ChannelOffsetsCH96, SlotLocationCH8, \
    ChannelOffsetsCH8, ChannelDefinitionCH8
import asyncio
# from tools.run_heat_96ch_script import heat_96ch
# from ot3_testing.devices.ssh import SSHClient

if __name__ == '__main__':
    flex_name = input("输入机器条码: ")
    # ret = input("Test Tools heat 96ch ? (Y/N)")
    # if ret.upper().strip() == "Y":
    #     ip_address = input("请输入ip地址:")
    #     client = SSHClient(ip_address.strip())
    #     heat_96ch(client, flex_name)

    ret = input("Test 96通道移液器平行 ? (Y/N)")
    if ret.upper().strip() == "Y":
        # run 96
        pipette_leveling = PipetteLeveling(SlotLocationCH96, ChannelDefinitionCH96, ChannelOffsetsCH96)
        asyncio.run(pipette_leveling.run_96ch_test(flex_name))
    ret = input("Test 8通道移液器平行 ? (Y/N)")
    if ret.upper().strip() == "Y":
        # run 8
        pipette_leveling = PipetteLeveling(SlotLocationCH8, ChannelDefinitionCH8, ChannelOffsetsCH8)
        pipette_leveling.test_name = "8ch"
        pipette_leveling.k = -2
        pipette_leveling.b = 35
        asyncio.run(pipette_leveling.run_8ch_test(flex_name))

    input("测试结束...")
