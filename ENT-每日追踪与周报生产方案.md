# ENT 每日文献追踪与周报生产方案

## 目标

建设一个公开的耳鼻喉科 PubMed 文献网站：每天北京时间 14:00 追踪新入库记录，覆盖**鼻科、耳科、咽喉科、鼻咽癌**；按**临床研究、AI/ML、基础研究、综述 Meta、指南共识**展示；每周自动形成按“专科 × 研究类型”组织、有编号引用和 PubMed 原文入口的中文长篇综述。

网站面向阅读者，不提供诊疗建议。所有翻译与综述均标识为 LLM 辅助内容，英文 PubMed 摘要与原始文献优先。

---

## 1. 总体架构

```text
 PubMed E-utilities
          │
          ▼
 每日/每周任务（cron 容器，Asia/Shanghai）
          │  EDAT 日监测 + PDAT 周度回补
          ▼
 FastAPI pipeline
 ├─ 检索与 XML 解析
 ├─ DeepSeek 分类/翻译
 ├─ JCR / CAS 与规则审计字段
 ├─ SQLite 持久化与审计日志
 └─ JSON snapshot 导出
          │
          ├───────────────────────► Astro 静态构建 ─► Nginx
          │                                               │
          └─ FastAPI 只读 API（健康检查/内部任务）        ▼
                                             Caddy（域名、HTTPS）
                                                       │
                                                       ▼
                                                     公开网站
```

采用单仓库、Docker Compose 和 SQLite。它比“前端直接请求 PubMed”更稳定：密钥不暴露、历史数据可追溯、每天更新后可重新构建静态页，并能在有限配置的 VPS 上运行。

---

## 2. 时间与数据口径

### 2.1 每日任务：北京时间 14:00

| 项目 | 设计 |
| --- | --- |
| 触发时间 | 每日 `14:00`，容器时区固定为 `Asia/Shanghai` |
| 主数据源 | PubMed `EDAT`（Entry Date，入库日） |
| 目标日期 | `America/New_York` 的前一个完整自然日，避免当天 PubMed 入库仍在变动 |
| 查询范围 | 四个专科主题块分别检索，以显式 `mindate`、`maxdate`、`datetype=edat` 限定 |
| 重跑规则 | 同一日期可安全重跑；以 PMID 去重、upsert，不重复生成卡片 |
| 更新结果 | SQLite 入库、生成 snapshot JSON、重建 Astro 静态站 |

北京时间 14:00 对应美东凌晨，能给 PubMed 的前一完整入库日留出约 1–2 小时封口时间。日志记录“北京时间任务日”和“实际 EDAT 目标日”，避免误解。

### 2.2 每周任务：周一 19:00

| 项目 | 设计 |
| --- | --- |
| 周期 | 上一个上海时区完整自然周（周一至周日） |
| 回补 | 对四个主题块额外运行 `PDAT` 周范围查询；这是独立标记的发表日期回补源，不和 EDAT 计数混淆 |
| 入选集 | 合并本周 EDAT 与 PDAT 回补后的合格记录，以 PMID 去重并保留双来源日期 |
| 输出 | DeepSeek 生成“专科 × 研究类型”中文长篇综述、编号引用表、Markdown 报告、审计 JSON、静态周报页 |
| 先后关系 | 14:00 日任务先完成对周日 EDAT 的采集，19:00 再生成周报，保证周界完整 |

---

## 3. PubMed 检索策略

### 3.1 查询配置

配置文件 `api/config/topic-queries.json` 管理四个主题块和版本号：

```json
{
  "version": "ent-v1",
  "topics": ["rhinology", "otology", "laryngology", "nasopharyngeal_carcinoma"],
  "global_exclusions": ["traditional Chinese medicine", "acupuncture", "moxibustion"],
  "notes": "每次布尔检索式变更必须递增 version，并写入下一期审计报告。"
}
```

检索应偏向召回，不用模糊的裸缩写（例如 `ENT`、`NPC`、`OSA`）扩大范围。每个候选保留：命中主题块、完整检索式、日期类型、查询区间、检索时间与 PMID。

### 3.2 调用规则

- 使用 NCBI E-utilities：`esearch` 获取 PMID、`efetch` 获取 XML 全记录。
- 固定传递 NCBI `tool` 与 `email`。
- 无 `NCBI_API_KEY` 时限速 3 req/s；有 key 时最多 10 req/s。
- 只读取 PubMed 元数据和摘要，不抓取或镜像出版社全文。
- 论文同时命中多个主题块时保存全部命中证据，但对外只分配一个主专科。

---

## 4. 数据处理与质量门禁

### 4.1 不可跳过的流水线

