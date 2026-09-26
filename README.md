# ENT Weekly

耳鼻喉科高质量 PubMed 文献日追踪与周报系统。

## 系统边界

- 每天北京时间 14:00 以 PubMed EDAT 追踪前一完整美东入库日。
- 每周一 19:00 合并上周 EDAT 记录与 PDAT 回补，生成带 PMID 引文的中文周报。
- 主数据流固定为：PubMed `EDAT` 新入库记录 → DeepSeek 结构化分类与中英翻译 → SQLite → snapshot JSON → Astro 静态站。
- JCR Q4、2025 CAS 预警、无摘要、期刊质量无法验证和中医药相关记录保留为可审计的规则结果；不符合公开条件的记录不进入站点列表或周报。
- DeepSeek 用于结构化分类、中英翻译和周报综述；英文 PubMed 摘要优先。

## 本地准备

1. 复制 `.env.example` 为 `.env`，填写 PubMed 邮箱、DeepSeek 配置和内部任务令牌。
2. 将已授权的 JCR/CAS 质量数据导出为 `data/journal-quality.json`。未找到可靠质量记录时，系统按“无法验证”排除而不猜测。
3. 在 `web/` 安装依赖后运行 `npm run dev`，或使用 Docker Compose 启动完整环境。

## 规则更新后的历史文献重筛

本地只发布页面模板、检索规则与后端代码；服务器的 `ent_data` 卷是唯一的抓取、筛选、快照与线上数据来源。`data/ent_weekly.db`、日/周快照均不提交 Git。检索或筛选规则升级后，已写入该数据卷的历史文献不会因 `git pull` 自动重判。

在服务器的 `/opt/ent-weekly` 中按以下顺序执行；命令不会删除数据库、快照或 Docker 数据卷。

```sh
# 常规代码发布：重建服务镜像与静态站点
git pull
sh scripts/deploy_server.sh

# 规则更新发布：额外全量重筛历史文献并重建已有周报
git pull
sh scripts/deploy_server.sh --rescreen

# 验证已排除文献不在 Nginx 静态目录中
docker compose exec web sh -lc 'grep -R "Balance Wood" /usr/share/nginx/html || true'
```

重筛会保留历史 LLM 审计记录，并在快照审计字段中写入本次重筛元数据；LLM 临时失败的记录会保留旧公开状态并计入 `errors`。建议先用 `--limit 20 --apply --reclassify --refresh-weekly` 验证输出。服务器每日任务会继续抓取并按当前筛选策略版本重新判定候选文献。

详细的数据规则见 [ENT-每日追踪与周报生产方案.md](./ENT-每日追踪与周报生产方案.md)。
