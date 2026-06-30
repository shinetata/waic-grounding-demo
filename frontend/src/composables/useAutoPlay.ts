import { ref, watch } from 'vue'

export function useAutoPlay(options: {
  scenes: string[]
  intervalMs?: number
  onSwitch: (scene: string) => void
}) {
  const currentIndex = ref(0)
  const paused = ref(false)
  let timer: ReturnType<typeof setTimeout> | null = null
  const interval = options.intervalMs ?? 10000

  function scheduleNext() {
    if (timer) clearTimeout(timer)
    if (paused.value) return
    timer = setTimeout(() => {
      currentIndex.value = (currentIndex.value + 1) % options.scenes.length
      options.onSwitch(options.scenes[currentIndex.value])
    }, interval)
  }

  function restart() {
    currentIndex.value = 0
    options.onSwitch(options.scenes[0])
  }

  function pause() { paused.value = true; if (timer) clearTimeout(timer) }
  function resume() { paused.value = false; scheduleNext() }

  function start() {
    currentIndex.value = 0
    paused.value = false
    options.onSwitch(options.scenes[0])
  }

  return { currentIndex, paused, scheduleNext, restart, pause, resume, start }
}
