from ot_type import TipRackRowPositionDefinition, Mount


class Utils:
    @classmethod
    def get_well_by_num(cls, num, slot_name='2'):
        row = int(num / 12)
        col = int(num % 12)
        col += 1
        return f"{TipRackRowPositionDefinition[row]}{col}"

    @classmethod
    def get_mount_from_value(cls, mount: str) -> Mount:
        if mount == 'left':
            return Mount.LEFT
        elif mount == "right":
            return Mount.RIGHT
        else:
            raise ValueError("un expect input")


if __name__ == '__main__':
    for i in range(96):
        ret = Utils.get_well_by_num(i)
        print(ret)
