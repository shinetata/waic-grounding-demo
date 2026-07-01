# AGENTS.md

面向在本仓库工作的 AI agent 的说明文档。

## 这是什么项目

这个仓库里有**两个互相独立、不共享代码/依赖/端口**的 Demo：

1. **`backend/` + `frontend/`**（本节主要描述的对象）：从更大的 `WAIC/waic-demo` monorepo 中
   拆分出来，用一个 Vue 前端 + 一个 FastAPI 后端，展示视觉语言 "computer use" agent 的三项能力，
   每项能力都是一个独立可播放的场景：

   | 场景 | 后端模块 | 前端组件 | 展示内容 |
   |---|---|---|---|
   | 一眼定位 (Grounding) | `backend/src/scenes/grounding.py` | `frontend/src/scenes/GroundingScene.vue` | 在一张高密度 Dashboard 截图上，针对递进难度的问题做精准 bbox 定位 |
   | 认知导航 (Navigation) | `backend/src/scenes/navigation.py` | `frontend/src/scenes/NavigationScene.vue` | 以安全审计员身份，在 6 页 SaaS 管理后台中自主选路（访问/跳过） |
   | 股票寻宝 (Stock Intelligence) | `backend/src/scenes/stock.py` | `frontend/src/scenes/StockScene.vue` | 跨页面信息整合：在 5 个模拟金融数据中心页面中 navigate/filter/sort/extract，回答复合投资问题 |

   没有真实的后端数据源——每个"页面"都是手工编写的 HTML 模拟页面，渲染成静态 PNG。模型从不接触
   真实数据，它看到的永远只是截图。

