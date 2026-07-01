# WAIC Active Grounding Demo

展示认知基模的核心能力：**精准视觉定位 (Grounding)**、**智能信息空间导航 (Computer Use)** 与 **跨页面信息整合 (Information Synthesis)**。

## 场景

### 一眼定位 (Grounding)

在一张高密度运维监控 Dashboard 上，通过递进式自然语言提问，模型精准框出答案位置。

### 认知导航 (Navigation)

在 6 个页面组成的 SaaS 管理后台中，模型以安全审计员身份自主选路、主动跳过无关内容。

### 股票寻宝 (Stock Intelligence)

在 5 个模拟金融数据中心页面（新股申购总览 / 科创板新股 / 连续上涨 / 持续放量 / 量价齐升，虚拟品牌 "FinData"，不含任何真实平台商标）中，模型针对复合投资问题自主排序、筛选、跨页整合，最终给出结构化答案。页面素材使用完全虚构的公司与行情数据，不代表任何真实上市公司信息。

## 快速开始

### 1. 渲染素材

```bash
cd backend
uv sync --extra render
uv run playwright install chromium
uv run python tools/render.py
```

### 2. 启动后端

```bash
cd backend
cp .env.example .env  # 编辑填入 API Key
uv sync
uv run uvicorn src.server:app --reload --port 8000
```

### 3. 启动前端

```bash
cd frontend
pnpm install
pnpm dev
```

打开 http://localhost:5173 即可看到 Demo。

## 技术栈

- **后端**: Python, FastAPI, WebSocket, OpenAI-compatible VLM API
- **前端**: Vue 3, TypeScript, Vite
- **素材**: HTML → Playwright → PNG + manifest JSON
