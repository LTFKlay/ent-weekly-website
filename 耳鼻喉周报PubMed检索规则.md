# 耳鼻喉周报 PubMed 检索与分类规则

> 用途：规范耳鼻喉周报从 PubMed 检索、去重、质量筛选、专科归属和审计留痕的流程。覆盖**鼻科、耳科、咽喉科、鼻咽癌（NPC）**四个主题；供手工检索、脚本化抓取和后续智能辅助筛选复用。
>
> 本规则采用**周报**口径：以上一完整自然周为一个批次，兼顾 PubMed 新入库记录与发表日期回补记录。检索式以召回率优先，最终纳入以题名、完整摘要和期刊质量复核为准。

---

## 一、时间范围：完整自然周与双日期来源

### 1.1 核心规则

- 报告周期固定为 `Asia/Shanghai` 时区内**最近一个已结束的自然周**：周一 00:00 至周日 23:59:59。
- 每个主题必须检索两次，并在数据与报告中保留来源标签：
  - **EDAT 主清单**：`[edat]`，本周新进入 PubMed 的记录，是周报监测的主结果；
  - **PDAT 回补清单**：`[pdat]`，发表日期落在本周、但可能较晚才被 PubMed 收录的记录，单独标记为回补，不能与 EDAT 静默合并计数。
- 使用 E-utilities 的 `mindate`、`maxdate` 和明确的 `datetype=edat|pdat`；不使用 `reldate`、`last 7 days` 等滚动窗口。
- EDAT 与 PDAT 均命中的 PMID 只抓取与筛选一次，但保留双重命中标签；周报统计分别报告 EDAT、PDAT 和去重后的候选数。
- 默认在周一北京时间 14:00 之后运行，以保证上一自然周已结束；用户指定周一日期时，以该周一至周日为准。

### 1.2 周期示例

| 执行日（北京时间） | 报告周 | EDAT / PDAT 日期参数 |
|---|---|---|
| 2026-09-14（周一） | 2026-09-07 至 2026-09-13 | `mindate=2026/09/07`，`maxdate=2026/09/13` |
| 2026-09-21（周一） | 2026-09-14 至 2026-09-20 | `mindate=2026/09/14`，`maxdate=2026/09/20` |

### 1.3 通用计算逻辑（Python）

```python
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

def most_recent_completed_week(now: datetime | None = None) -> tuple[date, date]:
    """返回最近完整自然周的周一和周日（Asia/Shanghai）。"""
    if now is None:
        now = datetime.now(ZoneInfo("Asia/Shanghai"))
    else:
        now = now.astimezone(ZoneInfo("Asia/Shanghai"))
    this_monday = now.date() - timedelta(days=now.weekday())
    week_start = this_monday - timedelta(days=7)
    return week_start, week_start + timedelta(days=6)
```

---

## 二、主题分类与单归属

### 2.1 四个主题

| key | 序号 | 专科 / 病种 | 检索覆盖重点 |
|---|---:|---|---|
| `rhinology` | 1 | 鼻科 | 鼻炎、鼻窦炎、鼻息肉、过敏性鼻炎、鼻中隔、鼻整形、鼻-鼻窦肿瘤、内镜鼻窦手术、嗅觉障碍等 |
| `otology` | 2 | 耳科 | 中耳炎、胆脂瘤、耳硬化、听力损失、人工耳蜗、耳鸣、前庭疾病、眩晕、面神经相关耳科疾病等 |
| `laryngology` | 3 | 咽喉科 | 喉与下咽疾病、嗓音与声带、吞咽障碍、气道狭窄、阻塞性睡眠呼吸暂停、头颈良恶性肿瘤（不含 NPC）及相关手术等 |
| `nasopharyngeal_carcinoma` | 4 | 鼻咽癌（NPC） | 鼻咽癌的诊断、分期、放疗、系统治疗、复发转移、预后、分子机制、康复与并发症等 |

> **边界约定**：鼻咽癌即便含鼻部、耳部或咽喉症状，仍优先归入 `nasopharyngeal_carcinoma`。头颈肿瘤中以喉/下咽为主的记录归入 `laryngology`；口腔、牙科、甲状腺和非 ENT 气道疾病不因局部关键词命中而纳入。

### 2.2 单归属约束

