import os,sys
addpathpat = os.path.dirname(__file__)
addpath = os.path.dirname(os.path.dirname(__file__))
addpath2 = os.path.dirname(addpath)
if addpath not in sys.path:
    sys.path.append(addpath)
if addpath2 not in sys.path:
    sys.path.append(addpath2)
if addpathpat not in sys.path:
    sys.path.append(addpathpat)
from ot3_testing.tests.pipette_leveling import PipetteLeveling
from ot3_testing.test_config.pipette_leveling_config import SlotLocationCH96, ChannelDefinitionCH96, ChannelOffsetsCH96, \
    SlotLocationCH8, \
    ChannelOffsetsCH8, ChannelDefinitionCH8
import asyncio
from tools.inquirer import prompt_flex_name, prompt_test_name, prompt_exit
from tools import heat_96ch
from __version__ import get_version
from gravimetric_testing.openwebapp import openweb

if __name__ == '__main__':
    get_version()
    flex_name = prompt_flex_name()
    while True:
        test_name = prompt_test_name()
        if "heat-96ch" in test_name:
            heat_96ch.test_run()
        elif "leveling-96ch" in test_name:
            pipette_leveling = PipetteLeveling(SlotLocationCH96, ChannelDefinitionCH96, ChannelOffsetsCH96)
            asyncio.run(pipette_leveling.run_96ch_test(flex_name))
        elif "leveling-8ch" in test_name:
            # run 8
            pipette_leveling = PipetteLeveling(SlotLocationCH8, ChannelDefinitionCH8, ChannelOffsetsCH8)
            pipette_leveling.test_name = "8ch"
            pipette_leveling.k = -2
            pipette_leveling.b = 35
            asyncio.run(pipette_leveling.run_8ch_test(flex_name))
        elif "grav-openweb" in test_name:
            openweb()

        else:
            pass

        ret = prompt_exit()
        if 'yes' in ret:
            break
        else:
            pass

