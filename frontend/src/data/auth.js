import { reject } from './contracts.js'
const bytesToBase64=bytes=>btoa(String.fromCharCode(...bytes))
const base64ToBytes=text=>Uint8Array.from(atob(text),letter=>letter.charCodeAt(0))
export async function createPreviewCredential(password, iterations=210000) {
 const salt=crypto.getRandomValues(new Uint8Array(16)); const key=await crypto.subtle.importKey('raw',new TextEncoder().encode(password),'PBKDF2',false,['deriveBits'])
 const bits=await crypto.subtle.deriveBits({name:'PBKDF2',salt,iterations,hash:'SHA-256'},key,256)
 return {salt:bytesToBase64(salt),digest:bytesToBase64(new Uint8Array(bits)),iterations,hash:'SHA-256'}
}
export async function verifyPreviewPassword(password,credential) {
 if (!credential) reject('PREVIEW_CREDENTIALS_MISSING','本机预览账号尚未配置，请按启动说明完成配置')
 if (!Number.isInteger(credential.iterations)||credential.iterations<1000||credential.hash!=='SHA-256') reject('CREDENTIAL_FORMAT','预览凭据格式无效')
 try {
  const key=await crypto.subtle.importKey('raw',new TextEncoder().encode(password),'PBKDF2',false,['deriveBits'])
  const actual=new Uint8Array(await crypto.subtle.deriveBits({name:'PBKDF2',salt:base64ToBytes(credential.salt),iterations:credential.iterations,hash:credential.hash},key,256));const expected=base64ToBytes(credential.digest)
  let difference=actual.length^expected.length;for(let i=0;i<actual.length;i++) difference|=actual[i]^(expected[i]??0)
  return difference===0
 } catch(error){ if(error.code) throw error;return false }
}
