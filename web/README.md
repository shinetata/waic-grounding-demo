# Mactive 股市探索 — 真实浏览器交互 Demo

一个完全独立的 demo（不依赖、不共享 `../backend`/`../frontend` 的任何代码或端口），
展示 Mactive 基模的**多模态 grounding 精准定位**能力——但底层不再是预先渲染的静态截图，
而是一个真实运行的浏览器会话：Mactive 会真实点击表头排序、真实点击标签/条件筛选、
真实点击导航链接，模型每一步看到的都是live截图。

## 场景：股市探索

两个真实可交互的模拟金融数据页面（虚构品牌 "FinData"，不含任何真实平台商标，数据均为
模拟演示数据）：

- **新股申购**（`ipo-subscribe`）：全市场新股申购信息，可按板块（科创板/创业板/...）
  真实筛选，可按发行价格/市盈率/申购日期等列真实排序。
- **行情排行**（`market-ranking`）：技术选股候选池，可组合"连涨天数"/"放量天数"两个
  条件真实筛选，可按涨跌幅/换手率等列真实排序。

Mactive 针对 3 道跨页面、需要筛选+排序才能回答的复合投资问题自主决策，每一步动作
都会在当前的真实截图上画出精确的 bbox。

## 架构

```
web/backend/   FastAPI + uv，owns 一个共享的 Playwright Chromium 浏览器进程；
               每个 WebSocket 连接拿到独立的 browser context/page
  site/        真实可运行的 HTML+JS+CSS 页面（唯一的素材来源，没有预渲染 PNG）
  src/env/     BrowserEnv：reset/navigate/sort_by/apply_filter/element_rect
               全部是对真实页面的真实操作，坐标全部实时查询
  src/agent/   policy.py（调用 VLM）、stock_prompts.py（系统提示词）、
               loop.py（run_stock 主循环）
  src/scenes/  stock.py：页面/题目/ground-truth/hint 映射的唯一权威来源
web/frontend/  Vue 3 + TypeScript + Vite，单场景 UI
```

## 快速开始

```bash
./dev.sh
```

或手动启动：

```bash
# 后端
cd backend
uv sync
uv run playwright install chromium
cp .env.example .env   # 编辑填入 API Key
uv run uvicorn src.server:app --reload --port 8010

# 前端
cd frontend
pnpm install
pnpm dev
```

打开 http://localhost:5183 即可看到 demo。

## 排障

- 如果 `playwright install chromium` 因网络受限下载失败，但 `../backend` 的 Playwright
  Chromium 已经装过（`~/Library/Caches/ms-playwright/chromium-*`），可以不装
  headless-shell：`src/server.py` 里浏览器启动已经带上了 `channel="chromium"`，会直接复用
  常规 Chromium 构建跑 headless 模式，不需要额外下载新版 headless-shell 二进制。

## 技术栈

- **后端**: Python, FastAPI, WebSocket, Playwright（真实浏览器会话）, OpenAI-compatible VLM API
- **前端**: Vue 3, TypeScript, Vite
- **素材**: 纯 HTML + 原生 JS + CSS，真实可点击/可排序/可筛选，由 FastAPI `StaticFiles` 直接
  serve，没有任何预渲染步骤
