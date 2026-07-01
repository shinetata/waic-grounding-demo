<script setup lang="ts">
import { ref, computed, watch, nextTick } from 'vue'
import ScreenshotView from '../components/ScreenshotView.vue'
import ThoughtStream from '../components/ThoughtStream.vue'
import QueryCard from '../components/QueryCard.vue'
import SceneProgress from '../components/SceneProgress.vue'
import EvidencePanel from '../components/EvidencePanel.vue'
import PageMap from '../components/PageMap.vue'
import AppHeader from '../components/AppHeader.vue'
import AnswerCard from '../components/AnswerCard.vue'
import type { Grounding } from '../components/ScreenshotView.vue'
import type { ThoughtEntry } from '../components/ThoughtStream.vue'
import type { EvidenceEntry } from '../components/EvidencePanel.vue'
import type { PageInfo } from '../components/PageMap.vue'
import { useWebSocket, type DemoEvent } from '../composables/useWebSocket'

const emit = defineEmits<{ done: [] }>()

const { events, running, connect, disconnect } = useWebSocket()

const PAGES: Record<string, { title: string }> = {
  'ipo-subscribe': { title: '新股申购' },
  'market-ranking': { title: '行情排行' },
}

const queries = [
  '科创板新股里，今天（申购日当天）仍可申购的股票中，发行价格最低的是哪一只？记下它的简称、申购代码、发行价格和申购日期。',
  '科创板新股中，发行市盈率相对所属行业市盈率溢价最大（即发行市盈率超出行业市盈率的差值最大）的是哪一只？记下它的简称、发行市盈率、行业市盈率和申购日期。',
  '今天连续放量上涨的股票里，涨幅最高的是哪只？记下名称、涨跌幅和换手率。',
]

interface AnswerEntry {
  queryIndex: number
  query: string
  answer: Record<string, string>
  fields: string[]
  sourceStageTitle: string
}

function dataUrl(b64: string): string {
  return `data:image/png;base64,${b64}`
}

const currentStage = ref('ipo-subscribe')
const currentImage = ref('')
const pageThumbs = ref<Record<string, string>>({})
const currentRect = ref({ x: 0, y: 0, w: 1, h: 1 })
const currentQueryIndex = ref(0)
const answers = ref<AnswerEntry[]>([])
let doneTimer: ReturnType<typeof setTimeout> | null = null

const visited = ref<Set<string>>(new Set(['ipo-subscribe']))
const navPath = ref<Array<{ from: string; to: string }>>([])
let visitOrder = 1
const visitOrders = ref<Record<string, number>>({ 'ipo-subscribe': 1 })
const answersStackRef = ref<HTMLElement | null>(null)

const pages = computed<PageInfo[]>(() => {
  return Object.entries(PAGES).map(([id, meta]) => ({
    id,
    title: meta.title,
    imageSrc: pageThumbs.value[id],
    status: id === currentStage.value ? 'current' : visited.value.has(id) ? 'visited' : 'idle',
    order: visitOrders.value[id],
  }))
})

const groundings = computed<Grounding[]>(() => {
  const result: Grounding[] = []
  for (const evt of events.value) {
    if (evt.type === 'step' && evt.stage === currentStage.value && evt.groundings) {
      for (const g of evt.groundings) {
        result.push({ ...g, queryIndex: evt.query_index ?? 0 })
      }
    }
  }
  return result
})

const thoughts = computed<ThoughtEntry[]>(() => {
  return events.value
    .filter((e: DemoEvent) => e.type === 'step')
    .map((e: DemoEvent) => ({
      step: e.step,
      thought: e.thought || '',
      actionType: e.action_type,
      stage: e.stage,
      elapsed: e.elapsed,
    }))
})

const evidenceEntries = computed<EvidenceEntry[]>(() => {
  const entries: EvidenceEntry[] = []
  for (const evt of events.value) {
    if (evt.type !== 'step') continue
    if (evt.action_type) {
      const parts = [`action: ${evt.action_type}`]
      if (evt.action_target !== undefined) parts.push(`target: ${JSON.stringify(evt.action_target)}`)
      if (evt.action_reason) parts.push(`reason: ${evt.action_reason}`)
      entries.push({ step: evt.step, type: 'action', raw: parts.join('\n'), stage: evt.stage })
    }
    if (evt.answer) {
      entries.push({ step: evt.step, type: 'reasoning', raw: JSON.stringify(evt.answer), stage: evt.stage })
    }
  }
  return entries
})

const progressSteps = computed(() => {
  return queries.map((_, i) => ({
    label: `Q${i + 1}`,
    status: answers.value.some((a) => a.queryIndex === i)
      ? 'done'
      : i === currentQueryIndex.value
        ? 'active'
        : 'idle',
  })) as Array<{ label: string; status: 'idle' | 'active' | 'done' }>
})

// `scene_start` and `query_start` are sent back-to-back with no await in
// between (see loop.py), so they can land in the same WS onmessage/reactive
// flush batch — watching only the *last* event would silently drop
// `scene_start`'s initial screenshot. Process every new event in order
// instead, tracking how many have already been handled.
let processedCount = 0

