from modules.magnetic import MagneticModule
from ot_type import ModuleName
import asyncio


async def _main():
    _magnetic = MagneticModule()
    mag_v2 = await _magnetic.get_module_id_by_name(ModuleName.MAGNETIC_MODULE_V2)
    height = await _magnetic.engage_magnetic(mag_v2[0], 20)
    print("Height: ", height)
    await _magnetic.disengage(mag_v2[0])


if __name__ == '__main__':
    asyncio.run(_main())
