"""Read-only GO Plus+ monitor. No accounts, orders, or payment operations."""
import base64,datetime,json,os,re,time,urllib.request,urllib.error
from html.parser import HTMLParser
from pathlib import Path

SITES=[
 {'id':'touch','name':'게임터치몰','product':'1053','url':'https://gametouchmall.com/product/detail.html?product_no=1053','kind':'cafe24'},
 {'id':'tech','name':'게임테크몰','product':'1118','url':'https://gametechmall.com/product/detail.html?product_no=1118','kind':'cafe24'},
 {'id':'official','name':'포켓몬스토어 공식몰','product':'114169355','url':'https://pokemonstore.co.kr/pages/product/product-detail.html?productNo=114169355','kind':'official'}]
MAX_PRICE=64800
STATE_BRANCH='pogoplus-state'

def variable(text,key):
 values=re.findall(r'\bvar\s+'+re.escape(key)+r"\s*=\s*'([^']*)'",text)
 return values[0] if len(values)==1 else None

class Metadata(HTMLParser):
 def __init__(self):super().__init__();self.values={}
 def handle_starttag(self,tag,attrs):
  a=dict(attrs)
  if tag=='meta' and a.get('property'):self.values[a['property']]=a.get('content','')

def parse_cafe24(text,site):
 meta=Metadata();meta.feed(text)
 name=variable(text,'product_name') or ''
 if meta.values.get('product:productId')!=site['product'] or '포켓몬' not in name or not re.search(r'GO\s*Plus\s*\+',name,re.I):return 'UNKNOWN',None
 value=variable(text,'product_price');price=int(value) if value and value.isdigit() else None
 if price is None:return 'UNKNOWN',None
 sold=variable(text,'is_soldout_icon');stock=variable(text,'stock_number')
 if sold=='T':return 'SOLD_OUT',price
 if sold=='F' and stock and stock.isdigit() and int(stock)>0 and variable(text,'has_option')=='F':
  return ('AVAILABLE' if price<=MAX_PRICE else 'OVER_PRICE'),price
 return 'UNKNOWN',price

def parse_official(data):
 text=data.get('text','')
 if not re.search(r'Pok[eé]mon\s+GO\s+Plus\s*\+',text,re.I) or not re.search(r'상품번호\s*114169355\b',text):return 'UNKNOWN',None
 # Product summary has name, then current price, before shipping and recommendations.
 match=re.search(r'Pok[eé]mon\s+GO\s+Plus\s*\+\s*([\d,]+)\s*원',text,re.I)
 price=int(match[1].replace(',','')) if match else None
 buttons=data.get('buttons',[])
 sold=any('구매불가' in b['text'] for b in buttons)
 buy=any(b['text'].strip()=='구매하기' and b.get('order') and b.get('enabled') for b in buttons)
 if sold and not buy:return 'SOLD_OUT',price
 if buy and not sold and price:return ('AVAILABLE' if price<=MAX_PRICE else 'OVER_PRICE'),price
 return 'UNKNOWN',price

def advance(old,status,price,now):
 result=dict(old);result.update(status=status,price=price,checked_at=now)
 if status!='AVAILABLE':
  result['confirmations']=0
  if status in ('SOLD_OUT','OVER_PRICE'):result['notified']=False
  return result,False
 result['confirmations']=1
 return result,not result.get('notified',False)

def request_json(url,token=None,payload=None,method=None):
 headers={'Accept':'application/vnd.github+json','User-Agent':'GOPlus-Restock-Monitor/1.0'}
 if token:headers['Authorization']='Bearer '+token
 body=json.dumps(payload).encode() if payload is not None else None
 if body is not None:headers['Content-Type']='application/json'
 req=urllib.request.Request(url,data=body,headers=headers,method=method)
 with urllib.request.urlopen(req,timeout=20) as response:return json.load(response)

def telegram(text,url=None):
 token=os.environ.get('TELEGRAM_BOT_TOKEN','');chat=os.environ.get('TELEGRAM_CHAT_ID','')
 if not token or not chat:return False
 payload={'chat_id':chat,'text':text,'disable_web_page_preview':True}
 if url:payload['reply_markup']={'inline_keyboard':[[{'text':'상품 페이지 열기','url':url}]]}
 try:return request_json('https://api.telegram.org/bot'+token+'/sendMessage',payload=payload).get('ok') is True
 except Exception:return False # Never print exception URLs containing bot credentials.

def load_state(repo,token):
 url=f'https://api.github.com/repos/{repo}/contents/pogoplus-state.json?ref={STATE_BRANCH}'
 try:
  item=request_json(url,token);return json.loads(base64.b64decode(item['content'])),item['sha']
 except urllib.error.HTTPError as e:
  if e.code==404:return {'version':1,'sites':{}},None
  raise RuntimeError('STATE_READ_FAILED') from None

