// [역할] 검증된 백업 서버 Git 배포 제어 v2. [의존성 관계] 기존 SSH agent. [변경 시 영향도] 바이너리 자산의 원시 byte를 보존합니다.
import fs from 'node:fs'; // 검토된 배포 소스와 결과 파일입니다.
import path from 'node:path'; // 승인된 프로젝트 경로입니다.
import {fileURLToPath} from 'node:url'; // Windows 경로를 안전하게 변환합니다.
import {execFileSync, spawnSync} from 'node:child_process'; // shell 문자열이 아닌 인자 배열입니다.
import {createHash} from 'node:crypto'; // 내용 비교용 SHA입니다.
import assert from 'node:assert/strict'; // 안전 조건 실패 시 중단합니다.
const here=path.dirname(fileURLToPath(import.meta.url)), root=path.resolve(here,'../../../../..'); // 프로젝트 루트입니다.
const git=(...args)=>execFileSync('git',args,{cwd:root}); // 비밀 인자가 없는 Git 명령입니다.
const target=git('rev-parse','HEAD').toString().trim(), previous='b637c79af1920e4255e5ccaad75fe63ccc9142c7'; // 원래 실배포본입니다.
assert.equal(git('diff','--name-only').toString().trim(),''); assert.equal(git('diff','--cached','--name-only').toString().trim(),''); // 타인의 변경을 같이 배포하지 않습니다.
assert.equal(git('ls-remote','--heads','origin','main').toString().split(/\s+/)[0],target); // commit/push 선행 여부입니다.
const runtime=name=>['app.py','requirements.txt'].includes(name)||/^(static|templates|utils|Resources)\//.test(name); // 운영 소스 범위입니다.
const names=commit=>git('ls-tree','-r','--name-only',commit).toString().trim().split('\n').filter(runtime); // 해당 commit의 실제 파일 목록입니다.
const oldNames=new Set(names(previous)), all=[...new Set([...oldNames,...names(target)])].sort(); // 추가 파일도 비교합니다.
const digest=bytes=>createHash('sha256').update(Buffer.from(bytes.toString('latin1').replaceAll('\r\n','\n'),'latin1')).digest('hex'); // UTF8 디코딩 손실 없이 Python의 byte-level CRLF 정규화와 일치합니다.
const files=Object.fromEntries(all.map(name=>[name,{previous:oldNames.has(name)?digest(git('show',previous+':'+name)):null,target:digest(git('show',target+':'+name))}])); // 내용 대신 hash를 전달합니다.
const script=fs.readFileSync(path.join(here,'backup_release.py'),'utf8'); // 검토 후 commit된 배포 도구입니다.
const quote=s=>"'"+s.replaceAll("'","'\\''")+"'"; // 원격 셸에서 코드를 단일 인자로 전달합니다.
assert.ok(['preflight','apply'].includes(process.argv[2])); // 암묵적 배포 실행을 금지합니다.
const payload={target,files,server_head:'5ab042a7cb1a4acd25af64732c6a1f64b644db94',pid:91637,apply:process.argv[2]==='apply'}; // 현재 상태가 달라지면 서버가 거부합니다.
const result=spawnSync('C:/Windows/System32/OpenSSH/ssh.exe',['-o','ConnectTimeout=8','eqmgmt-backup','/home/nekohost/services/Mini-Server-Web-EqMgmt/.venv/bin/python -B -c '+quote(script)],{input:JSON.stringify(payload),encoding:'utf8',timeout:240000,maxBuffer:8*1024*1024,env:{...process.env,PROGRAMDATA:process.env.PROGRAMDATA||'C:\\ProgramData'}}); // 기존 agent를 사용합니다.
const report={completedAt:new Date().toISOString(),ssh_exit:result.status,stdout:result.stdout,stderr:result.stderr,error:result.error?.message||null}; // 환경/키를 포함하지 않습니다.
fs.writeFileSync(path.join(here,(payload.apply?'deployment':'preflight')+'-v2-result.json'),JSON.stringify(report,null,2),{flag:'wx'}); // 이전 실패 증거를 덮어쓰지 않습니다.
console.log(JSON.stringify(report,null,2)); if(result.status!==0)process.exit(1); // 실제 오류를 상위에 전달합니다.
