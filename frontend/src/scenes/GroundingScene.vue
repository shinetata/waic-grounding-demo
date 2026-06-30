<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import ScreenshotView from '../components/ScreenshotView.vue'
import ThoughtStream from '../components/ThoughtStream.vue'
import QueryCard from '../components/QueryCard.vue'
import SummaryCard from '../components/SummaryCard.vue'
import type { Grounding } from '../components/ScreenshotView.vue'
import type { ThoughtEntry } from '../components/ThoughtStream.vue'
import { useWebSocket, type DemoEvent } from '../composables/useWebSocket'

const emit = defineEmits<{ done: [] }>()

const { events, running, connect } = useWebSocket()
const imageSrc = ref('')

const queries = [
  '在这个监控面板中，哪个服务的CPU使用率最高？它的具体数值是多少？',
  '过去24小时P99延迟有没有异常峰值？具体在什么时间、峰值是多少？',
  '这个延迟峰值和哪次部署操作有关？请同时定位延迟面板和部署时间线中的相关事件。',
]

const currentQueryIndex = ref(0)
const showSummary = ref(false)

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
    setTimeout(() => emit('done'), 8000)
  }
  if (latest.type === 'error') {
    console.error('Demo error:', latest.message)
  }
})

function start() {
  showSummary.value = false
  imageSrc.value = '/assets/pages/dashboard.png'
  connect('grounding')
}

defineExpose({ start })
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
