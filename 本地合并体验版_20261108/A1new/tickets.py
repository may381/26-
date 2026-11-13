"""Read-only official rail fares and production Amadeus flight offers.
No booking, simulated quotes, credential logging, or TLS verification bypass.
"""
import base64
import json
import os
import re
import ssl
import shutil
import subprocess
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from urllib.parse import urlencode, urlsplit
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError

ALLOWED_HOSTS = {'kyfw.12306.cn', 'api.amadeus.com'}
RAIL_HOME = 'https://kyfw.12306.cn/otn/leftTicket/init'
FLIGHT_HOME = 'https://www.travelsky.com/'
MAX_RESPONSE = 4 * 1024 * 1024
_cache = {}
_lock = threading.Lock()
_token = None

class TicketError(ValueError):
    pass

def now():
    return datetime.now(timezone.utc).isoformat()

def today():
    return datetime.now(timezone(timedelta(hours=8))).date()

def http(url, method='GET', body=None, headers=None):
    parsed=urlsplit(url)
    if parsed.scheme!='https' or parsed.hostname not in ALLOWED_HOSTS or parsed.username or parsed.password:
        raise TicketError('不允许的票务数据地址')
    headers={**(headers or {})}
    payload=None if body is None else body.encode('utf-8')
    request=Request(url,data=payload,headers=headers,method=method)
    try:
        if sys.platform=='win32':
            data=windows_http(url,method,body,headers)
        else:
            with urlopen(request,timeout=15) as response:
                data=response.read(MAX_RESPONSE+1)
    except HTTPError as exc:
        raise TicketError('票务数据源返回 HTTP '+str(exc.code)+'，未获得有效报价') from None
    except (URLError,TimeoutError,OSError):
        raise TicketError('票务网络连接失败或证书验证失败，请稍后重试或前往官网') from None
    if len(data)>MAX_RESPONSE:raise TicketError('票务响应过大')
    return data.decode('utf-8-sig')

