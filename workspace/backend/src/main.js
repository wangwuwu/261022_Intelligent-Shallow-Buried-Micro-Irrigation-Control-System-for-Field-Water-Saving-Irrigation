import { loadConfig } from './config.js'
import { openDatabase } from './db/database.js'
import { createIrrigationServer } from './http/server.js'
import { counts } from './services/seed.js'

const config = loadConfig()
const db = openDatabase(config)
const users = db.prepare('SELECT COUNT(*) AS count FROM users').get()?.count ?? 0
if (!users) {
  console.error('数据库中没有业务用户。请先执行共享资料显式导入：')
  console.error('  node scripts/import-seed.mjs')
  console.error('然后为管理员设置登录口令：')
  console.error('  node scripts/set-password.mjs <ADMIN账号>')
  db.close()
  process.exit(1)
}
const credentials = db.prepare('SELECT COUNT(*) AS count FROM credentials').get()?.count ?? 0
if (!credentials) {
  console.warn('尚未设置任何账号登录口令。请执行：node scripts/set-password.mjs <ADMIN账号>')
}
if (config.deviceChannel !== 'disabled') {
  console.warn(`设备通道配置为 ${config.deviceChannel}，但本版没有可用适配器；运行控制仍将返回 ADAPTER_UNAVAILABLE。`)
}

const server = createIrrigationServer({ db, config })
server.listen(config.port, config.host, () => {
  console.log(`灌溉管控后端已启动：http://${config.host}:${config.port}`)
  console.log(`SQLite：${config.dbPath}`)
  console.log(`静态目录：${config.staticDir || '未配置'}`)
  console.log(`设备通道：${config.deviceChannel}`)
  console.log('实体数量：', counts(db))
})

let closing = false
function shutdown(signal) {
  if (closing) return
  closing = true
  console.log(`收到 ${signal}，正在停止服务…`)
  server.close(() => {
    try {
      db.close()
    } catch {}
    process.exit(0)
  })
  setTimeout(() => process.exit(1), 10000).unref()
}
process.on('SIGINT', () => shutdown('SIGINT'))
process.on('SIGTERM', () => shutdown('SIGTERM'))
