from google_driver_handler.googledriveM import googledrive
from google_driver_handler.csvdriver import CsvFunc
# from sheetdrive import sheetdrive
from google_driver_handler.yamldrive import yamlfunc
import os, sys
import re
from google_driver_handler.globalconfig import ROWSINDEX
from datetime import datetime
from enum import Enum, auto
from typing import Optional, Callable

class Productions(Enum):
    Robot = "Robot"
    P50S = "P50S"
    P1000S = "P1000S"
    P50M = "P50M"
    P1000M = "P1000M"
    P50S_Millipore = "P50S Millipore"
    P1000S_Millipore = "P1000S Millipore"
    P50M_Ultima = "P50M Ultima"
    P1000M_Ultima = "P1000M Ultima"
    P50M_Millipore = "P50M Millipore"
    P1000M_Millipore = "P1000M Millipore"




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
    def __init__(self,Test_environment="debug") -> None:
        """
        Test_environment:测试环境切换 debug 调试使用 Production 生产环境

        Args:
            Test_environment (str, optional): _description_. Defaults to "debug".
        """
        # 更新数据
        if Test_environment == "debug":
            self.yamldata = yamldr.readyaml(failpath=codepath, nama="google_driver_handler/updata.yaml")
        elif Test_environment == "Production":
            self.yamldata = yamldr.readyaml(failpath=codepath, nama="google_driver_handler/updata_production.yaml")
        self.nowyear,self.nowmonth = self.get_current_month()

    def star_int(self):
        #self.shedrive = sheetdrive()
        self.gdrive = googledrive()

    def get_current_month(self):
        """获取服务器当前月份（1~12）"""
        now = datetime.now()   # 获取当前服务器本地时间
        return now.year,now.month
    # 1CH 8CH通道容量数据上传
    def updatavolume_1CH_8CH(self, upfilepath, pipettesn, pipettetype, upfailelist,Note_str="AUTO-UPLOAD-TE"):
        """_summary_

        Args:
            upfilepath (str): 原始数据的地址
            pipettesn (str): 要上传数据的移液器SN
            pipettetype (str): 移液器的类型 只支持（对应TRACKING SHEET里面的sheet名称）: P50S, P1000S, P50M, P1000M, P50S Millipore,P1000S  Millipore,P50M Ultima,P1000M Ultima , P50M Millipore , P1000M Millipore 
            Note_str (str):  TRACKING SHEET备注信息
        return:
        [uptemp = None #上传数据状态
        testpass = None #测试结果
        testall = None #所有测试结果
        move_success = None #移动数据状态
        upfailpass = None #上传源文件状态]
        """

        uptemp = "False" #上传数据状态
        testpass = None #测试结果
        testall = None #测试结果详细信息
        move_success = "False" #移动数据状态
        upfailpass = "False" #上传源文件状态

        List_1ch = ["P50S" ,"P1000S" ,"P50S Millipore" ,"P1000S  Millipore"]
        List_8ch = ["P50M" ,"P1000M","P50M Ultima","P1000M Ultima","P50M Millipore","P1000M Millipore"]

        # 更新容量数据demo
        if pipettetype in List_1ch: #== "P50S" or pipettetype == "P1000S" or pipettetype =="P50S Millipore" or pipettetype =="P1000S  Millipore":
            if isinstance(self.yamldata, dict) and "1ch_updata_volume" in self.yamldata and isinstance(
                self.yamldata["1ch_updata_volume"], list):
                u = self.yamldata["1ch_updata_volume"][0]
            else:
                raise ValueError("self.yamldata 中不存在 '1ch_updata_volume' 键，或其对应值不是列表类型")

        elif pipettetype in List_8ch: #== "P50M" or pipettetype == "P1000M"or pipettetype =="P50M Ultima"or pipettetype =="P1000M Ultima"or pipettetype =="P50M Millipore"or pipettetype =="P1000M Millipore":
            if isinstance(self.yamldata, dict) and "8ch_updata_volume" in self.yamldata and isinstance(
                    self.yamldata["8ch_updata_volume"], list):
                u = self.yamldata["8ch_updata_volume"][0]
            else:
                raise ValueError("self.yamldata 中不存在 '8ch_updata_volume' 键，或其对应值不是列表类型")

        if u["ifupdata"]:
            #创建原始文件的文件夹（SN命名）
            now = datetime.now()
            # 格式化为 YYYYMMDDHHMMSS
            current_time_str = now.strftime("%Y%m%d%H%M%S")
            # 获取源数据文件路径
            f = upfilepath
            newfilename = pipettesn + "-qc" + f"-{current_time_str}"
            pastesheetname = pipettetype
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

                getret = self.gdrive.update_excel_sheet_page_batch(spreadsheet_id=updatafileid,
                                                                    sheet_name=sheetname, ranges=allrangelist,
                                                                    new_values=alldatalist)
                if getret:
                    uptemp = "PASS"
                    print("更新文件:成功", u)
                else:
                    uptemp = "FAIL"
                    print("更新文件:失败", u)
            if uptemp == "PASS":
                copydatalist = []
                for cop in u["ifcopydata"]:
                    if cop["off/on"]:
                        cop['copyExcelId'] = updatafileid
                        copyExcelID = cop['copyExcelId']
                        stname = cop['copyExcelSheetName']
                        rangeval = cop["copyRange"]
                        copydata = self.gdrive.get_excel_sheet_page(copyExcelID, stname, "ROWS", rangeval)
                        testpass = copydata[0][0][2] #测试结果
                        testall = copydata
                        copydatalist.append(copydata)

                for cs, pase in enumerate(u["ifpaste"]):
                    if pase["off/on"]:

                        paseexcelid = pase["pastefileid"]
                        pase["pastesheetname"] = pastesheetname
                        pasesheetname = pase["pastesheetname"]

                        values = self.gdrive.get_excel_sheet(spreadsheetId=paseexcelid, range=pasesheetname)
                        if values:
                            found_index = -1

                            for index, row in enumerate(values):
                                if "P1000S" in row or "P50S" in row or "P50M" in row or "P1000M" in row:
                                    found_index = index + 2
                                    noval = values[found_index]

                                    if "P1000S" not in row and "P50S" not in row and "P50M" not in row and "P1000M" not in row:
                                        break
                            last_row_index = found_index
                            star=pase["pastelineRange"]["star"]
                            end = pase["pastelineRange"]["end"]
                            last_row_range = f"!{star}{last_row_index}:{end}{last_row_index}"  # 替换 Z 为你的最大列
                            print("最后一行范围：", last_row_range)

                        Noteval = pase["pastelineRange"]["note"]
                        pase["pasteRange"][0] = f"!{star}{last_row_index}:{end}{last_row_index}"
                        rangeval = pase["pasteRange"][0]
                        NOTES = f"!{Noteval}{last_row_index}:{Noteval}{last_row_index}"


                        pasedata = copydatalist[cs]
                        sheetlink = f"https://docs.google.com/spreadsheets/d/{copyExcelID}/edit#gid=0"  # 表格链接
                        pasedata[0][0].insert(0, sheetlink)
                        print(pasedata)
                        self.gdrive.update_excel_sheet_page_batch(spreadsheet_id=paseexcelid, sheet_name=pasesheetname,ranges=rangeval, new_values=pasedata[0])
                        self.gdrive.update_excel_sheet_page_batch(spreadsheet_id=paseexcelid, sheet_name=pasesheetname,ranges=NOTES, new_values=[[Note_str]])
                        # 移动数据到每月文件夹
                        monthid = u["movetestfail"][self.nowyear][self.nowmonth]
                        move_success=self.gdrive.move_file_Multi_level(updatafileid, monthid)


                        faterid = u["ifupdatarawdata"][self.nowyear][self.nowmonth]
                        upid=self.gdrive.create_folders(f"{pipettesn}_{current_time_str}",faterid)

                        # 上传原始文件到文件夹
                        for file_path in upfailelist:
                            upfaileid = self.gdrive.upload_to_drive(file_path, upid)
                            if upfaileid != '':
                                upfailpass = "True"
                            else:
                                upfailpass = "False"

        return [uptemp,testpass,testall,move_success["success"],upfailpass]

    def upload_testing_data_demo(self, file_name: str, sn: str, production: Productions, zip_file: str,
                                 note_str="AUTO-UPLOAD-TE", progress_callback: Optional[Callable[[int], None]] = None):
        """
        upload datas
        :param file_name:
        :param sn:
        :param production:
        :param zip_file:
        :param note_str:
        :param progress_callback:
        :return:
        """
        print(f"Upload: \n"
              f"File Name: {file_name}\n"
              f"Production: {production.name}\n"
              f"SN: {sn}\n"
              f"Raw Data: {zip_file}")
        for i in range(100):
            if (i + 1) %10 == 0 and progress_callback is not None:
                progress_callback(i+1)


