import enum
import random
from dataclasses import dataclass


class Code(enum.Enum):
    system_error = 'SYST:ERR'  # 返回缓冲区错误代码
    idn = '*idn'
    rmtoff = '*RMTOFF'         #断开远程连接

    system_lcd_cont = 'SYST:LCD:CONT'  # 设置屏幕对比度
    system_lcd_bright = 'SYST:LCD:BRIG'  # 设置屏幕亮度
    system_buzzer_psound = 'SYST:BUZZ:PSOUND'  # 开启通过蜂鸣器
    system_buzzer_fsound = 'SYST:BUZZ:FSOUND'  # 开启失败蜂鸣器
    system_buzzer_ptime = 'SYST:BUZZ:PTIM'  # 设置通过时蜂鸣器响应时间
    system_buzzer_ftime = 'SYST:BUZZ:FTIM'  # 设置失败时蜂鸣器响应时间
    system_gpib_version = 'SYST:GPIB:VERS'  #查询GPIB版本

    function_test= 'FUNC:TEST'  # 开启或关闭当前测试
    measure= 'MEAS'  # 获取测试结果   仅在menu模式使用
    main_func = 'MAIN:FUNC'  # Menu / Auto模式切换

    manu_step = 'MANU:STEP'  #设置MANU测试号
    manu_name = 'MANU:NAME'  #获取测试号名称
    manu_init = 'MANU:INIT'
    manu_rtim = 'MANU:RTIM'  #设置斜坡时间
    manu_edit_mode = 'MANU:EDIT:MODE'  #设置手动测试的模式

    manu_acw_vol = 'MANU:ACW:VOLT' # 设置ACW电压
    manu_acw_cur_hi_set = 'MANU:ACW:CHIS'  # 设置ACW HIGH SET 电流
    manu_acw_cur_lo_set = 'MANU:ACW:CLOS'  # 设置ACW low SET 电流
    manu_acw_ttime = 'MANU:ACW:TTIM'  # 设置ACW 测试时间
    manu_acw_freq = 'MANU:ACW:FREQ'  # 设置ACW 频率
    manu_acw_ref = 'MANU:ACW:REF'  # 设置ACW 参考值
    manu_acw_arc_cur = 'MANU:ACW:ARCC'  # 设置ACW arc电流

    manu_dcw_vol = 'MANU:DCW:VOLT'          # 设置DCW电压
    manu_dcw_cur_hi_set = 'MANU:DCW:CHIS'  # 设置DCW HIGH SET 电流
    manu_dcw_cur_lo_set = 'MANU:DCW:CLOS'  # 设置DCW LOW SET 电流
    manu_dcw_ttime = 'MANU:DCW:TTIM'    # 设置DCW 测试时间
    manu_dcw_ref = 'MANU:DCW:REF'       # 设置DCW 参考值
    manu_dcw_arc_cur = 'MANU:DCW:ARCC'  # 设置DCW arc电流

    # manu_ir_vol = 'MANU:IR:VOLT'  # 设置IR电压
    # manu_ir_r_hi_set = 'MANU:IR:RHIS'  # 设置IR HIGH SET 电阻
    # manu_ir_r_lo_set = 'MANU:IR:RLOS'  # 设置IR LOW SET 电阻
    # manu_ir_ttime = 'MANU:IR:TTIM'  # 设置IR 测试时间
    # manu_ir_ref = 'MANU:IR:REF'  # 设置IR 参考值







@dataclass()
class SimulateResponse:
    system_error: str = "0,No Error"  # 返回缓冲区错误代码

    idn: str = 'GPT-9902A,GES121109   ,V2.06,'
    system_lcd_cont: str = str(3)  # 设置屏幕对比度
    system_lcd_bright: str = str(1)  # 设置屏幕亮度
    system_buzzer_psound: str = 'ON'  # 开启通过蜂鸣器  ON/OFF
    system_buzzer_fsound: str = 'ON' # 开启失败蜂鸣器   ON/OFF
    system_buzzer_ptime: str = str(1.2) + " S"  # 设置通过时蜂鸣器响应时间
    system_buzzer_ftime: str = str(1.2) + " S"  # 设置失败时蜂鸣器响应时间
    system_gpib_version:str = "No GPIB connected"

    function_test: str = 'TEST ON'
    measure: str = '<ACW,VIEW ,0.000kV,000.0 mA ,  ---.-S>'  # 获取测试结果
    main_func: str = "AUTO MODE"   #'MANU MODE'

    manu_step :str = '001'  # 设置MANU测试号
    manu_name :str = 'MANU_NAME'  # 获取测试号名称
    manu_rtim :str= '0.5 s'  # 设置斜坡时间
    manu_edit_mode :str=  'ACW'  # 设置手动测试的模式

    manu_acw_vol :str= '0.100kV'  # 设置ACW电压
    manu_acw_cur_hi_set :str= '0.001mA'  # 设置ACW HIGH SET 电流
    manu_acw_cur_lo_set :str= '0.000mA'  # 设置ACW low SET 电流
    manu_acw_ttime :str= '001.0 S'  # 设置ACW 测试时间
    manu_acw_freq :str= '60 Hz'  # 设置ACW 频率
    manu_acw_ref :str= '0.000mA'  # 设置ACW 参考值
    manu_acw_arc_cur :str= 'MANU:ACW:ARCC'  # 设置ACW arc电流

    manu_dcw_vol :str= 'MANU:DCW:VOLT'  # 设置DCW电压
    manu_dcw_cur_hi_set :str= 'MANU:DCW:CHIS'  # 设置DCW HIGH SET 电流
    manu_dcw_cur_lo_set :str= 'MANU:DCW:CLOS'  # 设置DCW LOW SET 电流
    manu_dcw_ttime :str= 'MANU:DCW:TTIM'  # 设置DCW 测试时间
    manu_dcw_ref :str= 'MANU:DCW:REF'  # 设置DCW 参考值
    manu_dcw_arc_cur :str= 'MANU:DCW:ARCC'  # 设置DCW arc电流

    # manu_ir_vol :str= 'MANU:IR:VOLT'  # 设置IR电压
    # manu_ir_r_hi_set :str= 'MANU:IR:RHIS'  # 设置IR HIGH SET 电阻
    # manu_ir_r_lo_set :str= 'MANU:IR:RLOS'  # 设置IR LOW SET 电阻
    # manu_ir_ttime :str= 'MANU:IR:TTIM'  # 设置IR 测试时间
    # manu_ir_ref :str= 'MANU:IR:REF'  # 设置IR 参考值


