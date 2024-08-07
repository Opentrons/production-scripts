import time

from modules.heatershaker import HeaterShakerModule
from ot_type import ModuleName
import asyncio


async def _main():
    _shaker_module = HeaterShakerModule()
    shaker_v2 = await _shaker_module.get_module_id_by_name(ModuleName.HEATER_SHAKER_MODULE_V1)
    this_module_id = shaker_v2[0]
    await _shaker_module.set_target_temperature(this_module_id, 50)
    await _shaker_module.wait_for_temperature(this_module_id)
    await _shaker_module.set_wait_shaker_speed(this_module_id, 1000)
    temp = await _shaker_module.get_target_temperature(this_module_id)
    speed = await _shaker_module.get_target_speed(this_module_id)
    print(f"Temp: {temp}")
    print(f"Speed: {speed}")

    await _shaker_module.deactivate_shaker(this_module_id)
    await _shaker_module.deactivate_heater(this_module_id)

    await _shaker_module.open_labware_latch(this_module_id)
    status = await _shaker_module.get_latch_status(this_module_id)
    print(f"Latch Status: {status}")
    await _shaker_module.close_labware_latch(this_module_id)
    status = await _shaker_module.get_latch_status(this_module_id)
    print(f"Latch Status: {status}")

if __name__ == '__main__':
    asyncio.run(_main())
