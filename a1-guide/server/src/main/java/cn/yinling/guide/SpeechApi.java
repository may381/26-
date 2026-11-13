package cn.yinling.guide;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.multipart.MultipartFile;
import org.springframework.http.*;
import java.nio.file.*;
import java.util.*;
import java.util.concurrent.*;
import com.fasterxml.jackson.databind.ObjectMapper;
@RestController
public class SpeechApi {
 private final Semaphore ttsGate=new Semaphore(1),asrGate=new Semaphore(1);
 private final Map<String,Clip> clips=new ConcurrentHashMap<>();
 private record Clip(byte[] bytes,long created,String text,String voice){}
 public record Synthesis(String text,Double speechRate,String voice){}
 public record Voice(String id,String label,String engine){}
 static final Set<String> VOICES=Set.of("neural-66","neural-0","neural-100","system");
 static boolean neuralReady(){var root=Path.of("speech/models/vits");var sizes=Map.of("model.int8.onnx",39870124L,"tokens.txt",1671L,"lexicon.txt",2042943L,"date.fst",59154L,"number.fst",64482L,"phone.fst",88630L);try{for(var e:sizes.entrySet())if(!Files.isRegularFile(root.resolve(e.getKey()))||Files.size(root.resolve(e.getKey()))!=e.getValue())return false;return true;}catch(Exception e){return false;}}
 @GetMapping("/api/speech/voices")
 public AgentApi.Envelope voices(){var voices=new ArrayList<Voice>();if(neuralReady()){voices.add(new Voice("neural-66","音色一","LOCAL_NEURAL"));voices.add(new Voice("neural-0","音色二","LOCAL_NEURAL"));voices.add(new Voice("neural-100","音色三","LOCAL_NEURAL"));}voices.add(new Voice("system","系统备用","WINDOWS"));return AgentApi.Envelope.ok(Map.of("voices",voices,"defaultVoice",neuralReady()?"neural-66":"system"));}
 @PostMapping("/api/speech/syntheses")
 public AgentApi.Envelope synthesize(@RequestBody Synthesis body)throws Exception{
  if(body.text()==null||body.text().isBlank()||body.text().length()>4000||body.speechRate()==null||!Double.isFinite(body.speechRate())||body.speechRate()<.5||body.speechRate()>1.5)throw new IllegalArgumentException();
  String selected=body.voice()==null?(neuralReady()?"neural-66":"system"):body.voice();if(!VOICES.contains(selected))throw new IllegalArgumentException();if(selected.startsWith("neural-")&&!neuralReady())throw new OllamaClient.Unavailable("此音色暂未准备好，请选择系统备用音色。");
  var cached=clips.entrySet().stream().filter(e->System.currentTimeMillis()-e.getValue().created()<480000&&e.getValue().text().equals(body.text())&&e.getValue().voice().equals(selected)).findFirst();
  if(cached.isPresent())return AgentApi.Envelope.ok(Map.of("audioUrl","/api/speech/audio/"+cached.get().getKey(),"voice",selected));
  return AgentApi.Envelope.ok(run(ttsGate,()->{Path text=Files.createTempFile("a1-tts-",".txt"),wav=Files.createTempFile("a1-tts-",".wav");try{
   Files.writeString(text,body.text());
   if(selected.startsWith("neural-"))process(List.of(Path.of("../local-asr/.venv/Scripts/python.exe").toAbsolutePath().normalize().toString(),Path.of("speech/synthesize_neural.py").toAbsolutePath().toString(),text.toString(),wav.toString(),selected.substring(7)),45);
   else process(List.of("powershell.exe","-NoProfile","-NonInteractive","-ExecutionPolicy","Bypass","-File",Path.of("speech/synthesize.ps1").toAbsolutePath().toString(),"-TextFile",text.toString(),"-OutputFile",wav.toString(),"-Rate","0"),45);
   clips.entrySet().removeIf(e->System.currentTimeMillis()-e.getValue().created()>600000);if(clips.size()>=20)clips.entrySet().stream().min(Comparator.comparingLong(e->e.getValue().created())).ifPresent(e->clips.remove(e.getKey()));String id=UUID.randomUUID().toString();clips.put(id,new Clip(Files.readAllBytes(wav),System.currentTimeMillis(),body.text(),selected));return Map.of("audioUrl","/api/speech/audio/"+id,"voice",selected);
  }finally{Files.deleteIfExists(text);Files.deleteIfExists(wav);}}));
 }
 @GetMapping("/api/speech/audio/{id}")
 public ResponseEntity<byte[]> audio(@PathVariable String id){var clip=clips.get(id);if(clip==null||System.currentTimeMillis()-clip.created()>600000)return ResponseEntity.notFound().build();return ResponseEntity.ok().contentType(MediaType.parseMediaType("audio/wav")).body(clip.bytes());}
 @PostMapping("/api/speech/transcriptions")
 public AgentApi.Envelope transcribe(@RequestParam("file") MultipartFile file,@RequestParam(defaultValue="") String hints)throws Exception{
  if(file.isEmpty()||file.getSize()>4*1024*1024||hints.length()>1000)throw new IllegalArgumentException();
  var json=new ObjectMapper();var names=new ArrayList<String>();
  if(!hints.isBlank()){com.fasterxml.jackson.databind.JsonNode parsed;try{parsed=json.readTree(hints);}catch(Exception e){throw new IllegalArgumentException();}if(!parsed.isArray()||parsed.size()>12)throw new IllegalArgumentException();for(var name:parsed){if(!name.isTextual()||name.asText().length()>40)throw new IllegalArgumentException();names.add(name.asText());}}
  return AgentApi.Envelope.ok(run(asrGate,()->{Path input=Files.createTempFile("a1-asr-",".audio"),context=Files.createTempFile("a1-asr-hints-",".json");try{
   file.transferTo(input);Files.writeString(context,json.writeValueAsString(names));
   String output=process(List.of(Path.of("../local-asr/.venv/Scripts/python.exe").toAbsolutePath().normalize().toString(),Path.of("speech/transcribe.py").toAbsolutePath().toString(),input.toString(),context.toString()),90);
   var parsed=json.readTree(output);String text=parsed.path("text").asText("");if(text.isBlank())throw new OllamaClient.Unavailable("没有听清，请靠近麦克风，在安静环境中说完一句话后重试。");
   var result=new LinkedHashMap<String,Object>();result.put("text",text);result.put("engine",parsed.path("engine").asText("windows-compatibility"));if(parsed.has("confidence"))result.put("confidence",parsed.path("confidence").asDouble());result.put("corrections",parsed.path("corrections").isArray()?parsed.path("corrections"):json.createArrayNode());return result;
  }finally{Files.deleteIfExists(input);Files.deleteIfExists(context);}}));
 }
 private Object run(Semaphore gate,Callable<Object> action)throws Exception{if(!gate.tryAcquire(2,TimeUnit.SECONDS))throw new OllamaClient.Unavailable("另一段语音正在处理中，请稍后重试。");try{return action.call();}finally{gate.release();}}
 private String process(List<String> command,int seconds)throws Exception{
  Path output=Files.createTempFile("a1-speech-log-",".txt");Process child=null;try{child=new ProcessBuilder(command).redirectOutput(output.toFile()).redirectError(ProcessBuilder.Redirect.DISCARD).start();if(!child.waitFor(seconds,TimeUnit.SECONDS)){child.destroyForcibly();throw new OllamaClient.Unavailable("语音处理未完成，请检查本地服务或重试。");}if(child.exitValue()!=0)throw new OllamaClient.Unavailable("语音处理未完成，请检查本地服务或重试。");return Files.readString(output);}finally{if(child!=null&&child.isAlive())child.destroyForcibly();Files.deleteIfExists(output);}
 }
}
