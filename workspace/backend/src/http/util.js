import { AppError } from '../errors.js'

export const API_PREFIX = '/api/v1'

export function sendJson(res, status, payload, headers = {}) {
  const body = JSON.stringify(payload)
  res.writeHead(status, {
    'Content-Type': 'application/json; charset=utf-8',
    'Content-Length': Buffer.byteLength(body),
    'Cache-Control': 'no-store',
    ...headers,
  })
  res.end(body)
}

export function sendEmpty(res, status = 204, headers = {}) {
  res.writeHead(status, { 'Cache-Control': 'no-store', ...headers })
  res.end()
}

export async function readBody(req, limit = 2 * 1024 * 1024) {
  const chunks = []
  let size = 0
  for await (const chunk of req) {
    size += chunk.length
    if (size > limit) throw new AppError('BODY_TOO_LARGE', '请求内容超过限制', { status: 413 })
    chunks.push(chunk)
  }
  if (!chunks.length) return {}
  const text = Buffer.concat(chunks).toString('utf8')
  try {
    return JSON.parse(text)
  } catch {
    throw new AppError('INVALID_JSON', '请求体不是有效 JSON', { status: 400 })
  }
}

export function parseCookies(header) {
  const cookies = new Map()
  if (!header) return cookies
  for (const part of String(header).split(';')) {
    const index = part.indexOf('=')
    if (index < 0) continue
    cookies.set(part.slice(0, index).trim(), decodeURIComponent(part.slice(index + 1).trim()))
  }
  return cookies
}

export function checkOrigin(req, config) {
  if (!['POST', 'PUT', 'PATCH', 'DELETE'].includes(req.method)) return
  const origin = req.headers.origin
  if (!origin) return
  const forwardedProto = config.trustProxy ? req.headers['x-forwarded-proto'] : null
  const proto = forwardedProto?.split(',')[0]?.trim() || (req.socket.encrypted ? 'https' : 'http')
  const expected = `${proto}://${req.headers.host}`
  const allowed = new Set([expected, ...(config.allowedOrigins ?? [])])
  if (!allowed.has(origin)) throw new AppError('ORIGIN_REJECTED', '请求来源与当前站点不一致', { status: 403 })
}

export function requireCsrf(req, session) {
  if (!['POST', 'PUT', 'PATCH', 'DELETE'].includes(req.method)) return
  const token = req.headers['x-csrf-token']
  if (!token || !session?.csrfToken || token !== session.csrfToken) {
    throw new AppError('CSRF_FAILED', '请求缺少有效的防跨站令牌，请刷新会话后重试', { status: 403 })
  }
}

export function expectedVersionFrom(req, body = {}) {
  const header = req.headers['if-match']
  if (header) {
    const normalized = String(header).replace(/^W\//, '').replaceAll('"', '').trim()
    if (/^\d+$/.test(normalized)) return Number(normalized)
  }
  if (body.expectedVersion !== undefined) return Number(body.expectedVersion)
  return undefined
}

export function queryParams(url, extraFilters = {}) {
  const params = {}
  const filters = { ...extraFilters }
  for (const [key, value] of url.searchParams) {
    if (key === 'filters') {
      try {
        Object.assign(filters, JSON.parse(value))
      } catch {
        throw new AppError('INVALID_QUERY', 'filters 不是有效 JSON', { status: 400 })
      }
    } else if (key === 'filtersJson') {
      try {
        Object.assign(filters, JSON.parse(value))
      } catch {
        throw new AppError('INVALID_QUERY', 'filtersJson 不是有效 JSON', { status: 400 })
      }
    } else if (['page', 'pageSize'].includes(key)) {
      params[key] = Number(value)
    } else if (['id', 'sortBy', 'sortDirection', 'asOf', 'date'].includes(key)) {
      params[key] = value
    } else {
      filters[key] = value
    }
  }
  params.filters = filters
  return params
}

export function compactFilters(params) {
  const filters = Object.fromEntries(Object.entries(params.filters ?? {}).filter(([, value]) => value !== undefined && value !== null && value !== ''))
  return { ...params, filters }
}

export function csvContentDisposition(fileName) {
  const ascii = fileName.replace(/[^\x20-\x7e]/g, '_').replaceAll('"', "'")
  return `attachment; filename="${ascii}"; filename*=UTF-8''${encodeURIComponent(fileName)}`
}

const localTimeKeys = new Set(['scheduledAt', 'asOf', 'dueAt', 'startAt', 'endAt', 'from', 'to', 'observedAt'])
const localTimePattern = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(:\d{2})?$/

export function normalizeLocalTimes(value, key = null) {
  if (Array.isArray(value)) return value.map((item) => normalizeLocalTimes(item, key))
  if (value && typeof value === 'object') {
    return Object.fromEntries(Object.entries(value).map(([childKey, child]) => [childKey, normalizeLocalTimes(child, childKey)]))
  }
  if (typeof value === 'string' && localTimeKeys.has(key) && localTimePattern.test(value)) return `${value}+08:00`
  return value
}
