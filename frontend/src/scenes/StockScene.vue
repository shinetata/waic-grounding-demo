<script setup lang="ts">
import { ref, computed, watch, nextTick } from 'vue'
import ScreenshotView from '../components/ScreenshotView.vue'
import ThoughtStream from '../components/ThoughtStream.vue'
import QueryCard from '../components/QueryCard.vue'
import SceneProgress from '../components/SceneProgress.vue'
import EvidencePanel from '../components/EvidencePanel.vue'
import PageMap from '../components/PageMap.vue'
import StockHeader from '../components/StockHeader.vue'
import AnswerCard from '../components/AnswerCard.vue'
import type { Grounding } from '../components/ScreenshotView.vue'
import type { ThoughtEntry } from '../components/ThoughtStream.vue'
import type { EvidenceEntry } from '../components/EvidencePanel.vue'
import type { PageInfo } from '../components/PageMap.vue'
import { useWebSocket, type DemoEvent } from '../composables/useWebSocket'

const emit = defineEmits<{ done: [] }>()

const { events, running, connect, disconnect } = useWebSocket()

const STOCK_PAGES: Record<string, { title: string; group: string }> = {
  'ipo-overview': { title: '新股申购总览', group: '新股上市' },
  'ipo-star': { title: '科创板新股', group: '新股上市' },
  'rank-rising': { title: '连续上涨', group: '技术选股' },
  'rank-volume': { title: '持续放量', group: '技术选股' },
  'rank-vol-price': { title: '量价齐升', group: '技术选股' },
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

const currentStage = ref('ipo-overview')
const currentImage = ref('/assets/pages/ipo-overview.png')
const currentRect = ref({ x: 0, y: 0, w: 1, h: 1 })
const currentQueryIndex = ref(0)
const answers = ref<AnswerEntry[]>([])
let doneTimer: ReturnType<typeof setTimeout> | null = null

const visited = ref<Set<string>>(new Set(['ipo-overview']))
const navPath = ref<Array<{ from: string; to: string }>>([])
let visitOrder = 1
const visitOrders = ref<Record<string, number>>({ 'ipo-overview': 1 })
const answersStackRef = ref<HTMLElement | null>(null)

const pages = computed<PageInfo[]>(() => {
  return Object.entries(STOCK_PAGES).map(([id, meta]) => ({
    id,
    title: meta.title,
    imageSrc: `/assets/pages/${id}.png`,
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

watch(events, (evts) => {
  const latest = evts[evts.length - 1]
  if (!latest) return

  if (latest.type === 'query_start') {
    currentQueryIndex.value = latest.query_index ?? 0
  }

  if (latest.type === 'step') {
    if (latest.stage) currentStage.value = latest.stage
    if (latest.new_stage) {
      const from = currentStage.value
      currentStage.value = latest.new_stage
      currentImage.value = `/assets/pages/${latest.new_stage}.png`
      visited.value.add(latest.new_stage)
      if (!visitOrders.value[latest.new_stage]) {
        visitOrder++
        visitOrders.value[latest.new_stage] = visitOrder
      }
      if (from !== latest.new_stage) navPath.value.push({ from, to: latest.new_stage })
    }
    if (latest.observation?.rect) {
      currentRect.value = latest.observation.rect
    }
  }

  if (latest.type === 'query_end') {
    answers.value.push({
      queryIndex: latest.query_index,
      query: latest.query,
      answer: latest.answer || {},
      fields: latest.fields || [],
      sourceStageTitle: STOCK_PAGES[currentStage.value]?.title || currentStage.value,
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
})

function start() {
  if (doneTimer) { clearTimeout(doneTimer); doneTimer = null }
  visited.value = new Set(['ipo-overview'])
  navPath.value = []
  visitOrder = 1
  visitOrders.value = { 'ipo-overview': 1 }
  currentStage.value = 'ipo-overview'
  currentImage.value = '/assets/pages/ipo-overview.png'
  currentRect.value = { x: 0, y: 0, w: 1, h: 1 }
  currentQueryIndex.value = 0
  answers.value = []
  connect('stock')
}

function stop() {
  if (doneTimer) { clearTimeout(doneTimer); doneTimer = null }
  disconnect()
  answers.value = []
  events.value = []
}

defineExpose({ start, stop })
</script>

<template>
  <div class="stock-scene">
    <StockHeader />
    <div class="stock-body">
      <div class="stock-left">
        <PageMap :pages="pages" :navigation-path="navPath" />
        <SceneProgress :steps="progressSteps" />
      </div>
      <div class="stock-main">
        <ScreenshotView
          :image-src="currentImage"
          :groundings="groundings"
          :current-rect="currentRect"
          :show-viewport="currentRect.w < 0.95"
        />
        <div class="page-label">
          <span class="page-label-icon">📄</span>
          <span class="page-label-group">{{ STOCK_PAGES[currentStage]?.group }}</span>
          <span class="page-label-sep">›</span>
          {{ STOCK_PAGES[currentStage]?.title || currentStage }}
        </div>
      </div>
      <div class="stock-right">
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
.stock-scene {
  display: flex;
  flex-direction: column;
  gap: 10px;
  height: 100%;
  padding: 12px 16px;
}
.stock-body {
  display: flex;
  gap: 12px;
  flex: 1;
  min-height: 0;
}
.stock-left {
  width: 220px;
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  gap: 8px;
  align-self: flex-start;
}
.stock-main {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 8px;
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
.page-label-group { color: #58a6ff; font-weight: 500; }
.page-label-sep { color: #484f58; }
.stock-right {
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
