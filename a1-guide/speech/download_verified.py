"""Download public weights/wheels in bounded ranges and verify publisher SHA256."""
from pathlib import Path
import argparse,concurrent.futures,hashlib,re,subprocess

def download(url,size,digest,output):
    output=Path(output);output.parent.mkdir(parents=True,exist_ok=True)
    is_git=digest.startswith('git-sha1:');expected=digest.split(':',1)[1] if is_git else digest
    def checksum():return hashlib.sha1(b'blob '+str(size).encode()+b'\0') if is_git else hashlib.sha256()
    def matches(path):h=checksum();h.update(path.read_bytes());return h.hexdigest()==expected
    if output.exists() and matches(output):return
    parts=output.with_name(output.name+'.parts');parts.mkdir(exist_ok=True);chunk=256*1024
    def fetch(index):
        start=index*chunk;end=min(size,start+chunk)-1;part=parts/f'{index:04}';headers=parts/f'{index:04}.headers'
        if part.exists() and part.stat().st_size==end-start+1:return
        for attempt in range(3):
            suffix=('&' if '?' in url else '?')+f'a1range={index}'
            result=subprocess.run(['curl.exe','--fail','-L','--range',f'{start}-{end}','--connect-timeout','10','--max-time','75','-sS','-D',str(headers),'-o',str(part),url+suffix],capture_output=True)
            found=re.findall(r'content-range:\s*bytes\s+(\d+)-(\d+)/(\d+)',headers.read_text(errors='ignore') if headers.exists() else '',re.I)
            if result.returncode==0 and found and tuple(map(int,found[-1]))==(start,end,size) and part.stat().st_size==end-start+1:return
        raise RuntimeError(f'Range {index} incomplete')
    total=(size+chunk-1)//chunk
    with concurrent.futures.ThreadPoolExecutor(max_workers=48) as pool:
        for completed,_ in enumerate(pool.map(fetch,range(total)),1):
            if completed%20==0 or completed==total:print(f'{completed}/{total} ranges ready',flush=True)
    pending=output.with_name(output.name+'.verified.tmp');hasher=checksum()
    with pending.open('wb') as writer:
        for index in range(total):data=(parts/f'{index:04}').read_bytes();hasher.update(data);writer.write(data)
    if hasher.hexdigest()!=expected:raise RuntimeError('Publisher SHA256 mismatch')
    pending.replace(output);print('Publisher SHA256 verified',flush=True)

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--url',required=True);parser.add_argument('--size',type=int,required=True);parser.add_argument('--sha256',required=True);parser.add_argument('--output',required=True);args=parser.parse_args();download(args.url,args.size,args.sha256,args.output)
