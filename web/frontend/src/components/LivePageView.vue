<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, watch, nextTick } from 'vue'
import html2canvas from 'html2canvas'
import BoundingBox from './BoundingBox.vue'

export interface Grounding {
  bbox: number[]
  label: string
  queryIndex?: number
}

const props = defineProps<{
  pageId: string
  groundings?: Grounding[]
  currentRect?: { x: number; y: number; w: number; h: number }
  showViewport?: boolean
  locked?: boolean
}>()

const NATIVE_WIDTH = 1680

const wrapperRef = ref<HTMLElement | null>(null)
const iframeRef = ref<HTMLIFrameElement | null>(null)
const scale = ref(1)
const iframeHeight = ref(1200)
const iframeReady = ref(false)
const ripple = ref<{ x: number; y: number; visible: boolean }>({ x: 0, y: 0, visible: false })

function updateScale() {
  if (!wrapperRef.value) return
  const containerW = wrapperRef.value.clientWidth
  scale.value = containerW / NATIVE_WIDTH
}

let resizeObs: ResizeObserver | null = null
onMounted(() => {
  resizeObs = new ResizeObserver(updateScale)
  if (wrapperRef.value) resizeObs.observe(wrapperRef.value)
  updateScale()
})
onUnmounted(() => resizeObs?.disconnect())

watch(() => props.pageId, (newId) => {
  if (!iframeRef.value || !newId) return
  iframeReady.value = false
  iframeRef.value.src = `/site/${newId}.html`
})

function onIframeLoad() {
  iframeReady.value = true
  syncIframeHeight()
  flushWaiters()
}

let readyWaiters: Array<() => void> = []
function flushWaiters() {
  const list = readyWaiters.splice(0)
  list.forEach((r) => r())
}

async function waitForReady(): Promise<void> {
  if (iframeReady.value && iframeRef.value?.contentDocument?.body) return
  await new Promise<void>((resolve) => { readyWaiters.push(resolve) })
}

function syncIframeHeight() {
  const doc = iframeRef.value?.contentDocument
  if (!doc) return
  const h = doc.documentElement.scrollHeight || 1200
  iframeHeight.value = h
}

const scaledHeight = computed(() => iframeHeight.value * scale.value)


const containerStyle = computed(() => {
  const s = scale.value
  return {
    width: '100%',
    height: `${iframeHeight.value * s}px`,
    overflow: 'hidden' as const,
  }
})

const iframeStyle = computed(() => {
  const s = scale.value
  return {
    width: `${NATIVE_WIDTH}px`,
    height: `${iframeHeight.value}px`,
    transform: `scale(${s})`,
    transformOrigin: 'top left',
  }
})

// ---- Screenshot capture ----

async function captureScreenshot(): Promise<string> {
  await waitForReady()
  const doc = iframeRef.value?.contentDocument
  if (!doc?.body) return ''
  syncIframeHeight()
  try {
    const canvas = await html2canvas(doc.body, {
      width: doc.documentElement.scrollWidth,
      height: doc.documentElement.scrollHeight,
      scale: 2,
      useCORS: true,
      logging: false,
      backgroundColor: '#eef1f5',
    })
    const dataUrl = canvas.toDataURL('image/png')
    return dataUrl.replace(/^data:image\/png;base64,/, '')
  } catch (err) {
    console.error('html2canvas failed:', err)
    return ''
  }
}

function getDocSize(): { w: number; h: number } {
  const doc = iframeRef.value?.contentDocument
  if (!doc) return { w: NATIVE_WIDTH, h: 1200 }
  return {
    w: doc.documentElement.scrollWidth || NATIVE_WIDTH,
    h: doc.documentElement.scrollHeight || 1200,
  }
}

// ---- Action execution ----

function showRipple(elementId: string) {
  const doc = iframeRef.value?.contentDocument
  if (!doc) return
  const el = doc.getElementById(elementId)
  if (!el) return
  const rect = el.getBoundingClientRect()
  const docW = doc.documentElement.scrollWidth || NATIVE_WIDTH
  const docH = doc.documentElement.scrollHeight || 1200
  ripple.value = {
    x: ((rect.left + rect.width / 2) / docW) * 100,
    y: ((rect.top + rect.height / 2) / docH) * 100,
    visible: true,
  }
  setTimeout(() => { ripple.value.visible = false }, 800)
}

async function executeSort(elementId: string, direction?: string | null) {
  const doc = iframeRef.value?.contentDocument
  if (!doc) return
  const th = doc.getElementById(elementId)
  if (!th) return
  showRipple(elementId)
  th.click()
  if (direction === 'asc' || direction === 'desc') {
    await nextTick()
    const currentDir = th.getAttribute('data-dir')
    if (currentDir !== direction) {
      th.click()
    }
  }
  syncIframeHeight()
}

async function executeFilter(elementId: string) {
  const doc = iframeRef.value?.contentDocument
  if (!doc) return
  const chip = doc.getElementById(elementId)
  if (!chip) return
  showRipple(elementId)
  chip.click()
  syncIframeHeight()
}

