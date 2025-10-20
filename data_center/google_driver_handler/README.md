# googledrive
谷歌网盘、谷歌表格等操作相关API
updata_class 功能说明文档
类概述
updata_class 是一个用于自动化处理移液器测试数据并上传到Google Sheets的数据更新类。它支持1通道和8通道移液器的容量数据上传，并能自动管理测试文件的存储和跟踪。

初始化方法
__init__(Test_environment="debug")
初始化数据更新类。

参数：

Test_environment (str): 测试环境配置，可选值：

"debug": 调试环境，使用 updata.yaml 配置文件

"Production": 生产环境，使用 updata_production.yaml 配置文件

功能：

根据环境加载对应的YAML配置文件

获取当前服务器时间的年份和月份

主要方法
star_int()
初始化Google Drive连接。

功能：

创建Google Drive API连接实例

get_current_month()
获取当前服务器时间的年月。

返回：

tuple: (当前年份, 当前月份)

updatavolume_1CH_8CH(upfilepath, pipettesn, pipettetype, upfailelist, Note_str="AUTO-UPLOAD-TE")
上传1通道或8通道移液器的容量测试数据。

参数：

upfilepath (str): 原始CSV数据文件的路径

pipettesn (str): 移液器序列号

pipettetype (str): 移液器类型，支持：

1通道："P50S", "P1000S"

8通道："P50M", "P1000M"

特殊型号："P50S Millipore", "P1000S Millipore", "P50M Ultima", "P1000M Ultima"

upfailelist (list): 需要上传的原始文件路径列表

Note_str (str): 在跟踪表格中的备注信息，默认为 "AUTO-UPLOAD-TE"

返回：

list: 包含5个状态的列表：

uptemp: 数据上传状态 ("PASS"/"FAIL")

testpass: 测试结果

testall: 所有测试详细信息

move_success: 文件移动状态

upfailpass: 原始文件上传状态

工作流程
配置读取：根据移液器类型读取对应的YAML配置

模板复制：在Google Drive中复制数据模板文件

数据上传：将CSV数据批量上传到Google Sheets

结果提取：从处理后的数据中提取测试结果

跟踪更新：在跟踪表格中更新测试记录

文件管理：

将处理文件移动到月度文件夹

创建序列号命名的文件夹

上传原始测试文件到对应文件夹

支持的移液器类型
1通道移液器
P50S

P1000S

P50S Millipore

P1000S Millipore

8通道移液器
P50M

P1000M

P50M Ultima

P1000M Ultima

文件组织结构
text
Google Drive/
├── 月度文件夹 (按年月自动创建)
│   └── 处理后的数据文件
└── 序列号文件夹 (按SN和时间戳创建)
    └── 原始测试文件
依赖模块
googledriveM: Google Drive API操作

csvdriver: CSV文件读取功能

sheetdrive: Google Sheets操作

yamldrive: YAML配置文件读取

globalconfig: 全局配置常量

datetime: 日期时间处理

使用示例
python
# 初始化类
updater = updata_class(Test_environment="Production")
updater.star_int()

# 上传1通道移液器数据
result = updater.updatavolume_1CH_8CH(
    upfilepath="path/to/data.csv",
    pipettesn="P50SV3520241218A50",
    pipettetype="P50S",
    upfailelist=["data.csv", "recorder.csv"],
    Note_str="自动上传测试"
)

print(f"上传状态: {result[0]}")
print(f"测试结果: {result[1]}")
代码文件结构分析
python
main_updata.py
├── 导入模块
│   ├── googledriveM.googledrive
│   ├── csvdriver.CsvFunc
│   ├── sheetdrive.sheetdrive
│   ├── yamldrive.yamlfunc
│   ├── os, sys, re
│   └── globalconfig.ROWSINDEX, datetime.datetime
├── 路径配置
│   ├── codepath = os.path.dirname(__file__)
│   ├── addpath = os.path.dirname(os.path.dirname(__file__))
│   └── sys.path 添加路径
├── updata_class 类
│   ├── __init__() - 初始化方法
│   ├── star_int() - 初始化Google Drive连接
│   ├── get_current_month() - 获取当前年月
│   └── updatavolume_1CH_8CH() - 主要数据上传方法
└── 主程序入口
    └── 测试代码示例
配置要求
YAML配置文件结构
yaml
1ch_updata_volume:
  - ifupdata: true/false
    ifcopytemplate:
      copyTempExcelId: "模板文件ID"
    ExcelSheetName: ["工作表名称"]
    Range: ["数据范围"]
    ifcopydata:
      - off/on: true/false
        copyExcelId: "复制文件ID"
        copyExcelSheetName: "工作表名称"
        copyRange: "数据范围"
    ifpaste:
      - off/on: true/false
        pastefileid: "粘贴文件ID"
        pastesheetname: "工作表名称"
        pastelineRange:
          star: "起始列"
          end: "结束列"
          note: "备注列"
    movetestfail:
      年份:
        月份: "文件夹ID"
    ifupdatarawdata:
      年份:
        月份: "文件夹ID"
注意事项
需要正确的Google API认证配置

YAML配置文件需要包含完整的Google Drive文件ID和范围配置

确保有足够的Google Drive存储空间和API配额

生产环境使用时请使用Production模式

文件路径需要正确配置，确保程序有访问权限

网络连接稳定，避免上传过程中断

错误处理
配置验证：检查YAML配置中必要的键是否存在

文件操作：处理Google Drive API调用可能出现的异常

数据格式：验证CSV数据格式是否正确

网络连接：处理网络超时和重试机制

