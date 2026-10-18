/* Pure rendering model: no inventory requests, state writes, or notifications. */
(function(root){
'use strict';
const PRODUCT='8800286275732', TTL=900;
const CHAINS=['CU','이마트24','GS25','세븐일레븐'];
const CITIES={namwon:'남원',asan:'아산',jeonju:'전주'};
const PATHS={coordinates:'docs/stock/verified_coordinates.json',cuHealth:'cu_inventory_health.json',emHealth:'emart24_inventory_health.json',gsHealth:'gs25_inventory_health.json',sevenState:'seveneleven_watch_state.json',cuDirectory:'cu_official_verified_directory.json',cuOld:'cu_stock_state.json',emStores:'stores.json',emOld:'state.json',gsOld:'gs25_independent/gs25_stock_state.json',sevenDirectory:'data/seveneleven_watch_directory.json'};
const SOURCES={CU:['cuHealth','cu'],이마트24:['emHealth','emart24'],GS25:['gsHealth','gs25'],세븐일레븐:['sevenState',null]};
const GROUPS={network:'통신·외부 서비스 오류',missing:'응답에 없음·범위 미확정',quantity:'수량 미확인',identity:'매장 정보 대조 필요',validation:'응답 검증 실패',stale:'오래된 기록',clock:'기록 시각 확인 필요',file:'감시 상태 파일 확인 필요',pending:'아직 확인되지 않음',disabled:'감시 꺼짐'};
const object=x=>x!==null&&typeof x==='object'&&!Array.isArray(x);
const entries=x=>object(x)?Object.entries(x):[];
const list=x=>Array.isArray(x)?x:[];
const quantity=x=>typeof x==='number'&&Number.isInteger(x)&&x>=0?x:null;
const stamp=x=>typeof x==='number'&&Number.isFinite(x)&&x>0?x:null;
const cityOf=s=>{const m=String(s||'').match(/(?:^|\s)(남원시|아산시|전주시)(?:\s|$)/);return m?{남원시:'남원',아산시:'아산',전주시:'전주'}[m[1]]:null};
const timeIssue=(t,now)=>stamp(t)===null?'INVALID_TIMESTAMP':t>now?'FUTURE_TIMESTAMP':now-t>TTL?'STALE':null;
function validHealth(h,chain){const provider=SOURCES[chain][1];return object(h)&&h.version===1&&h.product===PRODUCT&&object(h.stores)&&(!provider||h.chain===provider)}
function group(code){
 if(/^(HTTP_|READ_TIMEOUT|NETWORK_ERROR|TRANSPORT_ERROR|QUERY_FAILURE|BATCH_ERROR|SINGLE_ERROR|HTTP_BLOCKED|RUN_FAILED|PARTIAL_SCAN)/.test(code))return 'network';
 if(['MISSING_IN_RESPONSE','NOT_IN_HEALTH'].includes(code))return 'missing';
 if(['NO_QUANTITY','NULL_OR_INVALID_QTY','INVALID_QUANTITY','STOCK_UNAVAILABLE'].includes(code))return 'quantity';
 if(/IDENTITY|CONFLICT|REGISTRY/.test(code))return 'identity';
 if(code==='STALE')return 'stale';
 if(/TIMESTAMP/.test(code))return 'clock';
 if(/HEALTH_|STATE_FILE/.test(code))return 'file';
 if(['NOT_ACTIVE','DISABLED'].includes(code))return 'disabled';
 if(['NOT_CHECKED','NOT_YET_CHECKED','PENDING'].includes(code))return 'pending';
 return 'validation';
}
function build(data,now=Date.now()/1000){
 const expected=new Map();
 function add(chain,code,name,address='',city=null,legacy=null){
  code=String(code||'');city=city||cityOf(address);if(!code||!Object.values(CITIES).includes(city))return;
  const key=chain+'|'+code,old=expected.get(key);
  expected.set(key,{chain,code,name:String(name||code),address:String(address||''),city,...old,...(old?{}:{legacy:quantity(legacy)})});
  if(old&&old.legacy===null&&quantity(legacy)!==null)expected.get(key).legacy=quantity(legacy);
 }
 for(const r of list(data.cuDirectory?.stores))if(object(r))add('CU',r.cu_store_code,r.name,r.address);
 for(const [c,r] of entries(data.cuOld?.stores))if(object(r))add('CU',c,r.name,r.address,['남원','아산','전주'].includes(r.city)?r.city:null,r.stock);
 const emLegacy=new Map();
 for(const [key,value]of entries(data.emOld)){const [ch,code,product]=key.split('|');if(product===PRODUCT&&['emart24','이마트24'].includes(ch)&&(!emLegacy.has(code)||ch==='이마트24'))emLegacy.set(code,quantity(value));}
 for(const [c,r]of entries(data.emStores?.stores))if(object(r))add('이마트24',c,r.name,r.address,null,emLegacy.get(c));
 for(const [rid,block]of entries(data.gsOld?.regions))for(const [c,r]of entries(block?.stores||block?.positive))if(object(r))add('GS25',c,r.name,'',CITIES[rid],r.quantity);
 for(const [rid,dir]of entries(data.sevenDirectory))for(const r of list(dir?.data?.stores))if(object(r))add('세븐일레븐',r.storeCode,r.storeName,r.address,CITIES[rid]);
 for(const chain of CHAINS){const h=data[SOURCES[chain][0]];if(validHealth(h,chain))for(const [c,r]of entries(h.stores))if(object(r))add(chain,c,r.name,r.address,CITIES[r.region]);}
 const rows=[];
 for(const e of expected.values()){
  const h=data[SOURCES[e.chain][0]], valid=validHealth(h,e.chain), r=valid&&object(h.stores[e.code])?h.stores[e.code]:null;
  let reason=!h?'STATE_FILE_MISSING':!valid?'HEALTH_INVALID':!r?'NOT_IN_HEALTH':String(r.reason||'PENDING');
  let current=null, disabled=r?.status==='DISABLED';
  if(r){
   const clock=timeIssue(h.updated_at,now)||timeIssue(r.checked_at,now);
   const mismatch=CITIES[r.region]!==e.city||(e.chain==='세븐일레븐'&&(r.name!==e.name||r.address!==e.address));
   if(disabled)reason='NOT_ACTIVE';
   else if(mismatch)reason='IDENTITY_HOLD';
   else if(clock)reason=clock;
   else if(r.status==='OK'&&quantity(r.quantity)!==null){current=quantity(r.quantity);reason='OBSERVED';}
   else if(r.status==='OK')reason='INVALID_QUANTITY';
   else if(reason==='OBSERVED')reason='UNVERIFIED_RESPONSE';
  }
  // Keep the last validated observation until a new valid response replaces it.
  // Legacy values without a trustworthy observation timestamp remain historical only.
  const mismatch=r&&(CITIES[r.region]!==e.city||(e.chain==='세븐일레븐'&&(r.name!==e.name||r.address!==e.address)));
  const held=mismatch||/IDENTITY|CONFLICT|REGISTRY/.test(String(r?.reason||''));
  const observed=!!r&&r.status==='OK'&&quantity(r.quantity)!==null&&stamp(r.checked_at)!==null&&r.checked_at<=now;
  const last=observed?quantity(r.quantity):quantity(r?.last_known_quantity)??e.legacy;
  const lastAt=observed?stamp(r.checked_at):quantity(r?.last_known_quantity)!==null?stamp(r?.last_success_at):null;
  const safeLastAt=last!==null&&lastAt!==null&&lastAt<=now?lastAt:null;
  const fileFailed=list(data.loadFailures).includes(SOURCES[e.chain][0]);
  if(fileFailed){current=null;reason='STATE_FILE_UNAVAILABLE';}
  if(held){current=null;reason='IDENTITY_HOLD';}
  const retained=!disabled&&!held&&valid&&safeLastAt!==null&&last!==null&&current===null;
  const qty=current??(retained?last:null),status=disabled?'disabled':current!==null?'known':retained?'retained':'unknown';
  rows.push({...e,qty,status,reason,sourceReason:r?.reason||null,group:current!==null?'known':disabled?'disabled':group(reason),checkedAt:stamp(r?.checked_at),lastKnown:last,lastAt:safeLastAt,unknownRuns:Number.isInteger(r?.unknown_runs)&&r.unknown_runs>=0?r.unknown_runs:null,firstUnknownAt:stamp(r?.first_unknown_at)});
 }
 const cards=CHAINS.map(chain=>{const rs=rows.filter(r=>r.chain===chain),h=data[SOURCES[chain][0]];return {chain,total:rs.length,known:rs.filter(r=>r.qty!==null).length,retained:rs.filter(r=>r.status==='retained').length,unknown:rs.filter(r=>r.status==='unknown').length,disabled:rs.filter(r=>r.status==='disabled').length,updatedAt:stamp(h?.updated_at),issue:!h?'STATE_FILE_MISSING':!validHealth(h,chain)?'HEALTH_INVALID':timeIssue(h.updated_at,now),errors:Array.isArray(h?.errors)?h.errors:[]};});
 return {rows,cards};
}
function filter(rows,{city='',chain='',status='',reason='',q=''}={}){q=q.trim().toLocaleLowerCase();return rows.filter(r=>(!city||r.city===city)&&(!chain||r.chain===chain)&&(!status||(status==='yes'?r.qty>0:status==='no'?r.qty===0:status===r.status))&&(!reason||r.group===reason)&&(!q||[r.name,r.code,r.address].join(' ').toLocaleLowerCase().includes(q)));}
function csv(rows){const cell=v=>{let s=String(v??'');if(/^[=+\-@\t\r]/.test(s))s="'"+s;return '"'+s.replaceAll('"','""')+'"'};return '\ufeff'+[['브랜드','지역','점포코드','매장명','주소','미확인 분류','사유 코드','최근 상태 기록(UTC)','이전 확인 수량','이전 수량 확인시각(UTC)','연속 미확인 실행 수'].map(cell).join(','),...rows.filter(r=>['unknown','retained'].includes(r.status)).map(r=>[r.chain,r.city,r.code,r.name,r.address,GROUPS[r.group]||r.group,r.reason,r.checkedAt?new Date(r.checkedAt*1000).toISOString():'',r.lastKnown,r.lastAt?new Date(r.lastAt*1000).toISOString():'',r.unknownRuns].map(cell).join(','))].join('\r\n');}
const api={PRODUCT,TTL,CHAINS,CITIES,PATHS,GROUPS,quantity,timeIssue,reasonGroup:group,validHealth,build,filter,csv};
if(typeof module!=='undefined'&&module.exports)module.exports=api;root.StockHealth=api;
})(typeof globalThis!=='undefined'?globalThis:this);


