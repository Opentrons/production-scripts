#!/usr/bin/env python3
"""OT3 Testing Module - Main Entry Point"""

import asyncio

from ot3_testing.__version__ import __version__, __author__, __description__
from ot3_testing.leveling_test.__main__ import run


def main():
    print(f"OT3 Leveling Testing Module")
    print(f"Version: {__version__}")
    print(f"Author: {__author__}")
    print(f"Description: {__description__}")
    print("-" * 50)
    asyncio.run(run("./"))


if __name__ == '__main__':
    main()
