<script setup lang="ts">
interface IndexQuote {
  name: string
  value: string
  change: string
  up: boolean
}

const indices: IndexQuote[] = [
  { name: '上证指数', value: '3421.58', change: '▲0.86%', up: true },
  { name: '深证成指', value: '11024.30', change: '▲0.52%', up: true },
  { name: '创业板指', value: '2298.71', change: '▲1.24%', up: true },
  { name: '科创50', value: '1456.92', change: '▲2.15%', up: true },
]

defineProps<{
  currentPage?: string
}>()
</script>

<template>
  <div class="stock-header">
    <div class="brand-block">
      <span class="brand-icon">📊</span>
      <div class="brand-text">
        <div class="brand-title">股票信息寻宝</div>
        <div class="brand-sub">跨页面信息整合能力展示</div>
      </div>
    </div>
    <div class="ticker-block">
      <div v-for="idx in indices" :key="idx.name" class="ticker-item">
        <span class="ticker-name">{{ idx.name }}</span>
        <span class="ticker-value">{{ idx.value }}</span>
        <span class="ticker-change" :class="idx.up ? 'up' : 'down'">{{ idx.change }}</span>
      </div>
    </div>
  </div>
</template>

<style scoped>
.stock-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 16px;
  background: #111318;
  border: 1px solid #1e222a;
  border-radius: 10px;
  flex-shrink: 0;
  gap: 16px;
}
.brand-block {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-shrink: 0;
}
.brand-icon { font-size: 18px; }
.brand-text { line-height: 1.25; }
.brand-title { font-size: 13px; font-weight: 700; color: #e0e0e0; }
.brand-sub { font-size: 10.5px; color: #484f58; }
.ticker-block {
  display: flex;
  gap: 18px;
  flex-wrap: wrap;
  justify-content: flex-end;
}
.ticker-item {
  display: flex;
  align-items: baseline;
  gap: 4px;
  font-size: 12px;
}
.ticker-name { color: #8b949e; }
.ticker-value {
  color: #e0e0e0;
  font-weight: 600;
  font-family: 'JetBrains Mono', monospace;
}
.ticker-change { font-family: 'JetBrains Mono', monospace; font-weight: 600; }
.ticker-change.up { color: #f85149; }
.ticker-change.down { color: #3fb950; }
</style>
