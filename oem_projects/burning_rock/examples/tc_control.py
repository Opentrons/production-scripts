import time

from oem_projects.burning_rock.modules.thermocycler import ThermocyclerModule
from oem_projects.burning_rock.ot_type import ModuleName
import asyncio


async def _main():
    _thermo_module = ThermocyclerModule()
    thermo_v2 = await _thermo_module.get_module_id_by_name(ModuleName.TC_V2)
    this_module_id = thermo_v2[0]

    # await _thermo_module.set_lid_temperature(this_module_id, 90)
    # for i in range(30):
    #     time.sleep(1)

    # await _thermo_module.deactivate_all(this_module_id)
    # await _thermo_module.wait_for_lid_temperature(this_module_id)
    # await _thermo_module.set_block_temperature(this_module_id, 50)
    # await _thermo_module.wait_for_block_temperature(this_module_id)
    #
    # lid_temp = await _thermo_module.get_lid_temperature(this_module_id)
    # block_temp = await _thermo_module.get_block_temperature(this_module_id)
    #
    # print(f"Lid Temp: {lid_temp}")
    # print(f"Block Temp: {block_temp}")
    #
    # await _thermo_module.deactivate_lid(this_module_id)
    # await _thermo_module.deactivate_block(this_module_id)

    # run profile
    await _thermo_module.run_profile(this_module_id, profile=[
        {"holdSeconds": 90, "celsius": 50},
        {"holdSeconds": 90, "celsius": 95},
        {"holdSeconds": 90, "celsius": 50},
        {"holdSeconds": 90, "celsius": 95}
    ])
    #
    # await _thermo_module.deactivate_all(this_module_id)

    await _thermo_module.open_lid(this_module_id)
    lid_status = await _thermo_module.get_lid_status(this_module_id)
    print(f"Lid Status: {lid_status}")
    await _thermo_module.close_lid(this_module_id)
    lid_status = await _thermo_module.get_lid_status(this_module_id)
    print(f"Lid Status: {lid_status}")


if __name__ == '__main__':
    asyncio.run(_main())
