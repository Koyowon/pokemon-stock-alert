/* UI only: no geocoding, inventory APIs, location permission, or notifications. */
(function(root){
'use strict';
let map=null,layer=null,viewKey=null;
const el=(tag,text)=>{const node=document.createElement(tag);if(text!==undefined)node.textContent=text;return node;};
const time=t=>t?new Date(t*1000).toLocaleString('ko-KR',{timeZone:'Asia/Seoul',hour12:false})+' KST':'확인 기록 없음';
async function copyAddress(address,button){
 const host=button.parentElement;let notice=host.querySelector('.copy-notice');
 if(!notice){notice=el('p');notice.className='copy-notice';notice.setAttribute('role','status');host.append(notice);}
 if(!address){notice.textContent='주소가 아직 확인되지 않았습니다.';return false;}
 try{if(!navigator.clipboard?.writeText)throw Error('Clipboard unavailable');await navigator.clipboard.writeText(address);notice.textContent='주소를 복사했습니다.';return true;}
 catch{notice.textContent='자동 복사가 제한됐습니다. 아래 주소를 길게 눌러 복사하세요.';
 let field=host.querySelector('.copy-fallback');if(!field){field=el('textarea');field.className='copy-fallback';field.readOnly=true;field.setAttribute('aria-label','복사할 매장 주소');host.append(field);}field.value=address;field.focus();field.select();return false;}
}
function detail(row){
 const card=el('article');card.className='map-store-card';
 card.append(el('strong',row.chain+' '+row.name),el('p',row.status==='known'?'재고 '+row.qty+'개':row.status==='retained'?'마지막 확인 재고 '+row.qty+'개 (이전 수량 유지)':'현재 재고 미확인'),el('p','마지막 수량 확인: '+time(row.lastAt||row.checkedAt)),el('p',row.address));
 if(row.status==='retained')card.append(el('p','최근 조회는 미확인 또는 오래된 기록입니다. 새 수량이 확인되면 갱신합니다.'));
 if(row.status==='unknown'&&row.lastKnown!==null&&row.lastKnown!==undefined)card.append(el('p','과거 확인 수량: '+row.lastKnown+'개 (현재 수량 아님)'));
 const button=el('button','주소 복사');button.type='button';button.addEventListener('click',()=>copyAddress(row.address,button));card.append(button);
 const source=el('a','위치 확인 출처');source.href=row.location.source;source.target='_blank';source.rel='noopener noreferrer';card.append(source);
 return card;
}
function render(rows,{includeZero=false,includeUnknown=false,positiveOnly=false,registryAvailable=false,registryCount=0}={}){
 const selected=root.StockMapModel.pins(rows,{includeZero,includeUnknown,positiveOnly});
 const eligible=rows.filter(r=>root.StockMapModel.eligible(r,{includeZero,includeUnknown,positiveOnly}));
 const message=document.getElementById('map-status');
 message.textContent=(positiveOnly?'재고 있는 매장 ':'필터 내 표시 대상 매장 ')+eligible.length+'곳 · 지도 표시 '+selected.length+'곳 · 좌표 확인 필요 '+(eligible.length-selected.length)+'곳';
 document.getElementById('map-note').textContent=!registryAvailable?'좌표 목록을 읽지 못했습니다. 임의 위치는 표시하지 않습니다. 아래 목록에서 주소를 확인해 주세요.':registryCount===0?'검증된 매장 좌표가 아직 등록되지 않았습니다. 좌표 등록 후 조건에 맞는 매장이 지도에 표시됩니다.':selected.length===0?(eligible.length>0?'표시 대상 '+eligible.length+'곳의 좌표가 아직 확인되지 않아 지도에 표시하지 못합니다. 아래 목록에서 매장명과 주소를 확인해 주세요.':positiveOnly?'현재 필터에서 마지막 확인 수량이 1개 이상인 매장이 없습니다. 재고 있는 매장만 표시 옵션을 끄면 다른 매장 위치도 볼 수 있습니다.':'현재 필터에서 지도에 표시할 매장이 없습니다. 미확인 매장 위치 표시를 켜거나 필터를 확인해 주세요.'):'초록 숫자: 최근 확인 재고 · 주황 숫자: 이전 수량 유지 · 회색 0: 확인된 0개 · 회색 ?: 현재 재고 미확인. 위치 등록 '+registryCount+'곳이며 미등록 매장은 표시되지 않습니다.';
 if(!root.L){document.getElementById('stock-map').textContent='지도를 불러오지 못했습니다. 아래 목록의 주소 복사 기능은 이용할 수 있습니다.';return;}
 if(!map){map=root.L.map('stock-map',{scrollWheelZoom:false}).setView([36.3,127.3],8);
 root.L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png',{maxZoom:19,attribution:'&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'}).addTo(map);
 layer=root.L.layerGroup().addTo(map);}
 layer.clearLayers();
 const groups=new Map();for(const row of selected){const key=row.location.latitude+','+row.location.longitude;if(!groups.has(key))groups.set(key,[]);groups.get(key).push(row);}
 for(const stores of groups.values()){
  const first=stores[0],sum=stores.reduce((n,r)=>n+(['known','retained'].includes(r.status)?r.qty:0),0),unknown=stores.some(r=>r.status==='unknown'),retained=stores.some(r=>r.status==='retained'),label=unknown?(sum>0?sum+'+?':'?'):String(sum),popup=el('div');
  for(const row of stores)popup.append(detail(row));
  const icon=root.L.divIcon({className:'stock-pin '+(sum>0?(retained?'stock-pin-retained':'stock-pin-positive'):unknown?'stock-pin-unknown':'stock-pin-zero'),html:'<span>'+label+'</span>',iconSize:[38,38],iconAnchor:[19,38]});
  root.L.marker([first.location.latitude,first.location.longitude],{icon,keyboard:true,title:stores.map(r=>r.chain+' '+r.name+' '+(['known','retained'].includes(r.status)?r.qty+'개'+(r.status==='retained'?' (이전 수량 유지)':''):'재고 미확인')).join(' / ')}).bindPopup(popup,{maxWidth:320,maxHeight:240}).addTo(layer);
 }
 const key=selected.map(r=>r.chain+'|'+r.code+'|'+r.location.latitude+','+r.location.longitude).sort().join(';');
 if(key!==viewKey&&selected.length){const bounds=root.L.latLngBounds(selected.map(r=>[r.location.latitude,r.location.longitude]));map.fitBounds(bounds,{padding:[30,30],maxZoom:16});}viewKey=key;
}
root.StockMap={render,copyAddress,detail};
})(typeof globalThis!=='undefined'?globalThis:this);