watch(events, (evts) => {
  for (; processedCount < evts.length; processedCount++) {
  const latest = evts[processedCount]
  if (!latest) continue

  if (latest.type === 'scene_start') {
    if (latest.current_stage) currentStage.value = latest.current_stage
    if (latest.thumbnail_b64) {
      currentImage.value = dataUrl(latest.thumbnail_b64)
      pageThumbs.value[currentStage.value] = currentImage.value
    }
  }

  if (latest.type === 'query_start') {
    currentQueryIndex.value = latest.query_index ?? 0
  }

  if (latest.type === 'step') {
    if (latest.stage) currentStage.value = latest.stage
    if (latest.new_stage) {
      const from = currentStage.value
      currentStage.value = latest.new_stage
      visited.value.add(latest.new_stage)
      if (!visitOrders.value[latest.new_stage]) {
        visitOrder++
        visitOrders.value[latest.new_stage] = visitOrder
      }
      if (from !== latest.new_stage) navPath.value.push({ from, to: latest.new_stage })
    }
    if (latest.observation) {
      if (latest.observation.rect) currentRect.value = latest.observation.rect
      if (latest.observation.thumbnail_b64) {
        currentImage.value = dataUrl(latest.observation.thumbnail_b64)
        pageThumbs.value[currentStage.value] = currentImage.value
      }
    }
  }

  if (latest.type === 'query_end') {
    answers.value.push({
      queryIndex: latest.query_index,
      query: latest.query,
      answer: latest.answer || {},
      fields: latest.fields || [],
      sourceStageTitle: PAGES[currentStage.value]?.title || currentStage.value,
    })
    nextTick(() => {
      const el = answersStackRef.value
      if (el) el.scrollTop = el.scrollHeight
    })
  }

  if (latest.type === 'scene_end') {
    doneTimer = setTimeout(() => emit('done'), 9000)
  }

  if (latest.type === 'error') {
    console.error('Demo error:', latest.message)
  }
  }
})

function start() {
  if (doneTimer) { clearTimeout(doneTimer); doneTimer = null }
  processedCount = 0
  visited.value = new Set(['ipo-subscribe'])
  navPath.value = []
  visitOrder = 1
  visitOrders.value = { 'ipo-subscribe': 1 }
  currentStage.value = 'ipo-subscribe'
  currentImage.value = ''
  pageThumbs.value = {}
  currentRect.value = { x: 0, y: 0, w: 1, h: 1 }
  currentQueryIndex.value = 0
  answers.value = []
  connect()
}

function stop() {
  if (doneTimer) { clearTimeout(doneTimer); doneTimer = null }
  disconnect()
  answers.value = []
  events.value = []
  processedCount = 0
}

defineExpose({ start, stop })
</script>

<template>
  <div class="market-scene">
    <AppHeader />
    <div class="market-body">
      <div class="market-left">
        <PageMap :pages="pages" :navigation-path="navPath" />
        <SceneProgress :steps="progressSteps" />
      </div>
      <div class="market-main">
        <ScreenshotView
          v-if="currentImage"
          :image-src="currentImage"
          :groundings="groundings"
          :current-rect="currentRect"
          :show-viewport="currentRect.w < 0.95"
        />
        <div v-else class="market-loading">正在加载…</div>
        <div class="page-label">
          <span class="page-label-icon">🌐</span>
          <span class="page-label-live">LIVE</span>
          <span class="page-label-sep">›</span>
          {{ PAGES[currentStage]?.title || currentStage }}
        </div>
      </div>
      <div class="market-right">
        <QueryCard
          :query="queries[currentQueryIndex]"
          :index="currentQueryIndex"
          :total="queries.length"
          :active="running"
        />
        <ThoughtStream :entries="thoughts" title="推理过程" />
        <EvidencePanel :entries="evidenceEntries" />
        <div v-if="answers.length" ref="answersStackRef" class="answers-stack">
          <AnswerCard
            v-for="a in answers"
            :key="a.queryIndex"
            :query-index="a.queryIndex"
            :query="a.query"
            :answer="a.answer"
            :fields="a.fields"
            :source-stage-title="a.sourceStageTitle"
          />
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.market-scene {
  display: flex;
  flex-direction: column;
  gap: 10px;
  height: 100%;
  padding: 12px 16px;
}
.market-body {
  display: flex;
  gap: 12px;
  flex: 1;
  min-height: 0;
}
.market-left {
  width: 220px;
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  gap: 8px;
  align-self: flex-start;
}
.market-main {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.market-loading {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #0d0f14;
  border-radius: 10px;
  border: 1px solid #1e222a;
  color: #484f58;
  font-size: 13px;
}
.page-label {
  flex-shrink: 0;
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 12px;
  background: #111318;
  border: 1px solid #1e222a;
  border-radius: 8px;
  font-size: 13px;
  font-weight: 600;
  color: #c0c5d0;
}
.page-label-icon { font-size: 14px; }
.page-label-live {
  color: #3fb950;
  font-weight: 800;
  font-size: 10.5px;
  letter-spacing: 0.5px;
  padding: 1px 6px;
  border: 1px solid #1a5c2a;
  border-radius: 4px;
}
.page-label-sep { color: #484f58; }
.market-right {
  width: 360px;
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  gap: 8px;
  overflow: hidden;
}
.answers-stack {
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  gap: 8px;
  max-height: 360px;
  overflow-y: auto;
  padding-right: 2px;
  scroll-behavior: smooth;
}
</style>
