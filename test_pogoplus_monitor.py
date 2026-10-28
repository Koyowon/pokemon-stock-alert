import unittest
from unittest.mock import patch,MagicMock
import pogoplus_monitor as m
class StockTests(unittest.TestCase):
 def test_json_requests_set_content_type(self):
  response=MagicMock();response.__enter__.return_value.read.return_value=b'{"ok":true}'
  with patch.object(m.urllib.request,'urlopen',return_value=response) as call:
   self.assertTrue(m.request_json('https://example.com',payload={'text':'test'})['ok'])
   self.assertEqual(call.call_args.args[0].get_header('Content-type'),'application/json')
 def cafe(self,sold='F',stock='2',price='64800',pid='1053',option='F'):
  return f'''<meta property="product:productId" content="{pid}"><script>var product_name = '포켓몬 Pokémon GO Plus+';var product_price = '{price}';var is_soldout_icon = '{sold}';var stock_number = '{stock}';var has_option = '{option}';</script>'''
 def test_positive_and_sold(self):
  self.assertEqual(m.parse_cafe24(self.cafe(),m.SITES[0]),('AVAILABLE',64800))
  self.assertEqual(m.parse_cafe24(self.cafe(sold='T',stock='0'),m.SITES[0])[0],'SOLD_OUT')
 def test_wrong_product_price_options_unknown(self):
  self.assertEqual(m.parse_cafe24(self.cafe(pid='999'),m.SITES[0])[0],'UNKNOWN')
  self.assertEqual(m.parse_cafe24(self.cafe(price='70000'),m.SITES[0])[0],'OVER_PRICE')
  self.assertEqual(m.parse_cafe24(self.cafe(option='T'),m.SITES[0])[0],'UNKNOWN')
  self.assertEqual(m.parse_cafe24(self.cafe(stock=''),m.SITES[0])[0],'UNKNOWN')
 def test_duplicate_conflicting_variable_unknown(self):
  self.assertEqual(m.parse_cafe24(self.cafe()+"var product_price = '1';",m.SITES[0])[0],'UNKNOWN')
 def test_single_check_and_dedup(self):
  state,send=m.advance({},'AVAILABLE',64800,1000);self.assertTrue(send)
  state,send=m.advance(state,'AVAILABLE',64800,1300);self.assertTrue(send)
  state['notified']=True
  state,send=m.advance(state,'AVAILABLE',64800,1600);self.assertFalse(send)
  state,_=m.advance(state,'SOLD_OUT',64800,1900)
  state,send=m.advance(state,'AVAILABLE',64800,2200);self.assertTrue(send)
  state,send=m.advance(state,'AVAILABLE',64800,2500);self.assertTrue(send)
 def test_error_and_stale_break_confirmation_preserve_notified(self):
  state,_=m.advance({},'AVAILABLE',64800,1000)
  state,_=m.advance(state,'ERROR',None,1300)
  state,send=m.advance(state,'AVAILABLE',64800,1600);self.assertTrue(send)
  _,send=m.advance(state,'AVAILABLE',64800,4000);self.assertTrue(send)
  state['notified']=True;state,_=m.advance(state,'UNKNOWN',None,1900);self.assertTrue(state['notified'])
 def test_official_identity_and_price(self):
  data={'text':'Pokémon GO Plus +\n64,800원\n상품번호\n114169355','buttons':[{'text':'구매하기','order':True,'enabled':True}]}
  self.assertEqual(m.parse_official(data),('AVAILABLE',64800))
  data['buttons'].append({'text':'구매불가'});self.assertEqual(m.parse_official(data)[0],'UNKNOWN')
  data['buttons']=[{'text':'구매불가'}];self.assertEqual(m.parse_official(data)[0],'SOLD_OUT')
  data['text']=data['text'].replace('114169355','999');self.assertEqual(m.parse_official(data)[0],'UNKNOWN')
 def test_official_disabled_purchase_never_available(self):
  self.assertEqual(m.parse_official({'text':'Pokémon GO Plus +\n64,800원\n상품번호\n114169355','buttons':[{'text':'구매하기','order':True,'enabled':False}]})[0],'UNKNOWN')
if __name__=='__main__':unittest.main()
