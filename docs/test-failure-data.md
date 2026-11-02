# 测试失败数据

入口：**缺陷分析助手 → 测试失败数据**，路径为 `/production/defect-search/test-failures`。

页面以归档文件夹为独立报告单位，一份文件夹显示一行。即使设备 SN 相同，不同文件夹也分别展示、分析和保存返修确认，不按 SN 或运行标识合并。支持查看失败证据、执行状态、协议给出的检查/复测建议及原始附件。返修确认记录当前登录用户和保存时间，保留历史；它不改变协议原有的测试结果，也不表示复测已经通过。

报告列表的异常摘要下方直接展示“失败分析与处理建议”卡片，默认显示当前文件夹内主报告的简版结果，支持切换本文件夹内的证据包、手动生成、展开完整建议及打开对应依据。报告详情使用同一份分析结果；检查步骤、处理方向和复测要求供人员核对，返修确认仍单独填写。代码来源、模型配置和接口见 [失败分析智能体](test-failure-analysis.md)。

## 同轮测试与右侧参考快照

协议新增的 `right-reference-50ul`、`right-reference-200ul`、`right-reference-1000ul` 阶段会保存右侧参考点水失败时的证据。它们与同轮主报告共享运行标识，但属于独立的报告包；平台分别保存 ID、证据版本及同名 JSON / LOG / encoder 附件，不让阶段快照覆盖最终结果。

同一文件夹中的 JSON、LOG、encoder CSV 是报告材料，右侧参考快照也是本文件夹报告的阶段证据。详情仅在当前文件夹内区分主报告和各规格快照，`result-summary` 显示为“最终汇总”。每份快照标出规格，并可查看本文件夹中相同运行标识的主报告。主报告尚未到齐时可以先查看快照；不同文件夹之间不跳转或关联，即使其 SN、时间或运行标识相同。

设备信息仍显示左侧被测移液器。文件夹报告数量与证据包数量分别统计：一个文件夹算一份报告，主报告及阶段快照分别算证据包。保存返修确认仅覆盖当前文件夹内当时存在的证据版本，其他文件夹的确认状态不变。

升级后首次成功扫描会重新解析旧索引来源，按文件夹隔离身份。原确认文字、人员、时间、覆盖范围及历史证据版本全部保留；已有确认依据原先实际覆盖的证据 ID 归属，不再因 SN 相同附加到其他报告。如果一条旧确认确实覆盖过多个文件夹，它会继续出现在原覆盖范围的历史中，这是保留旧记录；新确认只属于当前文件夹。此前被合并而新拆出的证据使用新 ID，保守显示待确认，不自动继承旧确认。原文件缺失时无法重建该文件的当前证据，已有历史仍保留。

## 按 SN 和运行编号匹配测试报告链接

列表文件夹列和报告详情提供“测试报告链接”。以当前证据包的 `sn + report_run_id` 为精确匹配键，只去掉首尾空格，不用序列号单字段、最近日期、文件夹时间或 trace `run_id` 代替。不同文件夹的本地报告、分析与返修确认仍分别保存；同文件夹主报告和右参考快照具有相同匹配键时，链接仅显示一次。

