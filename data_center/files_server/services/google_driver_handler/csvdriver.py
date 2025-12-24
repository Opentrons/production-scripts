import csv
import os
import time


class CsvFunc():
    def __init__(self) -> None:
        pass

    def Read_csv(self,path):
        #self.fullpath = os.path.join(path,filename)
        self.fullpath = path
        with open(self.fullpath, 'rt')as f:
            lines = []
            for line in f:
                if line != '\n':
                    line = str(line).replace("\n","").replace("\r","")
                    rowval = []
                    rowval.append(line)
                    lines.append(rowval)
            return lines
        
    
    def Read_csv_all(self,path):
        #self.fullpath = os.path.join(path,filename)
        self.fullpath = path
        with open(self.fullpath, 'rt')as f:
            lines = []
            for line in f:
                if line != '\n':
                    line = str(line).replace("\n","").split(",")
                    rowval = []
                    rowval.append(line)
                    lines.append(rowval)
            return lines
    
    
    def get_folder_all_fail(self,path,keyworld):
        """
        获取文件夹内csv文件
        param path 文件夹路径
        """
        allname = []
        try:
            for root, dirs, files in os.walk(path):
                for name in files:
                    if name.find(str(keyworld)) != -1:
                        pathval1 = os.path.join(path,name)
                        allname.append(pathval1)
            return allname
        except Exception as err:
            print(err)
            return allname



if __name__ == "__main__":
    aa = CsvFunc()
    #aa.get_folder_all_fail("""/Users/yew/googledriver/""")
    aa.Read_csv_all("""/Users/yew/googledriver/gravimetric-ot3-p1000_run-23-04-11-05-19-26_CSVReport-P1KSV3420230115A01.csv""")