/* Coordinates enter this map only through the reviewed registry, never guessed geocodes. */
(function(root){
'use strict';
const text=x=>typeof x==='string'?x.trim().replace(/\s+/g,' '):'';
const address=x=>text(x).replace(/^(전북특별자치도|전북) /,'전라북도 ').replace(/^충남 /,'충청남도 ');
function valid(entry,now){
 if(!entry||entry.verified!==true||!['CU','이마트24','GS25','세븐일레븐'].includes(entry.chain)||!text(entry.code)||!text(entry.name)||!address(entry.address))return false;
 if(typeof entry.latitude!=='number'||typeof entry.longitude!=='number'||!Number.isFinite(entry.latitude)||!Number.isFinite(entry.longitude)||entry.latitude<33||entry.latitude>39||entry.longitude<124||entry.longitude>132)return false;
 let url;try{url=new URL(entry.source_url)}catch{return false}if(url.protocol!=='https:'||url.username||url.password)return false;
 const verified=Date.parse(entry.verified_at);return Number.isFinite(verified)&&verified>0&&verified<=now*1000;
}
function attachLocations(rows,registry,now=Date.now()/1000){
 const records=new Map(),duplicates=new Set();
 if(registry?.version===1&&Array.isArray(registry.stores))for(const entry of registry.stores){
  const key=entry?.chain+'|'+entry?.code;
  if(records.has(key))duplicates.add(key);records.set(key,entry);
 }
 return rows.map(row=>{
  const key=row.chain+'|'+row.code,entry=records.get(key);
  const match=!duplicates.has(key)&&valid(entry,now)&&text(entry.name)===text(row.name)&&(!text(row.address)||address(entry.address)===address(row.address));
  return {...row,location:match?{latitude:entry.latitude,longitude:entry.longitude,source:entry.source_url,verifiedAt:entry.verified_at}:null,address:text(row.address)||(match?entry.address:'')};
 });
}
function eligible(row,{includeZero=false,includeUnknown=false}={}){return ['known','retained'].includes(row.status)&&Number.isInteger(row.qty)&&(row.qty>0||(includeZero&&row.qty===0))||includeUnknown&&row.status==='unknown'&&row.qty===null;}
function pins(rows,options={}){return rows.filter(r=>r.location&&eligible(r,options));}
const api={attachLocations,pins,eligible};if(typeof module!=='undefined'&&module.exports)module.exports=api;root.StockMapModel=api;
})(typeof globalThis!=='undefined'?globalThis:this);


