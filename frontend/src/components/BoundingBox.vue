<script setup lang="ts">
import { computed, ref, onMounted } from 'vue'

const props = withDefaults(defineProps<{
  bbox: number[]
  label?: string
  color?: string
  delay?: number
  queryIndex?: number
}>(), {
  label: '',
  color: '#ef4444',
  delay: 0,
})

const visible = ref(false)
onMounted(() => {
  setTimeout(() => { visible.value = true }, props.delay)
})

const style = computed(() => {
  const [x1, y1, x2, y2] = props.bbox
  return {
    left: `${x1 * 100}%`,
    top: `${y1 * 100}%`,
    width: `${(x2 - x1) * 100}%`,
    height: `${(y2 - y1) * 100}%`,
    borderColor: props.color,
    '--box-color': props.color,
  }
})

const queryLabel = computed(() => {
  if (props.queryIndex !== undefined) return `Q${props.queryIndex + 1}`
  return ''
})
</script>

<template>
  <div class="bbox-wrapper" :class="{ visible }" :style="style">
    <div class="bbox-border"></div>
    <div class="bbox-corner tl"></div>
    <div class="bbox-corner tr"></div>
    <div class="bbox-corner bl"></div>
    <div class="bbox-corner br"></div>
    <div v-if="label || queryLabel" class="bbox-label" :style="{ backgroundColor: color }">
      <span v-if="queryLabel" class="label-prefix">{{ queryLabel }}</span>
      <span v-if="label" class="label-text">{{ label }}</span>
    </div>
  </div>
</template>

<style scoped>
.bbox-wrapper {
  position: absolute;
  pointer-events: none;
  opacity: 0;
  transform: scale(1.1);
  transition: opacity 0.3s ease, transform 0.3s cubic-bezier(0.34, 1.56, 0.64, 1);
}
.bbox-wrapper.visible {
  opacity: 1;
  transform: scale(1);
}
.bbox-border {
  position: absolute;
  inset: 0;
  border: 2px solid var(--box-color, #ef4444);
  border-radius: 4px;
  animation: bbox-pulse 1.5s ease-in-out 2;
  box-shadow: 0 0 12px color-mix(in srgb, var(--box-color) 40%, transparent);
}
.bbox-corner {
  position: absolute;
  width: 8px;
  height: 8px;
  border-color: var(--box-color, #ef4444);
  border-style: solid;
}
.bbox-corner.tl { top: -1px; left: -1px; border-width: 3px 0 0 3px; border-radius: 3px 0 0 0; }
.bbox-corner.tr { top: -1px; right: -1px; border-width: 3px 3px 0 0; border-radius: 0 3px 0 0; }
.bbox-corner.bl { bottom: -1px; left: -1px; border-width: 0 0 3px 3px; border-radius: 0 0 0 3px; }
.bbox-corner.br { bottom: -1px; right: -1px; border-width: 0 3px 3px 0; border-radius: 0 0 3px 0; }
.bbox-label {
  position: absolute;
  bottom: calc(100% + 4px);
  left: 0;
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 2px 8px;
  font-size: 11px;
  font-weight: 600;
  color: #fff;
  border-radius: 4px;
  white-space: nowrap;
  max-width: 280px;
  overflow: hidden;
  text-overflow: ellipsis;
  backdrop-filter: blur(4px);
}
.label-prefix {
  padding: 0 4px;
  background: rgba(255, 255, 255, 0.2);
  border-radius: 3px;
  font-size: 10px;
  font-weight: 800;
  letter-spacing: 0.5px;
}
.label-text {
  overflow: hidden;
  text-overflow: ellipsis;
}
@keyframes bbox-pulse {
  0%, 100% { box-shadow: 0 0 8px color-mix(in srgb, var(--box-color) 30%, transparent); }
  50% { box-shadow: 0 0 20px color-mix(in srgb, var(--box-color) 60%, transparent); }
}
</style>
