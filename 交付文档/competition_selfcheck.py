"""Read-only competition readiness probe. Does not submit analyses or notify anyone."""
import argparse
import json
from datetime import datetime, timezone
from urllib.request import build_opener, ProxyHandler, Request
from urllib.error import HTTPError, URLError
from pathlib import Path


def check(url, json_body=False):
    try:
        opener = build_opener(ProxyHandler({}))
        with opener.open(Request(url, headers={'Accept':'application/json' if json_body else 'text/html'}), timeout=5) as response:
            raw=response.read(1024*1024)
            body=json.loads(raw) if json_body else None
            return {'reachable':True,'httpStatus':response.status,'data':body}
    except HTTPError as error:
        return {'reachable':True,'httpStatus':error.code,'error':'HTTP_ERROR'}
    except (URLError,TimeoutError,OSError,ValueError):
        return {'reachable':False,'error':'UNREACHABLE_OR_INVALID_RESPONSE'}


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--tourism-port',type=int,default=8091)
    parser.add_argument('--school',action='store_true',help='Explicitly probe school model list')
    args=parser.parse_args()
    if not 1<=args.tourism_port<=65535:parser.error('Invalid tourism port')
    tourism='http://127.0.0.1:'+str(args.tourism_port)
    results={
      'tourismPage':check(tourism+'/'),
      'showcase':check(tourism+'/showcase.html'),
      'fraudPage':check('http://127.0.0.1:5174/'),
      'fraudBackend':check('http://127.0.0.1:8000/api/health',True),
      'a1Shell':check('http://127.0.0.1:8093/health',True),
    }
    if args.school:
        raw=check('http://10.138.50.151:8000/v1/models',True)
        entries=(raw.get('data') or {}).get('data',[]) if isinstance(raw.get('data'),dict) else []
        results['schoolModel']={'reachable':raw['reachable'],'configuredModelListed':any(x.get('id')=='qwen3.8-27b' for x in entries)}
    # Do not copy backend local paths, usernames or stored business information into report.
    backend=results['fraudBackend'].pop('data',None)
    if isinstance(backend,dict):
        results['fraudBackend'].update({k:backend.get(k) for k in ('model_configured','model_ready','provider','model','database_ready')})
    report={'checkedAt':datetime.now(timezone.utc).isoformat(),'checks':results,
            'notice':'Reachability only. Not proof of model generation, business success or completed P2 integration.'}
    target=Path(__file__).resolve().parent/'运行自检结果.json'
    target.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(report,ensure_ascii=False,indent=2))


if __name__=='__main__':main()