- 每篇文献输出一个且仅一个 `primary_specialty`。
- 多主题检索同时命中时，以研究对象、主要结局和文章题名/摘要中的中心问题决定主归属，而非以第一个命中的检索式决定。
- 主病种为 NPC 的研究始终优先归入 NPC；涉及耳鼻喉多个亚专科的综合性研究，可按主要临床问题归类，无法确定时进入人工复核而不是重复展示。

### 2.3 研究类别（用于呈现与筛选）

每篇非排除记录再分为一类，优先级以研究实际设计为准：

| key | 类别 | 典型范围 / PubMed 线索 |
|---|---|---|
| `clinical` | 临床研究 | 人体原创研究、随机试验、队列、病例对照、诊断/预测模型验证、真实世界研究 |
| `ai_ml` | 人工智能与数字医学 | 影像、内镜、语音/听觉信号或临床数据的 AI/ML 模型开发、验证与外部验证 |
| `basic_translational` | 基础与转化研究 | 动物、细胞、类器官、组学、分子机制和非患者转化研究 |
| `review` | 证据综述 | 系统综述、Meta 分析、范围综述和重要叙述性综述 |
| `guideline` | 指南与共识 | 实践指南、临床共识、立场文件、循证建议 |

> 若项目只需要二分标签，可将 `clinical`、`ai_ml`、`review`、`guideline` 合并为“临床”，将 `basic_translational` 保持为“基础/转化”；原始 `article_category` 与细分 `research_type` 都应保留，避免丢失审计信息。

---

## 三、检索式：主题块与全局排除

### 3.1 设计原则

- 每个主题块均由 MeSH 受控词和题名/摘要自由词组成；新近收录记录可能尚未完成 MeSH 标引，因此不得只依赖 MeSH。
- 不使用单独的 `ENT`、`NPC`、`OSA`、`HL`、`CI` 等高歧义缩写；如需使用缩写，必须与全称或解剖部位组合。
- 检索式不预先限制语言、研究类型或期刊白名单，以降低遗漏风险；期刊与研究类型在抓取后筛选。
- 以下表达式的方括号字段遵循 PubMed 语法：`[mh]` 为 MeSH，`[tiab]` 为题名/摘要，`[pdat]`/`[edat]` 为日期来源。

### 3.2 鼻科主题块：`rhinology`

```text
(
  Rhinitis[mh] OR Sinusitis[mh] OR Nasal Polyps[mh] OR Paranasal Sinuses[mh]
  OR Nasal Obstruction[mh] OR Olfaction Disorders[mh]
  OR rhinitis[tiab] OR "allergic rhinitis"[tiab]
  OR rhinosinusitis[tiab] OR sinusitis[tiab]
  OR "chronic rhinosinusitis"[tiab] OR "nasal polyp*"[tiab]
  OR "paranasal sinus*"[tiab] OR "nasal obstruction"[tiab]
  OR septoplast*[tiab] OR rhinoplast*[tiab]
  OR "endoscopic sinus surgery"[tiab] OR FESS[tiab]
  OR "olfactory dysfunction"[tiab] OR anosmia[tiab] OR hyposmia[tiab]
  OR "nasal tumor*"[tiab] OR "sinonasal tumor*"[tiab]
)
```

### 3.3 耳科主题块：`otology`

```text
(
  Ear Diseases[mh] OR Hearing Loss[mh] OR Otitis Media[mh]
  OR Cochlear Implants[mh] OR Vestibular Diseases[mh]
  OR Tinnitus[mh] OR Cholesteatoma[mh] OR Otosclerosis[mh]
  OR otolog*[tiab] OR otitis[tiab] OR "otitis media"[tiab]
  OR "hearing loss"[tiab] OR deafness[tiab] OR "sensorineural hearing loss"[tiab]
  OR cochlear implant*[tiab] OR cholesteatoma[tiab] OR otosclerosis[tiab]
  OR tinnitus[tiab] OR vertigo[tiab] OR vestibular[tiab]
  OR "Meniere disease"[tiab] OR "Ménière disease"[tiab]
  OR "temporal bone"[tiab] OR tympanoplast*[tiab] OR mastoidectom*[tiab]
)
```

### 3.4 咽喉科主题块：`laryngology`

