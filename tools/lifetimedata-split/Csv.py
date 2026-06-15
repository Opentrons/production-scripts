import csv
import os
import time


string = 'stringtest'
headers = ('class','name','sex','height','year',1,2,3,4,5,6,7,8,9)

rows = (
    (1,'xiaoming','male',168,23),
    (1,'xiaohong','female',162,22),
    (2,'xiaozhang','female',163,21),
    (2,'xiaoli','male',158,21)
)
dic ={'a':1,'b':2,'c':3,'d':4}
res = {}
res['P12v'] = {'spec': (11.0,13.0), 'res': 0}
res['P12v']['spec'] = {'high':11,'low':13}
res['P36v'] = {'spec': (11.0,13.0), 'res': 0}
res['P36v']['spec'] = {'high':11,'low':13}
# list = []
# list.append(res)
LimitsConfigFileName = '5048LimitConfig.report'


class CsvFunc():
    def __init__(self,path='C:/ICT913-00050_TestData/',fileName= "ICT913-00050_TestData_" + time.strftime('%Y%m%d',time.localtime())+".report"):
        
        self.path = path
        self.filename = fileName # "ICT_{}_TestData_".format(fileName) + time.strftime('%Y%m%d',time.localtime())+".report"

        print(self.path)
        print(self.filename)
        self.fullpath = os.path.join(self.path,self.filename)
        # self.header = True
        self.updateHeader()
        if (not os.path.exists(self.path)):
            os.mkdir(self.path)

    def updateHeader(self):
        if os.path.exists(self.fullpath):
            self.header = False
        else:
            self.header = True
    def Read(self):
        with open(self.fullpath, 'rt')as f:
            lines = []
            for line in f:
                if line != '\n':
                    lines.append(line)
            return lines

    def NextRow(self):
        with open(self.fullpath,'a')as f:
            f.write('\r')

    def WriteStrAtEndCell(self,str):
        with open(self.fullpath,'a')as f:
            f.write(str)

    def WriteStrAtNextRow(self,str):
        with open(self.fullpath,'a')as f:
            f.write('\r' + str + '\r')

    def WriteStrAtNextColumn(self,str):
        with open(self.fullpath,'a')as f:
            f.write(',' + str)

    def WriteRow(self,rowdata):
        with open(self.fullpath, 'a',newline='',encoding='utf-8-sig')as f:
            w = csv.writer(f)
            w.writerow(rowdata)

    def WriteRows(self,rowsdata):
        with open(self.fullpath, 'a',newline='',encoding='utf-8-sig')as f:
            w = csv.writer(f)
            w.writerows(rowsdata)
    def Writeall(self,writedata):
        with open(self.fullpath, 'w', newline='') as file:
            writer = csv.writer(file)
            writer.writerows(writedata)

    def Writeallpath(self,writedata,name):
        with open(name, 'w', newline='') as file:
            writer = csv.writer(file)
            writer.writerows(writedata)
    def Readlist(self):
        rowslist = []
        with open(self.fullpath, 'r') as file:
            reader = csv.reader(file)
            rowslist = list(reader)
        return rowslist

if __name__== '__main__':
    f = CsvFunc()
    