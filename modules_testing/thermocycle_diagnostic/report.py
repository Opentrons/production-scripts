import csv
import time


class Report:
    def __init__(self, csv_name: str):
        self.csv_name = csv_name + "-" + time.strftime("%Y%m%d") + '.csv'

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
    r = Report("test")
    r.write_row(['n', 'c', 2])
    r.write_row([3, 4, 3])
    r.write_row([3, 4, 3])
    r.write_row([3, 4, 3])
    r.write_last_row([2, 3, 4])
    r.write_last_row([1, 3, 4])