```text
(
  Laryngeal Diseases[mh] OR Voice Disorders[mh] OR Laryngectomy[mh]
  OR Deglutition Disorders[mh] OR Sleep Apnea, Obstructive[mh]
  OR Laryngeal Neoplasms[mh] OR Hypopharyngeal Neoplasms[mh]
  OR laryng*[tiab] OR "laryngeal cancer"[tiab] OR "laryngeal neoplasm*"[tiab]
  OR "hypopharyngeal cancer"[tiab] OR "hypopharyngeal neoplasm*"[tiab]
  OR dysphonia[tiab] OR "voice disorder*"[tiab] OR "vocal fold*"[tiab]
  OR "vocal cord*"[tiab] OR dysphagia[tiab] OR swallowing[tiab]
  OR "airway stenosis"[tiab] OR "laryngotracheal stenosis"[tiab]
  OR "obstructive sleep apnea"[tiab] OR "sleep-disordered breathing"[tiab]
  OR tonsillectom*[tiab] OR adenoidectom*[tiab]
)
```

> `voice[tiab]`、`throat[tiab]` 等过宽词不单独使用；它们容易引入神经科学、语言学、消化科和非 ENT 记录。儿童腺样体/扁桃体、OSA 与吞咽研究应由题名和摘要复筛，排除牙科、神经科或非 ENT 假阳性。

### 3.5 鼻咽癌主题块：`nasopharyngeal_carcinoma`

```text
(
  Nasopharyngeal Neoplasms[mh]
  OR "nasopharyngeal carcinoma"[tiab]
  OR "nasopharyngeal cancer"[tiab]
  OR "nasopharyngeal neoplasm*"[tiab]
  OR "nasopharyngeal tumor*"[tiab]
  OR (nasopharyn*[tiab] AND (carcinoma*[tiab] OR cancer*[tiab] OR neoplasm*[tiab]))
  OR (("nasopharyngeal carcinoma"[tiab] OR nasopharyn*[tiab]) AND (EBV[tiab] OR "Epstein-Barr virus"[tiab]))
)
```

> 不使用裸词 `NPC[tiab]`，以免将与鼻咽癌无关的缩写混入。以 EBV 为主题但未明确鼻咽癌的论文不得自动纳入。

### 3.6 全局中医药排除块

以下块应附加于每一个主题检索式之外，作为第一层降噪；题名与摘要复筛仍须保留中医药排除判断。

```text
NOT (
  "traditional Chinese medicine"[tiab]
  OR "chinese medicine"[tiab]
  OR "Chinese herbal medicine"[tiab]
  OR "chinese herbal preparation*"[tiab]
  OR acupuncture[tiab] OR electroacupuncture[tiab]
  OR moxibustion[tiab] OR tuina[tiab] OR cupping[tiab]
  OR "Chinese patent medicine"[tiab] OR TCM[tiab]
)
```

### 3.7 每周最终检索式模板

对每个主题 `topic_query` 分别以 `EDAT` 和 `PDAT` 运行：

```text
(
  ( <topic_query> )
  AND <YYYY/MM/DD:YYYY/MM/DD[edat]>
)
NOT ( <global_tcm_exclusion> )
```

PDAT 回补仅将日期字段替换为 `[pdat]`：

```text
(
  ( <topic_query> )
  AND <YYYY/MM/DD:YYYY/MM/DD[pdat]>
)
NOT ( <global_tcm_exclusion> )
```

示例：检索 2026-09-07 至 2026-09-13 的鼻咽癌 EDAT 主清单：

```text
(
  (
    Nasopharyngeal Neoplasms[mh]
    OR "nasopharyngeal carcinoma"[tiab]
    OR "nasopharyngeal cancer"[tiab]
    OR "nasopharyngeal neoplasm*"[tiab]
    OR "nasopharyngeal tumor*"[tiab]
    OR (nasopharyn*[tiab] AND (carcinoma*[tiab] OR cancer*[tiab] OR neoplasm*[tiab]))
  )
  AND 2026/09/07:2026/09/13[edat]
)
NOT ("traditional Chinese medicine"[tiab] OR acupuncture[tiab] OR moxibustion[tiab] OR tuina[tiab] OR cupping[tiab] OR "Chinese herbal medicine"[tiab])
```

---

## 四、期刊质量门槛与筛选规则

### 4.1 质量门槛

- 先用本地、可审计的 **2026 JCR** 数据匹配期刊，再阅读摘要筛选；影响因子只记录 JCR 数据表中的 **5 Year JIF**。
- 排除所有 JCR Q4 期刊和 2025 年中国科学院预警期刊名单中的期刊。
- 期刊无法可靠匹配、名称存在歧义或缺失质量数据时，排除而非猜测分区。
- 不采用预置期刊白名单截断检索。先检索、后质量门控可保留新刊及跨学科高质量期刊，同时让排除原因可追溯。

