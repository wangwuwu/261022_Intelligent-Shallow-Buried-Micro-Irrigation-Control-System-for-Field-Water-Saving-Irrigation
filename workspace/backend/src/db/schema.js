import { entityTables } from './entities.js'

const numericColumns = new Set([
  'version',
  'area_mu',
  'capacity_m3h',
  'depth_cm',
  'step_order',
  'target_volume_m3',
  'volume_m3',
  'reference_area_mu',
  'reference_volume_m3',
  'reference_value',
  'measured_value',
])
const integerColumns = new Set(['seq'])

function columnType(name) {
  if (integerColumns.has(name)) return 'INTEGER'
  if (numericColumns.has(name)) return 'REAL'
  return 'TEXT'
}

const baseColumns = [
  ['id', 'TEXT PRIMARY KEY'],
  ['farm_id', 'TEXT'],
  ['status', 'TEXT'],
  ['version', 'INTEGER NOT NULL DEFAULT 1'],
  ['created_at', 'TEXT'],
  ['updated_at', 'TEXT'],
  ['payload', 'TEXT NOT NULL'],
]

function entityTableSql(name, definition) {
  const columns = [...baseColumns]
  for (const column of Object.keys(definition.extra({}))) columns.push([column, columnType(column)])
  return `CREATE TABLE IF NOT EXISTS ${name} (\n  ${columns.map(([column, type]) => `${column} ${type}`).join(',\n  ')}\n)`
}

const auxiliary = [
  `CREATE TABLE IF NOT EXISTS user_fields (
    user_id TEXT NOT NULL,
    field_id TEXT NOT NULL,
    PRIMARY KEY (user_id, field_id)
  )`,
  `CREATE TABLE IF NOT EXISTS strategy_zones (
    strategy_id TEXT NOT NULL,
    zone_id TEXT NOT NULL,
    PRIMARY KEY (strategy_id, zone_id)
  )`,
  `CREATE TABLE IF NOT EXISTS zone_soil_points (
    zone_id TEXT NOT NULL,
    point_id TEXT NOT NULL,
    PRIMARY KEY (zone_id, point_id)
  )`,
  `CREATE TABLE IF NOT EXISTS credentials (
    account TEXT PRIMARY KEY,
    salt TEXT NOT NULL,
    digest TEXT NOT NULL,
    iterations INTEGER NOT NULL,
    hash TEXT NOT NULL,
    updated_at TEXT NOT NULL
  )`,
  `CREATE TABLE IF NOT EXISTS sessions (
    token_hash TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    user_id TEXT NOT NULL,
    user_version INTEGER NOT NULL,
    csrf_token TEXT NOT NULL,
    created_at TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    revoked_at TEXT,
    last_seen_at TEXT
  )`,
  `CREATE TABLE IF NOT EXISTS idempotency_requests (
    user_id TEXT NOT NULL,
    action_id TEXT NOT NULL,
    client_request_id TEXT NOT NULL,
    request_hash TEXT NOT NULL,
    response TEXT NOT NULL,
    created_at TEXT NOT NULL,
    PRIMARY KEY (user_id, action_id, client_request_id)
  )`,
  `CREATE TABLE IF NOT EXISTS metadata (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
  )`,
  `CREATE TABLE IF NOT EXISTS export_rows (
    export_id TEXT NOT NULL,
    seq INTEGER NOT NULL,
    payload TEXT NOT NULL,
    PRIMARY KEY (export_id, seq)
  )`,
  `CREATE TABLE IF NOT EXISTS export_files (
    export_id TEXT PRIMARY KEY,
    path TEXT NOT NULL,
    byte_length INTEGER NOT NULL,
    checksum TEXT NOT NULL,
    created_at TEXT NOT NULL
  )`,
]

const indexes = [
  'CREATE INDEX IF NOT EXISTS idx_fields_farm ON fields(farm_id, status)',
  'CREATE INDEX IF NOT EXISTS idx_fields_code ON fields(code)',
  'CREATE INDEX IF NOT EXISTS idx_seasons_field ON crop_seasons(field_id, status)',
  'CREATE INDEX IF NOT EXISTS idx_zones_field ON irrigation_zones(field_id, status)',
  'CREATE INDEX IF NOT EXISTS idx_devices_farm ON devices(farm_id, status)',
  'CREATE INDEX IF NOT EXISTS idx_points_device ON points(device_id)',
  'CREATE INDEX IF NOT EXISTS idx_readings_point_time ON telemetry_readings(point_id, observed_at)',
  'CREATE INDEX IF NOT EXISTS idx_plans_farm_time ON plans(farm_id, scheduled_at)',
  'CREATE INDEX IF NOT EXISTS idx_plan_steps_plan ON plan_steps(plan_id, step_order)',
  'CREATE INDEX IF NOT EXISTS idx_runs_farm_time ON irrigation_runs(farm_id, requested_at)',
  'CREATE INDEX IF NOT EXISTS idx_run_steps_run ON run_steps(run_id, step_order)',
  'CREATE INDEX IF NOT EXISTS idx_commands_run ON command_outbox(run_id)',
  'CREATE INDEX IF NOT EXISTS idx_events_command ON command_events(command_id, occurred_at)',
  'CREATE INDEX IF NOT EXISTS idx_ledger_zone_time ON water_ledger(zone_id, ended_at)',
  'CREATE INDEX IF NOT EXISTS idx_alarms_farm_time ON alarms(farm_id, opened_at)',
  'CREATE INDEX IF NOT EXISTS idx_workorders_assignee ON work_orders(farm_id, assignee_id, status)',
  'CREATE INDEX IF NOT EXISTS idx_audit_farm_time ON audit_logs(farm_id, occurred_at)',
  'CREATE INDEX IF NOT EXISTS idx_exports_farm ON export_jobs(farm_id, created_by, created_at)',
  'CREATE INDEX IF NOT EXISTS idx_sessions_user ON sessions(user_id, expires_at)',
  'CREATE UNIQUE INDEX IF NOT EXISTS idx_devices_code_farm ON devices(farm_id, code)',
  'CREATE UNIQUE INDEX IF NOT EXISTS idx_points_device_address ON points(device_id, address)',
  'CREATE UNIQUE INDEX IF NOT EXISTS idx_events_gateway ON command_events(gateway_event_id)',
]

export function schemaStatements() {
  const statements = []
  for (const [kind, definition] of Object.entries(entityTables)) statements.push(entityTableSql(definition.table, definition))
  statements.push(...auxiliary, ...indexes)
  return statements
}

export function createSchema(db) {
  db.exec('PRAGMA journal_mode = WAL')
  db.exec('PRAGMA synchronous = NORMAL')
  db.exec('PRAGMA foreign_keys = OFF')
  db.exec('PRAGMA busy_timeout = 5000')
  const statements = schemaStatements()
  db.exec('BEGIN IMMEDIATE')
  try {
    for (const statement of statements) db.exec(statement)
    db.prepare('INSERT INTO metadata(key, value) VALUES (?, ?) ON CONFLICT(key) DO NOTHING').run('schema_version', '1')
    db.exec('COMMIT')
  } catch (error) {
    db.exec('ROLLBACK')
    throw error
  }
}
