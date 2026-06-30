<script setup lang="ts">
defineProps<{
  steps: Array<{
    label: string
    status: 'idle' | 'active' | 'done'
  }>
}>()
</script>

<template>
  <div class="scene-progress">
    <div
      v-for="(step, i) in steps"
      :key="i"
      class="progress-node"
      :class="step.status"
    >
      <div class="node-dot">
        <div v-if="step.status === 'active'" class="dot-pulse"></div>
      </div>
      <span class="node-label">{{ step.label }}</span>
      <div v-if="i < steps.length - 1" class="node-connector" :class="{ filled: step.status === 'done' }"></div>
    </div>
  </div>
</template>

<style scoped>
.scene-progress {
  display: flex;
  flex-direction: column;
  padding: 10px;
  background: #0d0f14;
  border-radius: 10px;
  border: 1px solid #1e222a;
  gap: 4px;
  flex-shrink: 0;
}
.progress-node {
  display: flex;
  align-items: center;
  gap: 8px;
  position: relative;
}
.node-dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  background: #2a2e38;
  border: 2px solid #3a3f4a;
  position: relative;
  transition: all 0.4s ease;
  flex-shrink: 0;
}
.progress-node.active .node-dot {
  background: #3b82f6;
  border-color: #58a6ff;
  box-shadow: 0 0 10px rgba(59, 130, 246, 0.5);
}
.progress-node.done .node-dot {
  background: #3fb950;
  border-color: #56d364;
}
.dot-pulse {
  position: absolute;
  inset: -4px;
  border-radius: 50%;
  border: 2px solid #3b82f6;
  animation: pulse-ring 1.5s ease-out infinite;
}
.node-label {
  font-size: 11px;
  color: #484f58;
  white-space: nowrap;
  transition: color 0.3s ease;
}
.progress-node.active .node-label { color: #e0e0e0; font-weight: 600; }
.progress-node.done .node-label { color: #3fb950; }
.node-connector {
  display: none;
}
@keyframes pulse-ring {
  0% { transform: scale(1); opacity: 0.8; }
  100% { transform: scale(1.8); opacity: 0; }
}
</style>