### 4.2 摘要复筛：纳入与背景/趋势

通过期刊质量门槛后，必须阅读完整题名和 PubMed 完整摘要，并作出唯一决定：

| 决定 | 适用情形 | 审计理由格式 |
|---|---|---|
| `include` | 直接相关的原创研究、指南或系统综述，且有明确临床/科学价值 | `Relevant: <一句话说明价值>` |
| `background/trend` | 主题相关但证据间接、方法/方案论文、叙述性综述或优先级较低的趋势信号 | `Relevant context: <一句话说明价值>` |
| `exclude` | 不相关、质量门槛不通过、不能形成证据卡片或关键信息不足 | `Exclude: <具体原因>` |

### 4.3 必须排除的情形

- 中医药相关干预或理论框架；理由：`Exclude: traditional Chinese medicine-related intervention or framework.`
- 非耳鼻喉语境的关键词命中，包括牙科、口腔颌面、纯工程/影像方法、非 ENT 气道或非人类语境。
- 勘误、纯社论、新闻、读者来信、重复发表版本、无原始数据的评论。
- 仅提及耳鼻喉疾病，但主要对象、研究问题或主要结局不属于四个主题。
- 无 PubMed 摘要，或摘要信息不足以制作所需证据卡片；理由：`Exclude: abstract unavailable for requested card format.`
- NPC 以外的 EBV 研究、非鼻咽部头颈肿瘤，除非鼻咽癌是明确主研究对象。

### 4.4 临床解读边界

- 每项拟纳入临床研究应核对摘要是否报告比较对象、研究人群、患者重要结局、效应方向、时间窗和安全性信息。
- 生物标志物、替代终点、横断面关联或统计学显著性本身不等同于临床获益。
- 周报可提示证据信号，但不得把单篇摘要、观察性研究或未经全文核实的结论表述为改变临床实践的建议。

---

## 五、检索、去重与智能辅助分类流程

```text
确定上一完整自然周（周一至周日，Asia/Shanghai）
        ↓
4 个主题 × 2 个日期来源（EDAT 主清单、PDAT 回补）运行 esearch
        ↓
按 PMID 合并去重，保留 topic_matches 与 date_type_matches
        ↓
efetch 获取 PubMed XML：题名、摘要、作者、机构、期刊、日期、PubType、DOI
        ↓
JCR Q4 / CAS 预警 / 期刊无法匹配 → 自动排除并留痕
        ↓
阅读题名与完整摘要：确定 include / background/trend / exclude
        ↓
LLM 辅助建议主专科、细分研究类别和中文翻译；人工规则可复核、可覆盖
        ↓
按四专科输出周报卡片与排除审计表
```

### 5.1 LLM 辅助分类约束

- LLM 仅辅助分类、翻译和生成候选排除理由；最终筛选必须能由原始题名、摘要、期刊质量信息复核。
- 每条记录输出一个 `primary_specialty`、一个 `research_type`、一个 `decision` 和一个具体理由。
- 多标签候选必须按单归属规则选定主专科；不确定时标记 `needs_review=true`，不得自动重复发布。
- 模型临时不可用时，使用主题命中来源与 PubType 进行启发式降级，并将 `llm_needs_review=true`；不得伪造中文摘要或临床结论。

建议的单篇结构化输出：

```json
{
  "pmid": "39012345",
  "primary_specialty": "nasopharyngeal_carcinoma",
  "research_type": "clinical",
  "article_category": "clinical",
  "decision": "include",
  "reason": "Relevant: reports survival and toxicity outcomes for a defined NPC population.",
  "title_zh": "中文标题（保留必要英文专有名词）",
  "abstract_zh": "中文摘要（仅在原始英文摘要完整可得时翻译）",
  "needs_review": false
}
```

---

## 六、NCBI E-utilities 调用规范

| 端点 | 用途 | 关键参数 |
|---|---|---|
| `esearch.fcgi` | 执行每个主题与日期来源的检索，返回 PMID | `db=pubmed`、`term`、`datetype`、`mindate`、`maxdate`、`retmode=json`、`retmax` |
| `efetch.fcgi` | 批量获取文章元数据与摘要 XML | `db=pubmed`、`id`、`retmode=xml` |

实施要求：

