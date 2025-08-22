from googledrive import googledrive
from csvdriver import CsvFunc
from sheetdrive import sheetdrive
from yamldrive import yamlfunc
import os, sys
import re
from globalconfig import ROWSINDEX

codepath = os.path.dirname(__file__)
addpath = os.path.dirname(os.path.dirname(__file__))
addpath2 = os.path.dirname(addpath)
if addpath not in sys.path:
    sys.path.append(addpath)
if addpath2 not in sys.path:
    sys.path.append(addpath2)

csvdr = CsvFunc()
yamldr = yamlfunc()


class updata_class():
    def __init__(self) -> None:
        # 更新数据
        # self.shedrive = None
        # self.shedrive = sheetdrive()
        # self.gdrive = googledrive()
        self.yamldata = yamldr.readyaml(failpath=codepath, nama="updata.yaml")
        # self.star_int()

    def star_int(self):
        self.shedrive = sheetdrive()
        self.gdrive = googledrive()

    # 单通道容量数据上传
    def updatavolume_1CH(self, upfilepath, pipettesn, pipettetype, upfailelist):
        """_summary_

        Args:
            upfilepath (str): 原始数据的地址
            pipettesn (str): 要上传数据的移液器SN
            pipettetype (str): 移液器的类型 like: P50S P1000S P50M P1000M
        """
        # 更新容量数据demo
        if isinstance(self.yamldata, dict) and "1ch_updata_volume" in self.yamldata and isinstance(
                self.yamldata["1ch_updata_volume"], list):
            u = self.yamldata["1ch_updata_volume"][0]
        else:
            raise ValueError("self.yamldata 中不存在 '1ch_updata_volume' 键，或其对应值不是列表类型")
        if u["explanation"] == "VOLUME1CH":
            if u["ifupdata"]:
                # 获取源数据文件路径
                f = upfilepath
                # 定义正则表达式模式
                # pattern = r'-(P\w+SV\d+A\d+)-qc\.csv'

                # # 匹配第一个字符串的目标部分
                # match1 = re.search(pattern, f)
                # if match1:
                #     pipettesn = match1.group(1)
                #     print(pipettesn)  # 输出 P1KSV3420230201A02

                # pattern = r"CSVReport-(P\w+SV\d{10}M\d{2})"
                # match = re.search(pattern, f)

                # if match:
                #     pipettesn = match.group(1)
                #     print(pipettesn)  # 输出：P1KSV3620250415M05

                newfilename = pipettesn + "-qc"
                pastesheetname = pipettetype
                # if str(pipettesn).upper().find("P50S") != -1:
                #     pastesheetname = "P50S"
                # elif str(pipettesn).upper().find("P1KS") != -1:
                #     pastesheetname = "P1000S"
                fz = self.gdrive.get_coppy_file(u["ifcopytemplate"]["copyTempExcelId"], newfilename)
                if fz:
                    u["updatafileid"] = fz[1]
                    updatafileid = u["updatafileid"]
                    # 获取更新sheet名称
                    sheetname = u["ExcelSheetName"][0]
                    # 获取需要更新的列范围
                    ranglist = u["Range"]
                    datalen = len(ranglist)

                    # 获取源数据
                    excelfail = csvdr.Read_csv_all(path=f)
                    # 获取源数据
                    excelfail = f
                    exdata = csvdr.Read_csv_all(path=excelfail)

                    alldatalist = []
                    allrangelist = []
                    starrange = 1
                    setdatalen = len(exdata)
                    setdata = []
                    for i, ii in enumerate(exdata):
                        lenh = len(ii[0])
                        for d in range(datalen - lenh):
                            ii[0].append("")
                        setdata.append(ii[0])
                        rangeb = ROWSINDEX[datalen - 1]
                        rangel = "!A{}:{}{}".format(starrange, rangeb, i + 1)
                        if int(i + 1) % 1000 == 0:
                            alldatalist.append(setdata)
                            allrangelist.append(rangel)
                            starrange = i + 1 + 1
                            setdata = []
                            continue
                        elif int(i + 1) == setdatalen:
                            alldatalist.append(setdata)
                            allrangelist.append(rangel)
                            starrange = i + 1 + 1

                    getret = self.shedrive.updata_excel_sheel_page_list(spreadsheet_id=updatafileid,
                                                                        range_name=sheetname, rangelist=allrangelist,
                                                                        new_values=alldatalist)
                    if getret:
                        print("更新文件:成功", u)
                    else:
                        print("更新文件:失败", u)

                copydatalist = []
                for cop in u["ifcopydata"]:
                    if cop["off/on"]:
                        cop['copyExcelId'] = updatafileid
                        copyExcelID = cop['copyExcelId']
                        stname = cop['copyExcelSheetName']
                        rangeval = cop["copyRange"]
                        copydata = self.shedrive.get_excel_sheel_page(copyExcelID, stname, "ROWS", rangeval)
                        copydatalist.append(copydata)

                for cs, pase in enumerate(u["ifpaste"]):
                    if pase["off/on"]:

                        paseexcelid = pase["pastefileid"]
                        pase["pastesheetname"] = pastesheetname
                        pasesheetname = pase["pastesheetname"]

                        values = self.shedrive.get_excel_sheel(spreadsheetId=paseexcelid, range=pasesheetname)
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
                        sheetlink = f"https://docs.google.com/spreadsheets/d/{copyExcelID}/edit#gid=0"  # 表格链接
                        pasedata[0][0].insert(0, sheetlink)
                        print(pasedata)
                        self.shedrive.updata_excel_sheel_page(spreadsheet_id=paseexcelid, range_name=pasesheetname,
                                                              range=rangeval, new_values=pasedata[0])

                        # 移动数据到每月文件夹
                        self.gdrive.move_files(updatafileid, "1u0ZgpBsIr6DNZTjiM8CRVJTMvfXYDyrc")

                        # 上传原始文件到文件夹
                        for file_path in upfailelist:
                            if u["ifupdatarawdata"][0]["off/on"]:
                                folder_id = u["ifupdatarawdata"][0]["folder_id"]
                                upfaileid = self.gdrive.upload_to_drive(file_path, folder_id)
                                if upfaileid != '':
                                    print("上传文件成功")


if __name__ == "__main__":
    aa = updata_class()
    aa.star_int()
    aa.updatavolume_1CH(
        "/Users/yew/Desktop/production-scripts/data_center/google_driver_handler/gravimetric-ot3-p1000-single_run-25-07-11-17-58-22_CSVReport-P1KSV3520230727A04-qc.csv",
        "P1KSV3520230727A04", "P1000S",
        ["/Users/yew/Desktop/production-scripts/data_center/google_driver_handler/gravimetric-ot3-p1000-single_run-25-07-11-17-58-22_CSVReport-P1KSV3520230727A04-qc.csv"])
    # #更新数据
    # shedrive = None
    # shedrive = sheetdrive()
    # gdrive = googledrive()
    # yamldata = yamldr.readyaml(failpath= codepath,nama= "updata.yaml")

    # #更新容量数据demo
    # for i, u in enumerate(yamldata["1ch_updata"]): 
    #     if u["explanation"] == "VOLUME1CH":
    #         if u["ifupdata"]:
    #             updatavolume_1CH(u=u)

    # 更新函数demo
    # for i, u in enumerate(yamldata["tabledataupdate"]): 
    #     if u["explanation"] == "function":
    #         if u["ifupdata"]:
    #             updata_Excel_1000(u=u)
    # updata_Excel()
