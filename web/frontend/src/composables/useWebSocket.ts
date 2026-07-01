import { ref, shallowRef } from 'vue'

export type DemoEvent = Record<string, any>

const COMMAND_TYPES = new Set(['observe', 'execute', 'query_rect'])

export function useWebSocket() {
  const connected = ref(false)
  const events = shallowRef<DemoEvent[]>([])
  const latestEvent = shallowRef<DemoEvent | null>(null)
  const running = ref(false)
  const error = ref<string | null>(null)

  let ws: WebSocket | null = null
  let commandHandler: ((msg: DemoEvent) => void) | null = null

  function onCommand(handler: (msg: DemoEvent) => void) {
    commandHandler = handler
  }

  function send(data: object) {
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify(data))
    }
  }

  function connect() {
    disconnect()
    events.value = []
    latestEvent.value = null
    error.value = null
    running.value = true

    const proto = location.protocol === 'https:' ? 'wss:' : 'ws:'
    const url = `${proto}//${location.host}/ws/run`
    ws = new WebSocket(url)

    ws.onopen = () => { connected.value = true }

    ws.onmessage = (e) => {
      try {
        const evt: DemoEvent = JSON.parse(e.data)

        if (COMMAND_TYPES.has(evt.type)) {
          commandHandler?.(evt)
          return
        }

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
    commandHandler = null
  }

  return { connected, events, latestEvent, running, error, connect, disconnect, send, onCommand }
}
