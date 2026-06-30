<script setup lang="ts">
import { computed, ref, onMounted } from 'vue'

const props = withDefaults(defineProps<{
  bbox: number[]
  label?: string
  color?: string
  delay?: number
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
</script>

<template>
  <div class="bbox-wrapper" :class="{ visible }" :style="style">
    <div class="bbox-border"></div>
    <div v-if="label" class="bbox-label" :style="{ backgroundColor: color }">
      {{ label }}
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
.bbox-label {
  position: absolute;
  bottom: calc(100% + 4px);
  left: 0;
  padding: 2px 8px;
  font-size: 11px;
  font-weight: 600;
  color: #fff;
  border-radius: 4px;
  white-space: nowrap;
  max-width: 280px;
  overflow: hidden;
  text-overflow: ellipsis;
}
@keyframes bbox-pulse {
  0%, 100% { box-shadow: 0 0 8px color-mix(in srgb, var(--box-color) 30%, transparent); }
  50% { box-shadow: 0 0 20px color-mix(in srgb, var(--box-color) 60%, transparent); }
}
</style>
