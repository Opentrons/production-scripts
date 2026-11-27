# 产品测试数据集成 API

本文档说明如何通过固定访问令牌和游标分页读取生产平台中的产品测试数据。该接口用于服务间集成，不依赖平台用户登录，也不接受登录 Cookie 代替集成令牌。

## 接口概览

```http
GET https://183.11.226.250:10443/api/integrations/collection-data
Authorization: Bearer <access-token>
Accept: application/json
```

- 默认一次返回 200 条，最大 1000 条。
- 使用 `next_cursor` 读取下一页，不使用页码或 MongoDB `skip`。
- 每次分页会固定首次请求时的 `snapshot_time`，分页期间新写入的数据不会插入当前批次。
- 不计算全量 `total`，避免每页执行高成本统计。
- 默认按 `update_time` 倒序排列；生产同步返修确认时使用 `time_field=sync_updated_at`，按同步更新时间倒序排列。相同时间使用数据集合和内部 ID 保证顺序稳定。
- 接口提供每条测试记录当前的最新返修确认，不提供完整确认历史。

## 配置访问令牌

环境变量名：

```dotenv
PRODUCTION_PLATFORM_COLLECTION_DATA_ACCESS_TOKEN=<至少 32 个随机字符>
```

生成令牌：

```bash
openssl rand -hex 32
```

把生成值写入后端使用的环境文件后重启服务。标准部署脚本会在该配置缺失或长度不足时自动生成令牌并保存到 `/etc/production-platform.env`，不会在部署日志中打印令牌。

令牌要求：

- 只能通过 HTTPS 请求头传输。
- 不要放在 URL 查询参数、前端源码或日志中。
- 调用方应从自身的密钥管理系统或环境变量读取令牌。
- 更换令牌后，调用方和服务端必须同步更新。

## 查询参数

| 参数 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `collection_name` | 否 | `__all__` | `__all__` 表示合并所有 `pipette_` 数据集合，也可以指定具体集合 |
| `limit` | 否 | `200` | 单页数量，范围 1 至 1000 |
| `cursor` | 否 | - | 上一页返回的 `next_cursor`；第一页不要传 |
| `model` | 否 | - | 产品型号精确匹配，例如 `P1000M` |
| `type` | 否 | - | 产品类型精确匹配，例如 `Opentrons` |
| `total_result` | 否 | - | 测试结果精确匹配，同时兼容源数据的 `total_result` 和 `total_qc_result` |
| `barcode` | 否 | - | 条码/SN 模糊匹配，不区分大小写 |
| `time_field` | 否 | `update_time` | 时间筛选、排序和游标使用的字段：`update_time`（测试数据更新时间）或 `sync_updated_at`（测试数据及返修确认的同步更新时间） |
| `updated_after` | 否 | - | 更新时间下限，支持 `YYYY-MM-DD` 或 ISO 8601 时间 |
| `updated_before` | 否 | - | 更新时间上限；只传日期时包含当天全部时间 |

`barcode` 会依次匹配源数据中的 `sn`、`serial_number`、`barcode` 和 `test_tag` 字段。

同一个游标只能和创建它时相同的集合、`time_field` 及筛选条件一起使用。可以调整 `limit`，但修改其他筛选参数会返回 `400 integration.invalid_cursor`。

## 返回字段

每条产品数据只返回以下字段，不暴露 MongoDB ID、CSV 链接、内部文件路径或其他源文档字段：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `record_key` | string | 稳定、不透明的记录标识，用于调用方幂等更新。区分数据库、集合及测试记录，同一 SN 的不同记录具有不同标识；修改确认不改变标识 |
| `collection` | string | 数据集合 |
| `update_time` | string | UTC ISO 8601 测试数据更新时间；仅修改返修确认不会改变此值 |
| `sync_updated_at` | string | UTC ISO 8601 同步更新时间，覆盖测试上传、确认修改及清空。历史记录缺少该字段时回退到原更新时间，无需迁移 |
| `repair_confirmation` | string/null | 当前有效的最新返修确认正文；`null` 表示当前无有效确认，调用方应清除已有值 |
| `repair_confirmed_by` | string/null | 对应确认人的显示名称；与确认正文一起更新或清空 |
| `repair_confirmation_updated_at` | string/null | UTC ISO 8601 确认字段最近同步变化的时间，包含清空；不是人工填写时间。无记录或旧数据未记录该时间时为 `null` |
| `sn` | string/null | 条码 / SN |
| `model` | string/null | 产品型号 |
| `type` | string/null | 产品类型 |
| `total_result` | string/null | 测试结果 |
| `failure` | string/null | MongoDB 测试文档中存储的失败详情，优先读取 `failure`，兼容旧字段 `failures`。多项以换行分隔。历史记录可能返回 `N/A` 或 `null` |

