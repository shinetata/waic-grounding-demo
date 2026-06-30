<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import ScreenshotView from '../components/ScreenshotView.vue'
import ThoughtStream from '../components/ThoughtStream.vue'
import QueryCard from '../components/QueryCard.vue'
import SummaryCard from '../components/SummaryCard.vue'
import SceneProgress from '../components/SceneProgress.vue'
import EvidencePanel from '../components/EvidencePanel.vue'
import type { Grounding } from '../components/ScreenshotView.vue'
import type { ThoughtEntry } from '../components/ThoughtStream.vue'
import type { EvidenceEntry } from '../components/EvidencePanel.vue'
import { useWebSocket, type DemoEvent } from '../composables/useWebSocket'

const emit = defineEmits<{ done: [] }>()

const { events, running, connect, disconnect } = useWebSocket()
const imageSrc = ref('')

const queries = [
  '在这28个服务中，CPU使用率最高的是哪个？它的具体数值和当前副本数各是多少？',
  '过去24小时P99延迟出现了异常峰值，峰值具体是多少毫秒？发生在什么时间？同时指出哪些资源因此接近饱和。',
  '根据事件关联时间线，v2.4.0部署后的级联故障链条是什么？请定位部署时间线和关联表中从部署到回滚的全部事件。',
]

const currentQueryIndex = ref(0)
const showSummary = ref(false)
let doneTimer: ReturnType<typeof setTimeout> | null = null

const groundings = computed<Grounding[]>(() => {
  const result: Grounding[] = []
  for (const evt of events.value) {
    if (evt.type === 'step' && evt.groundings) {
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
      answer: e.answer || undefined,
      elapsed: e.elapsed,
    }))
})

const evidenceEntries = computed<EvidenceEntry[]>(() => {
  const entries: EvidenceEntry[] = []
  for (const evt of events.value) {
    if (evt.type !== 'step') continue
    if (evt.groundings?.length) {
      const bboxes = evt.groundings.map((g: any) =>
        `[${g.bbox.map((v: number) => v.toFixed(3)).join(', ')}]`
      ).join(' ')
      entries.push({ step: evt.step, type: 'coordinates', raw: bboxes })
    }
    if (evt.thought) {
      entries.push({ step: evt.step, type: 'reasoning', raw: evt.thought })
    }
  }
  return entries
})

const progressSteps = computed(() => {
  return queries.map((q, i) => ({
    label: `Q${i + 1}`,
    status: i < currentQueryIndex.value ? 'done'
      : i === currentQueryIndex.value ? 'active'
      : 'idle',
  })) as Array<{ label: string; status: 'idle' | 'active' | 'done' }>
})

const summaryData = computed(() => {
  const end = events.value.find((e: DemoEvent) => e.type === 'scene_end')
  if (!end) return null
  return {
    totalSteps: end.total_steps || 0,
    groundingCount: end.total_groundings || 0,
  }
})

watch(events, (evts) => {
  const latest = evts[evts.length - 1]
  if (!latest) return
  if (latest.type === 'query_start') {
    currentQueryIndex.value = latest.query_index ?? 0
  }
  if (latest.type === 'scene_end') {
    showSummary.value = true
    doneTimer = setTimeout(() => emit('done'), 8000)
  }
  if (latest.type === 'error') {
    console.error('Demo error:', latest.message)
  }
})

function start() {
  if (doneTimer) { clearTimeout(doneTimer); doneTimer = null }
  showSummary.value = false
  imageSrc.value = '/assets/pages/dashboard.png'
  connect('grounding')
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
  <div class="grounding-scene">
    <div class="scene-main">
      <ScreenshotView
        :image-src="imageSrc || '/assets/pages/dashboard.png'"
        :groundings="groundings"
      />
    </div>
    <div class="scene-side">
      <SceneProgress :steps="progressSteps" />
      <div class="query-section">
        <QueryCard
          v-for="(q, i) in queries"
          :key="i"
          :query="q"
          :index="i"
          :total="queries.length"
          :active="i === currentQueryIndex && running"
        />
      </div>
      <ThoughtStream :entries="thoughts" title="推理过程" />
      <EvidencePanel :entries="evidenceEntries" />
      <SummaryCard
        v-if="showSummary && summaryData"
        scene="grounding"
        :total-steps="summaryData.totalSteps"
        :grounding-count="summaryData.groundingCount"
      />
    </div>
  </div>
</template>

<style scoped>
.grounding-scene {
  display: flex;
  gap: 16px;
  height: 100%;
  padding: 16px;
}
.scene-main {
  flex: 1;
  min-width: 0;
  display: flex;
  align-items: center;
  justify-content: center;
}
.scene-side {
  width: 340px;
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  gap: 12px;
  overflow: hidden;
}
.query-section {
  display: flex;
  flex-direction: column;
  gap: 8px;
  flex-shrink: 0;
}
</style>
