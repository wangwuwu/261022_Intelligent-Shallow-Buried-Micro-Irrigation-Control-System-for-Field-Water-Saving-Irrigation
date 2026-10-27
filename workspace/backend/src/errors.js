import { randomUUID } from 'node:crypto'

export class AppError extends Error {
  constructor(code, message, { status = 400, fieldErrors = {}, details = {}, requestId } = {}) {
    super(message)
    this.name = 'AppError'
    this.code = code
    this.status = status
    this.fieldErrors = fieldErrors
    this.details = details
    this.requestId = requestId || randomUUID()
  }
}

const statusByCode = new Map([
  ['UNAUTHENTICATED', 401],
  ['AUTH_FAILED', 401],
  ['CSRF_FAILED', 403],
  ['ORIGIN_REJECTED', 403],
  ['FORBIDDEN', 403],
  ['NOT_FOUND', 404],
  ['QUERY_UNSUPPORTED', 400],
  ['VALIDATION', 422],
  ['CONFIRMATION_REQUIRED', 400],
  ['VERSION_CONFLICT', 409],
  ['RESOURCE_CONFLICT', 409],
  ['RESOURCE_CHANGED', 409],
  ['DUPLICATE_ID', 409],
  ['IDEMPOTENCY_CONFLICT', 409],
  ['ACTIVE_REFERENCE', 409],
  ['ACTIVE_SEASON', 409],
  ['ALARM_STATE', 409],
  ['ALARM_NOT_RECOVERED', 409],
  ['WORKORDER_STATE', 409],
  ['WORKORDER_NOT_ACCEPTED', 409],
  ['DUPLICATE_WORKORDER', 409],
  ['PLAN_LOCKED', 409],
  ['PLAN_ALREADY_STARTED', 409],
  ['SCHEDULE_EXPIRED', 409],
  ['RUN_EXISTS', 409],
  ['EXPORT_STATE', 409],
  ['EXPORT_WINDOW', 422],
  ['EXPORT_UNAVAILABLE', 410],
  ['LAST_ADMIN', 409],
  ['CURRENT_USER', 409],
  ['VALVE_OCCUPIED', 409],
  ['SUPPLY_CYCLE', 409],
  ['ADAPTER_UNAVAILABLE', 503],
  ['CAPABILITY_UNVERIFIED', 503],
  ['STORAGE_UNAVAILABLE', 503],
  ['STORAGE_FAILED', 503],
  ['STORAGE_CORRUPT', 500],
  ['STORAGE_SCHEMA', 500],
])

export function toAppError(error, requestId) {
  if (error instanceof AppError) {
    if (!error.requestId) error.requestId = requestId
    return error
  }
  const code = error?.code || 'INTERNAL_ERROR'
  const status = statusByCode.get(code) || 500
  return new AppError(code, error?.message || '服务处理失败', {
    status,
    fieldErrors: error?.fieldErrors || {},
    details: error?.details || {},
    requestId: error?.requestId || requestId,
  })
}

export function errorPayload(error, requestId) {
  const normalized = toAppError(error, requestId)
  return {
    code: normalized.code,
    message: normalized.message,
    fieldErrors: normalized.fieldErrors || {},
    details: normalized.details || {},
    requestId: normalized.requestId,
  }
}
