#!/usr/bin/env node
import { resolve } from 'node:path'
import { loadConfig } from '../src/config.js'
import { openDatabase } from '../src/db/database.js'
import { counts, importSeed } from '../src/services/seed.js'

function parseArgs(argv) {
  const args = { force: false, source: null, db: null }
  for (let index = 0; index < argv.length; index++) {
    const item = argv[index]
    if (item === '--force') args.force = true
    else if (item === '--source') args.source = argv[++index]
    else if (item === '--db') args.db = argv[++index]
    else if (item === '--help' || item === '-h') args.help = true
    else throw new Error(`未知参数：${item}`)
  }
  return args
}

const args = parseArgs(process.argv.slice(2))
if (args.help) {
  console.log(`用法：node scripts/import-seed.mjs [--source ../shared_context.json] [--db var/irrigation.sqlite] [--force]

共享数据只通过此命令显式导入；服务启动时不会自动重灌数据。
--force 会用共享资料重建业务实体，但保留已经设置的账号口令。`)
  process.exit(0)
}

const config = loadConfig({
  ...(args.db ? { dbPath: resolve(process.cwd(), args.db) } : {}),
  ...(args.source ? { sourcePath: resolve(process.cwd(), args.source) } : {}),
})
const db = openDatabase(config)
try {
  const result = importSeed(db, args.source ? resolve(process.cwd(), args.source) : config.sourcePath, { force: args.force })
  console.log(`导入完成：${config.sourcePath}`)
  console.log(`来源 SHA-256：${result.sourceSha256}`)
  console.log('实体数量：', counts(db))
  console.log('下一步：先为至少一名 ADMIN 设置登录口令，再启动服务。')
} catch (error) {
  console.error(`导入失败：${error.message}`)
  process.exitCode = 1
} finally {
  db.close()
}
