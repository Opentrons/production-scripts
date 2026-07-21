# Productions Versions

生产版本检测与 BOM 核对工作流应用。项目结构参考 `productions-opentrons`，使用 FastAPI 后端和 Vue 3 前端，独立运行。

## 当前初始化范围

- 工作流创建、编辑、删除和本地 JSON 持久化。
- 工作流步骤编排、排序和删除。
- 手动触发工作流。
- 按分钟配置定时触发，启用状态下由后端调度线程执行。
- 预置 `Duro BOM 核对` 工作流模板。
- 展示工作流最近运行记录。
- 通过 OAuth 和 ghelper 代理读取 Google Drive / Google Sheets。
- 读取当前 SOP 总表，保留单元格真实 Drive hyperlink 并解析文件 ID。
- 下载 Google Drive 中的 SOP PDF，提取页数、元数据和逐页文本。
- 识别 PDF 中的“物料清单 / Material List”，提取料号、物料名称和数量，并按料号汇总料耗。
- 前端提供 SOP 子菜单、SOP 总览、筛选和 BOM 分析详情。
- 后端优先通过 `DURO_API_KEY` 抓取 Duro 产品列表与产品 BOM；临时 Bearer token 仍可覆盖，并保留产品版本、状态、图片和 BOM 关系字段。
- 前端提供 `Duro → 产品总览`，支持产品搜索、状态/Revision 筛选、图片预览、产品详情和可折叠 BOM 树。

Duro 产品与 BOM 查询连接器已经接入；工作流中的自动 BOM 差异核对步骤尚未接入，当前触发 Duro BOM 工作流仍会记录为“等待配置”，不会生成虚假的核对结果。

## 目录结构

```text
productions-versions/
├── backend/
│   ├── app.py
│   ├── pyproject.toml
│   ├── src/
│   │   ├── api/
│   │   ├── google_driver/
│   │   ├── sop/
│   │   ├── workflows/
│   │   ├── app.py
│   │   └── settings.py
│   └── tests/
├── web_ui/
│   ├── src/
│   │   ├── api/
│   │   ├── views/
│   │   ├── App.vue
│   │   └── main.ts
│   └── package.json
└── Makefile
```

## 本地运行

安装并启动后端：

```bash
cd productions-versions
make install
make backend
```

后端默认地址：`http://localhost:8100`。

安装并启动前端：

```bash
cd productions-versions
make web-ui-install
make web-ui-dev
```

前端默认地址：`http://localhost:8101`，开发服务器会把 `/api` 代理到后端 `8100` 端口。

部署到子路径时可使用 `WEB_UI_BASE_PATH` 和 `WEB_UI_API_BASE_URL`，例如：

```bash
make web-ui-build \
  WEB_UI_BASE_PATH=/productions-versions/ \
  WEB_UI_API_BASE_URL=/productions-versions/api
```

## 测试与构建

```bash
make test
make web-ui-build
```

运行数据默认写入 `backend/data/workflows.json`，该文件不会提交到 git。可通过 `PRODUCTIONS_VERSIONS_DATA_DIR` 修改数据目录。

## Google Drive 与 SOP 总表

默认 SOP 总表：

```text
Spreadsheet ID: 1BqkuAT27F_C-0sXlaqy-9AerJH4Er1LX8Llh-NoqOWI
Sheet gid: 991624078
Sheet title: All Project SOP
```

本地开发时，如果 `productions-versions/backend/auth` 和 `ghelper-test` 没有运行配置，后端会读取 `productions-opentrons/backend` 下现有的 OAuth token 和代理配置。独立部署时，将以下运行文件放入对应目录：

```text
backend/auth/credentials.json
backend/auth/token.json
backend/ghelper-test/skill_config.json
backend/ghelper-test/1779072081477.yml
```

这些文件均被 git 忽略。也可以通过环境变量覆盖路径：

```text
PRODUCTIONS_VERSIONS_GOOGLE_AUTH_DIR
PRODUCTIONS_VERSIONS_GOOGLE_TOKEN_PATH
PRODUCTIONS_VERSIONS_GOOGLE_CREDENTIALS_PATH
PRODUCTIONS_VERSIONS_GHELPER_DIR
```