响应示例：

```json
{
  "data": [
    {
      "record_key": "8929d79fd09fb977058159a7670fb5bc48f1e65bb89169b2dfb7269a029118cd8",
      "collection": "pipette_8ch_assembly_qc",
      "update_time": "2026-08-18T07:48:10Z",
      "sync_updated_at": "2026-11-27T02:30:00Z",
      "repair_confirmation": "更换密封圈，完成复测核对",
      "repair_confirmed_by": "李杰_Jerome",
      "repair_confirmation_updated_at": "2026-11-27T02:30:00Z",
      "sn": "P1KMV3520260814A01",
      "model": "P1000M",
      "type": "Opentrons",
      "total_result": "FAIL",
      "failure": "PRESSURE / Leak Check (PRESSURE_OUT_OF_RANGE)"
    }
  ],
  "count": 1,
  "limit": 200,
  "has_more": true,
  "next_cursor": "eyJwb3NpdGlvbiI6...",
  "collection": "__all__",
  "snapshot_time": "2026-11-27T03:00:00Z"
}
```

当 `has_more` 为 `false` 时，`next_cursor` 为 `null`，本批数据读取完成。

## curl 示例

第一页：

```bash
curl --fail-with-body \
  --header "Authorization: Bearer $COLLECTION_DATA_ACCESS_TOKEN" \
  --header "Accept: application/json" \
  "https://183.11.226.250:10443/api/integrations/collection-data?limit=500"
```

下一页：

```bash
curl --fail-with-body \
  --get \
  --header "Authorization: Bearer $COLLECTION_DATA_ACCESS_TOKEN" \
  --header "Accept: application/json" \
  --data-urlencode "limit=500" \
  --data-urlencode "cursor=$NEXT_CURSOR" \
  "https://183.11.226.250:10443/api/integrations/collection-data"
```

如果内部 HTTPS 证书未被调用机器信任，应把对应 CA 证书安装到系统信任链。不要在正式集成中长期使用 `curl -k` 跳过证书验证。

## JavaScript 全量分页示例

```javascript
const baseUrl = "https://183.11.226.250:10443/api/integrations/collection-data";
const accessToken = process.env.COLLECTION_DATA_ACCESS_TOKEN;
let cursor = null;

do {
  const params = new URLSearchParams({
    collection_name: "__all__",
    time_field: "sync_updated_at",
    limit: "500",
  });
  if (cursor) params.set("cursor", cursor);

  const response = await fetch(`${baseUrl}?${params}`, {
    headers: {
      Authorization: `Bearer ${accessToken}`,
      Accept: "application/json",
    },
  });
  if (!response.ok) {
    throw new Error(`Collection API returned HTTP ${response.status}: ${await response.text()}`);
  }

  const page = await response.json();
  await saveProductRows(page.data);
  cursor = page.next_cursor;
} while (cursor);
```

## 增量同步（生产推荐）

首次切换到新版接口时，使用 `time_field=sync_updated_at` 重新全量读取并建立 `record_key` 映射。仅有旧 `update_time` 检查点时，不应直接作为新版同步时间检查点，否则可能漏掉历史返修确认。

```bash
curl --fail-with-body --get \
  --header "Authorization: Bearer $COLLECTION_DATA_ACCESS_TOKEN" \
  --data-urlencode "time_field=sync_updated_at" \
  --data-urlencode "limit=500" \
  "https://183.11.226.250:10443/api/integrations/collection-data"
```

