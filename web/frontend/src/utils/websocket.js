import { ref, onUnmounted } from 'vue'
import { ElMessage } from 'element-plus'
import { useAuthStore } from '@/stores/auth'

class WebSocketManager {
  constructor() {
    this.ws = null
    this.reconnectAttempts = 0
    this.maxReconnectAttempts = 5
    this.reconnectDelay = 3000
    this.heartbeatInterval = null
    this.isConnecting = false
    this.messageHandlers = new Map()
    this.connectionStatus = ref('disconnected')
  }

  connect(url, token) {
    if (this.isConnecting || (this.ws && this.ws.readyState === WebSocket.OPEN)) {
      return
    }

    this.isConnecting = true
    this.connectionStatus.value = 'connecting'

    try {
      const wsUrl = `${url}?token=${token}`
      this.ws = new WebSocket(wsUrl)

      this.ws.onopen = () => {
        console.log('WebSocket连接成功')
        this.connectionStatus.value = 'connected'
        this.isConnecting = false
        this.reconnectAttempts = 0
        this.startHeartbeat()
      }

      this.ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data)
          this.handleMessage(data)
        } catch (error) {
          console.error('WebSocket消息解析失败:', error)
        }
      }

      this.ws.onerror = (error) => {
        console.error('WebSocket错误:', error)
        this.connectionStatus.value = 'error'
      }

      this.ws.onclose = (event) => {
        console.log('WebSocket连接关闭:', event.code, event.reason)
        this.connectionStatus.value = 'disconnected'
        this.stopHeartbeat()
        this.handleDisconnect()
      }
    } catch (error) {
      console.error('WebSocket连接失败:', error)
      this.connectionStatus.value = 'error'
      this.isConnecting = false
      this.handleDisconnect()
    }
  }

  disconnect() {
    if (this.ws) {
      this.stopHeartbeat()
      this.ws.close(1000, 'Normal closure')
      this.ws = null
      this.connectionStatus.value = 'disconnected'
      this.isConnecting = false
    }
  }

  send(data) {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      try {
        this.ws.send(JSON.stringify(data))
      } catch (error) {
        console.error('WebSocket发送消息失败:', error)
      }
    } else {
      console.warn('WebSocket未连接，无法发送消息')
    }
  }

  on(type, handler) {
    if (!this.messageHandlers.has(type)) {
      this.messageHandlers.set(type, [])
    }
    this.messageHandlers.get(type).push(handler)
  }

  off(type, handler) {
    if (this.messageHandlers.has(type)) {
      const handlers = this.messageHandlers.get(type)
      const index = handlers.indexOf(handler)
      if (index > -1) {
        handlers.splice(index, 1)
      }
    }
  }

  handleMessage(data) {
    const handlers = this.messageHandlers.get(data.type)
    if (handlers) {
      handlers.forEach(handler => {
        try {
          handler(data.data)
        } catch (error) {
          console.error('消息处理器执行失败:', error)
        }
      })
    }
  }

  handleDisconnect() {
    if (this.reconnectAttempts < this.maxReconnectAttempts) {
      this.reconnectAttempts++
      console.log(`尝试重新连接 (${this.reconnectAttempts}/${this.maxReconnectAttempts})...`)
      
      setTimeout(() => {
        const authStore = useAuthStore()
        if (authStore.token) {
          this.connect(this.ws?.url?.split('?')[0], authStore.token)
        }
      }, this.reconnectDelay)
    } else {
      console.error('达到最大重连次数，停止重连')
      ElMessage.error('连接服务器失败，请刷新页面重试')
    }
  }

  startHeartbeat() {
    this.stopHeartbeat()
    
    this.heartbeatInterval = setInterval(() => {
      this.send({ type: 'ping' })
    }, 30000)
  }

  stopHeartbeat() {
    if (this.heartbeatInterval) {
      clearInterval(this.heartbeatInterval)
      this.heartbeatInterval = null
    }
  }

  getStatus() {
    return this.connectionStatus.value
  }

  isConnected() {
    return this.ws && this.ws.readyState === WebSocket.OPEN
  }
}

const websocketManager = new WebSocketManager()

export function useWebSocket() {
  const authStore = useAuthStore()
  
  const connect = () => {
    if (authStore.token) {
      const wsUrl = `ws://localhost:8000/api/v1/ws/notifications`
      websocketManager.connect(wsUrl, authStore.token)
    }
  }

  const disconnect = () => {
    websocketManager.disconnect()
  }

  const send = (data) => {
    websocketManager.send(data)
  }

  const on = (type, handler) => {
    websocketManager.on(type, handler)
  }

  const off = (type, handler) => {
    websocketManager.off(type, handler)
  }

  const getStatus = () => {
    return websocketManager.getStatus()
  }

  const isConnected = () => {
    return websocketManager.isConnected()
  }

  onUnmounted(() => {
    disconnect()
  })

  return {
    connect,
    disconnect,
    send,
    on,
    off,
    getStatus,
    isConnected
  }
}

export default websocketManager
