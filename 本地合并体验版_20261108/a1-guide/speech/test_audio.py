import importlib.util,tempfile,unittest,wave
from pathlib import Path
import numpy as np
spec=importlib.util.spec_from_file_location('a1_transcribe',Path(__file__).with_name('transcribe.py'));audio=importlib.util.module_from_spec(spec);spec.loader.exec_module(audio)
class AudioPreparationTest(unittest.TestCase):
 def check_audio(self,samples,rate=16000):
  with tempfile.TemporaryDirectory() as folder:
   path=Path(folder)/'input.wav'
   with wave.open(str(path),'wb') as writer:writer.setnchannels(1);writer.setsampwidth(2);writer.setframerate(rate);writer.writeframes(samples.astype(np.int16).tobytes())
   return audio.prepare_audio(path)
 def test_silence_is_not_sent_to_recognizer(self):
  samples,duration=self.check_audio(np.zeros(16000));self.assertEqual(len(samples),0);self.assertAlmostEqual(duration,1)
 def test_dc_noise_is_removed(self):
  samples,_=self.check_audio(np.ones(16000)*1000);self.assertEqual(len(samples),0)
 def test_too_short_rejected(self):
  with self.assertRaises(ValueError):self.check_audio(np.zeros(4000))
 def test_too_long_rejected(self):
  with self.assertRaises(ValueError):self.check_audio(np.zeros(16000*36))
 def test_resampling_and_normalization(self):
  source=np.sin(np.arange(22050)*2*np.pi*440/22050)*4000;samples,duration=self.check_audio(source,22050);self.assertEqual(samples.dtype,np.float32);self.assertAlmostEqual(duration,1);self.assertLessEqual(abs(samples).max(),1);self.assertGreaterEqual(len(samples),15500)
 def test_homophones_are_suggestions_only(self):
  text='我想去洋江海领导';suggestions=audio.place_suggestions(text,['阳江','海陵岛']);self.assertEqual([s['name'] for s in suggestions],['阳江','海陵岛']);self.assertEqual(text,'我想去洋江海领导')
 def test_correct_names_do_not_need_correction(self):self.assertEqual(audio.place_suggestions('我想去海陵岛',['海陵岛']),[])
 def test_one_syllable_error_in_long_known_place_is_only_a_candidate(self):
  original='我们去党沙博物馆';suggestions=audio.place_suggestions(original,['长沙博物馆'])
  self.assertEqual(suggestions[0]['name'],'长沙博物馆');self.assertEqual(suggestions[0]['match'],'single-syllable');self.assertEqual(original,'我们去党沙博物馆')
 def test_unrelated_or_short_near_names_are_not_suggested(self):
  self.assertEqual(audio.place_suggestions('我们去广州动物园',['长沙博物馆']),[])
  self.assertEqual(audio.place_suggestions('去清云亭',['清风亭']),[])
if __name__=='__main__':unittest.main()
