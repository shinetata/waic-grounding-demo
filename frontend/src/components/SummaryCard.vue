<script setup lang="ts">
defineProps<{
  scene: 'grounding' | 'navigation'
  totalSteps: number
  findings?: Array<{ finding: string; stage?: string }>
  visited?: string[]
  skipped?: Array<{ id: string; reason: string }>
  groundingCount?: number
}>()
</script>

<template>
  <div class="summary-card" :class="'scene-' + scene">
    <div class="summary-header">
      <span class="summary-icon">{{ scene === 'grounding' ? '🎯' : '🧭' }}</span>
      <span class="summary-title">
        {{ scene === 'grounding' ? '定位完成' : '审计完成' }}
      </span>
    </div>

    <div class="stats-row">
      <div class="stat">
        <div class="stat-value">{{ totalSteps }}</div>
        <div class="stat-label">总步数</div>
      </div>
      <div v-if="groundingCount !== undefined" class="stat">
        <div class="stat-value">{{ groundingCount }}</div>
        <div class="stat-label">精准定位</div>
      </div>
      <div v-if="visited" class="stat">
        <div class="stat-value">{{ visited.length }}</div>
        <div class="stat-label">已访问</div>
      </div>
      <div v-if="skipped" class="stat">
        <div class="stat-value skip">{{ skipped.length }}</div>
        <div class="stat-label">主动跳过</div>
      </div>
    </div>

    <div v-if="findings && findings.length" class="findings-list">
      <div class="findings-title">发现的问题</div>
      <div v-for="(f, i) in findings" :key="i" class="finding-item">
        <span class="finding-bullet">{{ i + 1 }}</span>
        <span class="finding-text">{{ f.finding }}</span>
      </div>
    </div>
  </div>
</template>

<style scoped>
.summary-card {
  background: #111318;
  border: 1px solid #1e222a;
  border-radius: 12px;
  padding: 20px;
  animation: summary-appear 0.5s ease;
}
.summary-header {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 16px;
}
.summary-icon { font-size: 22px; }
.summary-title { font-size: 16px; font-weight: 700; color: #e0e0e0; }
.stats-row {
  display: flex;
  gap: 20px;
  margin-bottom: 16px;
}
.stat { text-align: center; flex: 1; }
.stat-value {
  font-size: 28px;
  font-weight: 700;
  color: #58a6ff;
  font-family: 'JetBrains Mono', monospace;
}
.stat-value.skip { color: #6b7280; }
.stat-label { font-size: 11px; color: #8b949e; margin-top: 2px; }
.findings-list {
  border-top: 1px solid #1e222a;
  padding-top: 12px;
}
.findings-title {
  font-size: 12px;
  font-weight: 600;
  color: #f85149;
  margin-bottom: 8px;
}
.finding-item {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  margin-bottom: 6px;
}
.finding-bullet {
  background: #f85149;
  color: #fff;
  width: 18px;
  height: 18px;
  border-radius: 50%;
  font-size: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: 700;
  flex-shrink: 0;
  margin-top: 1px;
}
.finding-text { font-size: 12px; color: #c0c5d0; line-height: 1.4; }
@keyframes summary-appear {
  from { opacity: 0; transform: translateY(12px); }
  to { opacity: 1; transform: translateY(0); }
}
</style>
