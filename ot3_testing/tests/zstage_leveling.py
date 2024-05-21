from ot3_testing.tests.base_init import TestBase
from ot3_testing.ot_type import Mount, Point
from devices.amsamotion_sensor import LaserSensor


class ZStageLeveling(TestBase):
    def __init__(self):
        super(ZStageLeveling).__init__()
        self.mount = Mount.LEFT
        self.laser_sensor = None

    def init_laser_sensor(self, send=False):
        """
        init 96ch device
        :return:
        """
        self.laser_sensor = LaserSensor(send=send)

    async def move_to_test_point(self, p: Point):
        """
        move to the test position
        :param p:
        :return:
        """
        await self.api.move_to(self.mount, p, target="pipette", )


