import asyncio
from __version__ import get_version
from ot3_testing.leveling_test.__main__ import run


if __name__ == '__main__':
    get_version()
    asyncio.run(run())

