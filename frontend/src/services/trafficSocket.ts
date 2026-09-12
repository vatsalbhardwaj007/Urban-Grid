import { backendConfig } from '../config/backend'
import { parseWebSocketMessage } from '../types/traffic'

type Handlers = { onOpen: () => void; onUpdate: (raw: unknown) => void; onPong: () => void; onMalformed: () => void; onClose: () => void; onError: () => void }

/** Thin transport wrapper: canonical parsing remains in the store. */
export function openTrafficSocket(handlers: Handlers) {
  const socket = new WebSocket(backendConfig.wsUrl)
  socket.onopen = handlers.onOpen
  socket.onerror = handlers.onError
  socket.onclose = handlers.onClose
  socket.onmessage = (message) => {
    try {
      const parsed = parseWebSocketMessage(JSON.parse(String(message.data)))
      if (!parsed) { handlers.onMalformed(); return }
      if (parsed.event === 'traffic.update') handlers.onUpdate(parsed.data)
      else handlers.onPong()
    } catch { handlers.onMalformed() }
  }
  return socket
}
