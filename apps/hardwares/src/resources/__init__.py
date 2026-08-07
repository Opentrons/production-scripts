# import os
# import sys
# addpathpat = os.path.dirname(__file__)
# addpath = os.path.dirname(os.path.dirname(__file__))
# addpath2 = os.path.dirname(addpath)
# if addpath not in sys.path:
#     sys.path.append(addpath)
# if addpath2 not in sys.path:
#     sys.path.append(addpath2)
# if addpathpat not in sys.path:
#     sys.path.append(addpathpat)
from pathlib import Path


RESOURCE_DIR = Path(__file__).resolve().parent


def resource_path(*parts: str) -> Path:
    return RESOURCE_DIR.joinpath(*parts)
