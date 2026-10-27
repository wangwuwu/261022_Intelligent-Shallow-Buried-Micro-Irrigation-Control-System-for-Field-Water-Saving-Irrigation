import {mkdir,readFile,writeFile} from 'node:fs/promises'
import readline from 'node:readline/promises'
import {createPreviewCredential} from '../src/data/auth.js'
async function secret(prompt){
 if(!process.stdin.isTTY)throw Error('请在交互终端运行，以隐藏口令输入')
 process.stdout.write(prompt);process.stdin.setRawMode(true);process.stdin.resume();process.stdin.setEncoding('utf8')
 return new Promise((resolve,reject)=>{
  let value=''
  const onInput=chunk=>{for(const char of chunk){if(char==='\u0003'){cleanup();reject(Error('已取消'));return}if(char==='\r'||char==='\n'){cleanup();resolve(value);return}if(char==='\u007f'){value=value.slice(0,-1)}else if(char>=' ')value+=char}}
  function cleanup(){process.stdin.off('data',onInput);process.stdin.setRawMode(false);process.stdin.pause();process.stdout.write('\n')}
  process.stdin.on('data',onInput)
 })
}
try{
 const rl=readline.createInterface({input:process.stdin,output:process.stdout});const account=(await rl.question('本机预览账号：')).trim();rl.close()
 if(!account)throw Error('账号必填')
 const password=await secret('设置口令（输入不回显）：'),confirm=await secret('再次输入口令：')
 if(password.length<8||password.length>128)throw Error('口令长度须为8至128个字符')
 if(password!==confirm)throw Error('两次口令不一致')
 const file=new URL('../.local/preview-credentials.json',import.meta.url);let credentials={}
 try{credentials=JSON.parse(await readFile(file,'utf8'))}catch(error){if(error.code!=='ENOENT')throw error}
 credentials[account]=await createPreviewCredential(password);await mkdir(new URL('../.local/',import.meta.url),{recursive:true});await writeFile(file,JSON.stringify(credentials,null,2),{mode:0o600})
 console.log(`已为 ${account} 设置本机预览凭据；请启动或刷新前端。正式认证不使用此文件。`)
}catch(error){console.error(error.message);process.exitCode=1}
