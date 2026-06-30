<script setup lang="ts">
defineProps<{
  query: string
  index: number
  total: number
  active: boolean
}>()
</script>

<template>
  <div class="query-card" :class="{ active }">
    <div class="query-badge">Q{{ index + 1 }}/{{ total }}</div>
    <div class="query-text">{{ query }}</div>
  </div>
</template>

<style scoped>
.query-card {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 16px;
  background: #161a22;
  border: 1px solid #2a2e38;
  border-radius: 10px;
  transition: all 0.3s ease;
}
.query-card.active {
  background: #1a1e2e;
  border-color: #3b82f6;
  box-shadow: 0 0 20px rgba(59, 130, 246, 0.15);
}
.query-badge {
  background: #3b82f6;
  color: #fff;
  padding: 3px 10px;
  border-radius: 12px;
  font-size: 11px;
  font-weight: 700;
  white-space: nowrap;
  flex-shrink: 0;
}
.query-text {
  font-size: 14px;
  color: #e0e0e0;
  line-height: 1.4;
}
</style>