默认内置两个只读来源：[1ch 测试报告总表](https://docs.google.com/spreadsheets/d/1eHeq3W0Mr-X6nC0MkNZuuS3DLW097Xtwl2pTkIEpSOU/edit#gid=955163313)和[8ch 测试报告总表](https://docs.google.com/spreadsheets/d/16GY8f7p788fbwxxIEH_Azn1RB-NWl3N7cRZzz-6SA_E/edit#gid=955163313)。根据报告型号及 SN 前缀选择对应来源：`P50S / P1000S` 查 1ch，`P50M / P1000M` 查 8ch，兼容协议型号别名和 `P1KS / P1KM` 序列号前缀。型号未知且 SN 也不能识别、或两者通道冲突时同时查两表；通道仅决定查询范围，匹配仍必须满足完整的 SN 与运行编号。

默认遍历所选总表的所有工作表，按每页表头定位 SN 与 QC Link / CSV Link / Link，兼容现存被标成 Description 的链接列以及普通 URL、超链接、HYPERLINK 公式；没有报告列的统计页不参与匹配。总表目前没有独立运行编号列，因此先找 SN 相同的候选，再读取候选报告的元数据：新格式 `META_DATA_START` 下的 `test_device_id / test_run_id`，旧格式 `METADATA` 下的 `pipette / date`。只有完整读取且两个身份字段一致才匹配；有 gid 时原则上仅核验该页。

部分历史链接仍带默认 `gid=0`，但报告中的 Assembly QC 页已经使用其他 gid。仅当明确指定的 `gid=0` 不存在且工作簿恰好有一个规范化名称为 `Assembly QC` 的数据页时，允许改为核验该页；仍需完整核验 SN 和运行编号，并将“查看测试报告”指向实际页的 gid。存在真实 gid 0、指定其他无效 gid、没有或存在多个 Assembly QC 页时，均不会按此规则跳到其他页。该兼容处理不改写外部总表，且不能凭工作表名称直接认定匹配。

唯一匹配显示“查看测试报告”和“总表位置”；相同目标链接去重，多份不同报告都精确命中时显示多候选，交给人员核对。缺少身份、没有匹配、Google 不可用分别提示；任一候选读取失败时不会宣称“唯一匹配”或“未找到”。查询两表时，任一来源读取失败也不会宣称唯一匹配或未找到；已知通道只受对应来源的读取状态影响，例如 1ch 权限失败不会阻断 8ch 报告匹配。总表指向非 Google 报告的链接不会打开。匹配结果不会写回总表或修改原始失败报告，也不改变证据版本、分析缓存或返修确认。

两个通道的 Google 访问分别在独立后台队列执行，前端仅在组件可见时查询与轮询。总表索引、已核验报告身份和匹配结果默认缓存 300 秒，持久化到 `DATA_DIR/defect-search/test-failure-report-links.sqlite3`；缓存按通道、总表及工作表配置隔离，独立于失败索引，每组来源的身份和结果各最多 1024 项，保留最近 4 组来源配置。失败短暂退避，旧结果明确标为过期。编辑人员可“重新匹配”强制读取最新数据；查看人员可刷新状态，过期数据自动重查。修改表结构或上传新报告后可使用重新匹配，无需重新扫描原始失败文件。

后端复用工程 Google 账号与代理，不依赖浏览器的 Google 登录，也不会弹出 OAuth 授权页。配置 `PRODUCTION_PLATFORM_GOOGLE_TOKEN_PATH` 指向现有 OAuth token，或 `PRODUCTION_PLATFORM_GOOGLE_SERVICE_ACCOUNT_PATH` 指向有权读取总表和候选报告的服务账号；服务账号需获授这些文档的读取权限。配置示例在 `apps/backend/.env.example`：

```dotenv
PRODUCTION_PLATFORM_TEST_FAILURE_REPORT_LINKS_ENABLED=true
PRODUCTION_PLATFORM_TEST_FAILURE_REPORT_SHEET_ID=16GY8f7p788fbwxxIEH_Azn1RB-NWl3N7cRZzz-6SA_E
PRODUCTION_PLATFORM_TEST_FAILURE_REPORT_SHEET_GIDS=
PRODUCTION_PLATFORM_TEST_FAILURE_REPORT_1CH_SHEET_ID=1eHeq3W0Mr-X6nC0MkNZuuS3DLW097Xtwl2pTkIEpSOU
PRODUCTION_PLATFORM_TEST_FAILURE_REPORT_1CH_SHEET_GIDS=
PRODUCTION_PLATFORM_TEST_FAILURE_REPORT_LINK_REFRESH_SECONDS=300
```

原有 `REPORT_SHEET_ID / REPORT_SHEET_GIDS` 继续配置 8ch 来源；新增 `REPORT_1CH_SHEET_ID / REPORT_1CH_SHEET_GIDS` 仅配置 1ch 来源，双方设置不会相互覆盖。各自的 `SHEET_GIDS` 留空搜索对应总表全部页；指定时填逗号分隔 gid。未设置这些配置时自动使用上述两个内置总表，不需另建 Google 登录凭据；服务器已有账号需能读取相应总表和候选报告。新设置在重启后端后生效。

## 型号与确认分类

列表提供两级标签：先选“全部型号”或具体型号，再选“未确认 / 已确认 / 全部”，默认查看全部型号下的未确认报告。协议中的已知型号名称统一展示，例如 `p50_multi_flex` 显示为 `P50M`，同型号的不同名称归入同一标签。

标签数量按文件夹报告统计，覆盖全部分页；同一设备的两个文件夹计为两份报告。搜索、日期、测试模式和异常类型会更新各分类数量。切换型号或确认状态立即生效并回到第一页，保留各报告未保存的返修文字。

文件夹中只要有一份当前证据包尚未确认，该报告就归入“未确认”。保存确认后归入“已确认”；本文件夹新增阶段证据或实质失败证据变化时，再归入“未确认”。另一个文件夹的到达不会改变本报告状态。已有确认历史仍可查看，型号名称的统一不会使确认失效。

## 失败信息搜索与知识库

列表关键词搜索覆盖设备 SN、型号、报告文件夹及本文件夹内证据的完整失败摘要、失败项、失败原因、错误码和执行异常。列表摘要最多显示 10 条，仅用于概览；后面的失败信息仍可搜索。匹配同一 SN 时，每个文件夹分别返回；命中某文件夹的失败信息不会带出其他文件夹。搜索结果按文件夹报告计数，并在分页前更新型号与确认状态标签数量。

在报告详情中选择一个失败项，再点击“检索历史缺陷知识库”。系统使用所选失败名称作为搜索词，型号作为独立筛选条件；相同失败名称合并为一个选项。搜索词最多 500 个字符，原报告摘要仍完整展示。知识库在新标签页打开，当前页面的返修输入草稿继续保留。

型号按报告名称传递，不自动推断硬件代次或变型。例如报告显示 `P50M`，而知识库按 `P50M-G3`、`P50M-MINI` 分类时，需在知识库核对并选择实际型号。没有匹配案例与请求失败分别显示；跳转成功不代表一定存在对应历史案例。

检索词的前端回归可在 `apps/web-ui` 运行 `node --experimental-strip-types --test scripts/check-test-failure-knowledge.mjs`，覆盖单项提取、去重、空值、Unicode 长度及型号边界。后端完整搜索回归位于 `apps/backend/tests/test_test_failures.py`。

## 数据来源与配置

后端读取与生产 QC 协议 `pipette_assembly_qc_ot3.py` 对应的失败归档：

```text
/opt/pipette_assembly_qc_log/
└── <设备SN>_<UTC时间>/
    ├── <报告名>.json
    ├── <报告名>.log
    ├── <报告名>.encoder.csv  # 可选
    ├── <报告名>.right-reference-50ul.json  # 该规格参考失败时
    ├── <报告名>.right-reference-50ul.log
    └── <报告名>.right-reference-50ul.encoder.csv  # 可选
```

```dotenv
PRODUCTION_PLATFORM_TEST_FAILURE_DIR=/opt/pipette_assembly_qc_log
PRODUCTION_PLATFORM_TEST_FAILURE_SCAN_SECONDS=60
```

将配置写入 `apps/backend/.env`；`.env.example` 仅作为模板，不会被后端加载。修改后需要重启后端。本机测试时，可将目录改为 `apps/backend/data/test-failure-reports/` 的绝对路径，并在其中放入完整报告文件夹。此本地样本目录已排除 Git 跟踪。

目录是 **FastAPI 服务所在机器的本地目录**。如果归档与后端不在同一台服务器，需先把归档挂载到后端可读的位置，再配置该目录。服务用户需要归档读取权限，以及平台 `data/defect-search/` 的写入权限。

首次启动和之后的定时扫描在后台执行；页面也可手动触发刷新。原始报告只读，SQLite 索引与确认历史保存在 `PRODUCTION_PLATFORM_DATA_DIR/defect-search/test-failures.sqlite3`，默认位于 `apps/backend/data/defect-search/`。该位置被 Git 忽略，并被现有远程部署脚本保留。备份平台数据时需包含此数据库；在线备份应使用 SQLite backup API，避免遗漏 WAL 中尚未合并的数据。

扫描使用最长 60 秒的内容摘要缓存，键包含安全打开文件的设备号、inode、大小、mtime 和 ctime；过期或属性变化时重新流式读取。未变化的报告无需重新解析，JSON 解析失败且内容不变时保留错误提示，待内容变化再重试。归档量较大时，可通过 `PRODUCTION_PLATFORM_TEST_FAILURE_SCAN_SECONDS` 调整扫描间隔。

## 解析契约

优先读取 `schema_version=1` 的 JSON。`failure_details` 用于摘要，`report_rows` 保留逐项证据，`runtime_error` 和 `trace.tests` 保留运行异常与执行状态，`recommendations` 作为协议提供的检查参考。LOG 用于证据追溯，JSON 暂缺时可按协议的明确日志章节降级解析；encoder CSV 作为可选附件查看。

- 只有明确的 `FAIL` 行计为测试不通过。`unknown`、`not_recorded`、配置跳过和前序失败阻断均独立展示。
- 已被测试捕获的动作异常不等同于最终运行异常；`completed_modes` 也不等同于通过。
- 逐项 `data` 的布局取决于测试 tag，页面保留原始测量数组与协议原因，不统一猜测其数值含义。
- 最近压力读数不等同于异常触发时压力；检查建议中的“原因待确认”不等同于人工返修确认状态。
- 同一前缀的 JSON、LOG、encoder CSV 只算一个证据包。身份首先限定在相同文件夹内，再使用运行 ID、测试模式及报告 ID，参考阶段另按规格区分；缺少身份时使用来源路径。不同文件夹始终独立，不混用不同文件夹或文件名前缀的附件。兼容归档根目录中的旧散文件时，每个文件名前缀单独显示，不把所有散文件合成一份报告。
- 参考快照中的 `last_failure` 可能尚未转存为已处理异常。仅当阶段、规格、安装位及结构化事件相符，且 `handled` 明确为 `true` 时，不据此推断整轮运行中断；显式运行错误及执行异常仍优先。LOG 的 `Action history` 章节同样参与识别，旧日志缺少该字段时保留保守判断。
- 上传分文件进行，附件可能先后到齐。服务器 JSON 中自身附件的 `pending_self_upload` 是正常快照状态，页面按实际文件存在情况提供附件。
- 缺少设备 SN 的报告独立保留；文件缺失、损坏或尚在写入时显示扫描/解析状态，已有处理记录不被扫描清空。
- 增量扫描同时核对文件内容摘要，文件大小和修改时间相同也能识别内容更新。可选附件删除后，下一次成功扫描会更新当前附件列表，历史失败证据与返修确认仍保留。

## 返修确认

操作员在报告行填写原因、措施或备注后保存。确认绑定保存时当前文件夹内的证据版本。不同文件夹的确认互相独立：A 已确认、B 未确认时，保存 A 的补充记录不改变 B；新增 C 文件夹也不改变 A。当前文件夹新增证据或实质失败证据变化后显示待确认，原有确认仍保留。重复扫描和附件上传状态变化不会清除确认。

每行按时间从新到旧显示本报告最近两条返修确认，分别标注“最新确认”和“上一条确认”。正文加粗突出显示，每条保留独立的确认人和时间；不足两条时按实际记录数展示。保存新确认后更新这两条预览，完整记录继续保存在“返修确认历史”中。

列表返回的 `version` 是当前文件夹的并发校验值；本报告的证据或确认发生变化时返回 HTTP 409，其他文件夹变化不影响此版本。前端保留草稿，提示核对后更新当前行的草稿版本再保存；普通刷新不自动更新草稿版本。确认人从登录会话取得，不接受浏览器指定用户。

所有接口均要求登录并沿用平台 CSRF 校验。`viewer` 可查看报告、附件和确认历史；`operator`、`device_operator`、`admin` 可触发扫描及保存确认。确认历史作为此功能内的共享生产记录，与现有缺陷知识库中的个人处理反馈独立保存。

## API

共同前缀：`/api/defect-search/test-failures`。

| 方法与路径 | 用途 |
| --- | --- |
| `GET /devices` | 文件夹报告分页；SN/关键词、型号、上海日期范围、模式、失败类型、确认状态筛选（保留路径名称兼容现有客户端） |
| `GET /reports/{id}` | 报告明细、执行状态、建议及附件信息 |
| `GET /reports/{id}/report-link` | 查询或后台匹配 SN + report_run_id 对应的测试报告链接 |
| `POST /reports/{id}/report-link` | 编辑权限；强制重新读取总表与候选报告元数据，返回 202 |
| `GET /reports/{id}/attachments/{kind}` | 下载 JSON、LOG 或 encoder CSV |
| `GET /reports/{id}/attachments/{kind}/preview` | 有大小/行数限制的附件预览 |
| `GET /scan` | 最近扫描状态及错误 |
| `POST /scan` | 后台触发增量扫描 |
| `GET /devices/{id}/confirmations` | 当前文件夹报告的完整返修确认历史 |
| `POST /devices/{id}/confirmations` | 仅对当前文件夹报告提交 `{ "text": "确认内容", "version": "列表返回的版本" }` |

附件通过报告 ID 和类型访问，不能提交任意服务器路径；下载和预览先核对索引 SHA256、读取前后属性及索引版本，再从不可变临时快照返回内容。详情仅校验可用性，不生成副本，并短暂缓存已验证状态。旧索引缺少 SHA256 时需先重新扫描；JSON 内的机器人本地文件路径不作为后端读取目标。

`GET /devices` 保留 `devices` 返回字段，但其中每项代表一个文件夹报告，`id` 也是文件夹范围的身份，`report_folder` 为归档根目录下的相对文件夹路径。`summary.devices`、列表 `total` 及分类数量均为文件夹报告数；`report_count`、`unconfirmed_count`、`summary.reports` 为证据包数。`facets.products` 为各型号的报告数量，`all` 为所有型号的合计，`confirmation` 为当前型号的确认状态数量。每组均含 `total`、`pending`、`confirmed`。型号统计不受当前型号和确认标签影响，确认统计不受当前确认标签影响；三者均遵循其他筛选条件，并在分页之前计算。

每行的 `recent_confirmations` 返回本报告最近两条确认的正文、确认人和时间；`confirmation` 继续返回最新一条，兼容既有调用。保存确认响应中的 `device` 也包含最近两条预览；完整历史通过确认历史接口读取。


## 2026-10-30 页面与审计优化

- `matched_report_ids` 返回当前文件夹内同时命中关键词、模式、异常类型和日期条件的证据 ID。列表保留完整文件夹，分析卡和默认详情使用命中的证据；文件夹/SN 搜索适用于其内部所有证据。
- `summary_total` / `summary_omitted` 提示摘要总数和省略数；搜索仍覆盖完整失败证据。
- `evidence_version` 独立于确认所用的失败 `revision`，包含附件路径、属性、内容哈希及解析状态；LOG/encoder 补传、删除或替换会更新详情和分析状态，但不会使已有返修确认失效。
- 列表刷新不卸载当前详情。当前证据版本变化时才重新读取，保存确认只刷新历史；显式失效的证据链接不跳转到其他报告。
- 返修草稿按登录用户及文件夹 ID 存入当前浏览器会话的 `sessionStorage`，刷新或返回页面可恢复；保留原 `version`，证据变化后必须核对再保存。草稿不等于已确认。存储不可用时仍能编辑、提交，并提示无法恢复草稿。
- `GET /devices/{id}/confirmations` 的历史项新增 `coverage`：每项含 `report_id`、`revision`、文件夹、来源文件、角色、测试时间、`current`。优先从对应历史 revision 读取元数据；旧索引缺少该历史版本时 `metadata_recorded=false`，不把当前元数据冒充历史快照。列表最近两条预览保持原有五字段。
- `reports[].confirmation_status` / `covered_by` 标出当前证据版本是否已确认及覆盖它的确认记录。确认历史仍全部保留，无删除入口。
- 扫描状态增加 `source_status` 与 `last_successful_scan_at`。目录不可用时清空过期诊断计数并保留上次成功时间、历史报告；部分报告异常或待处理时显示降级状态。
