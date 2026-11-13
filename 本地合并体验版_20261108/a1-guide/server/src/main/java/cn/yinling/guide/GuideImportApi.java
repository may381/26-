package cn.yinling.guide;

import com.fasterxml.jackson.databind.ObjectMapper;
import jakarta.validation.Valid;
import jakarta.validation.constraints.*;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.multipart.MultipartFile;
import java.nio.file.*;
import java.util.*;
import java.util.concurrent.*;
import java.util.regex.Pattern;
import javax.imageio.ImageIO;

@RestController
public class GuideImportApi {
 private final OllamaClient model;
 private final ObjectMapper json;
 private final GuideLinkReader linkReader;
 private final Semaphore ocrSlot=new Semaphore(1);
 public GuideImportApi(OllamaClient model,ObjectMapper json,GuideLinkReader linkReader){this.model=model;this.json=json;this.linkReader=linkReader;}
 public record LinkInput(@NotBlank @Size(max=2048) String url){}
 @PostMapping("/api/a1/guide-imports/read-link")
 public AgentApi.Envelope readLink(@Valid @RequestBody LinkInput input){return AgentApi.Envelope.ok(linkReader.read(input.url()));}
 public record Input(@NotBlank @Size(max=6000) String text){}
 @PostMapping("/api/a1/guide-imports/analyze")
 public AgentApi.Envelope analyze(@Valid @RequestBody Input input){
  String content=input.text().strip();
  var links=new ArrayList<String>();var match=Pattern.compile("https?://[^\\s<>\"，。]+",Pattern.CASE_INSENSITIVE).matcher(content);
  while(match.find()&&links.size()<3)links.add(match.group());
  String plain=content.replaceAll("https?://[^\\s<>\"，。]+","").strip();
  // A URL is not the note body. No arbitrary server-side URL requests are made.
  if(plain.length()<12)return result("NEEDS_CONTENT","",List.of(),links);
  try{
   var parsed=json.readTree(model.extractTravel(plain));
   String destination=parsed.path("destination").asText("").strip();
   if(destination.length()>40||!plain.contains(destination))destination="";
   var names=new LinkedHashSet<String>();var places=parsed.path("places");
   if(places.isArray())for(var item:places){String name=item.asText("").strip();if(name.length()>=2&&name.length()<=60&&plain.contains(name)&&names.size()<8)names.add(name);}
   return result(names.isEmpty()?"NEEDS_CONTENT":"REVIEW",destination,List.copyOf(names),links);
  }catch(OllamaClient.Unavailable e){throw e;}catch(Exception e){throw new OllamaClient.Unavailable("攻略提取结果未完整返回，请重试或减少正文长度。");}
 }
 private AgentApi.Envelope result(String status,String destination,List<String> places,List<String> links){return AgentApi.Envelope.ok(Map.of("status",status,"destination",destination,"places",places,"links",links,"source","USER_CONTENT","linkFetched",false,"message",status.equals("REVIEW")?"仅根据您提供的文字提取，请确认地点。":"尚未读取链接正文，请补充攻略正文或上传截图。"));}
 @PostMapping("/api/a1/guide-imports/ocr")
 public AgentApi.Envelope ocr(@RequestParam("file") MultipartFile file)throws Exception{
  if(file.isEmpty()||file.getSize()>4*1024*1024)throw new IllegalArgumentException();
  try(var input=ImageIO.createImageInputStream(file.getInputStream())){
   var readers=ImageIO.getImageReaders(input);if(!readers.hasNext())throw new IllegalArgumentException();var reader=readers.next();
   try{reader.setInput(input);String format=reader.getFormatName();if(!format.equalsIgnoreCase("jpeg")&&!format.equalsIgnoreCase("png"))throw new IllegalArgumentException();if(reader.getWidth(0)>5000||reader.getHeight(0)>5000||(long)reader.getWidth(0)*reader.getHeight(0)>16000000)throw new IllegalArgumentException();}finally{reader.dispose();}
  }
  if(!ocrSlot.tryAcquire())throw new OllamaClient.Unavailable("另一张图片正在识别，请稍后重试。");
  Path image=null,output=null;Process child=null;
  try{
   image=Files.createTempFile("a1-guide-image-",".png");output=Files.createTempFile("a1-guide-ocr-",".txt");file.transferTo(image);
   child=new ProcessBuilder("powershell.exe","-NoProfile","-NonInteractive","-ExecutionPolicy","Bypass","-File",Path.of("speech/ocr.ps1").toAbsolutePath().toString(),"-ImagePath",image.toString(),"-OutputPath",output.toString()).redirectOutput(ProcessBuilder.Redirect.DISCARD).redirectError(ProcessBuilder.Redirect.DISCARD).start();
   if(!child.waitFor(35,TimeUnit.SECONDS)||child.exitValue()!=0)throw new OllamaClient.Unavailable("截图识别未完成，请检查 Windows OCR 语言包，或直接粘贴正文。");
   String text=Files.readString(output).strip();if(text.isBlank())throw new OllamaClient.Unavailable("没有识别到文字，请使用清晰截图或粘贴正文。");
   return AgentApi.Envelope.ok(Map.of("text",text.substring(0,Math.min(6000,text.length())),"truncated",text.length()>6000,"source","USER_SCREENSHOT"));
  }finally{if(child!=null&&child.isAlive())child.destroyForcibly();if(image!=null)Files.deleteIfExists(image);if(output!=null)Files.deleteIfExists(output);ocrSlot.release();}
 }
}
