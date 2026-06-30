<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import ScreenshotView from '../components/ScreenshotView.vue'
import ThoughtStream from '../components/ThoughtStream.vue'
import PageMap from '../components/PageMap.vue'
import SummaryCard from '../components/SummaryCard.vue'
import SceneProgress from '../components/SceneProgress.vue'
import EvidencePanel from '../components/EvidencePanel.vue'
import type { Grounding } from '../components/ScreenshotView.vue'
import type { ThoughtEntry } from '../components/ThoughtStream.vue'
import type { EvidenceEntry } from '../components/EvidencePanel.vue'
import type { PageInfo } from '../components/PageMap.vue'
import { useWebSocket, type DemoEvent } from '../composables/useWebSocket'

const emit = defineEmits<{ done: [] }>()

const { events, running, connect, disconnect } = useWebSocket()

const currentStage = ref('overview')
const currentImage = ref('/assets/pages/overview.png')
const currentRect = ref({ x: 0, y: 0, w: 1, h: 1 })
const showSummary = ref(false)
let doneTimer: ReturnType<typeof setTimeout> | null = null

const PAGE_TITLES: Record<string, string> = {
  'overview': '总览面板',
  'users': '用户管理',
  'permissions': '权限设置',
  'api-keys': 'API 密钥',
  'analytics': '使用量分析',
  'logs': '审计日志',
}

const visited = ref<Set<string>>(new Set(['overview']))
const skippedPages = ref<Map<string, string>>(new Map())
const navPath = ref<Array<{ from: string; to: string }>>([])
let visitOrder = 1
const visitOrders = ref<Record<string, number>>({ 'overview': 1 })

const pages = computed<PageInfo[]>(() => {
  return Object.entries(PAGE_TITLES).map(([id, title]) => ({
    id,
    title,
    imageSrc: `/assets/pages/${id}.png`,
    status: id === currentStage.value
      ? 'current'
      : skippedPages.value.has(id)
        ? 'skipped'
        : visited.value.has(id)
          ? 'visited'
          : 'idle',
    skipReason: skippedPages.value.get(id),
    order: visitOrders.value[id],
  }))
})

const groundings = computed<Grounding[]>(() => {
  const result: Grounding[] = []
  const latestStep = [...events.value].reverse().find(
    (e: DemoEvent) => e.type === 'step' && e.stage === currentStage.value && e.groundings
  )
  if (latestStep?.groundings) {
    for (const g of latestStep.groundings) {
      result.push(g)
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
      finding: e.finding,
      elapsed: e.elapsed,
    }))
})

const evidenceEntries = computed<EvidenceEntry[]>(() => {
  const entries: EvidenceEntry[] = []
  for (const evt of events.value) {
    if (evt.type !== 'step') continue
    if (evt.action_type) {
      const parts = [`action: ${evt.action_type}`]
      if (evt.action_target) parts.push(`target: ${JSON.stringify(evt.action_target)}`)
      if (evt.action_reason) parts.push(`reason: ${evt.action_reason}`)
      entries.push({ step: evt.step, type: 'action', raw: parts.join('\n'), stage: evt.stage })
    }
    if (evt.finding) {
      entries.push({ step: evt.step, type: 'reasoning', raw: evt.finding, stage: evt.stage })
    }
  }
  return entries
})

const navProgressSteps = computed(() => {
  const pageIds = Object.keys(PAGE_TITLES)
  return pageIds.map(id => ({
    label: PAGE_TITLES[id],
    status: id === currentStage.value ? 'active'
      : visited.value.has(id) ? 'done'
      : skippedPages.value.has(id) ? 'done'
      : 'idle',
  })) as Array<{ label: string; status: 'idle' | 'active' | 'done' }>
})

const summaryData = computed(() => {
  const end = events.value.find((e: DemoEvent) => e.type === 'scene_end')
  if (!end) return null
  return {
    totalSteps: end.total_steps || 0,
    visited: end.visited || [],
    skipped: end.skipped || [],
    findings: end.findings || [],
  }
})

watch(events, (evts) => {
  const latest = evts[evts.length - 1]
  if (!latest) return

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
      navPath.value.push({ from, to: latest.new_stage })
    }
    if (latest.observation?.rect) {
      currentRect.value = latest.observation.rect
    }
    if (latest.action_type === 'skip' && latest.skipped_page) {
      skippedPages.value.set(latest.skipped_page, latest.action_reason || '与任务无关')
    }
  }

  if (latest.type === 'scene_end') {
    showSummary.value = true
    doneTimer = setTimeout(() => emit('done'), 8000)
  }
})

function start() {
  if (doneTimer) { clearTimeout(doneTimer); doneTimer = null }
  showSummary.value = false
  visited.value = new Set(['overview'])
  skippedPages.value = new Map()
  navPath.value = []
  visitOrder = 1
  visitOrders.value = { 'overview': 1 }
  currentStage.value = 'overview'
  currentImage.value = '/assets/pages/overview.png'
  currentRect.value = { x: 0, y: 0, w: 1, h: 1 }
  connect('navigation')
}

function stop() {
  if (doneTimer) { clearTimeout(doneTimer); doneTimer = null }
  disconnect()
  showSummary.value = false
  events.value = []
}

defineExpose({ start, stop })
</script>

<template>
  <div class="navigation-scene">
    <div class="nav-left">
      <PageMap :pages="pages" :navigation-path="navPath" />
    </div>
    <div class="nav-main">
      <ScreenshotView
        :image-src="currentImage"
        :groundings="groundings"
        :current-rect="currentRect"
        :show-viewport="currentRect.w < 0.95"
      />
    </div>
    <div class="nav-right">
      <div class="task-card">
        <div class="task-label">审计任务</div>
        <div class="task-text">评估 NexaCloud 管理后台的安全风险</div>
      </div>
      <SceneProgress :steps="navProgressSteps" />
      <ThoughtStream :entries="thoughts" title="审计过程" />
      <EvidencePanel :entries="evidenceEntries" />
      <SummaryCard
        v-if="showSummary && summaryData"
        scene="navigation"
        :total-steps="summaryData.totalSteps"
        :visited="summaryData.visited"
        :skipped="summaryData.skipped"
        :findings="summaryData.findings"
      />
    </div>
  </div>
</template>

<style scoped>
.navigation-scene {
  display: flex;
  gap: 16px;
  height: 100%;
  padding: 16px;
}
.nav-left {
  width: 220px;
  flex-shrink: 0;
}
.nav-main {
  flex: 1;
  min-width: 0;
  display: flex;
  align-items: center;
  justify-content: center;
}
.nav-right {
  width: 340px;
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  gap: 12px;
  overflow: hidden;
}
.task-card {
  background: #111318;
  border: 1px solid #1e222a;
  border-radius: 10px;
  padding: 14px;
  flex-shrink: 0;
}
.task-label {
  font-size: 10px;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  color: #8b949e;
  margin-bottom: 6px;
}
.task-text {
  font-size: 14px;
  color: #e0e0e0;
  line-height: 1.4;
}
</style>