SOP API：

```text
GET /api/sop/master-sheet
GET /api/sop/master-sheet?refresh=true
GET /api/sop/files/{drive_file_id}/analysis
```

总表接口默认缓存五分钟。PDF 分析接口会从 Drive 下载文件，并返回 PDF 元数据、页数、逐页文本、BOM 分段和汇总料耗；默认最大文件大小为 30 MB，最大文本为 500,000 字符，分析结果缓存 30 分钟。

## Duro 产品与 BOM 接口

当前已经接入 Duro 产品搜索和 BOM 懒加载接口：

```text
GET  /api/duro/status
GET  /api/duro/products
GET  /api/duro/products?refresh=true
POST /api/duro/products/search
GET  /api/duro/products/{product_id}/bom
GET  /api/duro/products/{product_id}/bom?refresh=true
GET  /api/duro/components/{component_id}/children
```

服务器部署优先使用 `backend/.env` 中的 Duro API Key：

```dotenv
DURO_API_KEY=...
```

`.env` 已被 git 忽略，不会提交到仓库。后端默认请求 Duro 的 API Origin `https://mfgapi.duro.app`；如果部署环境必须走 `mfg.duro.app` 代理，可设置 `PRODUCTIONS_VERSIONS_DURO_BASE_URL`。若临时调试时显式设置了短期 token，`PRODUCTIONS_VERSIONS_DURO_TOKEN` 会覆盖 API Key：

```bash
export PRODUCTIONS_VERSIONS_DURO_TOKEN='...'
```

本地也可以写入被 git 忽略的 `backend/auth/duro_token.txt` 作为最后一级回退。后端会解析 JWT 过期时间，过期或缺失时返回明确的 401，不会在 API 或日志中返回 token。API Key 本身若被 Duro 撤销或过期，需要在 `.env` 中替换后重启后端；它不能由一个已过期的 token 自动推导出新的 key。产品列表、产品 BOM 和组件子项默认缓存五分钟。

如果 Duro API Key 不被产品接口接受，也可以将从 `auth.duro.app` 导出的登录 Cookie 写入 `backend/auth/cookies.txt`。后端支持浏览器扩展 JSON、Netscape cookies.txt，以及 `refresh_token=...; other_cookie=...` 原始 Cookie 请求头格式；文件必须包含 HttpOnly 登录会话 Cookie，仅有 FullStory、Datadog 等统计 Cookie 无法刷新 token。产品请求认证失败时，后端会通过 Duro refresh endpoint 获取并缓存新的 access token，然后自动重试一次。若 Duro 同时轮换 refresh token，后端会将新 Cookie 原子写回文件并设置为 `0600` 权限。`cookies.txt` 已被 git 忽略，也可以通过 `PRODUCTIONS_VERSIONS_DURO_COOKIES_PATH` 修改路径。

对于绑定浏览器会话的 refresh token，推荐使用 Playwright Remote Chrome。启动专用 Chrome：

```bash
cd productions-versions
make remote-chrome
```

在打开的 Chrome 窗口中登录 Duro，然后保持该 Chrome 运行。后端通过 `http://127.0.0.1:9222` 的 CDP 接口连接浏览器，在 Duro 页面上下文中获取并缓存 access token，不再手工复制 Cookie。远程或容器化 Chrome 可通过以下环境变量指定：

```dotenv
PRODUCTIONS_VERSIONS_DURO_REMOTE_CHROME_URL=http://remote-chrome:9222
PRODUCTIONS_VERSIONS_DURO_REMOTE_CHROME_APP_URL=https://mfg.duro.app/dashboard
```

CDP 端口拥有完整浏览器控制能力，只应监听 localhost 或受保护的内网。

产品 BOM 根节点通过 Duro 产品详情接口读取第一层子项；前端展开有下级的组件时，再读取该组件的下一层子项，避免大型 BOM 一次性递归造成请求超时。下一阶段由 `duro_bom_fetch` 步骤复用这些接口拉取 BOM，`bom_compare` 步骤生成差异，`report` 步骤保存并展示报告。
