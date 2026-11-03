# 96 通道气压数据上传

手动上传弹窗新增“96气压数据”页签，支持 `QC`、`GRAVIMETRIC`、`LIFETIME` 三种报告类型。上传单个 CSV 后，后台任务会：

1. 根据 CSV 中的序列号识别 P2HH/P1KH，并复制对应 Google Sheet 模板。
2. 将 CSV 写入模板的 `CSV test results` 工作表，并把 `Summary!A2:Q2` 写入对应 checking sheet。
3. 读取 `Pressure Test-1` 至 `Pressure Test-10` 的 `A4:AR12`，过滤空行和全零数据，追加到对应型号和报告类型的气压总表。
4. 用源报告 Spreadsheet 链接做幂等判断，重复重试不会重复追加同一份报告。

任务使用现有持久化上传队列和服务器端 Google 凭证。模板、checking sheet 和总表 ID 集中维护在 `apps/backend/src/modules/uploads/pressure_upload.py`；Google 表格改版时只需更新该文件的映射和目标范围，并补充对应测试。

前端接口：`POST /upload-data/manual/96-pressure`，字段为 `csv_file`、`report_type`、可选 `record_id`。
