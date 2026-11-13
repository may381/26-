package cn.yinling.guide;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.web.bind.annotation.*;
import jakarta.servlet.http.HttpServletRequest;
import org.springframework.http.*;
import java.net.*;
import java.net.http.*;
import java.time.Duration;
import java.util.Map;
@RestController
public class AmapBrowserApi {
 private final String key,security;
 private final HttpClient client=HttpClient.newBuilder().connectTimeout(Duration.ofSeconds(5)).build();
 public AmapBrowserApi(@Value("${amap.js-key:}") String key,@Value("${amap.js-security:}") String security){this.key=key;this.security=security;}
 @GetMapping("/api/a1/map-config")
 public AgentApi.Envelope config(){if(key.isBlank()||security.isBlank())throw new OllamaClient.Unavailable("交互地图未配置 Web端 Key 和安全密钥。");return AgentApi.Envelope.ok(Map.of("key",key,"serviceHost","/_AMapService"));}
 @GetMapping("/_AMapService/**")
 public ResponseEntity<byte[]> proxy(HttpServletRequest request){
  String path=request.getRequestURI().substring("/_AMapService/".length());
  if(!path.matches("v3/[a-zA-Z0-9/_-]+|v4/map/styles"))throw new IllegalArgumentException();
  try{String query=request.getQueryString();var uri=URI.create("https://restapi.amap.com/"+path+"?"+(query==null?"":query)+"&jscode="+AmapPlaces.enc(security));
   var response=client.send(java.net.http.HttpRequest.newBuilder(uri).timeout(Duration.ofSeconds(15)).GET().build(),HttpResponse.BodyHandlers.ofByteArray());
   return ResponseEntity.status(response.statusCode()).header("Content-Type",response.headers().firstValue("Content-Type").orElse("application/json")).body(response.body());
  }catch(InterruptedException e){Thread.currentThread().interrupt();throw new OllamaClient.Unavailable("地图服务中断，请重试。");}catch(Exception e){throw new OllamaClient.Unavailable("地图服务暂不可用，请重试。");}
 }
}
