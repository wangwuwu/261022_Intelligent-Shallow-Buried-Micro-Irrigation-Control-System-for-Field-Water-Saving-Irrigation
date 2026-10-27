import { reactive } from 'vue'
import { buildIrrigationIndex } from '../domain/irrigation.js'
import { canOperate } from './permissions.js'
import { IrrigationError, primaryKeys } from './contracts.js'

const emptyEntities = () => Object.fromEntries(Object.keys(primaryKeys).map((kind) => [kind, []]))

function toError(payload, fallbackStatus = 0) {
  if (payload?.code) {
    const error = new IrrigationError(payload.code, payload.message || '请求失败', payload.fieldErrors ?? {}, payload.details ?? {})
    if (payload.requestId) error.requestId = payload.requestId
    error.status = fallbackStatus
    return error
  }
  return new IrrigationError('HTTP_ERROR', payload?.message || '正式数据服务请求失败', {}, { status: fallbackStatus })
}

export function createHttpIrrigationRepository({ baseUrl = import.meta.env?.VITE_API_BASE || '/api/v1', reactiveState = reactive, clock = () => new Date(), EventSourceImpl = globalThis.EventSource } = {}) {
  const state = reactiveState({
    entities: emptyEntities(),
    revision: 0,
    user: null,
    publicFarm: null,
    ready: false,
    error: null,
    channel: 'http',
    readOnly: false,
  })
  let csrfToken = null
  let expiresAt = null
  let indexCache = null
  let indexRevision = -1
  let refreshPromise = null
  let expiryTimer = null
  const subscribers = new Set()
  const seenRevisions = new Set()

  const url = (path) => `${baseUrl.replace(/\/$/, '')}${path}`

  function publish(event, authChanged = false) {
    for (const listener of subscribers) {
      try {
        listener({ revision: state.revision, changedEntities: event?.changedEntities ?? [], authChanged })
      } catch (error) {
        console.error('仓储订阅回调异常', error?.message)
      }
    }
  }

  function armExpiry() {
    if (expiryTimer !== null) clearTimeout(expiryTimer)
    expiryTimer = null
    if (!expiresAt) return
    const delay = Math.max(0, Date.parse(expiresAt) - clock().getTime())
    expiryTimer = setTimeout(() => {
      expiryTimer = null
      clearLocalSession(true)
    }, Math.min(delay, 2147483647))
    expiryTimer?.unref?.()
  }

  function clearLocalSession(notify = false) {
    if (expiryTimer !== null) clearTimeout(expiryTimer)
    expiryTimer = null
    const hadUser = !!state.user
    state.user = null
    state.entities = emptyEntities()
    state.revision = 0
    csrfToken = null
    expiresAt = null
    indexCache = null
    indexRevision = -1
    if (notify && hadUser) publish(null, true)
  }

  async function fetchJson(path, options = {}) {
    const { body, headers, ...rest } = options
    const response = await fetch(url(path), {
      credentials: 'same-origin',
      ...rest,
      headers: {
        Accept: 'application/json',
        ...(body !== undefined ? { 'Content-Type': 'application/json' } : {}),
        ...(headers ?? {}),
      },
      body: body !== undefined ? JSON.stringify(body) : undefined,
    })
    if (response.status === 204) return null
    let payload = null
    try {
      payload = await response.json()
    } catch {
      payload = null
    }
    if (!response.ok) throw toError(payload, response.status)
    return payload
  }

  function applySnapshot(snapshot) {
    if (!snapshot) return state
    state.entities = snapshot.entities ?? emptyEntities()
    state.revision = snapshot.revision ?? 0
    state.user = snapshot.user ?? null
    state.publicFarm = snapshot.publicFarm ?? state.publicFarm
    indexCache = null
    indexRevision = -1
    return state
  }

  async function applySession(payload) {
    state.user = payload.user
    csrfToken = payload.csrfToken
    expiresAt = payload.expiresAt
    state.publicFarm = payload.publicFarm ?? state.publicFarm
    state.revision = payload.revision ?? state.revision
    armExpiry()
  }

  async function refresh() {
    if (!state.user) return state
    if (refreshPromise) return refreshPromise
    refreshPromise = (async () => {
      try {
        const snapshot = await fetchJson('/snapshot')
        applySnapshot(snapshot)
        state.error = null
        return state
      } catch (error) {
        if (error.code === 'UNAUTHENTICATED') {
          clearLocalSession(true)
          return state
        }
        state.error = error
        throw error
      } finally {
        refreshPromise = null
      }
    })()
    return refreshPromise
  }

  async function load() {
    try {
      const bootstrap = await fetchJson('/bootstrap')
      state.publicFarm = bootstrap.publicFarm
      state.revision = bootstrap.revision ?? 0
      let session = null
      try {
        session = await fetchJson('/auth/session')
      } catch (error) {
        if (error.status !== 401 && error.code !== 'UNAUTHENTICATED') throw error
      }
      if (session?.user) {
        await applySession(session)
        await refresh()
      }
      state.error = null
    } catch (error) {
      state.error = error
      clearLocalSession(false)
    } finally {
      state.ready = true
    }
    return state
  }

  async function login(account, password) {
    if (!String(account ?? '').trim() || !password) {
      const error = new IrrigationError('VALIDATION', '请输入账号和密码', {
        account: !String(account ?? '').trim() ? '账号必填' : undefined,
        password: !password ? '密码必填' : undefined,
      })
      throw error
    }
    try {
      const payload = await fetchJson('/auth/login', { method: 'POST', body: { account: String(account).trim(), password } })
      await applySession(payload)
      await refresh()
      state.error = null
      publish(null, true)
      return state.user
    } catch (error) {
      state.error = error
      throw error
    }
  }

  async function logout() {
    try {
      await fetchJson('/auth/logout', { method: 'POST', headers: csrfToken ? { 'X-CSRF-Token': csrfToken } : {} })
    } finally {
      clearLocalSession(true)
      state.error = null
    }
  }

  async function query(name, params = {}, options = {}) {
    if (options.signal?.aborted) throw new DOMException('读取已取消', 'AbortError')
    if (!state.user) throw new IrrigationError('UNAUTHENTICATED', '请先登录')
    try {
      const response = await fetch(url('/query'), {
        method: 'POST',
        credentials: 'same-origin',
        headers: { Accept: 'application/json', 'Content-Type': 'application/json' },
        body: JSON.stringify({ name, params }),
        signal: options.signal,
      })
      const payload = await response.json().catch(() => null)
      if (!response.ok) {
        if (response.status === 401) clearLocalSession(true)
        throw toError(payload, response.status)
      }
      if (payload?.revision !== undefined && payload.revision > state.revision) refresh().catch(() => {})
      return payload
    } catch (error) {
      if (error.name === 'AbortError') throw error
      if (error instanceof IrrigationError) throw error
      const failure = new IrrigationError('NETWORK_ERROR', '无法连接正式数据服务', {}, { cause: error.message })
      state.error = failure
      throw failure
    }
  }

  async function commit(actionId, payload = {}, options = {}) {
    if (!state.user) throw new IrrigationError('UNAUTHENTICATED', '会话已失效，请重新登录')
    const clientRequestId = options.clientRequestId ?? globalThis.crypto?.randomUUID?.()
    try {
      const result = await fetchJson('/commit', {
        method: 'POST',
        headers: {
          'X-CSRF-Token': csrfToken ?? '',
          ...(clientRequestId ? { 'Idempotency-Key': clientRequestId } : {}),
        },
        body: {
          actionId,
          payload,
          options: {
            expectedVersion: options.expectedVersion,
            expectedVersions: options.expectedVersions,
            clientRequestId,
          },
        },
      })
      if (result?.authChanged) {
        clearLocalSession(true)
        return result
      }
      await refresh()
      state.error = null
      return result
    } catch (error) {
      if (error.code === 'UNAUTHENTICATED' || error.status === 401) clearLocalSession(true)
      throw error
    }
  }

  const can = (actionId, entity) => canOperate(state.user, actionId, entity, state.entities)

  const getIndex = () => {
    if (!indexCache || indexRevision !== state.revision) {
      indexCache = buildIrrigationIndex(state.entities, state.revision)
      indexRevision = state.revision
    }
    return indexCache
  }

  function checkSession() {
    if (!state.user) return false
    if (expiresAt && Date.parse(expiresAt) <= clock().getTime()) {
      clearLocalSession(true)
      return false
    }
    return true
  }

  function subscribe(listener) {
    subscribers.add(listener)
    let source = null
    let poll = null
    if (EventSourceImpl) {
      try {
        source = new EventSourceImpl(url('/events'), { withCredentials: true })
        source.addEventListener('revision', async (event) => {
          let payload = null
          try {
            payload = JSON.parse(event.data)
          } catch {}
          const revision = payload?.revision ?? Number(event.lastEventId) ?? 0
          if (seenRevisions.has(revision)) return
          seenRevisions.add(revision)
          if (seenRevisions.size > 500) seenRevisions.delete(seenRevisions.values().next().value)
          try {
            await refresh()
            listener({ revision: state.revision, changedEntities: payload?.changedEntities ?? [], authChanged: !!payload?.authChanged })
          } catch {}
        })
        source.onerror = () => {
          if (!source) return
        }
      } catch {
        source = null
      }
    }
    if (!source) {
      poll = setInterval(() => { refresh().catch(() => {}) }, 15000)
      poll.unref?.()
    }
    return () => {
      subscribers.delete(listener)
      try {
        source?.close()
      } catch {}
      if (poll !== null) clearInterval(poll)
    }
  }

  const backendOnly = async () => {
    throw new IrrigationError('BACKEND_MODE', '正式数据服务模式不支持本机恢复操作')
  }

  return {
    state,
    load,
    login,
    logout,
    refresh,
    query,
    commit,
    subscribe,
    can,
    getIndex,
    checkSession,
    exportCorruptSnapshot: backendOnly,
    recoverInitialSnapshot: backendOnly,
  }
}
