from Csv import CsvFunc
import sys,os

def updatasection():
    relative_path = input("输入要分割的csv名称[如:demo],按回车确认:")
    
    if getattr(sys, 'frozen', False):
        # 在EXE文件中运行
        base_path= os.path.dirname(sys.executable)
    else:
        # 在脚本中运行
        base_path= os.path.dirname(os.path.abspath(__file__))

    print(base_path)
        
    #yuanshipath =  os.path.join(base_path, relative_path)
    aa = CsvFunc(path=base_path,fileName=str(relative_path)+".csv")
    alllist = aa.Readlist()

    datalen = len(alllist)
    
    if datalen - 23040 >= 0:
        path1 = os.path.join(base_path, str(relative_path)+ "_1.csv")
        aa.Writeallpath(alllist[0:23040],path1)
        print("已生成：",path1)
    if datalen - 46080 >= 0:
        path1 = os.path.join(base_path, str(relative_path)+"_2.csv")
        aa.Writeallpath(alllist[23040:46081],path1)
        print("已生成：",path1)
    if datalen - 46081 >= 0:
        path1 = os.path.join(base_path, str(relative_path)+"_3.csv")
        aa.Writeallpath(alllist[46081:],path1)
        print("已生成：",path1)
    
   
    

    




if __name__ == '__main__':
    while True:
        try:
            print("把需要分割的csv文件放在程序的同一个文件夹下")
            updatasection()
        except Exception as err:
            print("数据拆分出错,请重试,错误信息:{}".format(err))