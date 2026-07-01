# AGENTS.md

Guidance for AI agents working in this repository.

## What this project is

A standalone demo (spun off from the larger `WAIC/waic-demo` monorepo) that showcases three
capabilities of a vision-language "computer use" agent, each as an independently playable scene
in one Vue app, backed by one FastAPI service:

| Scene | Backend module | Frontend component | Demonstrates |
|---|---|---|---|
| 一眼定位 (Grounding) | `backend/src/scenes/grounding.py` | `frontend/src/scenes/GroundingScene.vue` | Precise bbox grounding on one dense dashboard screenshot, across progressively harder queries |
| 认知导航 (Navigation) | `backend/src/scenes/navigation.py` | `frontend/src/scenes/NavigationScene.vue` | Autonomous multi-page routing (visit/skip) across a 6-page SaaS admin, as a security auditor |
| 股票寻宝 (Stock Intelligence) | `backend/src/scenes/stock.py` | `frontend/src/scenes/StockScene.vue` | Cross-page synthesis: navigate/filter/sort/extract across 5 financial data-center pages to answer compound investment questions |

There is no real backend data store — every "page" is a hand-authored HTML mockup rendered to a
static PNG. The model never touches live data; it only ever sees screenshots.

## Tech stack & layout

```
backend/    Python ≥3.10, FastAPI + WebSocket, uv-managed, OpenAI-compatible VLM client
  src/agent/     policy.py (VLM call), prompts.py + stock_prompts.py (system prompts), loop.py (per-scene agent loops)
  src/scenes/    one loader module per scene — defines pages, queries, and scene-specific config
  src/env/       ScreenshotEnv: the shared multi-page "environment" (navigate/see/zoom over static images)
  assets/site/   hand-authored HTML mockups (source of truth for the images)
  assets/pages/  rendered PNG screenshots (generated, gitignored via *.png but currently some are tracked from earlier commits — check before assuming clean)
  assets/manifests/  per-page JSON: exact pixel rects of key elements, extracted at render time
  tools/render.py   Playwright: HTML -> PNG + manifest. Single source of truth for the PAGES registry.
frontend/   Vue 3 + TypeScript + Vite
  src/scenes/       one *.vue per scene, orchestrates the WebSocket stream into local state
  src/components/   shared, scene-agnostic UI: ScreenshotView/BoundingBox (render), ThoughtStream/
                     EvidencePanel (reasoning log), PageMap/SceneProgress (navigation status)
  src/composables/  useWebSocket.ts (event stream), useAutoPlay.ts
```

## Common commands

```bash
# One-shot: installs deps, renders screenshots, starts both servers
./dev.sh

# Manual — backend
cd backend && uv sync --extra render && uv run playwright install chromium
uv run python tools/render.py            # re-render after editing assets/site/*.html
uv run uvicorn src.server:app --reload --port 8000

# Manual — frontend
cd frontend && pnpm install && pnpm dev   # http://localhost:5173

# Type-check frontend (tsconfig.node.json has a pre-existing, unrelated
# TS5096 error under `vue-tsc -b`; check just the app project instead):
npx vue-tsc --noEmit -p tsconfig.json
```

**Before starting dev servers**, check the `terminals/` folder / running processes — `dev.sh` or a
manual `uvicorn --reload` / `pnpm dev` is very often already running from a previous session
(ports 8000/5173, sometimes falling back to 5174 if occupied). Reusing it is faster and avoids
port-conflict confusion; `--reload` and Vite HMR mean file edits apply automatically.

## Architecture: how a scene runs

1. Frontend calls `connect(sceneName)` → opens `ws://.../ws/run?scene={name}`.
2. `server.py` loads the scene (`load_*_scene()` → `(stages, queries|task)`), builds a
   `ScreenshotEnv`, and runs the matching `run_*()` generator from `agent/loop.py`.