2. **`web/`**：一个完全独立的新 Demo——"Mactive 股市探索"，用真实运行的浏览器会话（Playwright）
   取代静态截图，模型的排序/筛选/导航都是对真实网页的真实点击。详见下面的
   [`web/`：Mactive 股市探索](#web-mactive-股市探索真实浏览器交互-demo) 一节，完整说明在
   [`web/README.md`](web/README.md)。

## 技术栈与目录结构

```
backend/    Python ≥3.10，FastAPI + WebSocket，uv 管理依赖，OpenAI 兼容的 VLM 客户端
  src/agent/     policy.py（调用 VLM）、prompts.py + stock_prompts.py（系统提示词）、loop.py（各场景的 agent 循环）
  src/scenes/    每个场景一个加载模块——定义页面、queries 及场景专属配置
  src/env/       ScreenshotEnv：共享的多页面"环境"（在静态图片上 navigate/see/zoom）
  assets/site/   手工编写的 HTML 模拟页面（图片的唯一真实来源）
  assets/pages/  渲染出的 PNG 截图（生成产物，*.png 已在 .gitignore 中，但早期提交里有几张仍被跟踪——不要默认工作区一定是干净的）
  assets/manifests/  每个页面对应的 JSON：渲染时提取的关键元素精确像素坐标
  tools/render.py   Playwright：HTML -> PNG + manifest。PAGES 注册表的唯一权威来源。
frontend/   Vue 3 + TypeScript + Vite
  src/scenes/       每个场景一个 *.vue，负责把 WebSocket 事件流编排成本地状态
  src/components/   与场景无关的通用 UI：ScreenshotView/BoundingBox（渲染）、ThoughtStream/
                     EvidencePanel（推理日志）、PageMap/SceneProgress（导航状态）
  src/composables/  useWebSocket.ts（事件流）、useAutoPlay.ts
```

## 常用命令

```bash
# 一键启动：安装依赖、渲染截图、启动前后端
./dev.sh

# 手动启动 — 后端
cd backend && uv sync --extra render && uv run playwright install chromium
uv run python tools/render.py            # 编辑 assets/site/*.html 后需要重新渲染
uv run uvicorn src.server:app --reload --port 8000

# 手动启动 — 前端
cd frontend && pnpm install && pnpm dev   # http://localhost:5173

# 前端类型检查（tsconfig.node.json 存在一个与本项目无关的历史遗留
# TS5096 报错，`vue-tsc -b` 会触发它；请只检查 app 项目本身）：
npx vue-tsc --noEmit -p tsconfig.json
```

**启动开发服务器前**，先检查 `terminals/` 文件夹或正在运行的进程——`dev.sh` 或手动起的
`uvicorn --reload` / `pnpm dev` 很可能已经在之前的会话里跑起来了（端口 8000/5173，若被占用会
回退到 5174）。复用已有的服务更快，也能避免端口冲突的困惑；`--reload` 和 Vite HMR 会自动应用
文件改动。

## 架构：一个场景是如何跑起来的

1. 前端调用 `connect(sceneName)` → 打开 `ws://.../ws/run?scene={name}`。
2. `server.py` 加载对应场景（`load_*_scene()` → `(stages, queries|task)`），构建 `ScreenshotEnv`，
   运行 `agent/loop.py` 里匹配的 `run_*()` 生成器。
3. 每一轮循环：构建多模态消息（缩略图 + 可选的局部放大裁剪图 + 轨迹摘要）→ `call_vlm()` → 解析
   模型返回的严格 JSON 动作 → 作用到 env 上 → yield 一个 `step` 事件。前端持续累积事件并做响应式
   渲染；服务端除当前这一次运行外不做任何缓存。
4. 运行结束后，`_save_fallback()` 会把整次运行写入 `assets/fallbacks/{scene}.json`，
   `/api/fallback/{scene}` 可以回放它——**注意：目前没有任何前端代码调用这个接口**，它已经存在但
   没接上，不要误以为它被用作实时失败兜底。

### 坐标系统

所有面向模型的 bbox 都是 **[0,1000] 整数空间**下的 `[x1,y1,x2,y2]`；`loop.py` 里的
`_normalize_bbox()` 会转换成 `[0,1]` 浮点数（并且把面积接近零的框视为无效，回退成整图）。
`ScreenshotView.vue` 在定位覆盖层之前，会考虑 `object-fit: contain` 产生的留白，计算出图片实际
渲染的矩形区域——这是一个真实出现过、已经修复的坑；不要退回到忽略留白、直接按容器百分比计算坐标
的写法。

### Grounding 精度 vs. 叙事性动作 —— 一个重要的区分

不是模型的每一个动作都有唯一客观正确的框。指向**具体存在的内容**（某个数字、某一行、某条告警）
的动作是真正的 grounding 任务——应该信任模型自己给出的坐标（可以搭配一层基于 ground truth 的校验
兜底，参见 `stock.py` 的 `QUERY_CLUES` / `loop.py` 的 `_validate_and_snap_answer`）。而要求模型指出
一个**抽象/过程性概念**的动作（比如股票场景里的 `sort`：「我正在参考的这一列」）根本没有唯一正确
答案，VLM 手绘的框必然显得不精准、发飘。对这类动作，应该吸附到页面 manifest 里已知正确的坐标
（参见 `scenes/stock.py` 的 `COLUMN_HINTS`），而不是试图靠提示词把模型调教到能像素级精确地指出一
个抽象概念——它只是用来叙述模型推理过程的 UI 呈现手段，不是 grounding 能力的考核点。

### 新增一个场景

1. 在 `assets/site/` 编写 HTML 模拟页面，在 `tools/render.py` 的 `PAGES` 字典里注册，并列出需要
   提取 manifest 坐标的元素 id，然后执行 `uv run python tools/render.py`。
2. 新增 `src/scenes/<name>.py`，提供 `load_<name>_scene() -> (stages, queries_or_task)`。
3. 在 `agent/prompts.py` 中新增提示词（如果动作 schema 与 grounding/navigation 差异较大，可以像
   `agent/<name>_prompts.py` 一样单独建一个文件），并在 `agent/loop.py` 中新增 `run_<name>()` 生成器。
4. 接入 `server.py`：新增 `/api/scenes/<name>` 接口 + `ws_run` 的分发分支。
5. 新增 `frontend/src/scenes/<Name>Scene.vue`——复用 `ScreenshotView`/`ThoughtStream`/
   `EvidencePanel`/`PageMap`/`SceneProgress`，不要重新造轮子；它们是有意做成与具体场景无关的通用
   组件（通过 `PageInfo`/`ThoughtEntry`/`EvidenceEntry`/`Grounding` 等通用类型接入）。
6. 在 `App.vue` 里加上对应的 tab。

### 模拟内容的品牌约束

任何模拟真实网站的场景（比如股票场景模拟的金融数据中心）都必须使用完全虚构的品牌名、公司名和
数据。HTML 模拟页面、文案、logo 中都不能出现真实平台/产品的名称，也不能让人联想到具体的真实平台
——本项目此前明确要求过要清理掉真实品牌引用（例如不能出现"同花顺"/"10jqka"这类名称）。数据的
*格式*要尽量真实，但不能对应任何真实存在的公司或证券。

## `web/`：Mactive 股市探索（真实浏览器交互 Demo）

完全独立的项目：自己的 `pyproject.toml`（uv）+ 自己的 `package.json`（pnpm/Vite），不 import
`backend/`/`frontend/` 的任何代码，端口也不同（后端 `:8010`，前端 `:5183`）。改这部分代码时不用
管上面几节讲的 `backend/`/`frontend/` 约定，反过来也一样。

只有一个场景（"股市探索"），但底层不再是"预渲染 PNG + 静态 manifest 坐标"，而是一个真正在跑的
浏览器会话：

```
web/backend/  FastAPI + uv + Playwright（async）
  site/       真实可运行的 HTML+JS+CSS 页面（唯一素材来源，没有预渲染步骤，没有 manifest）：
                ipo-subscribe.html（新股申购，真实板块 tab 筛选）
                market-ranking.html（行情排行，真实"连涨天数/放量天数"组合筛选）
                shared.js（真排序 + 真筛选的客户端逻辑：点表头真的重排 DOM 行，行 id 不变；
                点 tab/条件 chip 真的隐藏/显示行）
              由 FastAPI `StaticFiles` 挂载到 `/site`，Playwright 通过真实 HTTP URL 访问它
  src/env/browser_env.py   BrowserEnv：每个 WS 连接一个独立的 browser context/page；
                            navigate/sort_by/apply_filter 都是真实点击；element_rect() 永远
                            实时查询当前 DOM 位置（`bounding_box()`），排序/筛选后坐标依然精确，
                            不存在"位置随重排漂移"的问题
  src/agent/    policy.py（call_vlm，跟 backend/ 的实现基本一致）、stock_prompts.py、
                loop.py（run_stock：驱动真实点击 + 每步重新截图 + 实时 bbox 查询）
  src/scenes/stock.py   页面/题目/ground-truth/QUERY_CLUES/COLUMN_HINTS/FILTER_HINTS 的唯一权威来源
web/frontend/ Vue 3 + TypeScript + Vite，单场景 UI，复用 backend/frontend 里那套通用组件
              （ScreenshotView/BoundingBox/ThoughtStream/EvidencePanel/PageMap/SceneProgress）
              的设计模式，但每一步都消费 WS 事件里的实时截图 base64（不是固定图片路径）——
              排序/筛选后画面真的变了，没有"静态资源"这回事
```

常用命令：

```bash
cd web && ./dev.sh   # 一键启动，或参考 web/README.md 手动启动步骤
```

几个跟 `backend/`/`frontend/` 不一样、容易踩坑的点：

- **截图分辨率**：`browser_env.py` 的 `_observe()` 直接把 Playwright 的原始截图（未降采样）当作
  `thumbnail_b64` 发给前端——密集财经表格对清晰度要求高，`object-fit: contain` 只需要缩小一张大图
  （永远清晰），不能反过来放大一张 720px 的小图（在任何比 720px 宽的容器/HiDPI 屏幕上都会糊）。
- **事件批处理坑**：`loop.py` 里 `scene_start` 和 `query_start` 是背靠背 yield 的，中间没有
  `await` 让出控制权，可能落进同一次 WS onmessage/Vue 响应式 flush 里。`MarketExploreScene.vue`
  的 `watch(events, ...)` 因此**不能**只看 `evts[evts.length - 1]`（会静默丢掉 `scene_start` 的
  首屏截图），必须用 `processedCount` 游标把每一个新到达的事件都处理一遍。
- **Playwright headless-shell 下载失败**：网络受限环境下 `playwright install chromium` 可能因为
  新版默认要下载单独的 "headless shell" 二进制而失败；`server.py` 启动浏览器时带了
  `channel="chromium"` 复用常规 Chromium 构建（如果 `~/Library/Caches/ms-playwright/` 下已经有
  `chromium-*` 目录，不需要额外下载），绕开这个问题。
- 品牌约束跟 `backend/` 完全一样：`site/` 里的 "FinData"、公司名、行情数据全部虚构，不得出现任何
  真实平台/公司名称（详见上面"模拟内容的品牌约束"一节，同样适用于这里）。
- `web/backend/**/__pycache__/` 在 `.gitignore` 里（跟 `backend/` 那个历史遗留的"`.pyc` 被跟踪"
  不是一回事，`web/` 是干净的，不要把这个当成"应该保持一致"的理由去改动）。

## 已知的历史遗留问题

以下几条都是 `backend/`/`frontend/` 的历史遗留，不适用于 `web/`（`web/` 是后来新建的独立项目，
没有这些包袱）。

- `__pycache__/` 下的 `.pyc` 文件被 git 跟踪了（不太寻常，属于历史遗留）——除非有人明确要求，否则
  不用花精力去清理；执行 `uv run python ...` 导致它们被重新编译只是无害的噪音。
- `backend/assets/fallbacks/*.json` 在 `.gitignore` 里，但有几个 fallback 文件是在加入忽略规则
  之前就提交过的，所以每次真实运行完之后它们仍会显示为本地有修改。做不相关的功能开发时，不要把
  这些文件一起提交进去。
- `backend/.env` 里存的是用于本地测试的真实 API key；永远不要打印/记录它的内容，也不要假设
  `.env`/`.env.example` 里的 `MODEL_NAME` 就是"官方"默认值——本地测试过程中它被换过好几次模型。
