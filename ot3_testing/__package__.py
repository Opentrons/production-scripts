"""OT3 Testing Module Package Configuration

This module provides package-level metadata and utilities
for the ot3_testing package.
"""

import os
import sys
from ot3_testing.__version__ import __version__, __author__, __description__

# Package metadata
__name__ = "ot3_testing"
__title__ = "OT3 Testing Module"
__author_email__ = ""
__url__ = ""
__license__ = "MIT"
__copyright__ = "Copyright 2024 OT3 Testing Team"

# Package path
PACKAGE_PATH = os.path.dirname(__file__)

# External driver handling
EXTERNAL_DRIVERS = {
    'serial': 'pyserial',
    'winsound': 'winsound',
    'playsound': 'playsound',
    'crcmod': 'crcmod',
}


def is_driver_available(driver_name: str) -> bool:
    """Check if an external driver is available"""
    try:
        __import__(driver_name)
        return True
    except ImportError:
        return False


def lazy_import_driver(driver_name: str):
    """Lazy import an external driver"""
    if driver_name in EXTERNAL_DRIVERS:
        package_name = EXTERNAL_DRIVERS[driver_name]
        try:
            return __import__(package_name)
        except ImportError:
            raise ImportError(f"External driver '{package_name}' is not installed. "
                            f"Please install it with: pip install {package_name}")
    else:
        return __import__(driver_name)


# Package exports
__all__ = [
    'leveling_test',
    'hardware_control',
    'protocol',
    'maintenance_api',
    '__version__',
    '__author__',
    '__description__',
    'is_driver_available',
    'lazy_import_driver',
]
