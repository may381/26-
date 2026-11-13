"""Generate local neural speech. Text and audio stay on this computer."""
from pathlib import Path
import sys,wave,os
import numpy as np
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'vendor'))
import sherpa_onnx

def synthesize(text,output,speaker=66):
 if speaker not in (0,66,100):raise ValueError('Unknown voice')
 output=Path(output).resolve();os.chdir(ROOT);model=Path('models/vits')
 expected={'model.int8.onnx':39870124,'tokens.txt':1671,'lexicon.txt':2042943,'date.fst':59154,'number.fst':64482,'phone.fst':88630}
 if any(not (model/name).is_file() or (model/name).stat().st_size!=size for name,size in expected.items()):raise RuntimeError('Neural voice resources are incomplete')
 config=sherpa_onnx.OfflineTtsConfig(model=sherpa_onnx.OfflineTtsModelConfig(vits=sherpa_onnx.OfflineTtsVitsModelConfig(model=str(model/'model.int8.onnx'),lexicon=str(model/'lexicon.txt'),tokens=str(model/'tokens.txt'),noise_scale=.4,noise_scale_w=.65),num_threads=4,provider='cpu',debug=False),rule_fsts=','.join(str(model/name) for name in ('phone.fst','date.fst','number.fst')),max_num_sentences=2,silence_scale=.25)
 if not config.validate():raise RuntimeError('Invalid neural voice configuration')
 engine=sherpa_onnx.OfflineTts(config);audio=engine.generate(text,sid=speaker,speed=1)
 samples=np.asarray(audio.samples,dtype=np.float32)
 if not len(samples):raise RuntimeError('Empty neural audio')
 samples=np.clip(samples,-1,1)
 with wave.open(str(output),'wb') as writer:writer.setnchannels(1);writer.setsampwidth(2);writer.setframerate(audio.sample_rate);writer.writeframes((samples*32767).astype(np.int16).tobytes())
 print('VOICE=vits-'+str(speaker))
if __name__=='__main__':synthesize(Path(sys.argv[1]).read_text(encoding='utf-8'),sys.argv[2],int(sys.argv[3]))
