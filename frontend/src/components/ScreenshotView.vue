<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import BoundingBox from './BoundingBox.vue'

export interface Grounding {
  bbox: number[]
  label: string
  queryIndex?: number
}

const props = defineProps<{
  imageSrc: string
  groundings?: Grounding[]
  currentRect?: { x: number; y: number; w: number; h: number }
  showViewport?: boolean
}>()

const containerRef = ref<HTMLElement | null>(null)
const imgRef = ref<HTMLImageElement | null>(null)
const imgRect = ref({ left: 0, top: 0, width: 0, height: 0 })

function updateImgRect() {
  if (!imgRef.value || !containerRef.value) return
  const img = imgRef.value
  const container = containerRef.value
  const cRect = container.getBoundingClientRect()

  const naturalW = img.naturalWidth || img.width
  const naturalH = img.naturalHeight || img.height
  if (!naturalW || !naturalH) return

  const containerW = cRect.width
  const containerH = cRect.height
  const scale = Math.min(containerW / naturalW, containerH / naturalH)
  const renderedW = naturalW * scale
  const renderedH = naturalH * scale

  imgRect.value = {
    left: (containerW - renderedW) / 2,
    top: (containerH - renderedH) / 2,
    width: renderedW,
    height: renderedH,
  }
}

let resizeObserver: ResizeObserver | null = null
onMounted(() => {
  resizeObserver = new ResizeObserver(updateImgRect)
  if (containerRef.value) resizeObserver.observe(containerRef.value)
})
onUnmounted(() => { resizeObserver?.disconnect() })

function onImgLoad() { updateImgRect() }

const overlayStyle = computed(() => ({
  left: `${imgRect.value.left}px`,
  top: `${imgRect.value.top}px`,
  width: `${imgRect.value.width}px`,
  height: `${imgRect.value.height}px`,
}))
</script>

<template>
  <div class="screenshot-view" ref="containerRef">
    <img
      ref="imgRef"
      :src="imageSrc"
      alt="Screenshot"
      class="screenshot-img"
      @load="onImgLoad"
    />

    <!-- Overlay positioned exactly over the rendered image area -->
    <div class="bbox-overlay" :style="overlayStyle">
      <BoundingBox
        v-for="(g, i) in (groundings || [])"
        :key="i"
        :bbox="g.bbox"
        :label="g.label"
        :delay="i * 300"
        :color="g.queryIndex !== undefined ? ['#ef4444', '#f59e0b', '#3b82f6'][g.queryIndex % 3] : '#ef4444'"
      />

      <!-- Viewport indicator for navigation -->
      <div
        v-if="showViewport && currentRect && currentRect.w < 0.95"
        class="viewport-rect"
        :style="{
          left: `${currentRect.x * 100}%`,
          top: `${currentRect.y * 100}%`,
          width: `${currentRect.w * 100}%`,
          height: `${currentRect.h * 100}%`,
        }"
      />

      <!-- Connection lines between same-query bboxes -->
      <svg
        v-if="groundings && groundings.length > 1"
        class="connections-svg"
        viewBox="0 0 1 1"
        preserveAspectRatio="none"
      >
        <template v-for="(g, i) in groundings" :key="'line-' + i">
          <line
            v-if="i > 0 && groundings[i - 1].queryIndex === g.queryIndex"
            :x1="(groundings[i-1].bbox[0] + groundings[i-1].bbox[2]) / 2"
            :y1="(groundings[i-1].bbox[1] + groundings[i-1].bbox[3]) / 2"
            :x2="(g.bbox[0] + g.bbox[2]) / 2"
            :y2="(g.bbox[1] + g.bbox[3]) / 2"
            stroke="#f59e0b"
            stroke-width="0.003"
            stroke-dasharray="0.008 0.004"
            class="connection-line"
            :style="{ animationDelay: `${i * 300 + 200}ms` }"
          />
        </template>
      </svg>
    </div>
  </div>
</template>

<style scoped>
.screenshot-view {
  position: relative;
  width: 100%;
  height: 100%;
  overflow: hidden;
}
.screenshot-img {
  display: block;
  width: 100%;
  height: 100%;
  object-fit: contain;
  border-radius: 8px;
}
.bbox-overlay {
  position: absolute;
  pointer-events: none;
  border-radius: 8px;
}
.viewport-rect {
  position: absolute;
  border: 2px solid #ef4444;
  border-radius: 4px;
  animation: pulse-viewport 2s ease-in-out infinite;
}
@keyframes pulse-viewport {
  0%, 100% { opacity: 0.6; }
  50% { opacity: 1; }
}
.connections-svg {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
}
.connection-line {
  opacity: 0;
  animation: fade-in-line 0.4s ease forwards;
}
@keyframes fade-in-line {
  to { opacity: 0.8; }
}
</style>
