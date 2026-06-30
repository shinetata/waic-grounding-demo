<script setup lang="ts">
import { ref, onMounted } from 'vue'
import GroundingScene from './scenes/GroundingScene.vue'
import NavigationScene from './scenes/NavigationScene.vue'

type Scene = 'grounding' | 'navigation'

const currentScene = ref<Scene>('grounding')
const groundingRef = ref<InstanceType<typeof GroundingScene> | null>(null)
const navigationRef = ref<InstanceType<typeof NavigationScene> | null>(null)

function switchScene(scene: Scene) {
  currentScene.value = scene
  setTimeout(() => {
    if (scene === 'grounding') groundingRef.value?.start()
    else navigationRef.value?.start()
  }, 300)
}

function handleDone() {
  const next: Scene = currentScene.value === 'grounding' ? 'navigation' : 'grounding'
  switchScene(next)
}

function restart() {
  if (currentScene.value === 'grounding') groundingRef.value?.start()
  else navigationRef.value?.start()
}

onMounted(() => {
  switchScene('grounding')
})
</script>

<template>
  <div class="app-shell">
    <header class="app-header">
      <div class="header-left">
        <span class="header-logo">Active Grounding</span>
        <span class="header-sub">认知基模 · 视觉定位能力展示</span>
      </div>
      <div class="header-center">
        <button
          class="scene-tab"
          :class="{ active: currentScene === 'grounding' }"
          @click="switchScene('grounding')"
        >
          🎯 一眼定位
        </button>
        <button
          class="scene-tab"
          :class="{ active: currentScene === 'navigation' }"
          @click="switchScene('navigation')"
        >
          🧭 认知导航
        </button>
      </div>
      <div class="header-right">
        <button class="restart-btn" @click="restart">↻ 重新开始</button>
      </div>
    </header>

    <main class="app-main">
      <GroundingScene
        v-show="currentScene === 'grounding'"
        ref="groundingRef"
        @done="handleDone"
      />
      <NavigationScene
        v-show="currentScene === 'navigation'"
        ref="navigationRef"
        @done="handleDone"
      />
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
.app-header {
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
.header-center { display: flex; gap: 4px; }
.scene-tab {
  padding: 6px 16px;
  border: 1px solid #2a2e38;
  border-radius: 8px;
  background: transparent;
  color: #8b949e;
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s ease;
}
.scene-tab:hover { border-color: #484f58; color: #e0e0e0; }
.scene-tab.active {
  background: #161a22;
  border-color: #58a6ff;
  color: #e0e0e0;
}
.header-right { display: flex; align-items: center; }
.restart-btn {
  padding: 6px 14px;
  border: 1px solid #2a2e38;
  border-radius: 6px;
  background: transparent;
  color: #8b949e;
  font-size: 12px;
  cursor: pointer;
  transition: all 0.2s ease;
}
.restart-btn:hover { border-color: #484f58; color: #e0e0e0; }
.app-main {
  flex: 1;
  overflow: hidden;
}
</style>
