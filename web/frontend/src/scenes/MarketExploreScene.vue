<script setup lang="ts">
import { ref, computed, watch, nextTick } from 'vue'
import LivePageView from '../components/LivePageView.vue'
import ThoughtStream from '../components/ThoughtStream.vue'
import QueryCard from '../components/QueryCard.vue'
import SceneProgress from '../components/SceneProgress.vue'
import EvidencePanel from '../components/EvidencePanel.vue'
import PageMap from '../components/PageMap.vue'
import AppHeader from '../components/AppHeader.vue'
import AnswerCard from '../components/AnswerCard.vue'
import type { Grounding } from '../components/LivePageView.vue'
import type { ThoughtEntry } from '../components/ThoughtStream.vue'
import type { EvidenceEntry } from '../components/EvidencePanel.vue'
import type { PageInfo } from '../components/PageMap.vue'
import { useWebSocket, type DemoEvent } from '../composables/useWebSocket'

const emit = defineEmits<{ done: [] }>()

const { events, running, connect, disconnect, send, onCommand } = useWebSocket()

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

const currentStage = ref('ipo-subscribe')
const currentQueryIndex = ref(0)
const answers = ref<AnswerEntry[]>([])
let doneTimer: ReturnType<typeof setTimeout> | null = null

const visited = ref<Set<string>>(new Set(['ipo-subscribe']))
const navPath = ref<Array<{ from: string; to: string }>>([])
let visitOrder = 1
const visitOrders = ref<Record<string, number>>({ 'ipo-subscribe': 1 })
const answersStackRef = ref<HTMLElement | null>(null)
const livePageRef = ref<InstanceType<typeof LivePageView> | null>(null)

const pages = computed<PageInfo[]>(() => {
  return Object.entries(PAGES).map(([id, meta]) => ({
    id,
    title: meta.title,
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

// ---- Handle backend command messages ----

async function handleCommand(msg: DemoEvent) {
  const page = livePageRef.value
  if (!page) {
    console.warn('LivePageView not mounted, ignoring command:', msg.type)
    return
  }

  await page.waitForReady()

  if (msg.type === 'observe') {
    const b64 = await page.captureScreenshot()
    const docSize = page.getDocSize()
    send({
      type: 'screenshot',
      image_b64: b64,
      stage: currentStage.value,
      doc_width: docSize.w,
      doc_height: docSize.h,
    })
  } else if (msg.type === 'execute') {
    let elementRect: { x: number; y: number; w: number; h: number } | null = null

    if (msg.action === 'navigate') {
      const from = currentStage.value
      await page.executeNavigate(msg.page_id)
      currentStage.value = msg.page_id
      visited.value.add(msg.page_id)
      if (!visitOrders.value[msg.page_id]) {
        visitOrder++
        visitOrders.value[msg.page_id] = visitOrder
      }
      if (from !== msg.page_id) navPath.value.push({ from, to: msg.page_id })
    } else if (msg.action === 'sort') {
      await page.executeSort(msg.element_id, msg.direction)
      elementRect = page.getElementRect(msg.element_id)
    } else if (msg.action === 'filter') {
      await page.executeFilter(msg.element_id)
      elementRect = page.getElementRect(msg.element_id)
    }

    const b64 = await page.captureScreenshot()
    const docSize = page.getDocSize()
    send({
      type: 'screenshot',
      image_b64: b64,
      stage: currentStage.value,
      doc_width: docSize.w,
      doc_height: docSize.h,
      element_rect: elementRect,
    })
  } else if (msg.type === 'query_rect') {
    const rect = page?.getElementRect(msg.element_id) ?? null
    send({
      type: 'rect',
      element_id: msg.element_id,
      rect: rect,
    })
  }
}

// ---- Process display events ----

let processedCount = 0

watch(events, (evts) => {
  for (; processedCount < evts.length; processedCount++) {
    const latest = evts[processedCount]
    if (!latest) continue

    if (latest.type === 'query_start') {
      currentQueryIndex.value = latest.query_index ?? 0
    }

    if (latest.type === 'step') {
      if (latest.stage) currentStage.value = latest.stage
      if (latest.new_stage) {
        currentStage.value = latest.new_stage
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
  currentQueryIndex.value = 0
  answers.value = []
  onCommand(handleCommand)
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
        <LivePageView
          ref="livePageRef"
          :page-id="currentStage"
          :groundings="groundings"
          :locked="running"
        />
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