if __name__ == "__main__":
    aa = updata_class()
    import time

    T1 = time.time()
    T2 = time.time()
    aa.star_int()
    # while T2 - T1 <= 3600:
    #     time.sleep(2)
    #     pass

    # typelist=aa.updatavolume_1CH(
    #     "/Users/yew/Desktop/production-scripts/data_center/google_driver_handler/gravimetric-ot3-p1000-single_run-25-07-11-17-58-22_CSVReport-P1KSV3520230727A04-qc.report",
    #     "P1KSV3520230727A04", "P1000S",
    #     ["/Users/yew/Desktop/production-scripts/data_center/google_driver_handler/gravimetric-ot3-p1000-single_run-25-07-11-17-58-22_CSVReport-P1KSV3520230727A04-qc.report","/Users/yew/Desktop/production-scripts/data_center/google_driver_handler/gravimetric-ot3-p1000-single_run-25-07-11-17-58-22_GravimetricRecorder-P1KSV3520230727A04-qc.report"])

    # print(typelist)

    # typelist=aa.updatavolume_1CH(
    #     "/Users/yew/Desktop/production-scripts/data_center/google_driver_handler/gravimetric-ot3-p50-single_run-25-10-14-10-08-07_CSVReport-P50SV3520241218A50-qc.report",
    #     "P50SV3520241218A50", "P50S",
    #     ["/Users/yew/Desktop/production-scripts/data_center/google_driver_handler/gravimetric-ot3-p50-single_run-25-10-14-10-08-07_CSVReport-P50SV3520241218A50-qc.report","/Users/yew/Desktop/production-scripts/data_center/google_driver_handler/gravimetric-ot3-p50-single_run-25-10-14-10-08-07_GravimetricRecorder-P50SV3520241218A50-qc.report"])

    # print(typelist)


    # typelist=aa.updatavolume_1CH_8CH(
    #     "/Users/yew/Desktop/production-scripts/data_center/google_driver_handler/gravimetric-ot3-p50-single_run-25-10-14-10-08-07_CSVReport-P50SV3520241218A50-qc.report",
    #     "P50SV3520241218A50", "P50S",
    #     ["/Users/yew/Desktop/production-scripts/data_center/google_driver_handler/gravimetric-ot3-p50-single_run-25-10-14-10-08-07_CSVReport-P50SV3520241218A50-qc.report","/Users/yew/Desktop/production-scripts/data_center/google_driver_handler/gravimetric-ot3-p50-single_run-25-10-14-10-08-07_GravimetricRecorder-P50SV3520241218A50-qc.report"])

    # print(typelist)

    typelist=aa.updatavolume_1CH_8CH(
        "/Users/yew/Desktop/production-scripts/data_center/google_driver_handler/gravimetric-ot3-p1000-multi_run-25-10-10-16-14-38_CSVReport-P1KMV3520240110A04-qc.report",
        "P1KMV3520240110A04", "P1000M",
        ["/Users/yew/Desktop/production-scripts/data_center/google_driver_handler/gravimetric-ot3-p1000-multi_run-25-10-10-16-14-38_CSVReport-P1KMV3520240110A04-qc.report","/Users/yew/Desktop/production-scripts/data_center/google_driver_handler/gravimetric-ot3-p1000-single_run-25-07-11-17-58-22_GravimetricRecorder-P1KSV3520230727A04-qc.report"])

    print(typelist)