from solutions.calibration_flow import CalibrationFlow
import asyncio
from ot_type import Mount


async def _main():
    c_f = CalibrationFlow()
    # exit all
    await c_f.excuse_exit_calibration(_all=True)

    # deck calibration
    _input = input("do deck calibration ? (y/n)")
    if _input == 'y':
        await c_f.deck_calibration()

    # tip length calibration & pipette offset
    for mount in [Mount.LEFT, Mount.RIGHT]:
        _input = input(f"do tip length - {mount.value} calibration ? (y/n)")
        if _input == 'y':
            await c_f.tip_length_calibration(mount)

        _input = input(f"do pipette offset - {mount.value} calibration ? (y/n)")
        if _input == 'y':
            await c_f.pipette_offset_calibration(mount)

if __name__ == '__main__':
    asyncio.run(_main())