```text
PubMed（EDAT 新入库记录）
  → PMID 去重与 PubMed XML 解析
  → DeepSeek 分类与中英翻译
  → JCR + CAS 与完整摘要规则审计
  → SQLite 事务写入
  → 静态 JSON snapshot
  → Astro 静态构建
```

**主数据流以此为准**：PubMed EDAT → LLM 分类/翻译 → SQLite → snapshot JSON → Astro 静态站。质量门槛与规则初筛的结果会一并写入 SQLite 作为审计字段；不符合公开条件的记录仍不进入网页列表或周报。

### 4.2 期刊质量规则

使用 ISSN/eISSN 优先、规范化期刊名兜底匹配 2026 JCR 数据；每个候选记录：JCR 来源/发布年、分区、**5 Year JIF**、CAS 2025 预警名单状态与匹配方式。

直接排除：

- JCR Q4；
- 2025 CAS 预警期刊；
- 无法可靠匹配 JCR 或 CAS 状态的期刊；
- 无 PubMed 摘要；
- 明确中医药框架、方药、针灸、艾灸、推拿、拔罐、中成药干预；
- 非 ENT 语义命中、牙科/影像工程误命中、勘误、纯社论、重复出版版本。

不得用普通/当前 IF 替代 JCR 的 5 Year JIF，也不得由 IF 数值倒推分区。

### 4.3 双层分类体系

ENT 审计要求每篇非排除记录都有“临床”或“基础/转化”标签；公开站还要求五类研究类型。两者并存：

| 字段 | 值 | 用途 |
| --- | --- | --- |
| `primary_specialty` | rhinology / otology / laryngology / nasopharyngeal_carcinoma | 主专科、首页与周报分组 |
| `evidence_track` | clinical / basic_translational | ENT 审计硬要求 |
| `display_category` | clinical / ai_ml / basic / review_meta / guideline_consensus | 网站筛选、周报展示 |

`AI/ML` 根据研究对象同时标记 `evidence_track`：使用患者临床数据或诊疗结局的归为 clinical；细胞、动物、纯算法或前临床数据归为 basic_translational。综述/Meta 与指南共识通常归为 clinical，但保留独立展示类别。

---

## 5. DeepSeek 调用设计

### 5.1 逐篇分类与翻译

仅向模型提供已经通过质量门禁的：PMID、英文标题、完整英文摘要、期刊质量字段和主题命中信息。

模型只允许返回 JSON：

```json
{
  "primary_specialty": "otology",
  "evidence_track": "clinical",
  "display_category": "clinical",
  "classification_reason": "Relevant: ...",
  "title_zh": "...",
  "abstract_zh": "..."
}
```

约束：

- 必须通读完整摘要；不推测研究中未报告的对象、效应量、安全性或因果结论。
- `title_zh` 与 `abstract_zh` 是翻译，不是改写或总结；摘要章节顺序应与英文原文一致。
- 输出 schema 不合法、PMID 不一致、译文为空或疑似截断则视为失败，不发布该条。
- 记录 `provider`、`model`、`prompt_version`、`generated_at`、token 用量与原始 JSON，便于重跑和审计。

### 5.2 周报“LLM 长篇自动综述”

周报生成只读本期 `include`/`background_trend` 的最终结构化记录，不允许模型访问任意外部网页或自行补检索。

输入按下列维度组织：

```text
鼻科 × 临床 / AI/ML / 基础 / 综述Meta / 指南共识
耳科 × 临床 / AI/ML / 基础 / 综述Meta / 指南共识
咽喉科 × 临床 / AI/ML / 基础 / 综述Meta / 指南共识
鼻咽癌 × 临床 / AI/ML / 基础 / 综述Meta / 指南共识
```

模型返回严格 JSON，而非 HTML。每个段落包含 `markdown` 与 `pmids[]`：

- 每段至少一个 `[PMID:12345678]` 编号引用；仅能引用本期入选集。
- 需要提到设计、样本量、比较者、主要终点、效应方向与安全性时，只能复述摘要实际给出的信息；缺失时写“摘要未报告”。
- 观察性、单中心、单臂、病例报告、模型开发与临床前研究必须明确证据边界。
- 禁止“推荐”“应当使用”“改变临床实践”等诊疗措辞；末段固定说明“综述不构成临床指南”。
- 空分组显示固定“本周无符合条件文献”，不要求模型生成内容。

### 5.3 模型与密钥配置

```dotenv
DEEPSEEK_BASE_URL=https://api.deepseek.com/v1
DEEPSEEK_API_KEY=                 # 仅部署环境保存
DEEPSEEK_MODEL=                   # 由部署时选择可用模型
LLM_TIMEOUT_SECONDS=60
LLM_MAX_CONCURRENT=3
LLM_BATCH_SIZE=10
```

密钥只能进入 `.env` 或宿主机密钥管理，不进入 Git、SQLite snapshot、Markdown、网页、日志或错误消息。每日批量最多 3 个并发请求；失败按指数退避，超过阈值则终止当日发布。

