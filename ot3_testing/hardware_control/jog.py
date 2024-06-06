"""
@description: for jog ot2
"""
from ot3_testing.ot_type import Mount, Point, PositionSel
import sys
from ot3_testing.hardware_control.hardware_control import HardwareControl
import asyncio
import curses

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


async def jog(hc: HardwareControl, mount: Mount):
    step_size = [0.01, 0.05, 0.1, 0.5, 1, 2, 5, 10, 20, 50, 100]
    step_length_index = 3
    await hc.home()
    if mount == mount.LEFT:
        select = PositionSel.MOUNT_LEFT
    else:
        select = PositionSel.MOUNT_RIGHT
    # useful_pos = await hc.require_useful_pos(select)
    useful_pos = Point(50, 100, 500)
    print("useful_pos: ", useful_pos)
    await hc.move_to(mount, useful_pos, target="mount")

    while True:
        error = "0"
        key, std = getch()
        _input = chr(key)
        sys.stdout.flush()
        if _input == "a":
            # minus x direction
            sys.stdout.flush()
            try:
                await hc.move_rel(
                    mount, Point(-step_size[step_length_index], 0, 0))
            except:
                error = "No Response"
            useful_pos = useful_pos - Point(step_size[step_length_index], 0, 0)

        elif _input == "d":
            # plus x direction
            sys.stdout.flush()
            try:
                await hc.move_rel(
                    mount, Point(step_size[step_length_index], 0, 0))
            except:
                error = "No Response"
            useful_pos = useful_pos + Point(step_size[step_length_index], 0, 0)

        elif _input == "w":
            # minus y direction
            sys.stdout.flush()
            try:
                await hc.move_rel(
                    mount, Point(0, step_size[step_length_index], 0))
            except:
                error = "No Response"
            useful_pos = useful_pos + Point(0, step_size[step_length_index], 0)

        elif _input == "s":
            # plus y direction
            sys.stdout.flush()
            try:
                await hc.move_rel(
                    mount, Point(0, -step_size[step_length_index], 0))
            except:
                error = "No Response"
            useful_pos = useful_pos - Point(0, step_size[step_length_index], 0)

        elif _input == "i":
            sys.stdout.flush()
            try:
                await hc.move_rel(
                    mount, Point(0, 0, step_size[step_length_index]))
            except:
                error = "No Response"
            useful_pos = useful_pos + Point(0, 0, step_size[step_length_index])

        elif _input == "k":
            sys.stdout.flush()
            try:
                await hc.move_rel(
                    mount, Point(0, 0, -step_size[step_length_index]))
            except:
                error = "No Response"
            useful_pos = useful_pos - Point(0, 0, step_size[step_length_index])

        elif _input == "q":
            sys.stdout.flush()
            print("TEST CANCELLED")
            quit()

        elif _input == "+":
            sys.stdout.flush()
            step_length_index = step_length_index + 1
            if step_length_index >= len(step_size):
                step_length_index = len(step_size)

        elif _input == "-":
            sys.stdout.flush()
            step_length_index = step_length_index - 1
            if step_length_index <= 0:
                step_length_index = 0
        else:
            error = "click err"

        # save pos
        try:
            if mount == Mount.LEFT:
                hc.left_saved_pos = useful_pos
            elif mount == Mount.RIGHT:
                hc.right_saved_pos = useful_pos
            else:
                raise ValueError("mount err")
        except:
            error = "require position err"
            position = [0, 0, 0]
        std.addstr(15, 0, f"Press：{_input}, Point(x={useful_pos[0]} y={useful_pos[1]} z={useful_pos[2]}), "
                          f"Step={step_size[step_length_index]}, Error={error}")
        std.refresh()


if __name__ == '__main__':
    hc = HardwareControl("192.168.6.33")
    asyncio.run(jog(hc, Mount.LEFT))
