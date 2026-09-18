# ENT Weekly 工程协作规范

本文件供参与本仓库的开发者与编码代理使用。它描述当前真实架构、不可破坏的业务约束和安全运行方式。

## 1. 项目定位

ENT Weekly 是面向公开读者的耳鼻喉科 PubMed 文献追踪网站，覆盖鼻科、耳科、咽喉科和鼻咽癌。

主数据流不可改变：

```text
PubMed [EDAT] 入库日
  -> DeepSeek 分类和中英文翻译
  -> SQLite 审计库
  -> snapshot JSON
  -> Astro 静态站
```

日追踪在每天北京时间 14:00 运行。目标日期是前一完整美国东部入库日。周报计划在每周一北京时间 19:00 运行，汇总上一个自然周。

## 2. 当前架构

```text
                    外网
       PubMed E-utilities   DeepSeek API
                 |               |
                 +-------+-------+
                         |
                     FastAPI
                         |
                  SQLite WAL 数据库
                         |
              daily-YYYY-MM-DD.json
                         |
                   Astro 静态构建
                         |
                    nginx web 容器
                         |
                 Caddy HTTPS 与域名
                         |
                       公开网站
```

Docker Compose 当前包含四个服务：

| 服务 | 职责 | 关键点 |
|---|---|---|
| `api` | FastAPI、PubMed 抓取、DeepSeek、SQLite 写入 | 内部端口 8080 |
| `cron` | supercronic 调度日任务、周报任务和备份 | 使用北京时间解释 crontab |
| `web` | nginx 承载 Astro 静态文件 | 仅暴露给 Caddy |
| `caddy` | 域名反代与自动 HTTPS | 对外开放 80、443 |

前端构建期直接读取 `data/snapshots/`，不依赖浏览器端调用后端 API。后端公开 API 目前仅提供健康检查和文章 JSON；内部任务入口必须使用 `REGEN_TOKEN` 鉴权。

## 3. 真实实现状态

### 已实现

- 以 `api/config/topic-queries.json` 为唯一检索配置，按 EDAT 检索四个耳鼻喉专科。
- PubMed XML 解析、PMID 去重、原始英文标题、摘要、作者、单位和 PubMed 链接保存。
- DeepSeek 结构化分类、中文标题和摘要翻译。
- SQLite 审计表：候选文献、来源日期、质量记录、LLM 输出、筛选结论、排除记录和日运行记录。
- 严格 JCR/CAS 质量门禁和中医药排除规则。
- 静态首页、主题分类、主题详情、文章详情、方法与审计、关于和周报入口。
- 每日 14:00 生产任务脚本、每周一 10:00 备份任务脚本、Caddy HTTPS 配置。

### 部分实现或待实现

- `cron/jobs/weekly.sh` 与周报路由已存在，但 `/internal/run-weekly` 当前只返回 `queued`，尚未生成真实周报。不得把周报页面或定时任务描述为已上线。
- Docker Compose 已配置，当前本机未验证 Docker 运行时。公网部署前必须在目标 VPS 做端到端验证。
- 站点使用系统深色模式样式，不提供用户手动主题偏好持久化。

## 4. 领域与质量不变量

### 4.1 检索与时间

- 日追踪主来源是 PubMed `EDAT`，不可悄悄替换为 `PDAT` 或发表日期。
- 每个来源日期必须随文章保存为 `article_sources`。页面分组使用文章自身 EDAT，不使用快照文件名推断日期。
- `PDAT` 只能作为周报回补的独立来源，必须显式标记，不能和 EDAT 混算。
- 检索规则只在 `api/config/topic-queries.json` 修改。改动前须同步审阅 `耳鼻喉周报PubMed检索规则.md`。

### 4.2 文献门禁

- JCR Q4、2025 CAS 预警期刊、缺失或无法确认期刊质量、无摘要和中医药相关记录一律不进入公开网站。
- 影响因子只显示 JCR 数据中的 `5 Year JIF`，不能用普通 IF 替代。
- 所有候选均应留下具体筛选原因。排除记录留在 SQLite 审计库，不公开其明细。
- 展示的英文摘要必须保留 PubMed 原文，不得由 LLM 重写或补充未报告的结论。
- LLM 的分类或翻译不能替代临床判断。所有页面维持“文献追踪，不构成医疗建议”的边界。

### 4.3 分类与周报

