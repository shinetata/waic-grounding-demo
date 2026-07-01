<script setup lang="ts">
import { ref } from 'vue'
import MarketExploreScene from './scenes/MarketExploreScene.vue'

type PlayState = 'playing' | 'paused' | 'stopped'

const playState = ref<PlayState>('stopped')
const sceneRef = ref<InstanceType<typeof MarketExploreScene> | null>(null)

function handleDone() {
  playState.value = 'stopped'
}

function play() {
  playState.value = 'playing'
  sceneRef.value?.start()
}

function pause() {
  playState.value = 'paused'
}

function resume() {
  playState.value = 'playing'
}

function stop() {
  playState.value = 'stopped'
  sceneRef.value?.stop()
}

function restart() {
  playState.value = 'playing'
  sceneRef.value?.start()
}
</script>

<template>
  <div class="app-shell">
    <header class="top-bar">
      <div class="header-left">
        <span class="header-logo">Mactive</span>
        <span class="header-sub">股市探索 · 多模态 Grounding 定位能力展示</span>
      </div>
      <div class="header-right">
        <button
          v-if="playState === 'playing'"
          class="ctrl-btn pause-btn"
          @click="pause"
        >⏸ 暂停</button>
        <button
          v-else-if="playState === 'paused'"
          class="ctrl-btn resume-btn"
          @click="resume"
        >▶ 继续</button>
        <button
          v-else
          class="ctrl-btn play-btn"
          @click="play"
        >▶ 开始</button>
        <button
          class="ctrl-btn stop-btn"
          :disabled="playState === 'stopped'"
          @click="stop"
        >⏹ 停止</button>
        <button class="ctrl-btn restart-btn" @click="restart">↻ 重播</button>
      </div>
    </header>

    <main class="app-main">
      <MarketExploreScene ref="sceneRef" @done="handleDone" />
    </main>
  </div>
</template>

<style scoped>
.app-shell {
  display: flex;
  flex-direction: column;
  height: 100vh;
  background: #0a0c10;
  color: #e0e0e0;
}
.top-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 24px;
  background: #0f1117;
  border-bottom: 1px solid #1e222a;
  flex-shrink: 0;
}
.header-left { display: flex; align-items: center; gap: 12px; }
.header-logo {
  font-size: 16px;
  font-weight: 700;
  background: linear-gradient(135deg, #58a6ff, #a371f7);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
}
.header-sub { font-size: 12px; color: #484f58; }
.header-right { display: flex; align-items: center; gap: 6px; }
.ctrl-btn {
  padding: 6px 14px;
  border: 1px solid #2a2e38;
  border-radius: 6px;
  background: transparent;
  color: #8b949e;
  font-size: 12px;
  cursor: pointer;
  transition: all 0.2s ease;
}
.ctrl-btn:hover:not(:disabled) { border-color: #484f58; color: #e0e0e0; }
.ctrl-btn:disabled { opacity: 0.4; cursor: not-allowed; }
.play-btn, .resume-btn { border-color: #1a5c2a; color: #3fb950; }
.play-btn:hover, .resume-btn:hover { border-color: #2ea043; }
.pause-btn { border-color: #5c4a1a; color: #d29922; }
.pause-btn:hover { border-color: #d29922; }
.stop-btn { border-color: #5c1a1a; color: #f85149; }
.stop-btn:hover:not(:disabled) { border-color: #f85149; }
.app-main {
  flex: 1;
  overflow: hidden;
}
</style>
