<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{
  queryIndex: number
  query: string
  answer: Record<string, string>
  fields?: string[]
  sourceStageTitle?: string
}>()

const rows = computed(() => {
  const keys = props.fields?.length ? props.fields : Object.keys(props.answer || {})
  return keys.map((k) => ({ key: k, value: props.answer?.[k] ?? '—' }))
})
</script>

<template>
  <div class="answer-card">
    <div class="answer-header">
      <span class="answer-badge">Q{{ queryIndex + 1 }} 答案</span>
      <span v-if="sourceStageTitle" class="answer-source">来源：{{ sourceStageTitle }}</span>
    </div>
    <div class="answer-query">{{ query }}</div>
    <div class="answer-fields">
      <div v-for="row in rows" :key="row.key" class="answer-field">
        <span class="field-label">{{ row.key }}</span>
        <span class="field-value">{{ row.value }}</span>
      </div>
    </div>
  </div>
</template>

<style scoped>
.answer-card {
  background: linear-gradient(135deg, #132018, #111318);
  border: 1px solid #1e3a2f;
  border-radius: 10px;
  padding: 12px 14px;
  animation: answer-appear 0.4s cubic-bezier(0.34, 1.56, 0.64, 1);
}
.answer-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 6px;
}
.answer-badge {
  background: #3fb950;
  color: #06280f;
  font-size: 10.5px;
  font-weight: 800;
  padding: 2px 9px;
  border-radius: 10px;
  letter-spacing: 0.3px;
}
.answer-source {
  font-size: 10.5px;
  color: #58a6ff;
  margin-left: auto;
}
.answer-query {
  font-size: 11.5px;
  color: #8b949e;
  line-height: 1.4;
  margin-bottom: 10px;
  padding-bottom: 8px;
  border-bottom: 1px dashed #1e3a2f;
}
.answer-fields {
  display: flex;
  flex-direction: column;
  gap: 5px;
}
.answer-field {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 10px;
  font-size: 12.5px;
}
.field-label { color: #6b9c7f; flex-shrink: 0; }
.field-value {
  color: #e6ffee;
  font-weight: 700;
  font-family: 'JetBrains Mono', 'Inter', monospace;
  text-align: right;
}
@keyframes answer-appear {
  from { opacity: 0; transform: translateY(10px) scale(0.98); }
  to { opacity: 1; transform: translateY(0) scale(1); }
}
</style>
