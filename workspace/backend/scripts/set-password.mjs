#!/usr/bin/env node
import { resolve } from 'node:path'
import { loadConfig } from '../src/config.js'
import { openDatabase } from '../src/db/database.js'
import { setPassword } from '../src/services/auth.js'

function parseArgs(argv) {
  const args = { account: null, db: null, help: false }
  for (let index = 0; index < argv.length; index++) {
    const item = argv[index]
    if (item === '--db') args.db = argv[++index]
    else if (item === '--help' || item === '-h') args.help = true
    else if (!item.startsWith('-') && !args.account) args.account = item
    else throw new Error(`未知参数：${item}`)
  }
  return args
}

async function readHidden(prompt) {
  if (!process.stdin.isTTY) {
    const chunks = []
    for await (const chunk of process.stdin) chunks.push(chunk)
    const text = Buffer.concat(chunks).toString('utf8').split(/\r?\n/)[0]
    return text
  }
  process.stderr.write(prompt)
  process.stdin.setRawMode(true)
  process.stdin.resume()
  process.stdin.setEncoding('utf8')
  return new Promise((resolve, reject) => {
    let value = ''
    const onData = (chunk) => {
      for (const char of chunk) {
        if (char === '\u0003') {
          cleanup()
          reject(new Error('已取消'))
          return
        }
        if (char === '\r' || char === '\n') {
          cleanup()
          process.stderr.write('\n')
          resolve(value)
          return
        }
        if (char === '\u007f' || char === '\b') {
          value = value.slice(0, -1)
          continue
        }
        value += char
      }
    }
    const cleanup = () => {
      process.stdin.off('data', onData)
      process.stdin.setRawMode(false)
      process.stdin.pause()
    }
    process.stdin.on('data', onData)
  })
}

const args = parseArgs(process.argv.slice(2))
if (args.help) {
  console.log('用法：node scripts/set-password.mjs <账号> [--db var/irrigation.sqlite]\n\n口令从标准输入读取并在终端隐藏输入，不通过命令行参数传递。')
  process.exit(0)
}
if (!args.account) {
  console.error('请提供共享数据中已存在的启用账号，例如：node scripts/set-password.mjs zyq.admin')
  process.exit(2)
}

const config = loadConfig(args.db ? { dbPath: resolve(process.cwd(), args.db) } : {})
const db = openDatabase(config)
try {
  const password = await readHidden(`账号 ${args.account} 的新口令（8-128字符）：`)
  if (process.stdin.isTTY) {
    const confirmation = await readHidden('再次输入口令：')
    if (password !== confirmation) throw new Error('两次输入的口令不一致')
  }
  const user = setPassword(db, args.account, password)
  console.log(`已为 ${user.account}（${user.name}，${user.role}）设置登录口令，并撤销其已有会话。`)
} catch (error) {
  console.error(`设置失败：${error.message}`)
  process.exitCode = 1
} finally {
  db.close()
}
