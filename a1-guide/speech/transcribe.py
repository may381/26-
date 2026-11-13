"""Local ASR with audio checks. No recording is retained or uploaded."""
import sys,subprocess,tempfile,wave,json,re
from pathlib import Path
import av
import numpy as np
root=Path(__file__).resolve().parent

def prepare_audio(path):
 frames=[];duration=0
 with av.open(str(path)) as source:
  resampler=av.AudioResampler(format='s16',layout='mono',rate=16000)
  for frame in source.decode(audio=0):
   duration+=frame.samples/frame.sample_rate
   if duration>35:raise ValueError('Audio too long')
   for part in resampler.resample(frame):frames.append(part.to_ndarray().reshape(-1))
  for part in resampler.resample(None):frames.append(part.to_ndarray().reshape(-1))
 if duration<.5 or not frames:raise ValueError('Audio too short')
 samples=np.concatenate(frames).astype(np.float32)/32768
 samples-=samples.mean()
 rms=float(np.sqrt(np.mean(samples*samples)))
 if rms<.001:return np.empty(0,dtype=np.float32),duration
 blocks=samples[:len(samples)//320*320].reshape(-1,320)
 energy=np.sqrt(np.mean(blocks*blocks,axis=1));threshold=max(.0015,min(.006,float(np.percentile(energy,20))*1.5))
 active=np.flatnonzero(energy>threshold)
 if len(active):samples=samples[max(0,int(active[0])*320-4000):min(len(samples),(int(active[-1])+1)*320+4000)]
 peak=float(np.max(np.abs(samples)))
 if .01<peak<.2 and rms>.003:samples*=min(3,.5/peak)
 return np.clip(samples,-1,1).astype(np.float32),duration

def recognize(path):
 samples,duration=prepare_audio(path)
 if not len(samples):return {'text':'','engine':'audio-check','reason':'quiet'}
 model=root/'models'/'paraformer'/'model.int8.onnx';tokens=model.with_name('tokens.txt')
 if model.is_file() and model.stat().st_size==81828675 and tokens.is_file() and tokens.stat().st_size==75352:
  sys.path.insert(0,str(root/'vendor'))
  import sherpa_onnx
  recognizer=sherpa_onnx.OfflineRecognizer.from_paraformer(paraformer=str(model),tokens=str(tokens),num_threads=4,provider='cpu',debug=False)
  stream=recognizer.create_stream();stream.accept_waveform(16000,samples);recognizer.decode_stream(stream)
  text=re.sub(r'<\|[^>]+\|>','',stream.result.text).strip()
  return {'text':text,'engine':'paraformer-zh-small','duration':round(duration,2)}
 with tempfile.TemporaryDirectory(prefix='a1-sapi-') as folder:
  wavpath=Path(folder)/'recording.wav'
  with wave.open(str(wavpath),'wb') as output:
   output.setnchannels(1);output.setsampwidth(2);output.setframerate(16000);output.writeframes((samples*32767).astype(np.int16).tobytes())
  result=subprocess.run(['powershell.exe','-NoProfile','-NonInteractive','-File',str(root/'recognize.ps1'),'-InputFile',str(wavpath)],capture_output=True,timeout=70)
  if result.returncode:raise RuntimeError('Windows Chinese recognition unavailable')
  data=json.loads(result.stdout.decode('utf-8').lstrip('\ufeff'));data['engine']='windows-compatibility';return data

def place_suggestions(text,names):
 sys.path.insert(0,str(root/'vendor'))
 from pypinyin import lazy_pinyin
 suggestions=[]
 for name in list(dict.fromkeys(names))[:12]:
  if not isinstance(name,str) or not re.fullmatch(r'[\u4e00-\u9fff]{2,20}',name) or name in text:continue
  phonetic=lazy_pinyin(name)
  for at in range(len(text)-len(name)+1):
   fragment=text[at:at+len(name)]
   if not re.fullmatch(r'[\u4e00-\u9fff]+',fragment):continue
   spoken=lazy_pinyin(fragment)
   exact=spoken==phonetic
   near=len(name)>=4 and sum(a!=b for a,b in zip(spoken,phonetic))==1
   if exact or near:
    suggestions.append({'at':at,'fragment':fragment,'name':name,'match':'homophone' if exact else 'single-syllable'});break
  if len(suggestions)>=3:break
 return suggestions

if __name__=='__main__':
 result=recognize(sys.argv[1])
 if len(sys.argv)>2 and result.get('text'):
  names=json.loads(Path(sys.argv[2]).read_text(encoding='utf-8'))
  result['corrections']=place_suggestions(result['text'],names)
 print(json.dumps(result,ensure_ascii=True))
