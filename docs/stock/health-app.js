'use strict';
const Model=StockHealth;
const base='https://raw.githubusercontent.com/Koyowon/pokemon-stock-alert/main/';
const $=id=>document.getElementById(id);
const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const time=t=>t?new Date(t*1000).toLocaleString('ko-KR',{timeZone:'Asia/Seoul',month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit',second:'2-digit',hour12:false})+' KST':'확인 기록 없음';
let data={},view={rows:[],cards:[]},filtered=[],loading=false,loadedAt=null;
for(const [key,label]of Object.entries(Model.GROUPS))$('reason').add(new Option(label,key));
const el=(tag)=>document.createElement(tag);
async function copyAddress(address,button){
 const host=button.parentElement;let notice=host.querySelector('.copy-notice');
 if(!notice){notice=el('p');notice.className='copy-notice';notice.setAttribute('role','status');host.append(notice);}
 if(!address){notice.textContent='주소가 아직 확인되지 않았습니다.';return false;}
 try{if(!navigator.clipboard?.writeText)throw Error('Clipboard unavailable');await navigator.clipboard.writeText(address);notice.textContent='주소를 복사했습니다.';return true;}
 catch{notice.textContent='자동 복사가 제한됐습니다. 아래 주소를 길게 눌러 복사하세요.';
 let field=host.querySelector('.copy-fallback');if(!field){field=el('textarea');field.className='copy-fallback';field.readOnly=true;field.setAttribute('aria-label','복사할 매장 주소');host.append(field);}field.value=address;field.focus();field.select();return false;}
}
function selection(){return Object.fromEntries(['city','chain','status','reason','q'].map(id=>[id,$(id).value]));}
function render(){
 view=Model.build(data);const selected=selection();filtered=Model.filter(view.rows,selected);
 filtered.sort((a,b)=>(b.qty>0)-(a.qty>0)||a.city.localeCompare(b.city,'ko')||a.name.localeCompare(b.name,'ko'));
 $('cards').innerHTML=view.cards.map(c=>'<article class="card"><h2>'+esc(c.chain)+'</h2><p class="numbers">수량 확인 '+c.known+' <span class="muted">/ '+c.total+'곳</span></p><p><span class="tag '+(c.unknown?'warn':'good')+'">미확인 '+c.unknown+'곳</span>'+(c.retained?' <span class="tag warn">이전 수량 유지 '+c.retained+'곳</span>':'')+(c.disabled?' <span class="tag">감시 꺼짐 '+c.disabled+'</span>':'')+'</p><small>상태 기록: '+esc(time(c.updatedAt))+'</small>'+(c.issue?'<small class="unknown">'+esc(Model.GROUPS[Model.reasonGroup(c.issue)]||'상태 확인 필요')+'</small>':'')+(c.errors.length?'<small>조회 오류 기록 '+c.errors.length+'건</small>':'')+'</article>').join('');
 const unknown=filtered.filter(r=>['unknown','retained'].includes(r.status));
 $('count').textContent='표시 '+filtered.length+'곳 · 재고 있음 '+filtered.filter(r=>r.qty>0).length+' · 0개 '+filtered.filter(r=>r.qty===0).length+' · 이전 수량 유지 '+filtered.filter(r=>r.status==='retained').length+' · 수량 기록 없음 '+filtered.filter(r=>r.status==='unknown').length+' · 감시 꺼짐 '+filtered.filter(r=>r.status==='disabled').length;
 const groupRows=Model.filter(view.rows,{...selected,reason:'',status:selected.status==='disabled'?'disabled':selected.status});
 const counts={};for(const r of groupRows)if(['unknown','retained'].includes(r.status))counts[r.group]=(counts[r.group]||0)+1;
 $('breakdown').innerHTML=Object.entries(counts).sort((a,b)=>b[1]-a[1]).map(([key,n])=>'<button type="button" class="reason-button '+(selected.reason===key?'active':'')+'" data-reason="'+esc(key)+'">'+esc(Model.GROUPS[key]||key)+' '+n+'곳</button>').join('');
 for(const button of $('breakdown').querySelectorAll('button'))button.addEventListener('click',()=>{$('reason').value=$('reason').value===button.dataset.reason?'':button.dataset.reason;render();});
 $('body').innerHTML=filtered.map((r,index)=>{
 const details=r.qty===null&&r.lastKnown!==null?'<details><summary>과거 저장 수량 보기</summary><p>과거 '+r.lastKnown+'개 · '+(r.lastAt?esc(time(r.lastAt)):'확인 시각 미상')+'<br>현재 수량이 아닙니다.</p></details>':'';
 const label=r.status==='known'?'정상 수량 응답':r.status==='retained'?'이전 수량 유지 · '+(Model.GROUPS[r.group]||'갱신 대기'):Model.GROUPS[r.group]||'미확인';
 return '<tr><td>'+esc(r.chain)+'<small>'+esc(r.city)+'</small></td><td class="store"><strong>'+esc(r.name)+'</strong><details><summary>주소·상태 기록</summary><p>'+esc(r.address||'주소 기록 없음')+'<br>최근 상태 기록: '+esc(time(r.checkedAt))+(r.unknownRuns!==null?'<br>연속 미확인 '+r.unknownRuns+'회':'')+(r.firstUnknownAt?'<br>미확인 시작: '+esc(time(r.firstUnknownAt)):'')+'</p><p class="source-code">사유 '+esc(r.reason)+(r.sourceReason&&r.sourceReason!==r.reason?' / 원래 사유 '+esc(r.sourceReason):'')+'</p></details><button type="button" class="address-copy" data-copy-index="'+index+'" '+(!r.address?'disabled':'')+'>'+(!r.address?'주소 확인 필요':'주소 복사')+'</button></td><td class="quantity '+(r.qty===null?'unknown':r.status==='retained'?'retained':'known')+'">'+(r.status==='disabled'?'감시 꺼짐':r.qty===null?'미확인':r.qty+'개')+(r.status==='retained'?'<small>마지막 확인 수량 · 갱신 대기</small>':'')+details+'</td><td class="reason">'+esc(label)+(r.qty===0?'<small>조회 시점 수량 0</small>':'')+'</td><td class="time">'+esc(time(r.lastAt))+'</td></tr>';
 }).join('')||'<tr><td colspan="5">조건에 맞는 점포가 없습니다.</td></tr>';
 for(const button of $('body').querySelectorAll('[data-copy-index]'))button.addEventListener('click',()=>copyAddress(filtered[Number(button.dataset.copyIndex)].address,button));
 $('download').disabled=unknown.length===0;
}
async function load(){
 if(loading)return;loading=true;$('reload').disabled=true;$('msg').textContent='저장된 감시 파일 확인 중…';
 const results=await Promise.allSettled(Object.entries(Model.PATHS).map(async([key,path])=>{
 const controller=new AbortController(),timer=setTimeout(()=>controller.abort(),12000);
 try{const r=await fetch(base+path+'?t='+Date.now(),{cache:'no-store',signal:controller.signal});if(!r.ok)throw Error('HTTP '+r.status);const value=await r.json();const chain={cuHealth:'CU',emHealth:'이마트24',gsHealth:'GS25',sevenState:'세븐일레븐'}[key];if(chain&&!Model.validHealth(value,chain))throw Error('감시 파일 검증 실패');return [key,value];}finally{clearTimeout(timer);}
 }));
 const failed=[];data.loadFailures=[];const keys=Object.keys(Model.PATHS);const healthKeys=new Set(['cuHealth','emHealth','gsHealth','sevenState']);
 results.forEach((r,i)=>{const key=keys[i];if(r.status==='fulfilled')data[key]=r.value[1];else{failed.push(Model.PATHS[key]+': '+(r.reason?.name==='AbortError'?'파일 읽기 시간 초과':String(r.reason?.message||r.reason)));if(healthKeys.has(key)){data.loadFailures.push(key);if(!data[key])data[key]=null;}}});
 loadedAt=Date.now();render();$('msg').textContent='파일 확인: '+time(loadedAt/1000)+' · 화면의 수량 확인 시각과는 다릅니다.';
 $('notice').textContent=failed.length?'일부 파일을 읽지 못했습니다. 검증된 이전 수량이 있으면 유지하며, 파일을 다시 읽기 전까지 최신 확인으로 취급하지 않습니다.\n'+failed.join('\n'):'';
 loading=false;$('reload').disabled=false;
}
$('reload').addEventListener('click',load);
for(const id of ['city','chain','status','reason','q'])$(id).addEventListener('input',render);
$('download').addEventListener('click',()=>{const blob=new Blob([Model.csv(filtered)],{type:'text/csv;charset=utf-8'}),url=URL.createObjectURL(blob),a=document.createElement('a');a.href=url;a.download='pokemon-stock-unknown-'+new Date().toISOString().slice(0,10)+'.csv';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);});
setInterval(()=>{if(loadedAt!==null){render();load();}},60000);
load();





