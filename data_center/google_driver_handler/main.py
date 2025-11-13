from googledrive import googledrive
from csvdriver import CsvFunc
from sheetdrive import sheetdrive
from yamldrive import yamlfunc
import os,sys
import re
from globalconfig import ROWSINDEX
from tools import unzip_file
codepath = os.path.dirname(__file__)
addpath = os.path.dirname(os.path.dirname(__file__))
addpath2 = os.path.dirname(addpath)
if addpath not in sys.path:
    sys.path.append(addpath)
if addpath2 not in sys.path:
    sys.path.append(addpath2)


csvdr = CsvFunc()
yamldr = yamlfunc()


def upfail():
    gdrive = googledrive()
    
def updata_Excel():
    shedrive = sheetdrive()
    yamldata = yamldr.readyaml(failpath= codepath,nama= "updata.yaml")
    for i, u in enumerate(yamldata["tabledataupdate"]):
        allfail = csvdr.get_folder_all_fail(path= u["failfrompath"],keyworld= u["failkeywords"])
        excelfail = allfail[i]
        exdata = csvdr.Read_csv_all(path=excelfail)
        for i,ii in enumerate(exdata):
            setdata = []
            setdata.append(ii)
            lenh = len(ii[0])
            rangeb = ROWSINDEX[lenh-1]
            rangel = "!A{}:{}{}".format(i+1,rangeb,i+1)
            shedrive.updata_excel_sheel_page(spreadsheet_id="17Y6-PDvR9NcVjj-9gegbej7yuEtmDftIMBCP3zX3oVs",range_name="Pip1",range=rangel,new_values=ii)

        print("更新文件:成功",u)

def updata_Excel_1000(u):
    """更新函数数据表格
    param u 配置字典
    """

    spreadsheet_idlist = u["updatafileid"]

    #获取源数据文件路径
    allfail = csvdr.get_folder_all_fail(path= u["filefrompath"],keyworld= u["filekeywords"])
    print("获取文件路径：",allfail)

    #获取需要更新的列范围
    ranglist = u["Range"]
    datalen = len(ranglist)


    for excelid in spreadsheet_idlist:
        #获取更新sheet名称
        updatasheet = u["ExcelSheetName"]
        for iii,sheetname in enumerate(updatasheet):

            #获取源数据
            excelfail = allfail[iii]
            exdata = csvdr.Read_csv_all(path=excelfail)


            alldatalist = []
            allrangelist = []
            starrange = 1
            setdatalen = len(exdata)
            setdata = []
            for i,ii in enumerate(exdata):
                lenh = len(ii[0])
                for d in range(datalen - lenh):
                    ii[0].append("")
                setdata.append(ii[0])
                rangeb = ROWSINDEX[datalen-1]
                rangel = "!A{}:{}{}".format(starrange,rangeb,i+1)
                if int(i+1) % 1000 == 0:
                    alldatalist.append(setdata)
                    allrangelist.append(rangel)
                    starrange = i + 1 + 1
                    setdata = []
                    continue
                elif int(i+1) == setdatalen:
                    alldatalist.append(setdata)
                    allrangelist.append(rangel)
                    starrange = i + 1 + 1

            getret = shedrive.updata_excel_sheel_page_list(spreadsheet_id=excelid,range_name=sheetname,rangelist=allrangelist,new_values=alldatalist)
            if getret:
                print("更新文件:成功",u)
            else:
                print("更新文件:失败",u)

    copydatalist = []
    for cop in  u["ifcopydata"]:
        if cop["off/on"]:
            copyExcelID = cop['copyExcelId']
            stname = cop['copyExcelSheetName']
            rangeval = cop["copyRange"]
            copydata = shedrive.get_excel_sheel_page(copyExcelID,stname,"ROWS",rangeval)
            copydatalist.append(copydata)
    
    for cs,pase in enumerate(u["ifpaste"]):
        if pase["off/on"]:
            paseexcelid = pase["pastefileid"]
            pasesheetname = pase["pastesheetname"]
            rangeval = pase["pasteRange"]
            pasedata = copydatalist[cs]
            shedrive.updata_excel_sheel_page_list(spreadsheet_id=paseexcelid,range_name=pasesheetname,rangelist=rangeval,new_values=pasedata)



