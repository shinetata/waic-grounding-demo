import { ref, shallowRef } from 'vue'

export type DemoEvent = Record<string, any>

export function useWebSocket() {
  const connected = ref(false)
  const events = shallowRef<DemoEvent[]>([])
  const latestEvent = shallowRef<DemoEvent | null>(null)
  const running = ref(false)
  const error = ref<string | null>(null)

  let ws: WebSocket | null = null

  function connect(scene: string) {
    disconnect()
    events.value = []
    latestEvent.value = null
    error.value = null
    running.value = true

    const proto = location.protocol === 'https:' ? 'wss:' : 'ws:'
    const url = `${proto}//${location.host}/ws/run?scene=${scene}`
    ws = new WebSocket(url)

    ws.onopen = () => { connected.value = true }

    ws.onmessage = (e) => {
      try {
        const evt: DemoEvent = JSON.parse(e.data)
        events.value = [...events.value, evt]
        latestEvent.value = evt

        if (evt.type === 'scene_end' || evt.type === 'error') {
          running.value = false
        }
      } catch { /* ignore parse errors */ }
    }

    ws.onerror = () => {
      error.value = 'WebSocket connection error'
      running.value = false
    }

    ws.onclose = () => {
      connected.value = false
      running.value = false
    }
  }

  function disconnect() {
    if (ws) {
      ws.close()
      ws = null
    }
    connected.value = false
    running.value = false
  }

  return { connected, events, latestEvent, running, error, connect, disconnect }
}