- 每篇公开记录只有一个主专科和一个展示类型。
- 主专科固定为：`rhinology`、`otology`、`laryngology`、`nasopharyngeal_carcinoma`。
- 展示类型固定为：临床研究、AI/ML、基础研究、综述 Meta、指南共识。
- 真实周报必须按“病种或专科 x 研究类型”组织，中文综述中的每项证据均需带 PMID 编号引用和 PubMed 原文入口。
- 周报应在代码层检查引用完整性；不得将无 PMID 的自由文本发布为证据综述。

## 5. 数据与文件约定

| 路径 | 作用 | 规则 |
|---|---|---|
| `api/config/topic-queries.json` | 版本化检索规则 | 修改须改变版本标识 |
| `api/src/ent_weekly/` | 后端和数据管线 | 按领域职责维护，避免把业务逻辑塞进路由 |
| `data/ent_weekly.db` | SQLite 运行数据 | 忽略版本控制，不手工编辑 |
| `data/snapshots/` | 日快照和未来周报快照 | 由管线生成，不手工修补 |
| `data/journal-quality.json` | JCR/CAS 运行索引 | 来源工作簿不提交，缺失时按无法验证排除 |
| `web/src/data/site.ts` | Astro 的快照读取层 | 前端数据映射集中在此处 |
| `web/src/pages/` | 静态页面路由 | 保持既有 URL，不随视觉改版更名 |
| `cron/jobs/` | 容器调度脚本 | 修改后须验证时区、鉴权和构建路径 |
| `.env` | 密钥与环境参数 | 永不提交、永不打印、永不写入截图或快照 |

## 6. 本地开发与验证

Windows 本地日追踪命令：

```powershell
$env:PYTHONPATH = 'api/src'
& .\.venv\Scripts\python.exe scripts\run_daily.py --edat YYYY-MM-DD
```

该命令读取 `.env`，会访问 PubMed 和 DeepSeek，并写入 SQLite 与快照。仅在需要真实数据时运行。

前端开发与构建：

```powershell
cd web
npm run dev
npm run check
npm run build
```

构建产物在仓库根目录 `dist/`。本地静态预览服务使用 `preview-server.cjs`，默认地址为 `http://127.0.0.1:4173/`。

当前仓库没有自动化测试套件。不得笼统声称“测试全部通过”。至少分别报告：Python 语法检查或目标命令结果、`npm run check` 结果、`npm run build` 结果，以及所验证的页面或接口。

## 7. 部署与运行约束

- 公网域名使用 `www.<SITE_DOMAIN>` 作为主站，裸域由 Caddy 301 跳转。
- Caddy 自动签发证书需要 DNS 的 `@` 和 `www` A 记录指向 VPS，且 80、443 端口可达。
- 生产数据使用 Compose 命名卷 `ent_data` 与 `web_dist`。禁止执行 `docker compose down -v`，除非用户明确要求删除所有运行数据与证书。
- `data/journal-quality.json` 以只读挂载方式传入 API。部署时必须在目标主机提供这个已授权的运行索引。
- 生产变更前应先备份 SQLite、快照和 `.env`，再更新服务。不得在对话中索取或回显 VPS 密码、DeepSeek Key 或内部任务令牌。
- 周报任务在真实管线完成前必须保持失败可见，不得伪造成功、空报告或演示内容。

## 8. 开发规范

- 代码注释、用户可见文案、提交信息和项目文档使用中文；术语、环境变量和 API 字段保留英文原名。
- 提交信息遵循 Conventional Commits，例如 `feat(weekly): 增加带 PMID 引文的周报生成`。正文说明原因和风险。
- 先检查工作区已有修改；不得覆盖用户的未提交内容。
- 不删除或重建 SQLite、快照、JCR 运行索引、Docker 卷，除非用户明确授权并确认具体目标。
- 修改数据结构时同步更新数据库初始化、快照契约、前端映射、接口返回和本文档。
- 修改定时任务时，使用绝对日期和 `Asia/Shanghai`、`America/New_York` 语义验证，不靠本地系统默认时区猜测。
- 修改视觉界面不得破坏筛选、日期定位、主题详情、文章详情和键盘焦点可见性。

## 9. 完成定义

一次功能变更只有在以下条件满足后才算完成：

1. 不破坏本文件第 4 节的不变量。
2. 不泄露 `.env`、运行数据库、JCR 原始工作簿或内部令牌。
3. 后端变更至少完成相关命令或接口验证；前端变更完成 `npm run build`。
4. 公网相关变更在 HTTPS、域名、静态文件和每日任务都验证前，不宣称“已真实上线”。
5. 任何 LLM 生成的周报或展示内容都对来源、日期范围、检索版本和 PMID 引用保持可审计。
