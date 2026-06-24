from test_cli.leveling_test.leveling_z_stage import Z_Leveling
from test_cli.leveling_test.leveling_8ch_pipette import CH8_Leveling
from test_cli.leveling_test.leveling_96ch_pipette import CH96_Leveling
from test_cli.leveling_test.leveling_gripper import Gripper_Leveling
from test_cli.leveling_test.type import TestNameLeveling
from tools.inquirer import prompt_leveling, input_with_default
from tools.reading_laser import ReadLaser
from test_cli.cli import ui
import asyncio


__test_config = {
    TestNameLeveling.Z_Leveling: Z_Leveling,
    TestNameLeveling.CH96_Leveling: CH96_Leveling,
    TestNameLeveling.CH8_Leveling: CH8_Leveling,
    TestNameLeveling.Gripper_Leveling: Gripper_Leveling
}

__test_aliases = {
    "z": TestNameLeveling.Z_Leveling,
    "ch8": TestNameLeveling.CH8_Leveling,
    "ch96": TestNameLeveling.CH96_Leveling,
    "gripper": TestNameLeveling.Gripper_Leveling,
}


def _selected_answers(selected_test: str) -> list[str] | None:
    if selected_test == "menu":
        return None
    if selected_test == "all":
        return [test_name.value for test_name in __test_config]
    return [__test_aliases[selected_test].value]


async def run(
    script_dir,
    robot_ip: str | None = None,
    robot_sn: str | None = None,
    operator_name: str | None = None,
    simulate: bool = False,
    selected_test: str = "menu",
    debug: bool = False,
):
    sn = robot_sn
    
    try:
        if sn is None:
            default_sn = "SIMULATED-ROBOT" if simulate else "FLXA3020250805002"
            sn = (await asyncio.to_thread(
                input_with_default,
                "Please input the Robot Serial Number:",
                default_sn,
            )).strip()
        if robot_ip is None:
            default_ip = "simulator" if simulate else "192.168.6.1"
            robot_ip = (await asyncio.to_thread(
                input_with_default,
                "Please input the robot ip address:",
                default_ip,
            )).strip()
        
        if not sn:
            raise ValueError("Robot Serial Number cannot be empty")
        if not robot_ip:
            raise ValueError("Robot IP address cannot be empty")
        if operator_name is None:
            operator_name = ""
        
    except Exception as e:
        ui.exception_report(e, debug=debug)
        return
    
    while True:
        try:
            selected_answer = _selected_answers(selected_test)
            answer = selected_answer or await asyncio.to_thread(prompt_leveling)
            
            if not answer:
                ui.warning(ui.bilingual("No test selected", "未选择任何测试项目"))
                continue
            
            for test_name in [TestNameLeveling.Z_Leveling,
                              TestNameLeveling.CH8_Leveling,
                              TestNameLeveling.CH96_Leveling,
                              TestNameLeveling.Gripper_Leveling]:
                if test_name.value in answer:
                    try:
                        ui.test_banner(test_name.value, simulate=simulate)
                        test_obj = __test_config[test_name](robot_ip, script_dir=script_dir, simulate=simulate)
                        test_obj.robot_sn = sn
                        test_obj.operator_name = operator_name
                        await test_obj.run()
                        ui.success(ui.bilingual(f"{test_name.value} finished", f"{test_name.value} 完成"))
                    except Exception as e:
                        ui.exception_report(e, debug=debug)
            
            if "read-sensor" in answer:
                if simulate:
                    ui.warning(ui.bilingual("Sensor reading is skipped in simulation mode", "模拟模式跳过传感器读取"))
                    continue
                try:
                    ui.test_banner("read sensor", simulate=False)
                    l = ReadLaser(add_height=0)
                    await l.run_test(robot_ip)
                except Exception as e:
                    ui.exception_report(e, debug=debug)
            
            if "exit" in answer:
                break
            if selected_answer is not None:
                break
                
        except KeyboardInterrupt:
            ui.warning(ui.bilingual("User cancelled the operation", "用户中断操作"))
            break
        except Exception as e:
            ui.exception_report(e, debug=debug)
    
    if selected_test == "menu":
        input("按任意键退出...")


if __name__ == '__main__':
    try:
        asyncio.run(run("./"))
    except KeyboardInterrupt:
        ui.warning(ui.bilingual("Program cancelled by user", "程序被用户中断"))
    except Exception as e:
        ui.exception_report(e)
