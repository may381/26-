import argparse,concurrent.futures,hashlib,json,time,sys
from pathlib import Path
import requests
for output in (sys.stdout,sys.stderr):
 if hasattr(output,'reconfigure'):output.reconfigure(encoding='utf-8',errors='backslashreplace')
parser=argparse.ArgumentParser()
parser.add_argument('--model-dir',required=True)
parser.add_argument('--workers',type=int,default=8,choices=range(1,25))
args=parser.parse_args()
root=Path(args.model_dir).resolve();root.mkdir(parents=True,exist_ok=True)
files=[];sources=[];chunk=512*1024
for repo,folder,allow in [
 ('csukuangfj/kokoro-multi-lang-v1_1','kokoro-multi-lang-v1_1',None),
 ('csukuangfj/sherpa-onnx-sense-voice-zh-en-ja-ko-yue-2024-07-17','sherpa-onnx-sense-voice-zh-en-ja-ko-yue-int8-2024-07-17',{'model.int8.onnx','tokens.txt','LICENSE','README.md','test_wavs/zh.wav'})]:
 r=requests.get('https://huggingface.co/api/models/'+repo+'?blobs=true',timeout=30);r.raise_for_status();meta=r.json();revision=meta['sha'];sources.append({'repo':repo,'revision':revision})
 for f in meta['siblings']:
  name=f['rfilename']
  if name.startswith('.') or name.endswith('.py') or (allow is not None and name not in allow):continue
  dest=root/folder/name
  if not dest.resolve().is_relative_to(root):raise RuntimeError('Invalid file path')
  dest.parent.mkdir(parents=True,exist_ok=True)
  size=f['size'];sha=f.get('lfs',{}).get('sha256')
  if dest.exists() and dest.stat().st_size==size and (not sha or hashlib.sha256(dest.read_bytes()).hexdigest()==sha):continue
  files.append((f'https://huggingface.co/{repo}/resolve/{revision}/{name}',dest,size,sha))
jobs=[]
for url,dest,size,sha in files:
 if size<=chunk:jobs.append((url,dest,0,size-1,size,False))
 else:
  parts=dest.with_name(dest.name+'.ranges');parts.mkdir(exist_ok=True)
  for start in range(0,size,chunk):jobs.append((url,parts/str(start),start,min(size,start+chunk)-1,size,True))
def error_reason(exc):
 text=str(exc).lower()
 reasons=[p for p in ('CERTIFICATE_VERIFY_FAILED','UNEXPECTED_EOF','SSLEOFError','WRONG_VERSION_NUMBER','timed out','Connection reset') if p.lower() in text]
 return ', '.join(reasons) or 'Unclassified TLS/network error'

def download(job):
 url,dest,start,end,total,ranged=job
 if ranged and dest.exists() and dest.stat().st_size==end-start+1:return
 for attempt in range(4):
  try:
   headers={'Range':f'bytes={start}-{end}'} if ranged else {}
   r=requests.get(url,headers=headers,timeout=(30,90));r.raise_for_status()
   if ranged and (r.status_code!=206 or r.headers.get('Content-Range')!=f'bytes {start}-{end}/{total}'):raise RuntimeError('Incorrect range')
   if len(r.content)!=end-start+1:raise RuntimeError('Incorrect length')
   tmp=dest.with_name(dest.name+'.tmp');tmp.write_bytes(r.content);tmp.replace(dest);return
  except Exception as exc:
   if attempt==3:raise
   print('Retry:',dest.name,type(exc).__name__,'attempt',attempt+1,'reason:',error_reason(exc),flush=True)
   time.sleep(min(2**(attempt+1),15))
print('Chunks to download:',len(jobs),flush=True)
failed=0
with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as pool:
 pending={pool.submit(download,job) for job in jobs}
 checked=0
 while pending:
  done,pending=concurrent.futures.wait(pending,timeout=15,return_when=concurrent.futures.ALL_COMPLETED)
  for future in done:
   checked+=1
   try:future.result()
   except Exception as exc:
    failed+=1
    print('Chunk failed:',type(exc).__name__,'reason:',error_reason(exc),'saved chunks retained',flush=True)
  print('Chunks checked:',checked,'pending:',len(pending),'failed:',failed,flush=True)
if failed:
 print('Download incomplete. Rerun the same command to resume saved chunks.',flush=True)
 sys.exit(1)
for url,dest,size,sha in files:
 if size>chunk:
  parts=dest.with_name(dest.name+'.ranges');tmp=dest.with_name(dest.name+'.assemble')
  with tmp.open('wb') as out:
   for start in range(0,size,chunk):out.write((parts/str(start)).read_bytes())
  if sha and hashlib.sha256(tmp.read_bytes()).hexdigest()!=sha:raise RuntimeError('Model checksum mismatch')
  tmp.replace(dest)
 print('Verified:',dest.name,size,flush=True)
(root/'sources.json').write_text(json.dumps(sources,indent=2),encoding='utf-8')
print('ALL MODELS DOWNLOADED AND VERIFIED',flush=True)
