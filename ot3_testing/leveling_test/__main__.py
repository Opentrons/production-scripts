from ot3_testing.leveling_test.leveling_z_stage import Z_Leveling
from ot3_testing.leveling_test.leveling_8ch_pipette import CH8_Leveling
from ot3_testing.leveling_test.leveling_96ch_pipette import CH96_Leveling
from ot3_testing.leveling_test.leveling_gripper import Gripper_Leveling
from ot3_testing.leveling_test.type import TestNameLeveling
from tools.inquirer import prompt_leveling, input_with_default
from tools.reading_laser import ReadLaser
import asyncio
import traceback


__test_config = {
    TestNameLeveling.Z_Leveling: Z_Leveling,
    TestNameLeveling.CH96_Leveling: CH96_Leveling,
    TestNameLeveling.CH8_Leveling: CH8_Leveling,
    TestNameLeveling.Gripper_Leveling: Gripper_Leveling
}


async def run(script_dir):
    sn = None
    robot_ip = None
    
    try:
        sn = input_with_default("Please input the Robot Serial Number:", "FLXA3020250805002").strip()
        robot_ip = input_with_default("Please input the robot ip address:", "192.168.6.1").strip()
        
        if not sn:
            raise ValueError("Robot Serial Number cannot be empty")
        if not robot_ip:
            raise ValueError("Robot IP address cannot be empty")
        
    except Exception as e:
        print(f"输入错误: {e}")
        return
    
    while True:
        try:
            answer = prompt_leveling()
            
            if not answer:
                print("未选择任何测试项目")
                continue
            
            for test_name in [TestNameLeveling.Z_Leveling,
                              TestNameLeveling.CH8_Leveling,
                              TestNameLeveling.CH96_Leveling,
                              TestNameLeveling.Gripper_Leveling]:
                if test_name.value in answer:
                    try:
                        test_obj = __test_config[test_name](robot_ip, script_dir=script_dir)
                        test_obj.robot_sn = sn
                        await test_obj.run()
                    except ValueError as e:
                        print(f"参数错误: {e}")
                    except ConnectionError as e:
                        print(f"连接错误: {e}")
                    except TimeoutError as e:
                        print(f"超时错误: {e}")
                    except Exception as e:
                        print(f"测试运行时发生异常: {e}")
                        traceback.print_exc()
            
            if "read-sensor" in answer:
                try:
                    l = ReadLaser(add_height=0)
                    await l.run_test(robot_ip)
                except ConnectionError as e:
                    print(f"传感器连接错误: {e}")
                except Exception as e:
                    print(f"传感器测试异常: {e}")
                    traceback.print_exc()
            
            if "exit" in answer:
                break
                
        except KeyboardInterrupt:
            print("\n用户中断操作")
            break
        except Exception as e:
            print(f"发生异常: {e}")
            traceback.print_exc()
    
    input("按任意键退出...")


if __name__ == '__main__':
    try:
        asyncio.run(run("./"))
    except KeyboardInterrupt:
        print("\n程序被用户中断")
    except Exception as e:
        print(f"程序启动失败: {e}")
        traceback.print_exc()
