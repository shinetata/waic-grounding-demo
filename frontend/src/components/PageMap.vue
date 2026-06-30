<script setup lang="ts">
import { computed, ref, onMounted, onUnmounted, nextTick, watch } from 'vue'

export interface PageInfo {
  id: string
  title: string
  imageSrc?: string
  status: 'idle' | 'current' | 'visited' | 'skipped'
  skipReason?: string
  order?: number
}

const props = defineProps<{
  pages: PageInfo[]
  navigationPath: Array<{ from: string; to: string }>
}>()

const gridRef = ref<HTMLElement | null>(null)
const nodePositions = ref<Record<string, { x: number; y: number }>>({})

function updatePositions() {
  if (!gridRef.value) return
  const gridRect = gridRef.value.getBoundingClientRect()
  const positions: Record<string, { x: number; y: number }> = {}
  const thumbs = gridRef.value.querySelectorAll('[data-page-id]')
  thumbs.forEach((el) => {
    const id = el.getAttribute('data-page-id')!
    const rect = el.getBoundingClientRect()
    positions[id] = {
      x: rect.left - gridRect.left + rect.width / 2,
      y: rect.top - gridRect.top + rect.height / 2,
    }
  })
  nodePositions.value = positions
}

let resizeObs: ResizeObserver | null = null
onMounted(() => {
  nextTick(updatePositions)
  resizeObs = new ResizeObserver(updatePositions)
  if (gridRef.value) resizeObs.observe(gridRef.value)
})
onUnmounted(() => resizeObs?.disconnect())
watch(() => props.pages, () => nextTick(updatePositions), { deep: true })

const svgSize = computed(() => {
  if (!gridRef.value) return { w: 0, h: 0 }
  return { w: gridRef.value.offsetWidth, h: gridRef.value.offsetHeight }
})

const connectionLines = computed(() => {
  const lines: Array<{ x1: number; y1: number; x2: number; y2: number; index: number }> = []
  props.navigationPath.forEach((nav, i) => {
    const from = nodePositions.value[nav.from]
    const to = nodePositions.value[nav.to]
    if (from && to) lines.push({ x1: from.x, y1: from.y, x2: to.x, y2: to.y, index: i })
  })
  return lines
})
</script>

<template>
  <div class="page-map">
    <div class="map-header">
      <span class="map-icon">🗺️</span>
      <span class="map-title">页面导航</span>
      <span class="map-stats" v-if="navigationPath.length">
        {{ navigationPath.length }} 跳
      </span>
    </div>
    <div class="map-grid-wrapper">
      <div ref="gridRef" class="map-grid">
        <!-- SVG connections overlay -->
        <svg
          v-if="connectionLines.length"
          class="grid-connections"
          :viewBox="`0 0 ${svgSize.w} ${svgSize.h}`"
        >
          <defs>
            <marker id="arrow" markerWidth="6" markerHeight="4" refX="5" refY="2" orient="auto">
              <polygon points="0 0, 6 2, 0 4" fill="#58a6ff" opacity="0.8" />
            </marker>
          </defs>
          <line
            v-for="line in connectionLines"
            :key="'conn-' + line.index"
            :x1="line.x1" :y1="line.y1"
            :x2="line.x2" :y2="line.y2"
            stroke="#58a6ff"
            stroke-width="2"
            stroke-dasharray="4 3"
            marker-end="url(#arrow)"
            class="nav-connection"
            :style="{ animationDelay: `${line.index * 400}ms` }"
          />
        </svg>

        <div
          v-for="page in pages"
          :key="page.id"
          :data-page-id="page.id"
          class="page-thumb"
          :class="page.status"
        >
          <div class="thumb-preview">
            <img
              v-if="page.imageSrc"
              :src="page.imageSrc"
              :alt="page.title"
              class="thumb-img"
            />
            <div v-else class="thumb-placeholder">{{ page.title[0] }}</div>

            <div v-if="page.status === 'visited'" class="thumb-check">✓</div>
            <div v-if="page.status === 'current'" class="thumb-current-badge">当前</div>

            <div v-if="page.status === 'skipped'" class="skip-overlay">
              <div class="skip-line"></div>
              <div class="skip-label">已跳过</div>
            </div>

            <div v-if="page.order" class="visit-order">{{ page.order }}</div>
          </div>
          <div class="thumb-title">{{ page.title }}</div>
          <div v-if="page.skipReason" class="skip-reason">{{ page.skipReason }}</div>
        </div>
      </div>
    </div>

    <div class="path-summary" v-if="navigationPath.length > 0">
      <div class="path-label">导航路径</div>
      <div class="path-line">
        <template v-for="(nav, i) in navigationPath" :key="i">
          <span class="path-node">{{ nav.from }}</span>
          <span class="path-arrow">→</span>
        </template>
        <span class="path-node" v-if="navigationPath.length">
          {{ navigationPath[navigationPath.length - 1].to }}
        </span>
      </div>
    </div>
  </div>
