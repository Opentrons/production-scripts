import os,sys
codepath = os.path.dirname(__file__)
addpath = os.path.dirname(os.path.dirname(__file__))
addpath2 = os.path.dirname(addpath)
if addpath not in sys.path:
    sys.path.append(addpath)
if addpath2 not in sys.path:
    sys.path.append(addpath2)
from google_driver_handler.googledriveM import googledrive
from google_driver_handler.csvdriver import CsvFunc
# from sheetdrive import sheetdrive
from google_driver_handler.yamldrive import yamlfunc
import re
from google_driver_handler.globalconfig import ROWSINDEX
from datetime import datetime
from enum import Enum, auto
from typing import Optional, Callable

from files_server.logs import get_logger, setup_logging

setup_logging()
logger = get_logger("upload.to.google.driver")

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
    def updatavolume_1CH_8CH(self, upfilepath, pipettesn, pipettetype, zip_file, func_callback=None,
                                 Note_str="AUTO-UPLOAD-TE"):
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
        sheetlink = "" #测试报告链接
        pasestate = "False" #把测试结果复制到总表
        tracking_sheet = None #总表链接

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
        #进度
        if func_callback != None:
            func_callback(10)
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
            #进度
            if func_callback != None:
                func_callback(20)
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
                    logger.info("更新文件:成功")
                else:
                    uptemp = "FAIL"
                    logger.info("更新文件:失败")
                #进度
                if func_callback != None:
                    func_callback(50)
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
                        #进度
                        if func_callback != None:
                            func_callback(60)

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
                            #logger.info("最后一行范围：", last_row_range)

                        Noteval = pase["pastelineRange"]["note"]
                        pase["pasteRange"][0] = f"!{star}{last_row_index}:{end}{last_row_index}"
                        rangeval = pase["pasteRange"][0]
                        NOTES = f"!{Noteval}{last_row_index}:{Noteval}{last_row_index}"


                        pasedata = copydatalist[cs]
                        sheetlink = f"https://docs.google.com/spreadsheets/d/{copyExcelID}/edit#gid=0"  # 表格链接
                        pasedata[0][0].insert(0, sheetlink)
                        #logger.info(pasedata)
                        ret1 = self.gdrive.update_excel_sheet_page_batch(spreadsheet_id=paseexcelid, sheet_name=pasesheetname,ranges=rangeval, new_values=pasedata[0])
                        ret2 = self.gdrive.update_excel_sheet_page_batch(spreadsheet_id=paseexcelid, sheet_name=pasesheetname,ranges=NOTES, new_values=[[Note_str]])
                        if ret1:
                            pasestate = True
                        #进度
                        if func_callback != None:
                            func_callback(80)
                        
                        allgid = self.gdrive.get_sheet_gid_map(paseexcelid)
                        tracking_sheet = f"https://docs.google.com/spreadsheets/d/{paseexcelid}/edit?gid={allgid[pastesheetname]}#gid={allgid[pastesheetname]}"  # 表格链接
                        
                        # 移动数据到每月文件夹
                        monthid = u["movetestfail"][self.nowyear][self.nowmonth]
                        move_success_list=self.gdrive.move_file_Multi_level(updatafileid, monthid)
                        move_success = move_success_list["success"]

                        #进度
                        if func_callback != None:
                            func_callback(90)
                        faterid = u["ifupdatarawdata"][self.nowyear][self.nowmonth]
                        upid=self.gdrive.create_folders(f"{pipettesn}_{current_time_str}",faterid)

                        # 上传原始文件到文件夹
                        upfaileid = self.gdrive.upload_to_drive(zip_file, upid)
                        if upfaileid != '':
                            upfailpass = True
                        else:
                            upfailpass = False
                        #进度
                        if func_callback != None:
                            func_callback(95)

        if uptemp == "False" or move_success == "False" or upfailpass == "False" or pasestate == "False":
            upload_status = False
        else:
            upload_status = True
        
        if func_callback != None:
            func_callback(100) #进度
        return [uptemp,testpass,upfailpass,sheetlink,move_success,testall,upload_status,tracking_sheet]

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
        logger.info(f"Upload: \n"
              f"File Name: {file_name}\n"
              f"Production: {production.name}\n"
              f"SN: {sn}\n"
              f"Raw Data: {zip_file}")
        for i in range(100):
            if (i + 1) %10 == 0 and progress_callback is not None:
                progress_callback(i+1)
    
    # 1CH 8CH通道诊断数据上传
    def UpdateAssemblyQC_1CH_8CH(self, qcfilepath, pipettesn, pipettetype, zip_file, func_callback=None,
                                 csv_link=None):
        """_summary_

        Args:
            qcfilepath (str): qc测试原始数据的地址
            currentpath: 电流测试原始数据地址
            pipettesn (str): 要上传数据的移液器SN
            pipettetype (str): 移液器的类型 只支持（对应TRACKING SHEET里面的sheet名称）: P50S, P1000S, P50M, P1000M, P50S Millipore,P1000S  Millipore,P50M Ultima,P1000M Ultima , P50M Millipore , P1000M Millipore 
            
        return:
        [uptemp = None #上传数据状态
        testpass = None #测试结果
        testall = None #所有测试结果
        move_success = None #移动数据状态
        upfailpass = None #上传源文件状态]
        """
        #产品类型对应TRACKER里面sheet的名称
        nametypedict = {
            "P1000S":"P1000S-template-v1.5",
            "P50S":"P50S-template-v1.5",
            "P1000S Millipore":"Millipore P50S-template-v1.5",
            "P50S Millipore":"Millipore P50S-template-v1.5",
            "P50M":"P50M",
            "P1000M":"P1000M",
            "P1000M Millipore":"Millipore P1000M",
            "P50M Millipore":"Millipore  P1000M",
            "P1000M Ultima":"Ultima P1000M"
        }

        uptemp = "False" #上传数据状态
        testpass = None #测试结果
        testall = None #测试结果详细信息
        move_success = "False" #移动数据状态
        upfailpass = "False" #上传源文件状态
        sheetlink = "" #报告链接
        upload_status = False #上传成功状态
        copytestdata = True #复制数据到总表的状态
        tracking_sheet = None

        List_1ch = ["P50S" ,"P1000S" ,"P50S Millipore" ,"P1000S  Millipore"]
        List_8ch = ["P50M" ,"P1000M","P50M Ultima","P1000M Ultima","P50M Millipore","P1000M Millipore"]
        
        # 更新容量数据demo
        if pipettetype in List_1ch: #== "P50S" or pipettetype == "P1000S" or pipettetype =="P50S Millipore" or pipettetype =="P1000S  Millipore":
            if isinstance(self.yamldata, dict) and "1ch_updata_qc" in self.yamldata and isinstance(
                self.yamldata["1ch_updata_qc"], list):
                u = self.yamldata["1ch_updata_qc"][0]
            else:
                raise ValueError("self.yamldata 中不存在 '1ch_updata_qc' 键，或其对应值不是列表类型")
        
        elif pipettetype in List_8ch: #== "P50M" or pipettetype == "P1000M"or pipettetype =="P50M Ultima"or pipettetype =="P1000M Ultima"or pipettetype =="P50M Millipore"or pipettetype =="P1000M Millipore":
            if isinstance(self.yamldata, dict) and "8ch_updata_qc" in self.yamldata and isinstance(
                    self.yamldata["8ch_updata_qc"], list):
                u = self.yamldata["8ch_updata_qc"][0]
            else:
                raise ValueError("self.yamldata 中不存在 '8ch_updata_qc' 键，或其对应值不是列表类型")
        
        CopyTemplateId = ''
        if pipettetype == "P1000M Ultima":
            CopyTemplateId = u["ifcopytemplate"]["UltimacopyTempExcelId"]
        else:
            CopyTemplateId = u["ifcopytemplate"]["copyTempExcelId"]
        if func_callback != None:
            func_callback(10) #进度
        if u["ifupdata"]:
            pastesheetname = nametypedict[pipettetype]

            now = datetime.now()
            # 格式化为 YYYYMMDDHHMMSS
            current_time_str = now.strftime("%Y%m%d%H%M%S")
            if csv_link == None:
                #创建原始文件的文件夹（SN命名）
                # 获取源数据文件路径
                newfilename = pipettesn + "-QC-CURRENTSPEED" + f"-{current_time_str}"
                fz = self.gdrive.get_coppy_file(CopyTemplateId, newfilename)
                cpid = fz[1]
            else:
                logger.info(f"Get csv id {csv_link}")
                csv_id = str(csv_link).split("/")
                cpid = csv_id[5]
                logger.info(f"{csv_id}, {cpid}")
            if cpid:
                u["updatafileid"] = cpid
                updatafileid = u["updatafileid"]
                sheetlink = f"https://docs.google.com/spreadsheets/d/{cpid}/edit#gid=0"  # 表格链接
                # 获取更新sheet名称
                sheetname = u["ExcelSheetName"][0]
                # 获取需要更新的列范围
                ranglist = u["Range"]
                datalen = len(ranglist)
                # 获取QC源数据
                exdata = csvdr.Read_csv_all(path=qcfilepath)
                if func_callback != None:
                    func_callback(30) #进度
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
                if func_callback != None:
                    func_callback(40) #进度
                getret = self.gdrive.update_excel_sheet_page_batch(spreadsheet_id=updatafileid,
                                                                    sheet_name=sheetname, ranges=allrangelist,
                                                                    new_values=alldatalist)
                if getret:
                    uptemp = "Ture"
                    logger.info("更新文件:成功", u)
                else:
                    uptemp = "Fales"
                    logger.info("更新文件:失败", u)
                if func_callback != None:
                    func_callback(50) #进度
                
            if uptemp == "Ture":
                copydatalist = []
                for cop in u["ifcopydata"]:
                    if cop["off/on"]:
                        if csv_link != None:
                            cop['copyExcelId'] = updatafileid
                            copyExcelID = cop['copyExcelId']
                            stname = cop['copyExcelSheetName']
                            if pipettetype == "P1000M Ultima":
                                rangeval =  cop["UltimacopyRange"]
                                testpassrange = ["!Z11:Z11"]
                            else:
                                rangeval = cop["copyRange"]
                                testpassrange = ["!P11:P11"]
                            copydata = self.gdrive.get_excel_sheet_page(copyExcelID, stname, "ROWS", rangeval)
                            #testpass = copydata[0][0][3] #测试结果
                           
                            testpass = self.gdrive.get_excel_sheet_page(copyExcelID, stname, "ROWS", testpassrange)[0][0][0]
                            
                            testall = copydata
                            copydatalist.append(copydata)
                if func_callback != None:
                    func_callback(60) #进度
                for cs, pase in enumerate(u["ifpaste"]):
                    if pase["off/on"]:
                        if csv_link != None:
                            #复制测试结果到TRACKING SHEET 
                            
                            if pipettetype == "P1000M Ultima":
                                paseexcelid = pase["Ultimapastefileid"]
                            else:
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
                                if pipettetype == "P1000M Ultima":
                                    star=pase["UltimapastelineRange"]["star"]
                                    end = pase["UltimapastelineRange"]["end"]

                                else: 
                                    star=pase["pastelineRange"]["star"]
                                    end = pase["pastelineRange"]["end"]
                                last_row_range = f"!{star}{last_row_index}:{end}{last_row_index}"  # 替换 Z 为你的最大列
                                #logger.info("最后一行范围：", last_row_range)

                        
                            pase["pasteRange"][0] = f"!{star}{last_row_index}:{end}{last_row_index}"
                            rangeval = pase["pasteRange"][0]
                            pasedata = copydatalist[cs]
                            pasedata[0][0].insert(0, sheetlink)
                            #logger.info(pasedata)
                            copytestdata = self.gdrive.update_excel_sheet_page_batch(spreadsheet_id=paseexcelid, sheet_name=pasesheetname,ranges=rangeval, new_values=pasedata[0])
                            if copytestdata:
                                allgid = self.gdrive.get_sheet_gid_map(paseexcelid)
                                tracking_sheet = f"https://docs.google.com/spreadsheets/d/{paseexcelid}/edit?gid={allgid[pastesheetname]}#gid={allgid[pastesheetname]}"  # 表格链接
 
                            if func_callback != None:
                                func_callback(70) #进度
                        # 移动数据到每月文件夹
                        monthid = u["movetestfail"][self.nowyear][self.nowmonth]
                        move_successlist=self.gdrive.move_file_Multi_level(updatafileid, monthid)
                        move_success = move_successlist["success"]
                        if func_callback != None:
                            func_callback(80) #进度
                        # 上传原始文件到文件夹
                        faterid = u["ifupdatarawdata"][self.nowyear][self.nowmonth]
                        upid=self.gdrive.create_folders(f"{pipettesn}_{current_time_str}",faterid)
                        upfaileid = self.gdrive.upload_to_drive(zip_file, upid)
                        if upfaileid != '':
                            upfailpass = True
                        else:
                            upfailpass = False
                        if func_callback != None:   
                            func_callback(90) #进度
        if uptemp == "False" or move_success == "False" or upfailpass == "False":#or copytestdata == False:
            upload_status = False
        else:
            upload_status = True
        if func_callback != None:
            func_callback(100) #进度
        return [uptemp,testpass,upfailpass,sheetlink,move_success,testall,upload_status,tracking_sheet]
    
    # 1CH 8CH通道电流数据上传
    def UpdateSpeedCurrent_1CH_8CH(self,currentpath, pipettesn, pipettetype, zip_file, func_callback=None,
                                 csv_link=None):
        """_summary_

        Args:
            qcfilepath (str): qc测试原始数据的地址
            currentpath: 电流测试原始数据地址
            pipettesn (str): 要上传数据的移液器SN
            pipettetype (str): 移液器的类型 只支持（对应TRACKING SHEET里面的sheet名称）: P50S, P1000S, P50M, P1000M, P50S Millipore,P1000S  Millipore,P50M Ultima,P1000M Ultima , P50M Millipore , P1000M Millipore 
            csv_link (str): 诊断数据报告链接
        return:
        [uptemp = None #上传数据状态
        testpass = None #测试结果
        testall = None #所有测试结果
        move_success = None #移动数据状态
        upfailpass = None #上传源文件状态]
        """

        nametypedict = {
            "P1000S":"P1000S-template-v1.5",
            "P50S":"P50S-template-v1.5",
            "P1000S Millipore":"Millipore P50S-template-v1.5",
            "P50S Millipore":"Millipore P50S-template-v1.5",
            "P50M":"P50M",
            "P1000M":"P1000M",
            "P1000M Millipore":"Millipore P1000M",
            "P50M Millipore":"Millipore  P1000M",
            "P1000M Ultima":"Ultima P1000M"
        }

        speeduptemp = "False" #上传数据状态
        testpass = None #测试结果
        testall = None #测试结果详细信息
        move_success = "False" #移动数据状态
        upfailpass = "False" #上传源文件状态
        sheetlink = "" #报告链接
        copytestdata = False #复制测试结果到总表的状态
        tracking_sheet = None
        

        List_1ch = ["P50S" ,"P1000S" ,"P50S Millipore" ,"P1000S  Millipore"]
        List_8ch = ["P50M" ,"P1000M","P50M Ultima","P1000M Ultima","P50M Millipore","P1000M Millipore"]
        
        # 更新容量数据demo
        if pipettetype in List_1ch: #== "P50S" or pipettetype == "P1000S" or pipettetype =="P50S Millipore" or pipettetype =="P1000S  Millipore":
            if isinstance(self.yamldata, dict) and "1ch_updata_qc" in self.yamldata and isinstance(
                self.yamldata["1ch_updata_qc"], list):
                u = self.yamldata["1ch_updata_qc"][0]
            else:
                raise ValueError("self.yamldata 中不存在 '1ch_updata_qc' 键，或其对应值不是列表类型")
        
        elif pipettetype in List_8ch: #== "P50M" or pipettetype == "P1000M"or pipettetype =="P50M Ultima"or pipettetype =="P1000M Ultima"or pipettetype =="P50M Millipore"or pipettetype =="P1000M Millipore":
            if isinstance(self.yamldata, dict) and "8ch_updata_qc" in self.yamldata and isinstance(
                    self.yamldata["8ch_updata_qc"], list):
                u = self.yamldata["8ch_updata_qc"][0]
            else:
                raise ValueError("self.yamldata 中不存在 '8ch_updata_qc' 键，或其对应值不是列表类型")
        #进度
        if func_callback != None:
            func_callback(10)
        CopyTemplateId = ''
        if pipettetype == "P1000M Ultima":
            CopyTemplateId = u["ifcopytemplate"]["UltimacopyTempExcelId"]
        else:
            CopyTemplateId = u["ifcopytemplate"]["copyTempExcelId"]
        
        if u["ifupdata"]:
            pastesheetname = nametypedict[pipettetype]
            now = datetime.now()
            # 格式化为 YYYYMMDDHHMMSS
            current_time_str = now.strftime("%Y%m%d%H%M%S")
            if csv_link == None:
                #创建原始文件的文件夹（SN命名）
                # 获取源数据文件路径
                newfilename = pipettesn + "-QC-CURRENTSPEED" + f"-{current_time_str}"
                fz = self.gdrive.get_coppy_file(CopyTemplateId, newfilename)
                cpid = fz[1]
            else:
                logger.info(f"Get csv id {csv_link}")
                csv_id = str(csv_link).split("/")
                cpid = csv_id[5]
                logger.info(f"{csv_id}, {cpid}")
            if cpid:
                u["updatafileid"] = cpid
                updatafileid = u["updatafileid"]
                sheetlink = f"https://docs.google.com/spreadsheets/d/{cpid}/edit#gid=0"  # 表格链接
                # 获取更新sheet名称
                sheetname = u["UpCurrentSpeedTest"]["ExcelSheetName"]
                # 获取需要更新的列范围
                ranglist = u["UpCurrentSpeedTest"]["Range"]
                datalen = len(ranglist)
                # 获取SPEED源数据
                speed_exdata = csvdr.Read_csv_all(path=currentpath)
                if func_callback != None:
                    func_callback(30) #进度
                alldatalist = []
                allrangelist = []
                starrange = 1
                setdatalen = len(speed_exdata)
                setdata = []
                for i, ii in enumerate(speed_exdata):
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
                if func_callback != None:
                    func_callback(40) #进度
                getret = self.gdrive.update_excel_sheet_page_batch(spreadsheet_id=updatafileid,
                                                                    sheet_name=sheetname, ranges=allrangelist,
                                                                    new_values=alldatalist)
                if getret:
                    speeduptemp = "PASS"
                    logger.info("SPEED CURRENT 更新文件:成功")
                else:
                    speeduptemp = "FAIL"
                    logger.info("SPEED CURRENT 更新文件:失败")
                if func_callback != None:
                    func_callback(50) #进度


            if speeduptemp == "PASS":
                copydatalist = []
                for cop in u["ifcopydata"]:
                    if cop["off/on"]:
                        if csv_link != None:
                            cop['copyExcelId'] = updatafileid
                            copyExcelID = cop['copyExcelId']
                            stname = cop['copyExcelSheetName']
                            if pipettetype == "P1000M Ultima":
                                rangeval =  cop["UltimacopyRange"]
                            else:
                                rangeval = cop["copyRange"]
                            copydata = self.gdrive.get_excel_sheet_page(copyExcelID, stname, "ROWS", rangeval)
                            
                            if pipettetype in List_1ch:
                                testpass = self.gdrive.get_excel_sheet_page(copyExcelID, stname, "ROWS", ["!AQ11:AQ11"])[0][0][0]
                            elif pipettetype in List_8ch:
                                testpass = self.gdrive.get_excel_sheet_page(copyExcelID, stname, "ROWS", ["!BO11:BO11"])[0][0][0]
                            elif pipettetype == "P1000M Ultima":
                                testpass = self.gdrive.get_excel_sheet_page(copyExcelID, stname, "ROWS", ["!BY11:BYO11"])[0][0][0]
                            testall = copydata
                            copydatalist.append(copydata)
                            if func_callback != None:
                                func_callback(60) #进度

                for cs, pase in enumerate(u["ifpaste"]):
                    if pase["off/on"]:
                        if csv_link != None:
                            #复制测试结果到TRACKING SHEET 
                            if pipettetype == "P1000M Ultima":
                                paseexcelid = pase["Ultimapastefileid"]
                            else:
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
                                if pipettetype == "P1000M Ultima":
                                    star=pase["UltimapastelineRange"]["star"]
                                    end = pase["UltimapastelineRange"]["end"]
                                else:
                                    star=pase["pastelineRange"]["star"]
                                    end = pase["pastelineRange"]["end"]
                                last_row_range = f"!{star}{last_row_index}:{end}{last_row_index}"  # 替换 Z 为你的最大列
                               #logger.info("最后一行范围：", last_row_range)

                        
                            pase["pasteRange"][0] = f"!{star}{last_row_index}:{end}{last_row_index}"
                            rangeval = pase["pasteRange"][0]
                            pasedata = copydatalist[cs]
                            pasedata[0][0].insert(0, sheetlink)
                            #logger.info(pasedata)
                            copytestdata = self.gdrive.update_excel_sheet_page_batch(spreadsheet_id=paseexcelid, sheet_name=pasesheetname,ranges=rangeval, new_values=pasedata[0])
                            if copytestdata:
                                allgid = self.gdrive.get_sheet_gid_map(paseexcelid)
                                tracking_sheet = f"https://docs.google.com/spreadsheets/d/{paseexcelid}/edit?gid={allgid[pastesheetname]}#gid={allgid[pastesheetname]}"  # 表格链接
                            if func_callback != None:
                                func_callback(70) #进度
                        # 移动数据到每月文件夹
                        monthid = u["movetestfail"][self.nowyear][self.nowmonth]
                        move_successlist=self.gdrive.move_file_Multi_level(updatafileid, monthid)
                        move_success = move_successlist["success"]
                        if func_callback != None:
                            func_callback(80) #进度

                        # 上传原始文件到文件夹
                        faterid = u["ifupdatarawdata"][self.nowyear][self.nowmonth]
                        upid=self.gdrive.create_folders(f"{pipettesn}_{current_time_str}",faterid)
                        
                        upfaileid = self.gdrive.upload_to_drive(zip_file, upid)
                        if upfaileid != '':
                            upfailpass = True
                        else:
                            upfailpass = False
                        if func_callback != None:
                            func_callback(90) #进度
        if speeduptemp == "False" or move_success == "False" or upfailpass == "False":# or copytestdata == False:
            upload_status = False
        else:
            upload_status = True
        if func_callback is not None:
            func_callback(100) #进度
        return [speeduptemp,testpass,upfailpass,sheetlink,move_success,testall,upload_status,tracking_sheet]


    def update_data_to_google_drive(self,upfile_path, pipette_sn, pipette_type, zip_file,test_type,
                                    func_callback=None, csv_link=None, Note_str="AUTO-UPLOAD-TE"):
        """testtypelist = ["assembly_qc","speed_current_test","grav_test"]
        

        Args:
            upfile_path (str): 测试原始数据的服务器路径地址
            pipettesn (str): 要上传数据的移液器SN
            pipette_type (str): 移液器的类型 只支持（对应TRACKING SHEET里面的sheet名称）: P50S, P1000S, P50M, P1000M, P50S Millipore,P1000S  Millipore,P50M Ultima,P1000M Ultima , P50M Millipore , P1000M Millipore,P2HH,P1KH
            zip_file:需要上传的测试原文件的压缩包
            test_type (str): 测试类型 like: "assembly_qc","speed_current_test","grav_test","ninety-six-assembly-qc-ot3"
            csv_link (str): 诊断数据报告链接
            Note_str (str): TRACKER SHEET 中的备注
        
        return:
        {
        "success": True,
        "test_result": "PASS",
        "zip_success": True,
        "sheet_link": "http:xx",
        "move_success": True,
        "test_all_items":list
        }

        
        """
        test_res_dict = {
        "success": False,
        "test_result": "FAIL",
        "zip_success": False,
        "sheet_link": "http:xx",
        "move_success": False,
        "test_all_items":[],
        "tracking_sheet":None
        }
        logger.info(f"test type is {test_type}, try to upload to google driver")
        try:
            if test_type == "pipette-assembly-qc-ot3":
                test_res = self.UpdateAssemblyQC_1CH_8CH(upfile_path,pipette_sn,pipette_type,zip_file,
                                                         func_callback=func_callback, csv_link=csv_link)
            elif test_type == "grav_test":
                test_res = self.updatavolume_1CH_8CH(upfile_path,pipette_sn,pipette_type,zip_file ,func_callback=func_callback,Note_str=Note_str)
            elif test_type == "pipette-current-speed-qc-ot3":
                logger.info("pipette-current-speed-qc-ot3 handling")
                test_res = self.UpdateSpeedCurrent_1CH_8CH(upfile_path,pipette_sn,pipette_type,zip_file,
                                                           func_callback=func_callback, csv_link=csv_link)
            elif test_type == "ninety-six-assembly-qc-ot3":
                test_res = self.UpdateAssemblyQC_96CH_P200H_P1KH(upfile_path,pipette_sn,pipette_type,zip_file,
                                                            func_callback=func_callback, csv_link=csv_link)

            #return [uptemp,testpass,upfailpass,sheetlink,move_success,testall,upload_status]
            test_res_dict.update({
                "success": test_res[0],
                "test_result": test_res[1],
                "zip_success": test_res[2],
                "sheet_link": test_res[3],
                "move_success": test_res[4],
                "test_all_items":test_res[5],
                "tracking_sheet":test_res[7]
                })
            logger.info(f"Result: {test_res_dict}")
            return test_res_dict
        except Exception as errval:
            logger.error(errval)
            return test_res_dict
    # 1CH 8CH通道诊断数据上传
    def UpdateAssemblyQC_96CH_P200H_P1KH(self, qcfilepath, pipettesn, pipettetype, zip_file, func_callback=None,
                                 csv_link=None):
        """_summary_

        Args:
            qcfilepath (str): qc测试原始数据的地址
            pipettesn (str): 要上传数据的移液器SN
            pipettetype (str): 移液器的类型 只支持（对应TRACKING SHEET里面的sheet名称）: P200H,P1KH
            csv_link (str):更新测试数据使用
        return:
        [uptemp = None #上传数据状态
        testpass = None #测试结果
        testall = None #所有测试结果
        move_success = None #移动数据状态
        upfailpass = None #上传源文件状态]
        """
        #产品类型对应TRACKER里面sheet的名称
        nametypedict = {
            "P2HH":"P200 96CH UNIT TRACKER",
            "P1KH":"P1000 96CH UNIT TRACKER",
            
        }

        uptemp = "False" #上传数据状态
        testpass = None #测试结果
        testall = None #测试结果详细信息
        move_success = "False" #移动数据状态
        upfailpass = "False" #上传源文件状态
        sheetlink = "" #报告链接
        upload_status = False #上传成功状态
        copytestdata = True #复制数据到总表的状态
        tracking_sheet = None

        List_P200H = ["P2HH"]
        List_P1000H = ["P1KH"]
        
        
        if pipettetype in List_P200H or pipettetype in List_P1000H : 
            if isinstance(self.yamldata, dict) and "9ch_lv_updata_qc" in self.yamldata and isinstance(
                self.yamldata["9ch_lv_updata_qc"], list):
                u = self.yamldata["9ch_lv_updata_qc"][0]
            else:
                raise ValueError("self.yamldata 中不存在 '9ch_lv_updata_qc' 键，或其对应值不是列表类型")
        
        CopyTemplateId = ''
        if pipettetype == "P1KH":
            CopyTemplateId = u["ifcopytemplate"]["UltimacopyTempExcelId"]
        elif pipettetype == "P2HH":
            CopyTemplateId = u["ifcopytemplate"]["copyTempExcelId"]
        if func_callback != None:
            func_callback(10) #进度
        if u["ifupdata"]:
            pastesheetname = nametypedict[pipettetype]

            now = datetime.now()
            # 格式化为 YYYYMMDDHHMMSS
            current_time_str = now.strftime("%Y%m%d%H%M%S")
            if csv_link == None:
                #创建原始文件的文件夹（SN命名）
                # 获取源数据文件路径
                newfilename = pipettesn + "-ninety-six-assembly-qc-ot3" + f"-{current_time_str}"
                fz = self.gdrive.get_coppy_file(CopyTemplateId, newfilename)
                cpid = fz[1]
            else:
                logger.info(f"Get csv id {csv_link}")
                csv_id = str(csv_link).split("/")
                cpid = csv_id[5]
                logger.info(f"{csv_id}, {cpid}")
            if cpid:
                u["updatafileid"] = cpid
                updatafileid = u["updatafileid"]
                sheetlink = f"https://docs.google.com/spreadsheets/d/{cpid}/edit#gid=0"  # 表格链接
                # 获取更新sheet名称
                sheetname = u["ExcelSheetName"][0]
                # 获取需要更新的列范围
                ranglist = u["Range"]
                datalen = len(ranglist)
                # 获取QC源数据
                exdata = csvdr.Read_csv_all(path=qcfilepath)
                if func_callback != None:
                    func_callback(30) #进度
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
                if func_callback != None:
                    func_callback(40) #进度
                getret = self.gdrive.update_excel_sheet_page_batch(spreadsheet_id=updatafileid,
                                                                    sheet_name=sheetname, ranges=allrangelist,
                                                                    new_values=alldatalist)
                if getret:
                    uptemp = "Ture"
                    logger.info("更新文件:成功", u)
                else:
                    uptemp = "Fales"
                    logger.info("更新文件:失败", u)
                if func_callback != None:
                    func_callback(50) #进度
                
            if uptemp == "Ture":
                copydatalist = []
                for cop in u["ifcopydata"]:
                    if cop["off/on"]:
                        cop['copyExcelId'] = updatafileid
                        copyExcelID = cop['copyExcelId']
                        stname = cop['copyExcelSheetName']
                        if pipettetype == "P1KH":
                            rangeval =  cop["UltimacopyRange"]
                        elif pipettetype == "P2HH":
                            rangeval = cop["copyRange"]
                        copydata = self.gdrive.get_excel_sheet_page(copyExcelID, stname, "ROWS", rangeval)
                        #testpass = copydata[0][0][3] #测试结果
                        copydata[0][0][3] = sheetlink #在测试结果插入测试链接

                        Test_Result = {
                            "CurrentPlunger":copydata[0][0][5],
                            "CurrentJaws":copydata[0][0][6],
                            "CAPACITANCE":copydata[0][0][7],
                            "PRESSURE":copydata[0][0][8],
                            "TIP-SENSOR":copydata[0][0][10],
                            "DROPLETS":copydata[0][0][11],
                        }
                        
                        failed_items = {k: v for k, v in Test_Result.items() if v != "PASS"}
                        if not failed_items:
                            #print("全部通过")
                            testpass = "PASS"
                        else:
                            testpass = "FAIL"
                            #print("以下项目未通过 ❌：", failed_items)
                        testall = copydata
                        copydatalist.append(copydata)
                if func_callback != None:
                    func_callback(60) #进度
                for cs, pase in enumerate(u["ifpaste"]):
                    if pase["off/on"]:
                        #复制测试结果到TRACKING SHEET 
                        if pipettetype == "P1KH":
                            paseexcelid = pase["Ultimapastefileid"]
                        else:
                            paseexcelid = pase["pastefileid"]
                        pase["pastesheetname"] = pastesheetname
                        pasesheetname = pase["pastesheetname"]

                        allgid = self.gdrive.get_sheet_gid_map(paseexcelid)
                        values = self.gdrive.get_excel_sheet(spreadsheetId=paseexcelid, range=pasesheetname)
                        if values:
                            found_index = -1

                            for index, row in enumerate(values):
                                # matches = [x for x in row if "P2HH" in x]
                                # if matches:
                                # #if "P2HH" in row or "P1KH" in row:
                                #     found_index = index + 2
                                #     #noval = values[found_index]
                                # else:
                                #     #if "P2HH" not in row and "P1KH" not in row :
                                #     break
                                if any(x for x in row if "P2HH" in x or "P1KH" in x):
                                    last_found_index = index   # 保存最后匹配的行号
                                    last_found_row = row       # 保存这一行内容
                            last_row_index = last_found_index + 2
                            if pipettetype == "P1KH":
                                star=pase["UltimapastelineRange"]["star"]
                                end = pase["UltimapastelineRange"]["end"]

                            else: 
                                star=pase["pastelineRange"]["star"]
                                end = pase["pastelineRange"]["end"]
                            last_row_range = f"!{star}{last_row_index}:{end}{last_row_index}"  # 替换 Z 为你的最大列
                            #logger.info("最后一行范围：", last_row_range)

                    
                        pase["pasteRange"][0] = f"!{star}{last_row_index}:{end}{last_row_index}"
                        rangeval = pase["pasteRange"][0]
                        pasedata = copydatalist[cs]
                        #pasedata[0][0].insert(0, sheetlink)
                        #logger.info(pasedata)
                        copytestdata = self.gdrive.update_excel_sheet_page_batch(spreadsheet_id=paseexcelid, sheet_name=pasesheetname,ranges=rangeval, new_values=pasedata[0])
                        if copytestdata:
                            tracking_sheet = f"https://docs.google.com/spreadsheets/d/{paseexcelid}/edit#gid={allgid[pastesheetname]}#gid={allgid[pastesheetname]}"  # 表格链接
                        if func_callback != None:
                            func_callback(70) #进度
                        # 移动数据到每月文件夹
                        if pipettetype == "P1KH":
                            monthid = u["movetestfail"]["P1KH"][self.nowyear][self.nowmonth]
                        elif pipettetype == "P2HH":
                            monthid = u["movetestfail"]["P2HH"][self.nowyear][self.nowmonth]
                        move_successlist=self.gdrive.move_file_Multi_level(updatafileid, monthid)
                        move_success = move_successlist["success"]
                        if func_callback != None:
                            func_callback(80) #进度
                        # 上传原始文件到文件夹
                        if pipettetype == "P1KH":
                            faterid = u["ifupdatarawdata"]["P1KH"][self.nowyear][self.nowmonth]
                        elif pipettetype == "P2HH":
                            faterid = u["ifupdatarawdata"]["P2HH"][self.nowyear][self.nowmonth]
                        upid=self.gdrive.create_folders(f"{pipettesn}_{current_time_str}",faterid)
                        upfaileid = self.gdrive.upload_to_drive(zip_file, upid)
                        if upfaileid != '':
                            upfailpass = True
                        else:
                            upfailpass = False
                        if func_callback != None:   
                            func_callback(90) #进度
        if uptemp == "False" or move_success == "False" or upfailpass == "False":#or copytestdata == False:
            upload_status = False
        else:
            upload_status = True
        if func_callback != None:
            func_callback(100) #进度
        return [uptemp,testpass,upfailpass,sheetlink,move_success,testall,upload_status,tracking_sheet]

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
    #     "/Users/yew/Desktop/production-scripts/data_center/google_driver_handler/gravimetric-ot3-p1000-single_run-25-07-11-17-58-22_CSVReport-P1KSV3520230727A04-qc.csv",
    #     "P1KSV3520230727A04", "P1000S",
    #     ["/Users/yew/Desktop/production-scripts/data_center/google_driver_handler/gravimetric-ot3-p1000-single_run-25-07-11-17-58-22_CSVReport-P1KSV3520230727A04-qc.csv","/Users/yew/Desktop/production-scripts/data_center/google_driver_handler/gravimetric-ot3-p1000-single_run-25-07-11-17-58-22_GravimetricRecorder-P1KSV3520230727A04-qc.csv"])

    # logger.info(typelist)

    # typelist=aa.updatavolume_1CH(
    #     "/Users/yew/Desktop/production-scripts/data_center/google_driver_handler/gravimetric-ot3-p50-single_run-25-10-14-10-08-07_CSVReport-P50SV3520241218A50-qc.csv",
    #     "P50SV3520241218A50", "P50S",
    #     ["/Users/yew/Desktop/production-scripts/data_center/google_driver_handler/gravimetric-ot3-p50-single_run-25-10-14-10-08-07_CSVReport-P50SV3520241218A50-qc.csv","/Users/yew/Desktop/production-scripts/data_center/google_driver_handler/gravimetric-ot3-p50-single_run-25-10-14-10-08-07_GravimetricRecorder-P50SV3520241218A50-qc.csv"])

    # logger.info(typelist)


    # typelist=aa.updatavolume_1CH_8CH(
    #     "/Users/yew/Desktop/production-scripts/data_center/google_driver_handler/gravimetric-ot3-p50-single_run-25-10-14-10-08-07_CSVReport-P50SV3520241218A50-qc.csv",
    #     "P50SV3520241218A50", "P50S",
    #     ["/Users/yew/Desktop/production-scripts/data_center/google_driver_handler/gravimetric-ot3-p50-single_run-25-10-14-10-08-07_CSVReport-P50SV3520241218A50-qc.csv","/Users/yew/Desktop/production-scripts/data_center/google_driver_handler/gravimetric-ot3-p50-single_run-25-10-14-10-08-07_GravimetricRecorder-P50SV3520241218A50-qc.csv"])

    # logger.info(typelist)

    # typelist=aa.updatavolume_1CH_8CH(
    #     "/Users/yew/Desktop/production-scripts/data_center/google_driver_handler/gravimetric-ot3-p1000-multi_run-25-10-10-16-14-38_CSVReport-P1KMV3520240110A04-qc.csv",
    #     "P1KMV3520240110A04", "P1000M",
    #     ["/Users/yew/Desktop/production-scripts/data_center/google_driver_handler/gravimetric-ot3-p1000-multi_run-25-10-10-16-14-38_CSVReport-P1KMV3520240110A04-qc.csv","/Users/yew/Desktop/production-scripts/data_center/google_driver_handler/gravimetric-ot3-p1000-single_run-25-07-11-17-58-22_GravimetricRecorder-P1KSV3520230727A04-qc.csv"])

    # logger.info(typelist)
    # typelist=aa.UpdateAssemblyQC_1CH_8CH(
    #     "/Users/yew/Desktop/production-scripts/data_center/google_driver_handler/pipette-current-speed-qc-ot3_run-25-10-17-02-12-26_CSVReport-P1KMV3520250828A03.csv",
    #     "P50SV3520240914A02", "P1",
    #     "/Users/yew/Desktop/production-scripts/data_center/google_driver_handler/gravimetric-ot3-p1000-multi_run-25-10-10-16-14-38_CSVReport-P1KMV3520240110A04-qc.csv",
    #     csv_link="https://docs.google.com/spreadsheets/d/1P9T3jrSqMxb1e9WeFJszUf6O7-fn6aeVH6P5vsD7IU0/edit?gid=859846748#gid=859846748"
    # )
    # logger.info(typelist)

    # typelist=aa.UpdateAssemblyQC_1CH_8CH(
    #     "/Users/yew/Desktop/production-scripts/data_center/google_driver_handler/pipette-assembly-qc-ot3_run-25-09-16-02-20-41_P50SV3520240914A02.csv",
    #     "P50SV3520240914A02", "P50S",
    #     "/Users/yew/Desktop/production-scripts/data_center/google_driver_handler/pipette-current-speed-qc-ot3_run-25-10-17-02-12-26_CSVReport-P1KMV3520250828A03.csv"
    #     ,csv_link="https://docs.google.com/spreadsheets/d/1WUQO1p908FwNNV8Tq60hNrpfSQe3spMWG8xHFGMnEcA/edit?gid=859846748#gid=859846748")
    
    # logger.info(typelist)


    typelist=aa.UpdateAssemblyQC_96CH_P200H_P1KH(
        "/Users/yew/Desktop/production-scripts/data_center/google_driver_handler/ninety-six-assembly-qc-ot3_run-25-11-04-07-01-22_CSVReport-P2HHV3220251031A02.csv",
        "P2HHV3220251031A02",
        "P1KH",
        "/Users/yew/Desktop/production-scripts/data_center/google_driver_handler/ninety-six-assembly-qc-ot3_run-25-11-04-07-01-22_CSVReport-P2HHV3220251031A02.csv"
    )
    print(typelist)