- 请求附带 NCBI `tool` 和可联系的 `email`；API key 仅从环境变量 `NCBI_API_KEY` 读取，不写入报告、日志或仓库。
- 无 API key 时限速不高于 3 次/秒（建议间隔 0.34 秒）；有 key 时不高于 10 次/秒（建议间隔 0.10 秒）。
- `esearch` 的 `retmax` 建议不高于 500；`efetch` 建议每批不超过 200 个 PMID，大批量 UID 使用 POST。
- 保存每次运行的完整检索式、日期参数、主题命中、日期来源、PMID 列表、请求时间和失败信息，形成 JSON manifest。
- PubMed XML 仅用于元数据和摘要；不得以此规则批量抓取期刊全文。

### 6.1 伪代码

```python
TOPICS = {"rhinology": RHINOLOGY, "otology": OTOLOGY,
          "laryngology": LARYNGOLOGY, "nasopharyngeal_carcinoma": NPC}
DATE_TYPES = ("edat", "pdat")

week_start, week_end = most_recent_completed_week()
hits = {}
for topic_key, topic_query in TOPICS.items():
    for date_type in DATE_TYPES:
        term = f"({topic_query} AND {week_start:%Y/%m/%d}:{week_end:%Y/%m/%d}[{date_type}]) NOT ({TCM_EXCLUSION})"
        hits[topic_key, date_type] = esearch(term=term)

pmid_provenance = merge_pmids_keep_all_matches(hits)
records = efetch_in_batches(pmid_provenance.keys(), batch_size=200)
quality_checked = apply_journal_quality_gate(records)
screened = screen_title_and_full_abstract(quality_checked, pmid_provenance)
write_manifest_and_weekly_report(screened)
```

---

## 七、数据字段与输出审计

### 7.1 每条候选记录最少字段

| 字段 | 说明 |
|---|---|
| `pmid` | PubMed ID，主键 |
| `topic_matches` | 命中的一个或多个检索主题 |
| `date_type_matches` | `edat`、`pdat` 或二者均命中 |
| `title` / `abstract` | PubMed 原始题名与完整摘要 |
| `journal` / `journal_abbr` | 期刊匹配所需名称 |
| `publication_date` / `edat` | 发表日期与入库日期，均保留 |
| `authors` / `affiliations` / `doi` / `publication_types` | 证据卡片与复核元数据 |
| `jcr_quartile` / `five_year_jif` | 质量门槛与展示所用指标 |
| `primary_specialty` / `research_type` | 单归属专科与细分类别 |
| `decision` / `reason` | 唯一筛选决定及具体理由 |

### 7.2 周报固定结构

1. `## 1. Retrieval and quality audit`：报告周、时区、检索时间、查询版本、各主题 EDAT/PDAT 命中数、去重数、质量门槛和筛选统计。
2. `## 2. 文献卡片`：按鼻科、耳科、咽喉科、鼻咽癌分组；每张非排除卡片应在同一信息表中列出期刊、PMID、原文链接、发表日期、作者、作者单位、SCI 分区、5 年影响因子、研究类型和所属专科。
3. `## 3. Exclusion log`：记录每条排除文献的 PMID、题名、期刊、主题命中来源和具体排除原因；不在面向普通读者的卡片区展示。

非排除记录的证据卡片应嵌入完整 PubMed 原始摘要，保持原语言与原始小节顺序；无完整摘要的记录按本规则排除。

---

## 八、不变量与版本维护

1. 报告周期为上一完整自然周（`Asia/Shanghai`），不使用含当前未结束日期的滚动周。
2. 每周均运行 EDAT 主清单和 PDAT 回补清单，并显式标注来源，禁止静默混合计数。
3. 固定覆盖鼻科、耳科、咽喉科和鼻咽癌四个主题；每篇仅有一个最终主专科归属。
4. 主题块追求召回率；题名、完整摘要与期刊质量门槛决定最终纳入，不能以检索词替代人工/可审计筛选。
5. 排除中医药相关记录，并保留具体排除理由。
6. 仅纳入通过期刊质量门槛的记录；JCR Q4、CAS 预警及无法可靠匹配期刊均排除。
7. 不得以临床重要性替代证据强度；摘要层面的单篇研究不构成临床实践建议。
8. 修改任一主题检索式、排除词或质量门槛时，必须递增 `query_version`，在后续周报审计区说明修改原因；不同版本的计数不得直接比较。

### 修订记录

| 版本 | 日期 | 变更 |
|---|---|---|
| v1 | 2026-09-17 | 初版：建立鼻科、耳科、咽喉科与鼻咽癌四主题的周报检索、双日期来源、质量门槛和审计规范。 |

