import os
import sys
from ot3_testing.tests.pipette_leveling import PipetteLeveling
from ot3_testing.tests.gripper_leveling import GripperLeveling
from ot3_testing.tests.zstage_leveling import ZStageLeveling
from ot3_testing.test_config.pipette_leveling_config import SlotLocationCH96, ChannelDefinitionCH96, \
    SlotLocationCH8, ChannelDefinitionCH8
from ot3_testing.test_config.zstage_leveling_config import ZStagePoint
from ot3_testing.test_config.gripper_leveling_config import Gripper_Position
import asyncio
from tools.inquirer import prompt_flex_name, prompt_test_name, prompt_exit
from tools import heat_96ch
from __version__ import get_version
from gravimetric_testing.openwebapp import openweb

addpathpat = os.path.dirname(__file__)
addpath = os.path.dirname(os.path.dirname(__file__))
addpath2 = os.path.dirname(addpath)
if addpath not in sys.path:
    sys.path.append(addpath)
if addpath2 not in sys.path:
    sys.path.append(addpath2)
if addpathpat not in sys.path:
    sys.path.append(addpathpat)

if __name__ == '__main__':
    get_version()
    flex_name = prompt_flex_name()
    project_path = os.getcwd()
    while True:
        test_name = prompt_test_name()
        if "heat-96ch" in test_name:
            heat_96ch.test_run()
        elif "leveling-96ch" in test_name:
            pipette_leveling = PipetteLeveling(SlotLocationCH96, ChannelDefinitionCH96, )
            asyncio.run(pipette_leveling.run_96ch_test(flex_name, project_path=project_path))
        elif "leveling-z-stage" in test_name:
            z_leveling = ZStageLeveling(ZStagePoint)
            asyncio.run(z_leveling.run_z_stage_test(flex_name, project_path=project_path))
        elif 'leveling-gripper' in test_name:
            _gripper = GripperLeveling(Gripper_Position)
            asyncio.run(_gripper.run_gripper_test(flex_name, project_path=project_path))
        elif "leveling-8ch" in test_name:
            # run 8
            pipette_leveling = PipetteLeveling(SlotLocationCH8, ChannelDefinitionCH8)
            pipette_leveling.test_name = "8ch"
            pipette_leveling.k = -2
            pipette_leveling.b = 35
            asyncio.run(pipette_leveling.run_8ch_test(flex_name, project_path=project_path))
        elif "grav-openweb" in test_name:
            openweb()

        else:
            pass

        ret = prompt_exit()
        if 'yes' in ret:
            break
        else:
            pass
