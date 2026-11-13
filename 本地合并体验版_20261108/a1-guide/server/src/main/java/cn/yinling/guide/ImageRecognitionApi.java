package cn.yinling.guide;
import jakarta.validation.Valid;
import jakarta.validation.constraints.*;
import org.springframework.web.bind.annotation.*;
import javax.imageio.ImageIO;
import java.io.*;
import java.util.*;
@RestController
public class ImageRecognitionApi {
 private final OllamaClient model;
 public ImageRecognitionApi(OllamaClient model){this.model=model;}
 public record Input(@NotBlank @Size(max=6000000) String image,@NotBlank @Size(max=1000) String question){}
 @PostMapping("/api/a1/images/analyze")
 public AgentApi.Envelope analyze(@Valid @RequestBody Input input)throws Exception{
  if(!input.image().matches("(?s)^data:image/(png|jpeg);base64,[A-Za-z0-9+/=]+$"))throw new IllegalArgumentException();
  byte[] bytes=Base64.getDecoder().decode(input.image().substring(input.image().indexOf(',')+1));if(bytes.length>4*1024*1024)throw new IllegalArgumentException();
  try(var stream=ImageIO.createImageInputStream(new ByteArrayInputStream(bytes))){var readers=ImageIO.getImageReaders(stream);if(!readers.hasNext())throw new IllegalArgumentException();var reader=readers.next();try{reader.setInput(stream);var format=reader.getFormatName();if(!Set.of("png","jpeg","jpg").contains(format.toLowerCase(Locale.ROOT))||(long)reader.getWidth(0)*reader.getHeight(0)>16000000)throw new IllegalArgumentException();}finally{reader.dispose();}}
  return AgentApi.Envelope.ok(Map.of("text",model.recognizeImage(input.image(),input.question()),"source","USER_IMAGE","model",model.model(),"locationVerified",false));
 }
}
