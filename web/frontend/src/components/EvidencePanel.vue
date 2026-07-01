<script setup lang="ts">
import { ref, watch, nextTick } from 'vue'

export interface EvidenceEntry {
  step: number
  type: 'coordinates' | 'action' | 'reasoning'
  raw: string
  stage?: string
}

const props = defineProps<{
  entries: EvidenceEntry[]
}>()

const collapsed = ref(true)
const container = ref<HTMLElement | null>(null)

watch(() => props.entries.length, async (len) => {
  if (len > 0) collapsed.value = false
  await nextTick()
  if (container.value) {
    container.value.scrollTop = container.value.scrollHeight
  }
})
</script>

<template>
  <div class="evidence-panel" :class="{ collapsed }">
    <div class="panel-header" @click="collapsed = !collapsed">
      <span class="panel-icon">⟨/⟩</span>
      <span class="panel-title">原始输出</span>
      <span class="panel-count" v-if="entries.length">{{ entries.length }}</span>
      <span class="panel-toggle">{{ collapsed ? '▸' : '▾' }}</span>
    </div>
    <div v-show="!collapsed" ref="container" class="panel-body">
      <div
        v-for="entry in entries"
        :key="entry.step + entry.type"
        class="evidence-entry"
      >
        <div class="evidence-meta">
          <span class="evidence-step">#{{ entry.step }}</span>
          <span class="evidence-type" :class="'type-' + entry.type">{{ entry.type }}</span>
          <span v-if="entry.stage" class="evidence-stage">{{ entry.stage }}</span>
        </div>
        <pre class="evidence-raw">{{ entry.raw }}</pre>
      </div>
      <div v-if="entries.length === 0" class="panel-empty">
        等待模型返回...
      </div>
    </div>
  </div>
</template>

<style scoped>
.evidence-panel {
  display: flex;
  flex-direction: column;
  background: #0d0f14;
  border-radius: 10px;
  border: 1px solid #1e222a;
  overflow: hidden;
  max-height: 240px;
  transition: max-height 0.3s ease;
}
.evidence-panel.collapsed {
  max-height: 38px;
}
.panel-header {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  cursor: pointer;
  border-bottom: 1px solid #1e222a;
  flex-shrink: 0;
  user-select: none;
}
.panel-header:hover { background: #131620; }
.panel-icon { font-size: 12px; color: #a371f7; font-family: monospace; }
.panel-title { font-size: 11px; font-weight: 600; color: #8b949e; }
.panel-count {
  background: #a371f7;
  color: #fff;
  font-size: 9px;
  padding: 1px 6px;
  border-radius: 8px;
  font-weight: 700;
}
.panel-toggle { margin-left: auto; color: #484f58; font-size: 10px; }
.panel-body {
  flex: 1;
  overflow-y: auto;
  padding: 6px;
}
.evidence-entry {
  margin-bottom: 4px;
  padding: 6px 8px;
  background: #111318;
  border-radius: 6px;
  border-left: 2px solid #a371f7;
  animation: slide-in-evidence 0.2s ease;
}
.evidence-meta {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-bottom: 4px;
}
.evidence-step {
  font-size: 9px;
  color: #484f58;
  font-family: 'JetBrains Mono', monospace;
}
.evidence-type {
  font-size: 9px;
  padding: 1px 5px;
  border-radius: 3px;
  font-weight: 600;
}
.type-coordinates { background: #1e3a2f; color: #3fb950; }
.type-action { background: #1e2d3d; color: #58a6ff; }
.type-reasoning { background: #2d2a1e; color: #d29922; }
.evidence-stage {
  font-size: 9px;
  color: #58a6ff;
  font-family: 'JetBrains Mono', monospace;
}
.evidence-raw {
  font-size: 10px;
  color: #7d8590;
  font-family: 'JetBrains Mono', 'SF Mono', monospace;
  line-height: 1.5;
  margin: 0;
  white-space: pre-wrap;
  word-break: break-all;
  max-height: 60px;
  overflow-y: auto;
}
.panel-empty {
  text-align: center;
  padding: 16px;
  color: #484f58;
  font-size: 11px;
}
@keyframes slide-in-evidence {
  from { opacity: 0; transform: translateX(-4px); }
  to { opacity: 1; transform: translateX(0); }
}
</style>