def save_state(repo,token,state,sha):
 payload={'message':'Update GO Plus+ monitoring state [skip ci]','branch':STATE_BRANCH,
          'content':base64.b64encode(json.dumps(state,ensure_ascii=False,indent=2).encode()).decode()}
 if sha:payload['sha']=sha
 request_json(f'https://api.github.com/repos/{repo}/contents/pogoplus-state.json',token,payload,'PUT')

def fetch_cafe24(site):
 req=urllib.request.Request(site['url'],headers={'User-Agent':'Mozilla/5.0 (compatible; RestockMonitor/1.0)'})
 with urllib.request.urlopen(req,timeout=20) as response:
  raw=response.read(3000001)
  if len(raw)>3000000:raise ValueError('TOO_LARGE')
  content=raw.decode('utf8',errors='replace')
 return parse_cafe24(content,site)

def fetch_official(site):
 from playwright.sync_api import sync_playwright
 with sync_playwright() as p:
  browser=p.chromium.launch(channel='chrome',headless=True)
  try:
   page=browser.new_page();page.goto(site['url'],wait_until='domcontentloaded',timeout=30000)
   page.get_by_role('heading',name='Pokémon GO Plus +',exact=True).wait_for(timeout=20000)
   page.wait_for_function("() => [...document.querySelectorAll('button')].some(b => b.getClientRects().length && /구매불가|구매하기/.test(b.innerText))",timeout=20000)
   data=page.evaluate("""() => ({text:document.body.innerText,buttons:[...document.querySelectorAll('button')].filter(b=>b.getClientRects().length&&getComputedStyle(b).visibility!=='hidden').map(b=>({text:b.innerText,enabled:!b.disabled&&b.getAttribute('aria-disabled')!=='true',order:b.getAttribute('shopby-action')==='PRODUCT_ORDER'}))})""")
   return parse_official(data)
  finally:browser.close()

def run():
 repo=os.environ['GITHUB_REPOSITORY'];token=os.environ['GITHUB_TOKEN']
 state,sha=load_state(repo,token)
 if state.get('version')!=1 or not isinstance(state.get('sites'),dict):raise RuntimeError('INVALID_STATE')
 now=time.time();report={'checked_at':now,'sites':{}}
 if not state.get('startup_test_accepted'):
  accepted=telegram('[포고플플 GitHub 감시 연결 테스트]\n정가 64,800원 이하 상품을 약 5분 예약 주기로 확인합니다. GitHub 사정으로 실행이 늦어질 수 있습니다. 실제 재입고 알림이 아닙니다.')
  report['startup_test_accepted']=accepted;state['startup_test_accepted']=accepted
 for site in SITES:
  old=state['sites'].get(site['id'],{})
  if now<old.get('retry_until',0):report['sites'][site['id']]={'status':'BACKOFF','retry_until':old['retry_until']};continue
  code=None
  try:status,price=fetch_official(site) if site['kind']=='official' else fetch_cafe24(site)
  except urllib.error.HTTPError as e:status,price,code='ERROR',None,e.code
  except Exception:status,price='ERROR',None
  new,send=advance(old,status,price,now)
  failures=old.get('failures',0)+1 if status in ('ERROR','UNKNOWN') else 0
  new['failures']=failures
  if failures:new['retry_until']=now+min(3600,300*2**min(failures-1,4))
  else:new.pop('retry_until',None)
  if send:
   accepted=telegram(f"[포고플플 구매 가능 감지]\n{site['name']}\n{price:,}원 (배송비 별도)\n구매 가능 상태를 1회 확인했습니다. 최종 재고·구매 조건은 직접 확인하세요.\n{site['url']}",site['url'])
   new['notified']=accepted;new['last_alert_accepted']=accepted
  if failures>=3 and now-old.get('failure_notice_at',0)>=21600:
   if telegram(f"[포고플플 감시 점검 필요]\n{site['name']}에서 {failures}회 연속 조회·판독에 실패했습니다. 품절로 판단하지 않으며 대기 후 재확인합니다."):
    new['failure_notice_at']=now
  state['sites'][site['id']]=new
  report['sites'][site['id']]={'status':status,'price':price,'failures':failures,'http_error':code,'alert_attempted':send}
 state['checked_at']=now;state['last_report']=report
 save_state(repo,token,state,sha)
 Path('pogoplus-report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
 print(json.dumps(report,ensure_ascii=False))
 if not state.get('startup_test_accepted'):raise RuntimeError('TELEGRAM_CONFIGURATION_OR_DELIVERY_FAILED')

if __name__=='__main__':
 try:run()
 except Exception as e:print('MONITOR_FAILED: '+type(e).__name__);raise SystemExit(1)
