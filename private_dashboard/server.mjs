// Dependency-free shared-password gateway. No inventory API or Telegram requests.
import http from 'node:http';
import {readFile} from 'node:fs/promises';
import {fileURLToPath} from 'node:url';
import {resolve} from 'node:path';
import {scryptSync,randomBytes,timingSafeEqual,createHmac} from 'node:crypto';
const COOKIE='__Host-stock_session',AGE=12*60*60,MAX_BODY=4096;
const FILES=['docs/stock/verified_coordinates.json','cu_inventory_health.json','emart24_inventory_health.json','gs25_inventory_health.json','seveneleven_watch_state.json','cu_official_verified_directory.json','cu_stock_state.json','stores.json','state.json','gs25_independent/gs25_stock_state.json','data/seveneleven_watch_directory.json'];
const ASSETS=new Map(['index.html','health-app.js','health-model.js','stock-map.js','stock-map-model.js'].map(f=>['/stock/'+(f==='index.html'?'':f),f]));
const HEADERS={'Cache-Control':'private, no-store','Vary':'Cookie','X-Content-Type-Options':'nosniff','Referrer-Policy':'no-referrer','X-Frame-Options':'DENY','Content-Security-Policy':"default-src 'none'; script-src 'self' https://unpkg.com; style-src 'self' 'unsafe-inline' https://unpkg.com; img-src 'self' data: https://tile.openstreetmap.org; connect-src 'self'; font-src 'self'; form-action 'self'; base-uri 'none'; frame-ancestors 'none'"};
function reply(res,status,body='',headers={}){res.writeHead(status,{...HEADERS,'Content-Type':'text/plain; charset=utf-8',...headers});res.end(body);}
function form(message=''){return '<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>재고 현황 로그인</title><style>body{font:16px system-ui;background:#f4f6fa;color:#17243a}main{max-width:360px;margin:12vh auto;padding:24px;background:white;border-radius:16px}input,button{font:inherit;padding:12px;box-sizing:border-box;width:100%;margin-top:14px}button{background:#234b91;color:white;border:0;border-radius:8px}</style><main><h1>재고 현황</h1><p>공용 비밀번호를 입력해 주세요.</p><form method="post" action="/login"><label>비밀번호<input name="password" type="password" autocomplete="current-password" required maxlength="1024"></label><button>접속하기</button></form><p role="status">'+message+'</p></main></html>';}
async function body(req){const chunks=[];let bytes=0;for await(const c of req){bytes+=c.length;if(bytes>MAX_BODY)throw Error('BODY_LIMIT');chunks.push(c);}return Buffer.concat(chunks).toString('utf8');}
export function createApp(env,{fetcher=fetch,clock=()=>Date.now(),root=resolve(fileURLToPath(new URL('..',import.meta.url)))}={}){
 const origin=new URL(env.PUBLIC_ORIGIN||env.RENDER_EXTERNAL_URL||'');if(origin.protocol!=='https:')throw Error('PUBLIC_ORIGIN must be HTTPS');
 if(typeof env.DASHBOARD_PASSWORD!=='string'||env.DASHBOARD_PASSWORD.length<16)throw Error('Set a shared password of at least 16 characters in the host secret settings');
 if(typeof env.SESSION_SECRET!=='string'||env.SESSION_SECRET.length<32)throw Error('Set a session secret of at least 32 characters');
 if(!/^[A-Za-z0-9_.-]+\/[A-Za-z0-9_.-]+$/.test(env.DATA_REPOSITORY||'')||!env.GITHUB_READ_TOKEN)throw Error('Private data repository and read-only token are required');
 const salt=randomBytes(16),passwordKey=scryptSync(env.DASHBOARD_PASSWORD,salt,32),sessionKey=createHmac('sha256',env.SESSION_SECRET).update(passwordKey).digest();
 const sign=payload=>createHmac('sha256',sessionKey).update(payload).digest('base64url');
 function authenticated(req){const value=(req.headers.cookie||'').split(';').map(v=>v.trim()).find(v=>v.startsWith(COOKIE+'='))?.slice(COOKIE.length+1);if(!value||value.length>512)return false;const [expires,nonce,signature,...extra]=value.split('.');if(extra.length||!/^\d+$/.test(expires)||!/^[-\w]{32}$/.test(nonce||'')||!/^[-\w]{43}$/.test(signature||''))return false;const expiry=Number(expires),now=Math.floor(clock()/1000);if(expiry<=now||expiry>now+AGE)return false;return timingSafeEqual(Buffer.from(sign(expires+'.'+nonce)),Buffer.from(signature));}
 const ghHeaders={'Authorization':'Bearer '+env.GITHUB_READ_TOKEN,'Accept':'application/vnd.github+json','User-Agent':'private-stock-dashboard'};
 let privacyUntil=0,privacyPending=null;
 async function privateRepo(){if(clock()<privacyUntil)return true;if(privacyPending)return privacyPending;privacyPending=(async()=>{try{const r=await fetcher('https://api.github.com/repos/'+env.DATA_REPOSITORY,{headers:ghHeaders,signal:AbortSignal.timeout(10000),redirect:'error'});if(!r.ok)return false;const j=await r.json();if(j.private!==true)return false;privacyUntil=clock()+60000;return true;}catch{return false;}finally{privacyPending=null;}})();return privacyPending;}
 let attempts=0,windowStart=clock();
 return async(req,res)=>{try{
  const url=new URL(req.url,origin),path=url.pathname;
  if(path==='/healthz'&&req.method==='GET')return reply(res,200,'ok');
  if(path==='/login'&&req.method==='GET')return reply(res,200,form(),{'Content-Type':'text/html; charset=utf-8'});
  if(path==='/login'&&req.method==='POST'){
   if(req.headers.origin!==origin.origin)return reply(res,403,'Forbidden');
   if(!String(req.headers['content-type']||'').startsWith('application/x-www-form-urlencoded'))return reply(res,415,'Unsupported form');
   if(clock()-windowStart>=60000){attempts=0;windowStart=clock();}if(++attempts>10)return reply(res,429,'잠시 후 다시 시도해 주세요.',{'Retry-After':'60'});
   const submitted=new URLSearchParams(await body(req)).get('password')||'';
   if(submitted.length>1024||!timingSafeEqual(scryptSync(submitted,salt,32),passwordKey))return reply(res,401,form('비밀번호가 일치하지 않습니다.'),{'Content-Type':'text/html; charset=utf-8'});
   const payload=(Math.floor(clock()/1000)+AGE)+'.'+randomBytes(24).toString('base64url');
   return reply(res,303,'',{'Location':'/stock/','Set-Cookie':COOKIE+'='+payload+'.'+sign(payload)+'; Path=/; HttpOnly; Secure; SameSite=Strict; Max-Age='+AGE});
  }
  if(path==='/logout'&&req.method==='POST'){
   if(req.headers.origin!==origin.origin)return reply(res,403,'Forbidden');
   return reply(res,303,'',{'Location':'/login','Set-Cookie':COOKIE+'=; Path=/; HttpOnly; Secure; SameSite=Strict; Max-Age=0'});
  }
  if(!authenticated(req))return path.startsWith('/data/')?reply(res,401,'Authentication required'):reply(res,303,'',{'Location':'/login'});
  if(req.method!=='GET')return reply(res,405,'Method not allowed',{'Allow':'GET'});
  if(!(await privateRepo()))return reply(res,503,'데이터 저장소의 비공개 상태를 확인하지 못했습니다. 관리자 설정이 필요합니다.');
  if(path==='/'||path==='/stock')return reply(res,303,'',{'Location':'/stock/'});
  if(ASSETS.has(path)){
   const file=ASSETS.get(path);let content=await readFile(resolve(root,'docs/stock',file),'utf8');
   if(file==='health-app.js'){const old="const base='https://raw.githubusercontent.com/Koyowon/pokemon-stock-alert/main/';";if(!content.includes(old))throw Error('DATA_BASE_MISMATCH');content=content.replace(old,"const base='/data/';");}
   if(file==='index.html')content=content.replace('</main>','<form action="/logout" method="post"><button type="submit">로그아웃</button></form></main>');
   return reply(res,200,content,{'Content-Type':file.endsWith('.js')?'text/javascript; charset=utf-8':'text/html; charset=utf-8'});
  }
  if(path.startsWith('/data/')){
   const file=path.slice(6);if(!FILES.includes(file))return reply(res,404,'Not found');
   const upstream='https://api.github.com/repos/'+env.DATA_REPOSITORY+'/contents/'+file.split('/').map(encodeURIComponent).join('/')+'?ref='+encodeURIComponent(env.DATA_REF||'main');
   const r=await fetcher(upstream,{headers:ghHeaders,signal:AbortSignal.timeout(10000),redirect:'error'});if(!r.ok)return reply(res,502,'Saved data unavailable');
   const data=await r.json();if(data.type!=='file'||data.encoding!=='base64'||typeof data.content!=='string'||data.size>2*1024*1024)return reply(res,502,'Invalid saved data');
   const json=Buffer.from(data.content,'base64').toString('utf8');JSON.parse(json);return reply(res,200,json,{'Content-Type':'application/json; charset=utf-8'});
  }
  return reply(res,404,'Not found');
 }catch{return reply(res,503,'요청을 처리하지 못했습니다. 잠시 후 다시 시도해 주세요.');}};
}
if(process.argv[1]&&resolve(process.argv[1])===fileURLToPath(import.meta.url)){
 try{const app=createApp(process.env);http.createServer(app).listen(Number(process.env.PORT||10000),'0.0.0.0',()=>console.log('Private dashboard listening'));}
 catch{console.error('Private dashboard configuration is incomplete');process.exitCode=1;}
}
