import csv
import os.path
import time


class Report:
    def __init__(self, file_path, csv_name: str):
        self.csv_name = csv_name + "-" + time.strftime("%Y%m%d") + '.csv'
        self.csv_name = os.path.join(file_path, self.csv_name)

    def init_report(self):
        """
        init csv
        :return:
        """

        head1 = ["Test: Barcode Scan", "Test: Get System Info", "Test: Get System Info", "Test: Get Board HW Revision",
                 "Test: UI LED Test", "Test: Front Button LED", "Test: Seal Retracted Switch Test",
                 "Test: Seal Retracted Switch Test",
                 "Test: Plate Lift Test", "Test: Lid Open Switch Test", "Test: Lid Open Switch Test",
                 "Test: Front Button Press", "Test: Front Button Press", "Test: Close Lid Extend Seal Switch Test",
                 "Test: Close Lid Extend Seal Switch Test",
                 "Test: Lid Thermistor Test", "Test: Lid Thermistor Test", "Test: Plate Thermistor Test",
                 "Test: Plate Thermistor Test",
                 "Test: Heatsink Fan Test", "Test: Heatsink Fan Test", "Test: Lid Heater Test", "Test: Lid Heater Test",
                 "Test: Cold Peltier Test", "Test: Cold Peltier Test", "Test: Hot Peltier Test",
                 "Test: Hot Peltier Test", "Test: Plate Temperature&Light", "Test: Plate Temperature&Light"]

        head2 = ["Unit Barcode Number", "Unit Firmware Serial Number", "Unit Firmware Revision",
                 "Unit Board HW Revision",
                 "RESULT", "RESULT", "M901.D Response", "RESULT", "RESULT", "M901.D Response", "RESULT",
                 "M901.D Response", "RESULT", "M901.D Response", "RESULT", "Lid Thermistor M141 Response", "RESULT",
                 "Plate Thermistor M105.D Response", "RESULT", "Heatsink Fan M103.D Response", "RESULT",
                 "M141 Response",
                 "RESULT", "Cold Peltier Test M105.D Response", "RESULT", "Hot Peltier Test M105.D Response", "RESULT",
                 "RESULT Blue(<23C)", "RESULT Red(>23C)"
                 ]
        if os.path.exists(self.csv_name):
            pass
        else:
            self.write_row(head1)
            self.write_row(head2)

    def write_row(self, row: list):
        """
        write list to csv
        :param row:
        :return:
        """
        with open(self.csv_name, 'a+', encoding='utf8', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(row)

    def write_last_row(self, row: list):
        """
        del last row and replace
        :param row:
        :return:
        """

        def delete_lines(filename, tail):
            fin = open(filename, 'r')
            a = fin.readlines()
            fout = open(filename, 'w')
            b = ''.join(a[:-tail])
            fout.write(b)

        delete_lines(self.csv_name, 1)

        self.write_row(row)


if __name__ == '__main__':
    pass
