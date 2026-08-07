import json
import sys
import os

a=["1"]
print(a)
if "1"  in a:
    print(3)
relative_path = "ylcs.txt"
if getattr(sys, 'frozen', False):  # 是否Bundle Resource
    base_path = sys._MEIPASS
    #base_path = os.path.abspath(sys.argv[0])
else:
    base_path = os.path.dirname(__file__)
    
yuanshipath =  os.path.join(base_path, relative_path)

with open(yuanshipath,encoding='utf-8') as f:
    
    aaa = f.readlines()
    print(aaa)
list = []

inputname = input("请输入保存函数的文件名称(input save fail name)：")
if inputname == "":
    savename = "function.txt"
else:

    savename = str(inputname) + ".txt"
savenamepath =  os.path.join(base_path, savename)
for csa ,ii in enumerate(aaa):
    #print(ii)
    aaaaaaa = []
    aa =str(ii).replace("\t",",").replace(" ",",").replace("\n","").split(",")
    linval = ''
    for cs,iiiii in enumerate(aa):
        aaaaaaa.append(float(iiiii))
        if cs+1 >= len(aa):
            linval = linval+iiiii
        else:
            linval = linval+iiiii+","
    if csa + 1 >= len(aaa):
        linval = "["+linval +"]\n"
    else:
        linval = "["+linval +"],\n"
    

    with open(savenamepath,mode='a',encoding='utf-8') as f:
        f.write(linval)

    print(aa)
    list.append(aaaaaaa)

dadas = []
dadas.append(list)
dddd = {}
dddd.setdefault("aspirate",list)
print(dddd)
print("函数文件保存目录(fail path):",savenamepath)
