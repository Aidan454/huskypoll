// Live updates for one course over a WebSocket, with automatic reconnect.
//
//   const stop = connectCourse(courseId, (msg) => { ... })
//   ...
//   stop()
//
// Messages: {type: 'hello'}, {type: 'poll_opened', poll}, {type: 'poll_closed', poll_id},
//           {type: 'results', results}
import { WS_BASE } from './config.js'

export function connectCourse(courseId, onMessage, onStatus = () => {}) {
  let socket = null
  let stopped = false
  let retry = 0
  let timer = null

  function open() {
    socket = new WebSocket(`${WS_BASE}/ws/courses/${courseId}`)
    socket.onopen = () => {
      retry = 0
      onStatus('connected')
    }
    socket.onmessage = (event) => {
      try {
        onMessage(JSON.parse(event.data))
      } catch {
        // ignore anything that isn't JSON
      }
    }
    socket.onclose = (event) => {
      onStatus('disconnected')
      // 4401 = not logged in, 4403 = not in this course: retrying won't help
      if (stopped || event.code === 4401 || event.code === 4403) return
      retry = Math.min(retry + 1, 6)
      timer = setTimeout(open, 500 * 2 ** retry)
    }
  }

  open()
  return () => {
    stopped = true
    clearTimeout(timer)
    socket?.close()
  }
}
