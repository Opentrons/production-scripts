__version__ = "1.5.9"
__author__ = "OT3 Testing Team"
__description__ = "Only for OT3 Leveling Testing So Far"

import os
import subprocess


def get_version():
    """Get the current version"""
    print(f"__VERSION__ is {__version__}")
    return __version__


def build(mode='mac'):
    """
    Build executable for ot3_testing
    
    Args:
        mode: 'mac' for macOS, 'win' for Windows
    """
    import sys
    
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    spec_path = os.path.join(project_root, 'ot3_testing', f'package{"-win" if mode == "win" else ""}.spec')
    
    cmd = f'python "{spec_path}"'
    print(f"Building ot3_leveling-{__version__} for {mode}...")
    
    process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, cwd=project_root)
    while True:
        line = process.stdout.readline()
        if not line:
            break
        else:
            print(line, end='')
    process.wait()
    
    output_path = os.path.join(project_root, "dist")
    print(f"\nComplete! target file -> {output_path}")


if __name__ == "__main__":
    import sys
    mode = sys.argv[1] if len(sys.argv) > 1 else 'mac'
    build(mode)