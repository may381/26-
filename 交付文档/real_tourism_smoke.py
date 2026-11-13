"""Opt-in real tourism smoke using public place data, never booking or notifying."""
import json
from urllib.request import build_opener, HTTPCookieProcessor, ProxyHandler, Request
from urllib.error import HTTPError
from http.cookiejar import CookieJar
from datetime import datetime, timedelta, timezone
from pathlib import Path
import argparse


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--port',type=int,default=8092);parser.add_argument('--save-draft',action='store_true');args=parser.parse_args()
    if not 1<=args.port<=65535:parser.error('invalid port')
    opener=build_opener(ProxyHandler({}),HTTPCookieProcessor(CookieJar()))
    base='http://127.0.0.1:'+str(args.port)
    def call(method,path,payload=None):
        request=Request(base+path,method=method,data=None if payload is None else json.dumps(payload,ensure_ascii=False).encode('utf-8'),headers={'Content-Type':'application/json'})
        try:
            with opener.open(request,timeout=150) as response:return response.status,json.load(response)
        except HTTPError as error:return error.code,json.load(error)
    date=(datetime.now(timezone(timedelta(hours=8)))+timedelta(days=2)).date().isoformat()
    payload=dict(destination='长沙',startDate=date,days=2,walkMinutes=20,companions='家人同行',avoidSteps=True,restFrequency='frequent',travelMode='transit',pace='slow')
    status,result=call('POST','/api/a1/travel-drafts',payload)
    assert status==200 and result['code']=='OK', 'draft failed'
    draft=result['data'];assert draft['source']=='AMAP' and len(draft['days'])==2
    assert all(len(day['places'])<=2 for day in draft['days'])
    assert all(day['timeline'] for day in draft['days'] if day['places'])
    summary={'mode':'REAL_AMAP_LOCAL_DRAFT','port':args.port,'dayCount':2,'placeCounts':[len(day['places']) for day in draft['days']], 'initialVersion':draft['version'],'saved':False,'bookingExecuted':False,'notificationExecuted':False}
    known_city_place=next((p for day in draft['days'] for p in day['places'] if p.get('city')),None)
    summary['citySourceAvailable']=known_city_place is not None
    if known_city_place:
        wrong_city={**payload,'destination':'北京','importedPlaceIds':[known_city_place['id']]}
        rejected,_=call('POST','/api/a1/travel-drafts',wrong_city)
        assert rejected==400,'cross-city place was accepted'
        current_status,current=call('GET','/api/a1/travel-drafts/current')
        assert current_status==200 and current['data']['id']==draft['id'],'rejected request changed current draft'
        summary.update(crossCityStatus=rejected,previousDraftPreserved=True)
    if args.save_draft:
        edit={'id':draft['id'],'title':'验收测试草案（非正式行程）','expectedVersion':draft['version'],'days':[{'date':d['date'],'placeIds':[p['id'] for p in d['places']]} for d in draft['days']]}
        status,result=call('PUT','/api/a1/travel-drafts/current',edit)
        assert status==200 and result['data']['version']==draft['version']+1,'save failed'
        status,restored=call('GET','/api/a1/travel-drafts/current')
        assert status==200 and restored['data']['id']==draft['id'],'restore failed'
        conflict,_=call('PUT','/api/a1/travel-drafts/current',edit)
        assert conflict==409,'stale edit was accepted'
        summary.update(saved=True,savedVersion=result['data']['version'],staleEditStatus=conflict)
    target=Path(__file__).resolve().parent/'旅游实际HTTP验收结果.json'
    target.write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(summary,ensure_ascii=False,indent=2))


if __name__=='__main__':main()
