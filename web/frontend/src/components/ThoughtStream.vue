<script setup lang="ts">
import { ref, watch, nextTick } from 'vue'

export interface ThoughtEntry {
  step: number
  thought: string
  actionType?: string
  stage?: string
  finding?: string
  answer?: string
  elapsed?: number
}

const props = defineProps<{
  entries: ThoughtEntry[]
  title?: string
}>()

const container = ref<HTMLElement | null>(null)

watch(() => props.entries.length, async () => {
  await nextTick()
  if (container.value) {
    container.value.scrollTop = container.value.scrollHeight
  }
})
</script>

<template>
  <div class="thought-stream">
    <div class="stream-header">
      <span class="stream-icon">💭</span>
      <span class="stream-title">{{ title || '思维流' }}</span>
    </div>
    <div ref="container" class="stream-entries">
      <div
        v-for="entry in entries"
        :key="entry.step"
        class="stream-entry"
        :class="{
          'has-finding': !!entry.finding,
          'is-skip': entry.actionType === 'skip',
          'is-eos': entry.actionType === 'eos',
        }"
      >
        <div class="entry-header">
          <span class="step-badge">{{ entry.step }}</span>
          <span v-if="entry.stage" class="stage-tag">{{ entry.stage }}</span>
          <span v-if="entry.actionType" class="action-tag" :class="'action-' + entry.actionType">
            {{ entry.actionType }}
          </span>
          <span v-if="entry.elapsed" class="elapsed">{{ entry.elapsed }}s</span>
        </div>
        <div class="entry-thought">{{ entry.thought }}</div>
        <div v-if="entry.finding" class="entry-finding">
          <span class="finding-icon">⚠</span> {{ entry.finding }}
        </div>
        <div v-if="entry.answer" class="entry-answer">
          {{ entry.answer }}
        </div>
      </div>

      <div v-if="entries.length === 0" class="stream-empty">
        等待模型推理...
      </div>
    </div>
  </div>
</template>

<style scoped>
.thought-stream {
  display: flex;
  flex-direction: column;
  flex: 1;
  min-height: 0;
  background: #111318;
  border-radius: 12px;
  border: 1px solid #1e222a;
  overflow: hidden;
}
.stream-header {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px 16px;
  border-bottom: 1px solid #1e222a;
  flex-shrink: 0;
}
.stream-icon { font-size: 16px; }
.stream-title { font-size: 13px; font-weight: 600; color: #e0e0e0; }
.stream-entries {
  flex: 1;
  overflow-y: auto;
  padding: 8px;
}
.stream-entry {
  padding: 10px 12px;
  margin-bottom: 6px;
  background: #161a22;
  border-radius: 8px;
  border-left: 3px solid #2a2e38;
  animation: slide-in 0.3s ease;
}
.stream-entry.has-finding { border-left-color: #ef4444; }
.stream-entry.is-skip { border-left-color: #6b7280; opacity: 0.7; }
.stream-entry.is-eos { border-left-color: #3b82f6; }
.entry-header {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-bottom: 6px;
}
.step-badge {
  background: #2a2e38;
  color: #8b949e;
  border-radius: 10px;
  padding: 1px 8px;
  font-size: 10px;
  font-weight: 600;
}
.stage-tag {
  font-size: 10px;
  color: #58a6ff;
  font-family: 'JetBrains Mono', monospace;
}
.action-tag {
  font-size: 10px;
  padding: 1px 6px;
  border-radius: 3px;
  font-weight: 500;
}
.action-see { background: #1e3a2f; color: #3fb950; }
.action-navigate { background: #1e2d3d; color: #58a6ff; }
.action-skip { background: #2d2222; color: #8b949e; }
.action-eos { background: #1e2d3d; color: #79c0ff; }
.action-zoom_in { background: #2d2a1e; color: #d29922; }
.elapsed { font-size: 10px; color: #484f58; margin-left: auto; }
.entry-thought { font-size: 12px; color: #c0c5d0; line-height: 1.5; }
.entry-finding {
  margin-top: 6px;
  padding: 6px 10px;
  background: #2d1f1f;
  border-radius: 4px;
  font-size: 11px;
  color: #f85149;
}
.finding-icon { margin-right: 4px; }
.entry-answer {
  margin-top: 6px;
  padding: 6px 10px;
  background: #1e2d3d;
  border-radius: 4px;
  font-size: 12px;
  color: #79c0ff;
  font-weight: 500;
}
.stream-empty {
  text-align: center;
  padding: 20px 16px;
  color: #484f58;
  font-size: 12px;
}
@keyframes slide-in {
  from { opacity: 0; transform: translateY(8px); }
  to { opacity: 1; transform: translateY(0); }
}
</style>
