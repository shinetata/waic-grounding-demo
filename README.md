# WAIC Active Grounding Demo

展示认知基模的核心能力：**精准视觉定位 (Grounding)**、**智能信息空间导航 (Computer Use)** 与 **跨页面信息整合 (Information Synthesis)**。

> 本仓库包含两个互相独立的 Demo：下面的 `backend/`+`frontend/`（静态截图三场景），以及
> [`web/`](web/README.md)（Mactive 股市探索，真实浏览器交互，见文末单独一节）。两者不共享代码、
> 依赖或端口，可以只启动其中一个。

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

---

## 独立 Demo：Mactive 股市探索（真实浏览器交互）

`web/` 目录下是一个完全独立的项目（不依赖、不共享上面这套 `backend/`/`frontend/` 的任何代码或端口），
用一个真实运行的 Playwright 浏览器会话取代静态截图：模型对"新股申购"/"行情排行"两个真实可交互的
模拟金融页面进行真实的点击排序、真实的条件筛选、真实的页面跳转，每一步都在当前的真实截图上画出
精确的 grounding bbox。

```bash
cd web
./dev.sh
```

打开 http://localhost:5183 即可看到。完整架构说明、手动启动步骤、排障见 [`web/README.md`](web/README.md)。
