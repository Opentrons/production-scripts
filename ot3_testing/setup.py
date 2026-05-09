"""Setup script for OT3 Testing Module

This setup script handles packaging of the ot3_testing module,
with special handling for external driver dependencies.
"""

import os
from setuptools import setup, find_packages

# Read version from __version__.py
version = {}
with open(os.path.join(os.path.dirname(__file__), '__version__.py')) as f:
    exec(f.read(), version)

# Package metadata
NAME = 'ot3_testing'
VERSION = version['__version__']
DESCRIPTION = 'OT3 Leveling Testing Module'
AUTHOR = 'OT3 Testing Team'
URL = ''

# Package requirements
REQUIRED_PACKAGES = [
    'typing-extensions',
    'dataclasses',
]

# Optional dependencies (external drivers)
EXTRAS_REQUIRE = {
    'drivers': [
        'pyserial',
        'playsound',
        'crcmod',
    ],
}

# Package data
PACKAGE_DATA = {
    'ot3_testing.leveling_test': ['leveling_config.json'],
}

# Entry points
ENTRY_POINTS = {
    'console_scripts': [
        'ot3-leveling=ot3_testing.main:main',
    ],
}

# Setup configuration
setup(
    name=NAME,
    version=VERSION,
    description=DESCRIPTION,
    author=AUTHOR,
    url=URL,
    packages=find_packages(exclude=['tests', '*.tests', '*.tests.*']),
    package_data=PACKAGE_DATA,
    install_requires=REQUIRED_PACKAGES,
    extras_require=EXTRAS_REQUIRE,
    entry_points=ENTRY_POINTS,
    include_package_data=True,
    zip_safe=False,
    classifiers=[
        'Development Status :: 4 - Beta',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python :: 3.10',
        'Programming Language :: Python :: 3.11',
        'Programming Language :: Python :: 3.12',
        'Operating System :: OS Independent',
    ],
)