3. Each loop iteration: build multimodal messages (thumbnail + optional zoomed crop + trajectory
   summary) → `call_vlm()` → parse the model's strict-JSON action → apply it to the env → yield a
   `step` event. The frontend accumulates events and renders reactively; nothing is buffered
   server-side beyond the current run.
4. On completion, `_save_fallback()` writes the run to `assets/fallbacks/{scene}.json` and
   `/api/fallback/{scene}` can replay it — **note: no frontend code currently calls this endpoint**;
   it's there but unwired. Don't assume it's used for live failure recovery.

### Coordinate system

All model-facing bboxes are `[x1,y1,x2,y2]` in **integer [0,1000] space**; `_normalize_bbox()` in
`loop.py` converts to `[0,1]` floats (and treats near-zero-area boxes as invalid, falling back to
full-image). `ScreenshotView.vue` computes the actual rendered image rect accounting for
`object-fit: contain` letterboxing before positioning overlays — this was a real, previously-fixed
bug class; don't reintroduce raw `%`-of-container math that ignores letterboxing.

### Grounding precision vs. narrative actions — an important distinction

Not every action a model takes has one objectively-correct bounding box. Actions that point at
**concrete, existing content** (a specific number, table row, alert) are genuine grounding tasks —
trust the model's own coordinates (optionally with a ground-truth-based validation safety net, see
`stock.py`'s `QUERY_CLUES` / `loop.py`'s `_validate_and_snap_answer`). Actions that ask the model to
indicate an **abstract/procedural concept** (e.g. stock scene's `sort`: "the column I'm reasoning
about") have no single right answer and a VLM's freehand guess will look visibly imprecise/jittery.
For those, snap to a known-correct rect from the page's manifest instead (see `COLUMN_HINTS` in
`scenes/stock.py`) rather than trying to prompt-engineer the model into pixel-perfect abstraction
pointing — it's a UI affordance for narrating the model's reasoning, not a grounding benchmark.

### Adding a new scene

1. Author HTML mockup(s) in `assets/site/`, register in `tools/render.py`'s `PAGES` dict with the
   element ids you'll want manifest rects for, then `uv run python tools/render.py`.
2. Add `src/scenes/<name>.py` with a `load_<name>_scene() -> (stages, queries_or_task)`.
3. Add prompts in `agent/prompts.py` (or a dedicated `agent/<name>_prompts.py` if the action schema
   differs from grounding/navigation) and a `run_<name>()` generator in `agent/loop.py`.
4. Wire into `server.py`: `/api/scenes/<name>` + the `ws_run` dispatch branch.
5. Add `frontend/src/scenes/<Name>Scene.vue` — reuse `ScreenshotView`/`ThoughtStream`/
   `EvidencePanel`/`PageMap`/`SceneProgress` rather than rebuilding them; they're deliberately
   scene-agnostic (typed via generic `PageInfo`/`ThoughtEntry`/`EvidenceEntry`/`Grounding` props).
6. Add the tab in `App.vue`.

### Mock content policy

Any scene that simulates a real-world website (like the stock scene simulating a financial data
center) must use entirely fictional brand names, company names, and data. Never reference or
resemble real platforms/products by name in HTML mockups, copy, or logos — this project has
previously been asked to explicitly scrub real brand references (e.g. no "同花顺"/"10jqka"-style
names). Data should look realistic in *format* but not correspond to real companies/securities.

## Known rough edges

- `.pyc` files under `__pycache__/` are tracked in git (unusual, pre-existing) — don't worry about
  cleaning these up unless asked; regenerating them via `uv run python ...` is harmless noise.
- `backend/assets/fallbacks/*.json` is gitignored but some fallback files were committed before
  the ignore rule existed, so they can still show as locally modified after a live run. Don't
  include them in commits about unrelated feature work.
- `backend/.env` holds a real API key for local testing; never print/log it, and don't assume
  `MODEL_NAME` in `.env`/`.env.example` reflects the "official" default — it's been swapped
  between models during local experimentation.
