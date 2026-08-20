# 贡献指南

欢迎对本项目的文档与代码提出建议与改进。本仓库遵循"一条任务 = 一次清晰的改动"的轻量协作方式。

## 开发环境

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env          # 填入 LLM 凭证（勿提交 .env）
```

文档站本地预览：

```bash
cd docs
npm install
npm run docs:dev              # 默认 http://localhost:5173（本地用 DOCS_BASE=/ 可根路径预览）
```

构建静态产物：

```bash
cd docs
npm run docs:build            # 输出 docs/.vitepress/dist
```

## 文档约定

- 文档源位于 `docs/`，使用 Markdown + VitePress；
- 新增页面请在 `docs/.vitepress/config.ts` 的 `sidebar` 中登记；
- 中文文档为主，代码标识符保留英文；
- 涉及参数 / API 的改动，请同步更新 `docs/api/` 与 `docs/guide/configuration.md`，保持与代码一致；
- 首页与 `.vitepress/config.ts` 中 `base` 固定为 `/AgriPolicy-Sandbox/`（GitHub Pages 项目站点基路径）。

## 代码约定

- **解耦优先**：核算逻辑放 `economics.py`（零平台依赖），参数放 `configs/*.json`，环境工具放 `agri_policy_env.py`；
- **可单测**：`economics.py` 纯函数必须有单测（`tests/test_economics.py`）；
- **可标定**：新参数尽量走 `configs/economics.json`，避免写死在代码里；
- **可复现**：涉及随机性处使用 `seed`，并记录到 `run_meta.json`。

## 提交信息

- 使用简洁的英文或中文祈使句标题（如 `docs: 补充回放数据表说明`）；
- 一次提交聚焦一个主题；涉及文档与 CI 的改动可分开提交。

## 问题反馈

请在 GitHub 仓库提交 Issue 或 PR：[Maicarons/AgriPolicy-Sandbox](https://github.com/Maicarons/AgriPolicy-Sandbox)。
