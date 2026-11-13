"""Download public SenseVoice weights, resume verified ranges, check official SHA256."""
from pathlib import Path
import concurrent.futures, hashlib, re, subprocess

ROOT=Path(__file__).resolve().parent/'models'/'sensevoice'
URL='https://huggingface.co/csukuangfj/sherpa-onnx-sense-voice-zh-en-ja-ko-yue-2024-07-17/resolve/main/'
SIZE=239233841
SHA='c71f0ce00bec95b07744e116345e33d8cbbe08cef896382cf907bf4b51a2cd51'
CHUNK=2*1024*1024

def fetch(index):
    start=index*CHUNK;end=min(SIZE,start+CHUNK)-1
    path=ROOT/f'range-{index:03}'
    if path.exists() and path.stat().st_size==end-start+1:return
    for attempt in range(3):
        headers=path.with_suffix('.headers')
        result=subprocess.run(['curl.exe','--fail','-L','--range',f'{start}-{end}','--connect-timeout','10','--max-time','90','-sS','-D',str(headers),'-o',str(path),URL+f'model.int8.onnx?download=true&a1part={index}'],capture_output=True)
        ranges=re.findall(r'content-range:\s*bytes\s+(\d+)-(\d+)/(\d+)',headers.read_text(errors='ignore') if headers.exists() else '',re.I)
        if result.returncode==0 and ranges and tuple(map(int,ranges[-1]))==(start,end,SIZE) and path.stat().st_size==end-start+1:
            print(f'part {index+1}/{(SIZE+CHUNK-1)//CHUNK} ready',flush=True);return
    raise RuntimeError(f'Range {index} incomplete; rerun to resume')

if __name__=='__main__':
    ROOT.mkdir(parents=True,exist_ok=True)
    with concurrent.futures.ThreadPoolExecutor(max_workers=16) as pool:list(pool.map(fetch,range((SIZE+CHUNK-1)//CHUNK)))
    output=ROOT/'verified-model.tmp';digest=hashlib.sha256()
    with output.open('wb') as target:
        for index in range((SIZE+CHUNK-1)//CHUNK):
            data=(ROOT/f'range-{index:03}').read_bytes();target.write(data);digest.update(data)
    if digest.hexdigest()!=SHA:raise RuntimeError('Official model SHA256 mismatch')
    subprocess.run(['curl.exe','--fail','-L','--connect-timeout','10','--max-time','60','-sS','-o',str(ROOT/'tokens.txt'),URL+'tokens.txt'],check=True)
    output.replace(ROOT/'model.int8.onnx')
    print('SenseVoice model SHA256 verified; ready for local inference',flush=True)