async function executeNavigate(pageId: string) {
  if (!iframeRef.value) return
  const currentSrc = iframeRef.value.src
  const targetPath = `/site/${pageId}.html`
  const alreadyLoaded = currentSrc.endsWith(targetPath) && iframeReady.value
  if (alreadyLoaded) {
    syncIframeHeight()
    return
  }
  iframeReady.value = false
  iframeRef.value.src = targetPath
  await waitForReady()
}

function getElementRect(elementId: string): { x: number; y: number; w: number; h: number } | null {
  const doc = iframeRef.value?.contentDocument
  if (!doc) return null
  const el = doc.getElementById(elementId)
  if (!el) return null
  const box = el.getBoundingClientRect()
  if (!box || (box.width === 0 && box.height === 0)) return null
  const docW = doc.documentElement.scrollWidth || NATIVE_WIDTH
  const docH = doc.documentElement.scrollHeight || 1200
  return {
    x: box.left / docW,
    y: box.top / docH,
    w: box.width / docW,
    h: box.height / docH,
  }
}

defineExpose({
  captureScreenshot,
  executeSort,
  executeFilter,
  executeNavigate,
  getElementRect,
  getDocSize,
  waitForReady,
  get ready() { return iframeReady.value },
})
</script>

<template>
  <div class="live-page-view" ref="wrapperRef">
    <div class="iframe-container" :style="containerStyle">
      <iframe
        ref="iframeRef"
        :src="`/site/${pageId}.html`"
        :style="iframeStyle"
        class="live-iframe"
        @load="onIframeLoad"
      />
    </div>

    <!-- Grounding overlay -->
    <div class="bbox-overlay">
      <BoundingBox
        v-for="(g, i) in (groundings || [])"
        :key="i"
        :bbox="g.bbox"
        :label="g.label"
        :delay="i * 300"
        :color="g.queryIndex !== undefined ? ['#ef4444', '#f59e0b', '#3b82f6'][g.queryIndex % 3] : '#ef4444'"
        :query-index="g.queryIndex"
      />

      <!-- Viewport indicator for zoom -->
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

      <!-- Trajectory lines -->
      <svg
        v-if="groundings && groundings.length > 1"
        class="connections-svg"
        viewBox="0 0 1 1"
        preserveAspectRatio="none"
      >
        <defs>
          <linearGradient id="traj-grad-live" x1="0%" y1="0%" x2="100%" y2="0%">
            <stop offset="0%" stop-color="#ef4444" stop-opacity="0.6" />
            <stop offset="50%" stop-color="#f59e0b" stop-opacity="0.8" />
            <stop offset="100%" stop-color="#3b82f6" stop-opacity="0.6" />
          </linearGradient>
          <filter id="glow-live">
            <feGaussianBlur stdDeviation="0.003" result="blur" />
            <feMerge>
              <feMergeNode in="blur" />
              <feMergeNode in="SourceGraphic" />
            </feMerge>
          </filter>
        </defs>
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

      <!-- Click ripple animation -->
      <div
        v-if="ripple.visible"
        class="click-ripple"
        :style="{ left: `${ripple.x}%`, top: `${ripple.y}%` }"
      />
    </div>

    <!-- Interaction lock during AI run -->
    <div v-if="locked" class="interaction-lock">
      <div class="lock-badge">AI 操控中</div>
    </div>
  </div>
</template>

<style scoped>
.live-page-view {
  position: relative;
  width: 100%;
  overflow: hidden;
  background: #0d0f14;
  border-radius: 10px;
  border: 1px solid #1e222a;
}
.iframe-container {
  border-radius: 8px;
}
.live-iframe {
  display: block;
  border: none;
}
.bbox-overlay {
  position: absolute;
  inset: 0;
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
.trajectory-node {
  opacity: 0;
  animation: pop-node 0.3s cubic-bezier(0.34, 1.56, 0.64, 1) forwards;
}
@keyframes pop-node {
  from { opacity: 0; r: 0; }
  to { opacity: 0.9; }
}
.click-ripple {
  position: absolute;
  width: 24px;
  height: 24px;
  margin-left: -12px;
  margin-top: -12px;
  border-radius: 50%;
  background: rgba(59, 130, 246, 0.4);
  pointer-events: none;
  animation: ripple-out 0.8s ease-out forwards;
}
@keyframes ripple-out {
  0% { transform: scale(0.5); opacity: 1; box-shadow: 0 0 0 0 rgba(59, 130, 246, 0.5); }
  100% { transform: scale(3); opacity: 0; box-shadow: 0 0 0 12px rgba(59, 130, 246, 0); }
}
.interaction-lock {
  position: absolute;
  inset: 0;
  z-index: 10;
  cursor: not-allowed;
}
.lock-badge {
  position: absolute;
  top: 8px;
  right: 8px;
  background: rgba(59, 130, 246, 0.85);
  color: #fff;
  padding: 3px 10px;
  border-radius: 6px;
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 0.5px;
  backdrop-filter: blur(4px);
  animation: pulse-lock 2s ease-in-out infinite;
}
@keyframes pulse-lock {
  0%, 100% { opacity: 0.8; }
  50% { opacity: 1; }
}
</style>
