"""PyInstaller Configuration for OT3 Testing Module (macOS)

This spec file handles external driver dependencies and ensures
smooth packaging of the ot3_testing module for macOS.
"""

import sys
import os
from pathlib import Path

# Get the project root directory
project_root = Path(__file__).parent.parent

# Add project root to path for imports
sys.path.insert(0, str(project_root))

# Import version information
from ot3_testing.__version__ import __version__, __author__, __description__

# External drivers that should be excluded from packaging to avoid conflicts
EXCLUDED_DRIVERS = [
    'pywin32',
    'winsound',
    'adodbapi',
    'pyserial',
    'playsound',
    'crcmod',
]

# Hidden imports for dynamic loading
HIDDEN_IMPORTS = [
    'ot3_testing.leveling_test.config',
    'ot3_testing.leveling_test.type',
    'ot3_testing.leveling_test.model.base',
    'ot3_testing.leveling_test.report.report',
    'ot3_testing.hardware_control.hardware_control',
    'ot3_testing.protocol.protocol_context',
    'ot3_testing.maintenance_api.maintenance_run',
]

# Data files to include
DATA_FILES = [
    (str(project_root / 'ot3_testing' / 'leveling_test' / 'leveling_config.json'), 'ot3_testing/leveling_test'),
]

# Binaries to exclude
EXCLUDED_BINARIES = []


def build_exe():
    """Build executable using PyInstaller"""
    import PyInstaller.__main__
    
    # Use appropriate separator based on OS
    sep = ';' if sys.platform == 'win32' else ':'
    
    # Get the path to main.py
    main_py_path = str(project_root / 'ot3_testing' / 'main.py')
    
    args = [
        main_py_path,
        f'--name=ot3_leveling-{__version__}',
        '--onefile',
        '--windowed',
        '--hidden-import=' + ','.join(HIDDEN_IMPORTS),
        '--exclude-module=' + ','.join(EXCLUDED_DRIVERS),
        '--distpath=' + str(project_root / 'dist'),
        '--workpath=' + str(project_root / 'build'),
        '--specpath=' + str(project_root / 'ot3_testing'),
    ]
    
    # Add data files
    for src, dst in DATA_FILES:
        args.append(f'--add-data={src}{sep}{dst}')
    
    PyInstaller.__main__.run(args)


if __name__ == '__main__':
    build_exe()
