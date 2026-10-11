# markjin 工作流

## 六个阶段
1. **收集 collect**：每日 05:00 与 06:00 (SGT) 抓取 arXiv、FRED、X（2026-10-12 起，与路线图一致）；原始数据逐字节存入 `markjin-data/raw/YYYY-MM-DD/`，sha256 记入 manifest。
2. **消化 digest**：抽取要点，写入 `markjin-data/digest/`，每条要点保留来源链接。
3. **生产 produce**：生成中文每日信号与专题草稿。
4. **发布 publish**：合入本仓库 `content/`，Actions 自动部署。
5. **反馈 feedback**：读者通过 Issues（`feedback` 标签）/ 评论反馈（联系方式不对外公开，2026-10-12 起不再列邮箱）。
6. **改进 improve**：改进提案以 `proposal` 标签提交，审核后标 `approved` / `rejected`。

## Bot 角色
| Bot | 职责 |
|---|---|
| markjin 采集 | 05:00、06:00 SGT 收集；原始数据逐字节存档 |
| markjin 生产与发布 | 撰写中文稿件；只发布通过审查门禁的稿件（依据 t161u：每日信号每天都须经 Codex 审查，只需 Codex 批准，没有低风险自动批准；宏观（macro）、统一系统观（tongyi）、信号卡（signal card）须 Codex 批准并另经王总批准；每个 `*.en.md` 都须单独取得 Codex APPROVED。稿件只认结论 APPROVED，仅有结论不算通过；APPROVED_WITH_FOLLOWUPS 只用于规划文件） |
| markjin 审查与治理 | 脚本负责格式与词表门禁；脚本不批准任何稿件。完整门禁要等发布门禁在新仓库重新落地后才有；在那之前，日报发布的依据是审查与治理 bot 人工核对新 markjin-data main 上的 Codex 记录（核对日期、06:55 截止和中英配对），宏观稿和信号卡另外还要王总批准 |
| markjin 反馈与改进 | 整理反馈与改进提案 |
| Grok Bot 协调 | 每日健康摘要、周日复盘、维护 CHANGELOG |

各角色与门禁的完整规则以 docs/roadmap.md 为准。

来源图片规则见 [docs/images.md](images.md)（依据王总 t172u，由 Grok Bot 制定具体规则；自 2026-10-12 的每日信号起适用）。
