import unittest
from datetime import timedelta
from unittest.mock import patch
import tickets

class TicketTests(unittest.TestCase):
 def setUp(self):tickets._cache.clear();tickets._token=None
 def test_query_path_comes_from_official_page(self):
  with patch.object(tickets,'http',return_value="var CLeftTicketUrl = 'leftTicket/queryG';"):
   self.assertEqual(tickets.rail_query_path(),'leftTicket/queryG')
 def test_query_path_rejects_arbitrary_url(self):
  with patch.object(tickets,'http',return_value="var CLeftTicketUrl = 'https://evil.test';"):
   with self.assertRaises(tickets.TicketError):tickets.rail_query_path()
 def test_money_rejects_unavailable_and_nonfinite(self):
  self.assertEqual(tickets.money('¥960.0'),960)
  for value in ('无','--','NaN','Infinity',-2,True,'0'):self.assertIsNone(tickets.money(value))
 def test_official_station_parsing(self):
  with patch.object(tickets,'http',return_value="var station_names='@szb|深圳北|IOQ|shenzhenbei|szb|1|';"):
   self.assertEqual(tickets.stations({'query':'深圳'})['stations'][0]['code'],'IOQ')
 def test_rail_separates_price_failure_from_empty_routes(self):
  p=['']*36;p[2]='train';p[3]='G1';p[6]='AAA';p[7]='BBB';p[8]='09:00';p[9]='12:00';p[10]='03:00';p[11]='Y';p[16]='01';p[17]='02';p[30]='无';p[35]='O'
  def get(url,**kw):
   if 'queryTicketPrice' in url:return {'status':True,'data':{'O':'¥88.50'}}
   return {'status':True,'data':{'result':['|'.join(p)],'map':{}}}
  stations=[{'code':'AAA','name':'起点'},{'code':'BBB','name':'终点'}]
  with patch.object(tickets,'station_list',return_value=stations),patch.object(tickets,'get_json',side_effect=get),patch.object(tickets,'rail_query_path',return_value='leftTicket/queryG'):
   result=tickets.search({'kind':'rail','origin':'AAA','destination':'BBB','date':str(tickets.today()+timedelta(days=1))})
   self.assertEqual(result['offers'][0]['fares'][0]['price'],88.5)
   self.assertEqual(result['offers'][0]['fares'][0]['availability'],'无')
   self.assertNotIn('_fare',result['offers'][0]);self.assertNotIn('secret',str(result))
 def test_flight_never_uses_test_environment_or_fake_prices(self):
  with patch.dict(tickets.os.environ,{'AMADEUS_CLIENT_ID':'','AMADEUS_CLIENT_SECRET':''}):
   with self.assertRaisesRegex(tickets.TicketError,'缺少正式航班'):tickets.flights({'origin':'SZX','destination':'PEK','date':str(tickets.today())})
 def test_no_arbitrary_network_target(self):
  for url in ('http://api.amadeus.com/x','https://evil.test/x','https://api.amadeus.com.evil.test/x','https://a:b@api.amadeus.com/x'):
   with self.assertRaises(tickets.TicketError):tickets.http(url)
 def test_invalid_and_past_dates(self):
  for date in ('bad','2020-01-01',None):
   with self.assertRaises(tickets.TicketError):tickets.date_input({'date':date})
 def test_flight_reads_grand_total(self):
  data={'data':[{'price':{'currency':'CNY','grandTotal':'1234.50','total':'1200'},'itineraries':[{'duration':'PT3H','segments':[{'carrierCode':'CZ','number':'123','departure':{'iataCode':'SZX','at':'2030-01-01T10:00'},'arrival':{'iataCode':'PEK','at':'2030-01-01T13:00'}}]}]}]}
  with patch.object(tickets,'flight_token',return_value='secret-token'),patch.object(tickets,'get_json',return_value=data) as get:
   result=tickets.flights({'origin':'SZX','destination':'PEK','date':str(tickets.today())})
   self.assertEqual(result['offers'][0]['fares'][0]['price'],1234.5)
   self.assertTrue(get.call_args.args[0].startswith('https://api.amadeus.com/'))
   self.assertNotIn('secret-token',str(result))
if __name__=='__main__':unittest.main()