#单通道数据上传
def updatavolume_1CH(u):
    #获取源数据文件路径
    base_path = os.path.abspath(sys.argv[0])
    base_path2 = os.path.abspath(".")
    upfilepath = os.path.join(base_path2,u["filefrompath"])
    

    allfail = csvdr.get_folder_all_fail(path= upfilepath,keyworld= u["filekeywords"])
    for f in allfail:

        pipettesn = 'NONE'
        # 定义正则表达式模式
        # pattern = r'-(P\w+SV\d+A\d+)-qc\.report'

        
        # # 匹配第一个字符串的目标部分
        # match1 = re.search(pattern, f)
        # if match1:
        #     pipettesn = match1.group(1)
        #     print(pipettesn)  # 输出 P1KSV3420230201A02

        pattern = r"CSVReport-(P\w+SV\d{10}M\d{2})"
        match = re.search(pattern, f)

        if match:
            pipettesn = match.group(1)
            print(pipettesn)  # 输出：P1KSV3620250415M05

        newfilename = pipettesn+"-qc"

        pastesheetname = ''
        if str(pipettesn).upper().find("P50S") != -1:
            pastesheetname = "P50S"
        elif str(pipettesn).upper().find("P1KS") != -1:
            pastesheetname = "P1000S"
        fz = gdrive.get_coppy_file(u["ifcopytemplate"]["copyTempExcelId"],newfilename)
        if fz:
            u["updatafileid"] = fz[1]
            updatafileid = u["updatafileid"]
            #获取更新sheet名称
            sheetname = u["ExcelSheetName"][0]
            #获取需要更新的列范围
            ranglist = u["Range"]
            datalen = len(ranglist)

            #获取源数据
            excelfail = csvdr.Read_csv_all(path=f)
            #获取源数据
            excelfail = f
            exdata = csvdr.Read_csv_all(path=excelfail)


            alldatalist = []
            allrangelist = []
            starrange = 1
            setdatalen = len(exdata)
            setdata = []
            for i,ii in enumerate(exdata):
                lenh = len(ii[0])
                for d in range(datalen - lenh):
                    ii[0].append("")
                setdata.append(ii[0])
                rangeb = ROWSINDEX[datalen-1]
                rangel = "!A{}:{}{}".format(starrange,rangeb,i+1)
                if int(i+1) % 1000 == 0:
                    alldatalist.append(setdata)
                    allrangelist.append(rangel)
                    starrange = i + 1 + 1
                    setdata = []
                    continue
                elif int(i+1) == setdatalen:
                    alldatalist.append(setdata)
                    allrangelist.append(rangel)
                    starrange = i + 1 + 1

            getret = shedrive.updata_excel_sheel_page_list(spreadsheet_id=updatafileid,range_name=sheetname,rangelist=allrangelist,new_values=alldatalist)
            if getret:
                print("更新文件:成功",u)
            else:
                print("更新文件:失败",u)

        copydatalist = []
        for cop in  u["ifcopydata"]:
            if cop["off/on"]:
                cop['copyExcelId'] = updatafileid
                copyExcelID = cop['copyExcelId']
                stname = cop['copyExcelSheetName']
                rangeval = cop["copyRange"]
                copydata = shedrive.get_excel_sheel_page(copyExcelID,stname,"ROWS",rangeval)
                copydatalist.append(copydata)

        for cs,pase in enumerate(u["ifpaste"]):
            if pase["off/on"]:

                paseexcelid = pase["pastefileid"]
                pase["pastesheetname"] = pastesheetname
                pasesheetname = pase["pastesheetname"]
                

                values = shedrive.get_excel_sheel(spreadsheetId=paseexcelid,range=pasesheetname)
                if values:
                    found_index = -1

                    for index, row in enumerate(values):
                        # if "P1KS" in row or "P50S" in row:
                        #     found_index = len(values) - index
                        #     break
                        # elif "PACKED FOR SHIPPING" in row:
                        #     found_index = len(values) - index
                        #     break
                        if "P1000S" in row or "P50S" in row or "P50M" in row or "P1000M" in row:
                            found_index = index + 1
                            noval = values[found_index]

                            if "P1000S" not in row and "P50S" not in row and "P50M" not in row and "P1000M" not in row:
                                break



                    

                    last_row_index = found_index
                    last_row_range = f"!D{last_row_index}:AN{last_row_index}"  # 替换 Z 为你的最大列
                    print("最后一行范围：", last_row_range)

                pase["pasteRange"][0] = f"!D{last_row_index}:AN{last_row_index}" 
                rangeval = pase["pasteRange"][0]
                
                pasedata = copydatalist[cs]
                sheetlink = f"https://docs.google.com/spreadsheets/d/{copyExcelID}/edit#gid=0" #表格链接
                pasedata[0][0].insert(0,sheetlink)
                print(pasedata)
                shedrive.updata_excel_sheel_page(spreadsheet_id=paseexcelid,range_name=pasesheetname,range=rangeval,new_values=pasedata[0])

                #移动数据到每月文件夹
                gdrive.move_files(updatafileid,"1u0ZgpBsIr6DNZTjiM8CRVJTMvfXYDyrc")

                #上传原始文件到文件夹



if __name__ == "__main__":

    
    
    #更新数据
    shedrive = None
    shedrive = sheetdrive()
    gdrive = googledrive()
    yamldata = yamldr.readyaml(failpath= codepath,nama= "updata.yaml")

    #更新容量数据demo
    for i, u in enumerate(yamldata["1ch_updata"]): 
        if u["explanation"] == "VOLUME1CH":
            if u["ifupdata"]:
                updatavolume_1CH(u=u)

    
    #更新函数demo
    # for i, u in enumerate(yamldata["tabledataupdate"]): 
    #     if u["explanation"] == "function":
    #         if u["ifupdata"]:
    #             updata_Excel_1000(u=u)
    # updata_Excel()