完整读取本批游标链，按 `record_key` 幂等保存每条数据，然后持久化本批最大的 `sync_updated_at`。后续同步：

```http
GET /api/integrations/collection-data?time_field=sync_updated_at&updated_after=2026-11-27T02:30:00Z&limit=500
Authorization: Bearer <access-token>
```

下一页必须保留相同的 `time_field`、`updated_after` 及其他筛选条件，再增加 `cursor`。只有整批全部处理成功后才提交检查点；失败时保留旧检查点，允许重读。空批次保留原检查点。

`updated_after` 为包含边界的查询，因此边界记录可能重复，调用方须按 `record_key` 覆盖更新。同一 SN 可以有多份测试记录，不可仅以 SN 作为唯一键。无时区的时间参数按 UTC 处理。

同步约定：

- 上传测试数据或返修确认字段发生变化时，推进 `sync_updated_at`。重复同步相同确认不会推进时间。
- 确认被清空时仍返回该记录，两个确认字段为 `null`；调用方应覆盖旧值，不能忽略 `null`。
- `total_result` 仍是测试结果，存在返修确认不代表测试已通过。有有效 `failure` 时，即使总结果为 `PASS`，也可能需要返修处理；同步全部确认时不要仅筛选 `total_result=FAIL`。
- 返修确认通过后台异步写回，本接口返回当前已经同步到测试数据库的值。尚未匹配测试记录的归档报告不会单独出现在此接口中。
- `snapshot_time` 是当前分页批次的时间上界，并非数据库事务快照。分页期间更新到上界之后的记录会在后续增量批次中读取。
- 本接口不提供删除事件，也不提供完整确认历史。

不传 `time_field` 时继续沿用旧版 `update_time` 的筛选、排序和游标行为，但该模式无法可靠跟踪仅返修确认发生的变化。

## 按产品型号读取

使用 GET 参数 `model` 可以只读取指定型号。例如只读取 `P1000M`：

```http
GET /api/integrations/collection-data?collection_name=__all__&model=P1000M&limit=500
Authorization: Bearer <access-token>
```

`model` 为精确匹配。使用游标读取下一页时必须继续带上相同的 `model=P1000M`，否则服务会返回 `400 integration.invalid_cursor`。

对应的 curl 请求：

```bash
curl --fail-with-body --get \
  --header "Authorization: Bearer $COLLECTION_DATA_ACCESS_TOKEN" \
  --header "Accept: application/json" \
  --data-urlencode "collection_name=__all__" \
  --data-urlencode "model=P1000M" \
  --data-urlencode "limit=500" \
  "https://183.11.226.250:10443/api/integrations/collection-data"
```

返回的每一条记录的 `model` 都是 `P1000M`；如果没有匹配记录，返回空的 `data` 数组。

## 状态码

| 状态码 | 错误代码 | 说明 |
| --- | --- | --- |
| `200` | - | 请求成功 |
| `400` | `integration.invalid_cursor` | 游标损坏，或游标与筛选条件不匹配 |
| `401` | `integration.authentication_required` | Bearer Token 缺失或错误 |
| `404` | `errors.not_found` | 指定的数据集合不存在 |
| `422` | FastAPI validation error | 参数长度或 `limit` 范围不正确 |
| `503` | `integration.configuration_error` | 服务端没有正确配置访问令牌 |
| `503` | `errors.service_unavailable` | 测试数据库暂时不可用 |

错误响应示例：

```json
{
  "detail": {
    "code": "integration.authentication_required",
    "message": "集成接口访问令牌无效或缺失",
    "params": {}
  }
}
```

生产令牌只写入受权限保护的环境文件 `/etc/production-platform.env`，不写入 Git 仓库、API 文档、前端代码或 URL。部署脚本会在令牌缺失时使用 `openssl rand -hex 32` 自动生成；需要轮换时修改该环境变量并重启后端服务。

## 浏览器跨域调用

该接口主要面向后端服务。如果必须从其他域名的浏览器页面调用，需要把来源域名加入 `PRODUCTION_PLATFORM_AUTH_ALLOWED_ORIGINS`。不要把固定令牌嵌入可公开下载的浏览器 JavaScript 包中。
