"""Setup script for Test CLI

This setup script handles packaging of the test_cli module,
with special handling for external driver dependencies.
"""

import os
from setuptools import setup, find_packages

# Read version from __version__.py
version = {}
with open(os.path.join(os.path.dirname(__file__), '__version__.py')) as f:
    exec(f.read(), version)

# Package metadata
NAME = 'test_cli'
VERSION = version['__version__']
DESCRIPTION = 'Cross-platform production test CLI'
AUTHOR = 'Test CLI Team'
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
        'crcmod',
    ],
}

# Package data
PACKAGE_DATA = {
    'test_cli.leveling_test': ['leveling_config.json'],
}

# Entry points
ENTRY_POINTS = {
    'console_scripts': [
        'test-cli=test_cli.main:main',
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