</template>

<style scoped>
.page-map {
  background: #111318;
  border-radius: 12px;
  border: 1px solid #1e222a;
  padding: 12px;
}
.map-header {
  display: flex;
  align-items: center;
  gap: 8px;
  padding-bottom: 10px;
  border-bottom: 1px solid #1e222a;
  margin-bottom: 10px;
}
.map-icon { font-size: 14px; }
.map-title { font-size: 13px; font-weight: 600; color: #e0e0e0; }
.map-stats {
  margin-left: auto;
  font-size: 10px;
  color: #58a6ff;
  background: #1e2d3d;
  padding: 2px 8px;
  border-radius: 8px;
  font-weight: 600;
}
.map-grid-wrapper { position: relative; }
.map-grid {
  position: relative;
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 8px;
}
.grid-connections {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  pointer-events: none;
  z-index: 1;
}
.nav-connection {
  opacity: 0;
  animation: draw-nav 0.5s ease forwards;
}
@keyframes draw-nav {
  to { opacity: 0.7; }
}
.page-thumb {
  text-align: center;
  transition: all 0.4s ease;
}
.page-thumb.skipped {
  opacity: 0.35;
  filter: grayscale(1);
}
.page-thumb.current .thumb-preview {
  border-color: #3b82f6;
  box-shadow: 0 0 12px rgba(59, 130, 246, 0.3);
}
.page-thumb.visited .thumb-preview {
  border-color: #3fb950;
}
.thumb-preview {
  position: relative;
  border-radius: 6px;
  border: 2px solid #2a2e38;
  overflow: hidden;
  aspect-ratio: 4/3;
  background: #1c2028;
  transition: all 0.3s ease;
}
.thumb-img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}
.thumb-placeholder {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 100%;
  font-size: 20px;
  font-weight: 700;
  color: #484f58;
}
.thumb-check {
  position: absolute;
  top: 4px;
  left: 4px;
  background: #3fb950;
  color: #fff;
  width: 18px;
  height: 18px;
  border-radius: 50%;
  font-size: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: 700;
}
.thumb-current-badge {
  position: absolute;
  top: 4px;
  right: 4px;
  background: #3b82f6;
  color: #fff;
  padding: 1px 6px;
  border-radius: 3px;
  font-size: 9px;
  font-weight: 600;
}
.skip-overlay {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(0, 0, 0, 0.4);
  animation: fade-in-skip 0.5s ease;
}
.skip-line {
  position: absolute;
  width: 120%;
  height: 2px;
  background: #ef4444;
  transform: rotate(-25deg);
}
.skip-label {
  position: relative;
  background: #ef4444;
  color: #fff;
  padding: 2px 8px;
  border-radius: 3px;
  font-size: 10px;
  font-weight: 700;
}
.visit-order {
  position: absolute;
  bottom: 4px;
  right: 4px;
  background: rgba(0,0,0,0.7);
  color: #fff;
  width: 18px;
  height: 18px;
  border-radius: 50%;
  font-size: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: 600;
}
.thumb-title {
  font-size: 10px;
  color: #8b949e;
  margin-top: 4px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.skip-reason {
  font-size: 9px;
  color: #ef4444;
  margin-top: 2px;
}
.path-summary {
  margin-top: 10px;
  padding-top: 10px;
  border-top: 1px solid #1e222a;
}
.path-label {
  font-size: 9px;
  color: #484f58;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  margin-bottom: 6px;
}
.path-line {
  display: flex;
  align-items: center;
  gap: 4px;
  flex-wrap: wrap;
  font-size: 10px;
}
.path-node {
  background: #1e2d3d;
  color: #58a6ff;
  padding: 2px 6px;
  border-radius: 3px;
  font-family: 'JetBrains Mono', monospace;
}
.path-arrow { color: #484f58; }
@keyframes fade-in-skip {
  from { opacity: 0; }
  to { opacity: 1; }
}
</style>
