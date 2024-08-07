"""
@description: for jog ot2
"""
from ot_type import Mount, Point, PositionSel
import sys
from .hardware_control import HardwareControl
import asyncio
import curses

hc = HardwareControl()
stdscr = curses.initscr()


def getch():
    """
    fd: file descriptor stdout, stdin, stderr
    This functions gets a single input keyboard character from the user
    """

    def _getch(stdscr):
        curses.curs_set(0)  # disable curse
        information_str = """
                            Click  >>   i   << to move up
                            Click  >>   k   << to move down
                            Click  >>   a  << to move left
                            Click  >>   d  << to move right
                            Click  >>   w  << to move forward
                            Click  >>   s  << to move back
                            Click  >>   +   << to Increase the length of each step
                            Click  >>   -   << to decrease the length of each step
                            Click  >> Enter << to save position
                            Click  >> q << to quit the test script
                                        """
        stdscr.addstr(1, 0, information_str)
        key = stdscr.getch()
        stdscr.refresh()
        return key, stdscr

    return curses.wrapper(_getch)


async def jog(mount: Mount):
    step_size = [0.01, 0.05, 0.1, 0.5, 1, 10, 20, 50]
    step_length_index = 3
    while True:
        error = "0"
        key, std = getch()
        _input = chr(key)
        sys.stdout.flush()
        if mount == Mount.LEFT:
            select = PositionSel.MOUNT_LEFT
        else:
            select = PositionSel.MOUNT_RIGHT
        if _input == "a":
            # minus x direction
            sys.stdout.flush()
            try:
                await hc.move_rel(
                    mount, Point(-step_size[step_length_index], 0, 0))
            except:
                error = "No Response"

        elif _input == "d":
            # plus x direction
            sys.stdout.flush()
            try:
                await hc.move_rel(
                    mount, Point(step_size[step_length_index], 0, 0))
            except:
                error = "No Response"

        elif _input == "w":
            # minus y direction
            sys.stdout.flush()
            try:
                await hc.move_rel(
                    mount, Point(0, step_size[step_length_index], 0))
            except:
                error = "No Response"

        elif _input == "s":
            # plus y direction
            sys.stdout.flush()
            try:
                await hc.move_rel(
                    mount, Point(0, -step_size[step_length_index], 0))
            except:
                error = "No Response"

        elif _input == "i":
            sys.stdout.flush()
            try:
                await hc.move_rel(
                    mount, Point(0, 0, step_size[step_length_index]))
            except:
                error = "No Response"

        elif _input == "k":
            sys.stdout.flush()
            try:
                await hc.move_rel(
                    mount, Point(0, 0, -step_size[step_length_index]))
            except:
                error = "No Response"

        elif _input == "q":
            sys.stdout.flush()
            print("TEST CANCELLED")
            quit()

        elif _input == "+":
            sys.stdout.flush()
            step_length_index = step_length_index + 1
            if step_length_index >= 7:
                step_length_index = 7

        elif _input == "-":
            sys.stdout.flush()
            step_length_index = step_length_index - 1
            if step_length_index <= 0:
                step_length_index = 0
        else:
            error = "click err"

        try:
            if mount == Mount.LEFT:
                position = hc.pipette_left_saved_position
            elif mount == Mount.RIGHT:
                position = hc.pipette_right_saved_position
            else:
                raise ValueError("mount err")
        except:
            error = "require position err"
            position = [0, 0, 0]
        std.addstr(15, 0, f"Press：{_input}, Point(x={position[0]} y={position[1]} z={position[2]}), "
                          f"Step={step_size[step_length_index]}, Error={error}")
        std.refresh()