---

## 6. SQLite 数据库

SQLite 适合 MVP 和单机公开站：每日记录量较低、写入只有 cron 单任务、便于备份与审计。开启 WAL，所有写入在事务中完成；将来出现多人编辑或高并发 API 搜索时再迁移 PostgreSQL。

### 6.1 核心表

| 表 | 主键/关键字段 | 说明 |
| --- | --- | --- |
| `articles` | `pmid` | PubMed 原始元数据、标题、完整英文摘要、作者、单位、发表日期 |
| `article_sources` | `pmid + date_type + source_date` | EDAT/PDAT 来源与命中主题块，不混淆来源 |
| `journal_quality` | `pmid` | ISSN、JCR 发布年、分区、5 Year JIF、CAS 状态、匹配证据 |
| `screening` | `pmid` | include/background_trend/exclude、具体理由、主专科、二元证据轨道 |
| `llm_records` | `pmid + prompt_version` | 分类 JSON、中文标题、中文摘要、模型与处理状态 |
| `daily_runs` | `run_id` | 日期、检索式版本、计数、开始/结束、失败原因 |
| `weekly_reports` | `week_start` | 周界、统计、综述 JSON/Markdown、模型版本 |
| `weekly_report_articles` | `week_start + pmid` | 本期报告与文献的不可变关联 |
| `exclusions` | `pmid + run_id` | 每个排除决定及精确原因 |

建议为 `articles(title_en, abstract_en)` 建立 FTS5 虚拟表，作为后续站内搜索的基础；MVP 可不在界面暴露搜索框。

### 6.2 一致性规则

- `articles.pmid` 唯一；重复抓取只能更新来源或补全元数据，不创建第二篇记录。
- 任何 `include`/`background_trend` 都必须有合格 `journal_quality`、完整英文摘要和成功 LLM 记录。
- 周报一旦发布，`weekly_report_articles` 是该期快照；之后补充的记录进入修订版本并记录 `revision`，不静默篡改历史。
- 数据库每日备份为压缩文件；保留至少 30 天，网站 snapshot 保留至少 180 天。

---

## 7. FastAPI 后端

### 7.1 模块布局

```text
api/
  src/ent_weekly/
    main.py
    settings.py
    pubmed/        # query、client、XML parser、日期处理
    quality/       # JCR/CAS matcher
    screening/     # 固定排除规则、LLM 分类校验
    llm/           # DeepSeek client、JSON schema、prompts
    db/             # SQLite schema、repositories、migrations
    pipeline/       # daily.py、weekly.py、snapshots.py
    routers/        # public.py、internal.py、health.py
```

### 7.2 API 边界

| 路由 | 权限 | 作用 |
| --- | --- | --- |
| `GET /api/health` | 公开 | 容器健康检查 |
| `GET /api/articles` | 公开，只读 | 未来动态检索的分页接口；MVP 静态页不依赖它 |
| `GET /api/articles/{pmid}` | 公开，只读 | 单篇结构化记录 |
| `GET /api/reports/{week_start}` | 公开，只读 | 周报结构化数据 |
| `POST /internal/run-daily` | Bearer token，仅 cron 网络 | 指定 EDAT 日期的采集和发布准备 |
| `POST /internal/run-weekly` | Bearer token，仅 cron 网络 | PDAT 回补、周报生成和发布准备 |
| `POST /internal/rebuild` | Bearer token，仅 cron 网络 | 受控历史重跑 |

内部路由必须只在 Docker 内部网络可达，且使用随机 `REGEN_TOKEN`；绝不将它暴露到 Caddy/Nginx 的公网路径。

---

## 8. Astro 前端与公开页面

Astro 负责从 snapshot JSON 静态生成，运行时没有 API Key、数据库连接或 LLM 调用。

| 页面 | 路径 | 内容 |
| --- | --- | --- |
| 全部文献 | `/` | 按 EDAT 日期倒序的卡片；专科 × 五类别双筛选 |
| 专题页 | `/topics/` | 四专科入口及文章列表 |
| 文献详情 | `/article/[pmid]/` | 中英文标题、PMID、作者单位、完整中英摘要、期刊、5 Year JIF、JCR、PubMed 链接、来源日期 |
| 周报索引 | `/weekly/` | 自然周列表、篇数、四专科计数 |
| 单期周报 | `/weekly/[week-start]/` | “专科 × 五类别”DeepSeek 长文、编号引用、参考文献与审计摘要 |
| 期刊目录 | `/journals/` | 已收录期刊的分区与 5 Year JIF，非白名单承诺 |
| 方法与审计 | `/methodology/` | 查询版本、质量规则、每期计数与下载入口 |
| 关于 | `/about/` | 数据、翻译、免责声明与联系方式 |

