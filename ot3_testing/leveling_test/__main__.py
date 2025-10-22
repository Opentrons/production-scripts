from ot3_testing.leveling_test.leveling_z_stage import Z_Leveling
from ot3_testing.leveling_test.leveling_8ch_pipette import CH8_Leveling
from ot3_testing.leveling_test.leveling_96ch_pipette import CH96_Leveling
from ot3_testing.leveling_test.type import TestNameLeveling
from tools.inquirer import prompt_leveling, input_with_default
import asyncio
from tools.reading_laser import ReadLaser

__test_config = {
    TestNameLeveling.Z_Leveling: Z_Leveling,
    TestNameLeveling.CH96_Leveling: CH96_Leveling,
    TestNameLeveling.CH8_Leveling: CH8_Leveling
}


async def _run():
    sn = input_with_default("Please input the Robot Serial Number:", "FLXA3020250805002").strip()
    robot_ip = input_with_default("Please input the robot ip address:", "192.168.6.1").strip()
    while True:
        try:
            answer = prompt_leveling()
            for test_name in [TestNameLeveling.Z_Leveling,
                              TestNameLeveling.CH8_Leveling,
                              TestNameLeveling.CH96_Leveling]:
                if test_name.value in answer:
                    test_obj = __test_config[test_name](robot_ip)
                    test_obj.robot_sn = sn
                    await test_obj.run()
            if "read_sensor" in test_name:
                l = ReadLaser(add_height=0)
                await l.run_test(robot_ip)
            if "exit" in answer:
                break
        except Exception as e:
            print("捕获到异常：\n")
            print(e)


if __name__ == '__main__':
    asyncio.run(_run())
