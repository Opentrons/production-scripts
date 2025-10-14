import asyncio

from ot3_testing.leveling_test.leveling_z_stage import Z_Leveling
from ot3_testing.leveling_test.leveling_8ch_pipette import CH8_Leveling
from ot3_testing.leveling_test.leveling_96ch_pipette import CH96_Leveling
from ot3_testing.leveling_test.type import TestNameLeveling
import asyncio

__test_config = {
    TestNameLeveling.Z_Leveling: Z_Leveling,
    TestNameLeveling.CH96_Leveling: CH96_Leveling,
    TestNameLeveling.CH8_Leveling: CH8_Leveling
}


async def _run():
    sn = input("Please input the Robot Serial Number: ").strip()
    robot_ip = input("Please input the robot ip address: ").strip()
    while True:
        for test_name in [TestNameLeveling.Z_Leveling,
                          TestNameLeveling.CH8_Leveling,
                          TestNameLeveling.CH96_Leveling]:
            answer = input(f"是否开始测试 {test_name.value.upper()}(y/n) ?").upper()
            if "Y" in answer:
                test_obj = __test_config[test_name](robot_ip)
                test_obj.robot_sn = sn
                await test_obj.run()
        answer = input(f"是否退出 (y/n) ?").upper()
        if "Y" in answer:
            break


if __name__ == '__main__':
    asyncio.run(_run())