卡片上展示：中文标题、英文标题、期刊、日期、PMID、主专科、展示分类、5 Year JIF、JCR 分区；不展示 CAS 名单状态或筛选内部理由。详情页保留完整英文摘要原文和中文译文。

---

## 9. Docker、Nginx、Caddy 与 HTTPS

### 9.1 Compose 服务

```text
docker-compose.yml
├─ api    FastAPI + SQLite，暴露给内部网络
├─ cron   supercronic + Node/Astro build，运行每日/每周脚本
├─ web    Nginx，只读提供 Astro dist 与公开 /api 代理（如启用）
└─ caddy  唯一公开入口，80/443、自动 HTTPS、域名重定向
```

### 9.2 持久化卷

| 卷 | 内容 |
| --- | --- |
| `ent_data` | SQLite、备份、JSON snapshot、原始 run 产物 |
| `web_dist` | Astro 构建产物；Nginx 以只读方式挂载 |
| `caddy_data` / `caddy_config` | ACME 证书、账户和 Caddy 配置 |

### 9.3 发布过程

1. cron 调用内部 FastAPI 日/周任务；任务成功后写入 SQLite 和 `snapshots/`。
2. cron 在共享卷上运行 `astro build`，将 `dist/` 原子同步到 `web_dist`。
3. Nginx 立即服务新的静态版本；构建失败则继续服务上一成功版本。
4. Caddy 将 `www` 主域名反代至 Nginx，裸域名 301 跳转到主域名，并自动申请/续期 Let's Encrypt HTTPS 证书。

### 9.4 必需环境变量

```dotenv
TZ=Asia/Shanghai
PUBMED_EMAIL=your-email@example.org
NCBI_API_KEY=
DEEPSEEK_BASE_URL=https://api.deepseek.com/v1
DEEPSEEK_API_KEY=
DEEPSEEK_MODEL=
REGEN_TOKEN=<long-random-token>
DB_PATH=/data/ent_weekly.db
SNAPSHOT_DIR=/data/snapshots
SITE_DOMAIN=example.org
CADDY_EMAIL=ops@example.org
```

`.env` 只存放在服务器上，权限限制为部署用户可读；仓库只提交 `.env.example`。

---

## 10. 定时任务与可靠性

```cron
# Cron 解释为 Asia/Shanghai
0 14 * * *  daily.sh      # 前一完整美东 EDAT 日期
0 10 * * 1  backup.sh     # 先备份 SQLite
0 19 * * 1  weekly.sh     # 上周 EDAT 汇总 + PDAT 回补 + 周报
0 10 * * 1  cleanup.sh    # 清理 180 天前的静态 snapshot（数据库不删）
```

`daily.sh` 与 `weekly.sh` 采用互斥锁；周报任务会等待每日任务结束。每次运行写一条 `daily_runs` 或 `weekly_reports` 状态记录，包含开始/结束、版本、计数和异常摘要。

失败策略：

- PubMed 请求、JCR 数据、DeepSeek 结构化输出或构建失败时，**不发布半成品**。
- 保持上一成功静态版本在线；任务状态写为失败，并保存可诊断日志。
- 支持受保护的手动回填接口，按指定日期或周重跑；历史修订必须有 revision 记录。

---

## 11. 交付顺序

### 第一阶段：可阅读网站

- Astro 主题、双栏阅读布局、首页筛选、详情页、周报页、方法页。
- 使用脱敏样例 snapshot 验证桌面端和手机端阅读体验。

### 第二阶段：可信数据层

- PubMed EDAT 日抓取、XML 解析、SQLite schema、JCR/CAS 门禁、审计日志。
- 接入 DeepSeek 分类与翻译，完成 JSON schema 与失败阻断。

### 第三阶段：周报与发布

- PDAT 周度回补、编号引用校验、长篇中文综述、Markdown 导出。
- Astro snapshot 构建、Docker Compose、Nginx、Caddy、域名和 HTTPS。

### 第四阶段：上线验收

- 选择一个已完成自然周端到端回填。
- 抽样核对 PMID、英文摘要、译文、作者单位、JCR 和 5 Year JIF。
- 验证每段周报引文都存在于本期入选列表，且排除条目不出现在公开页面。
- 验证 14:00 日任务、19:00 周任务、失败回滚、HTTPS、移动端与备份恢复。

---

## 12. MVP 完成标准

当系统连续运行一个完整周后，应能在公开域名提供：每天新增的四专科 PubMed 文献；专科与五类别筛选；每篇可追溯的 PMID、作者单位、双语摘要、5 Year IF、JCR 分区；每周带编号引用与 PubMed 入口的 DeepSeek 中文综述；以及完整的检索、质量、排除和运行审计记录。
