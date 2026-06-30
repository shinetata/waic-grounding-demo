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
        :query-index="g.queryIndex"
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

      <!-- Trajectory lines connecting all bbox centers in sequence -->
      <svg
        v-if="groundings && groundings.length > 1"
        class="connections-svg"
        viewBox="0 0 1 1"
        preserveAspectRatio="none"
      >
        <defs>
          <linearGradient id="traj-grad" x1="0%" y1="0%" x2="100%" y2="0%">
            <stop offset="0%" stop-color="#ef4444" stop-opacity="0.6" />
            <stop offset="50%" stop-color="#f59e0b" stop-opacity="0.8" />
            <stop offset="100%" stop-color="#3b82f6" stop-opacity="0.6" />
          </linearGradient>
          <filter id="glow">
            <feGaussianBlur stdDeviation="0.003" result="blur" />
            <feMerge>
              <feMergeNode in="blur" />
              <feMergeNode in="SourceGraphic" />
            </feMerge>
          </filter>
        </defs>

        <!-- Full trajectory polyline -->
        <polyline
          :points="groundings.map(g => `${(g.bbox[0]+g.bbox[2])/2},${(g.bbox[1]+g.bbox[3])/2}`).join(' ')"
          fill="none"
          stroke="url(#traj-grad)"
          stroke-width="0.003"
          stroke-linecap="round"
          stroke-linejoin="round"
          class="trajectory-line"
          filter="url(#glow)"
        />

        <!-- Same-query dashed connectors -->
        <template v-for="(g, i) in groundings" :key="'line-' + i">
          <line
            v-if="i > 0 && groundings[i - 1].queryIndex === g.queryIndex"
            :x1="(groundings[i-1].bbox[0] + groundings[i-1].bbox[2]) / 2"
            :y1="(groundings[i-1].bbox[1] + groundings[i-1].bbox[3]) / 2"
            :x2="(g.bbox[0] + g.bbox[2]) / 2"
            :y2="(g.bbox[1] + g.bbox[3]) / 2"
            :stroke="['#ef4444', '#f59e0b', '#3b82f6'][g.queryIndex! % 3]"
            stroke-width="0.004"
            stroke-dasharray="0.008 0.004"
            class="connection-line"
            :style="{ animationDelay: `${i * 300 + 200}ms` }"
          />
        </template>

        <!-- Animated dot traversing the trajectory -->
        <circle
          v-if="groundings.length >= 2"
          r="0.008"
          fill="#fff"
          filter="url(#glow)"
          class="trajectory-dot"
        >
          <animateMotion
            :path="`M${groundings.map(g => `${(g.bbox[0]+g.bbox[2])/2} ${(g.bbox[1]+g.bbox[3])/2}`).join(' L')}`"
            dur="3s"
            repeatCount="indefinite"
            calcMode="spline"
            :keySplines="groundings.slice(1).map(() => '0.4 0 0.2 1').join('; ')"
            :keyTimes="groundings.map((_, i) => (i / (groundings!.length - 1)).toFixed(3)).join('; ')"
          />
        </circle>

        <!-- Step number labels at each node -->
        <template v-for="(g, i) in groundings" :key="'node-' + i">
          <circle
            :cx="(g.bbox[0]+g.bbox[2])/2"
            :cy="(g.bbox[1]+g.bbox[3])/2"
            r="0.012"
            :fill="['#ef4444', '#f59e0b', '#3b82f6'][g.queryIndex! % 3]"
            opacity="0.9"
            class="trajectory-node"
            :style="{ animationDelay: `${i * 300}ms` }"
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
.trajectory-line {
  opacity: 0;
  animation: draw-line 1s ease forwards 0.5s;
  stroke-dasharray: 3;
  stroke-dashoffset: 3;
}
@keyframes draw-line {
  to { stroke-dashoffset: 0; opacity: 0.7; }
}
.connection-line {
  opacity: 0;
  animation: fade-in-line 0.4s ease forwards;
}
@keyframes fade-in-line {
  to { opacity: 0.8; }
}
.trajectory-dot {
  opacity: 0;
  animation: fade-in-dot 0.3s ease forwards 1s;
}
@keyframes fade-in-dot {
  to { opacity: 0.9; }
}
.trajectory-node {
  opacity: 0;
  animation: pop-node 0.3s cubic-bezier(0.34, 1.56, 0.64, 1) forwards;
}
@keyframes pop-node {
  from { opacity: 0; r: 0; }
  to { opacity: 0.9; }
}
</style>