def windows_http(url,method,body,headers):
    # Native .NET validates certificates against the Windows trust store.
    # Request content travels via stdin, never process arguments or logs.
    script=r'''$ErrorActionPreference='Stop'; try { $v=[Console]::In.ReadToEnd()|ConvertFrom-Json; $h=@{}; $v.headers.psobject.Properties|ForEach-Object { $h[$_.Name]=$_.Value }; $ticketRequestArgs=@{Uri=$v.url;Method=$v.method;TimeoutSec=15}; if($h.Count){$ticketRequestArgs.Headers=$h}; if($null -ne $v.body){$ticketRequestArgs.Body=$v.body}; $r=Invoke-WebRequest @ticketRequestArgs; if($r.Content.Length -gt 4194304){throw 'size'}; [Console]::Out.Write([Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes([string]$r.Content))) } catch { [Console]::Error.Write('upstream failed'); exit 1 }'''
    encoded=base64.b64encode(script.encode('utf-16le')).decode('ascii')
    try:
        result=subprocess.run([shutil.which('pwsh') or 'powershell.exe','-NoProfile','-NonInteractive','-EncodedCommand',encoded],input=json.dumps({'url':url,'method':method,'body':body,'headers':headers}),text=True,encoding='utf-8',capture_output=True,timeout=22,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        if result.returncode:raise TicketError('官方票务数据源暂不可用，请前往官网查询')
        return base64.b64decode(result.stdout.strip(),validate=True)
    except (subprocess.TimeoutExpired,OSError,ValueError) as exc:
        if isinstance(exc,TicketError):raise
        raise TicketError('票务查询超时或系统证书验证失败，请前往官网查询') from None

def get_json(url, **kw):
    try:
        raw=http(url,**kw)
        if raw.lstrip().startswith('<'):
            if '网络可能存在问题' in raw:raise TicketError('12306当前返回网络异常页面，未返回车次或票价；请打开12306官网核实')
            raise TicketError('12306返回网页而非票务数据，可能需要官网验证；未取得票价')
        value=json.loads(raw)
        if not isinstance(value,dict):raise ValueError()
        return value
    except (ValueError,TypeError) as exc:
        if isinstance(exc,TicketError):raise
        raise TicketError('官方数据源未返回有效数据，可能需要在官网验证') from None

def cached(key, ttl, fn):
    with _lock:
        old=_cache.get(key)
        if old and time.monotonic()-old[0]<ttl:return old[1]
    value=fn()
    with _lock:
        if len(_cache)>150:_cache.clear()
        _cache[key]=(time.monotonic(),value)
    return value

def station_list():
    def load():
        text=http('https://kyfw.12306.cn/otn/resources/js/framework/station_name.js')
        values=[]
        for record in text.split('@')[1:]:
            p=record.split('|')
            if len(p)>=5 and re.fullmatch('[A-Z]{3}',p[2]):values.append({'name':p[1],'code':p[2],'pinyin':p[3],'initials':p[4]})
        if not values:raise TicketError('未获得有效的官方站名表')
        return values
    return cached('stations',86400,load)

def stations(payload):
    query=payload.get('query','')
    if not isinstance(query,str) or not 1<=len(query.strip())<=40:raise TicketError('请输入车站名称或拼音')
    q=query.strip().lower()
    values=sorted((s for s in station_list() if q in s['name'] or q in s['pinyin'] or q in s['initials'] or q==s['code'].lower()),key=lambda s:(s['name']!=query,len(s['name'])))[:12]
    return {'source':'中国铁路12306公开站名表','stations':values,'retrievedAt':now()}

def money(value):
    if not isinstance(value,(str,int,float)) or isinstance(value,bool):return None
    text=str(value).replace('¥','').replace('￥','').strip()
    try:
        number=Decimal(text)
        return float(number) if number.is_finite() and number>0 else None
    except InvalidOperation:return None

def date_input(payload):
    try:day=date.fromisoformat(payload.get('date',''))
    except (ValueError,TypeError):raise TicketError('请选择有效出发日期') from None
    if day<today() or day>today()+timedelta(days=330):raise TicketError('请选择今天起330天以内的日期')
    return day.isoformat()

def rail_query_path():
    def load():
        page=http(RAIL_HOME)
        match=re.search(r"var\s+CLeftTicketUrl\s*=\s*['\"](leftTicket/query[A-Za-z]*)['\"]",page)
        if not match:raise TicketError('12306官网未提供可识别的查询入口，请在官网查询')
        return match.group(1)
    return cached('official-rail-query-path',600,load)

def rail(payload):
    day=date_input(payload);origin=payload.get('origin','');destination=payload.get('destination','')
    if not all(isinstance(v,str) and re.fullmatch('[A-Z]{3}',v) for v in (origin,destination)) or origin==destination:
        raise TicketError('请从官方站名列表选择不同的出发站和到达站')
    by_code={s['code']:s for s in station_list()}
    if origin not in by_code or destination not in by_code:raise TicketError('车站代码不在官方站名表内')
    query={'leftTicketDTO.train_date':day,'leftTicketDTO.from_station':origin,'leftTicketDTO.to_station':destination,'purpose_codes':'ADULT'}
    def load():
        data=get_json('https://kyfw.12306.cn/otn/'+rail_query_path()+'?'+urlencode(query),headers={'Referer':RAIL_HOME})
        if data.get('status') is not True or not isinstance(data.get('data'),dict):raise TicketError('12306暂未返回余票数据，日期可能未开售，请在官网核对')
        raw=data['data'].get('result')
        if not isinstance(raw,list):raise TicketError('12306查询格式已变化，请前往官网')
        rows=[]
        for text in raw[:8]:
            p=text.split('|') if isinstance(text,str) else []
            if len(p)<36:continue
            names=data['data'].get('map',{})
            rows.append({'service':p[3],'origin':names.get(p[6],by_code.get(p[6],{}).get('name',p[6])),'destination':names.get(p[7],by_code.get(p[7],{}).get('name',p[7])),'departure':p[8],'arrival':p[9],'duration':p[10],'bookable':p[11]=='Y','_fare':{'train_no':p[2],'from_station_no':p[16],'to_station_no':p[17],'seat_types':p[35],'train_date':day},'_seats':{'O':p[30],'M':p[31],'A9':p[32],'A4':p[23],'A3':p[28],'A1':p[29],'WZ':p[26]}})
        def prices(row):
            try:
                response=get_json('https://kyfw.12306.cn/otn/leftTicket/queryTicketPrice?'+urlencode(row['_fare']),headers={'Referer':RAIL_HOME})
                if response.get('status') is not True:raise TicketError('票价暂不可用')
                prices=response.get('data',{})
                seats=[]
                for code,label in [('O','二等座'),('M','一等座'),('A9','商务座'),('A4','软卧'),('A3','硬卧'),('A1','硬座'),('WZ','无座')]:
                    amount=money(prices.get(code))
                    if amount is not None:seats.append({'name':label,'price':amount,'currency':'CNY','availability':row['_seats'].get(code) or '余票待核实'})
                row['fares']=seats
                if not seats:row['priceNotice']='此车次未返回可核实席别价格'
            except TicketError:row['fares']=[];row['priceNotice']='车次已查到，票价暂未返回，请在12306核实'
            row.pop('_fare',None);row.pop('_seats',None)
            return row
        with ThreadPoolExecutor(max_workers=2) as executor:offers=list(executor.map(prices,rows))
        return {'kind':'rail','source':'中国铁路12306','sourceUrl':RAIL_HOME,'retrievedAt':now(),'date':day,'origin':by_code[origin]['name'],'destination':by_code[destination]['name'],'offers':offers,'totalServices':len(raw),'notice':'展示前8班；成人票价与余票以支付确认时为准。席别为实时查询值，不代表已锁票；卧铺铺别价格请在官网确认。' if offers else '该日期或站点暂无返回车次，可能未开售；请在12306核对。'}
    return cached(('rail',day,origin,destination),30,load)

def flight_token():
    global _token
    key=os.getenv('AMADEUS_CLIENT_ID','');secret=os.getenv('AMADEUS_CLIENT_SECRET','')
    if not key or not secret:raise TicketError('缺少正式航班报价凭证：请在本机配置AMADEUS_CLIENT_ID和AMADEUS_CLIENT_SECRET；未取得报价')
    with _lock:
        if _token and time.monotonic()<_token[0]:return _token[1]
    data=get_json('https://api.amadeus.com/v1/security/oauth2/token',method='POST',body=urlencode({'grant_type':'client_credentials','client_id':key,'client_secret':secret}),headers={'Content-Type':'application/x-www-form-urlencoded'})
    if not isinstance(data.get('access_token'),str):raise TicketError('航班供应商授权未成功')
    with _lock:_token=(time.monotonic()+max(0,int(data.get('expires_in',0))-60),data['access_token'])
    return data['access_token']

def flights(payload):
    day=date_input(payload);origin=payload.get('origin','');destination=payload.get('destination','')
    if not all(isinstance(v,str) and re.fullmatch('[A-Z]{3}',v) for v in (origin,destination)) or origin==destination:raise TicketError('请输入不同的机场/城市IATA三字码，例如SZX、PEK')
    token=flight_token()
    data=get_json('https://api.amadeus.com/v2/shopping/flight-offers?'+urlencode({'originLocationCode':origin,'destinationLocationCode':destination,'departureDate':day,'adults':1,'currencyCode':'CNY','max':12}),headers={'Authorization':'Bearer '+token})
    if not isinstance(data.get('data'),list):raise TicketError('航班供应商未返回有效报价')
    offers=[]
    for offer in data['data']:
        price=offer.get('price',{});amount=money(price.get('grandTotal') or price.get('total'))
        if amount is None:continue
        itineraries=offer.get('itineraries',[])
        if not itineraries:continue
        segments=itineraries[0].get('segments',[])
        if not segments:continue
        offers.append({'service':' / '.join(str(s.get('carrierCode',''))+str(s.get('number','')) for s in segments),'origin':segments[0].get('departure',{}).get('iataCode',origin),'destination':segments[-1].get('arrival',{}).get('iataCode',destination),'departure':segments[0].get('departure',{}).get('at'),'arrival':segments[-1].get('arrival',{}).get('at'),'duration':itineraries[0].get('duration'),'stops':len(segments)-1,'fares':[{'name':'单程成人报价','price':amount,'currency':price.get('currency','CNY'),'availability':'可售状态仍需下单前复核'}],'lastTicketingDate':offer.get('lastTicketingDate')})
    return {'kind':'flight','source':'Amadeus正式环境','sourceUrl':'https://developers.amadeus.com/','retrievedAt':now(),'date':day,'origin':origin,'destination':destination,'offers':offers,'notice':'正式供应商返回的一名成人单程总报价；行李、退改和附加收费以出票条款为准。当前未锁价或购票，部分航司和国内航线可能不在供应商覆盖内。'}

def search(payload):
    if not isinstance(payload,dict):raise TicketError('查询格式无效')
    return rail(payload) if payload.get('kind')=='rail' else flights(payload) if payload.get('kind')=='flight' else (_ for _ in ()).throw(TicketError('请选择火车票或机票'))
