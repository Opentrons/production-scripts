from modules.temperature_module import TemperatureModule
from ot_type import ModuleName
import asyncio


async def _main():
    _tem_module = TemperatureModule()
    tem_v2 = await _tem_module.get_module_id_by_name(ModuleName.TEMPERATURE_MODULE_V2)
    this_module_id = tem_v2[0]
    await _tem_module.set_temperature(this_module_id, 50.0)
    await _tem_module.wait_for_temperature(this_module_id)
    temp = await _tem_module.get_target_temperature(this_module_id)
    print(f"Temp: {temp}")
    await _tem_module.deactivate(this_module_id)


if __name__ == '__main__':
    asyncio.run(_main())
