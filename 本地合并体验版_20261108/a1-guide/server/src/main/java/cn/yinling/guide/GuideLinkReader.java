package cn.yinling.guide;

import com.fasterxml.jackson.databind.*;
import org.springframework.stereotype.Service;
import java.net.*;
import java.net.http.*;
import java.nio.ByteBuffer;
import java.nio.charset.StandardCharsets;
import java.time.*;
import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.Flow;
import java.util.regex.*;

/** Read public note pages only. Never execute scripts or forward browser credentials. */
@Service
public class GuideLinkReader {
 private static final Set<String> HOSTS=Set.of("xhslink.com","www.xhslink.com","xhslink.cn","www.xhslink.cn","www.xiaohongshu.com","xiaohongshu.com");
 private static final int MAX_BYTES=2*1024*1024;
 private final HttpClient client=HttpClient.newBuilder().connectTimeout(Duration.ofSeconds(5)).followRedirects(HttpClient.Redirect.NEVER).build();
 private final ObjectMapper json;
 private final Semaphore requests=new Semaphore(2);
 private record Cached(Result result,long expires){}
 private final Map<String,Cached> cache=new LinkedHashMap<>();
 public GuideLinkReader(ObjectMapper json){this.json=json;}
 public record Result(String status,String title,String text,String sourceUrl,String platform,String retrievedAt,String message){}
 static URI checked(String value){
  try{var uri=URI.create(value.strip());String host=Objects.toString(uri.getHost(),"").toLowerCase(Locale.ROOT);
   if(!"https".equalsIgnoreCase(uri.getScheme())||!HOSTS.contains(host)||uri.getRawUserInfo()!=null||(uri.getPort()!=-1&&uri.getPort()!=443))throw new IllegalArgumentException();
   if(host.endsWith("xiaohongshu.com")&&!Objects.toString(uri.getPath(),"").matches("/(explore|discovery/item)/[a-zA-Z0-9]+/?"))throw new IllegalArgumentException();
   return uri;
  }catch(Exception e){throw new IllegalArgumentException("目前支持小红书笔记链接和 xhslink 分享短链接，请检查链接或补充正文。");}
 }
 public Result read(String value){
  URI target=checked(value);String cacheKey=target.toString();var recent=cached(cacheKey);if(recent!=null)return recent;if(!requests.tryAcquire())return unavailable(value,"正在读取其他攻略，请稍后重试，或直接粘贴正文。");
  try{
   long deadline=System.nanoTime()+TimeUnit.SECONDS.toNanos(30);
   for(int redirects=0;redirects<5;redirects++){
    long remaining=deadline-System.nanoTime();if(remaining<=0)throw new java.io.IOException();
    var request=HttpRequest.newBuilder(target).timeout(Duration.ofNanos(Math.min(remaining,TimeUnit.SECONDS.toNanos(10)))).header("User-Agent","Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/130.0 Safari/537.36").header("Accept","text/html,application/xhtml+xml").GET().build();
    var response=client.send(request,info->new LimitedBody());
    if(Set.of(301,302,303,307,308).contains(response.statusCode())){String location=response.headers().firstValue("location").orElseThrow();var next=target.resolve(location);if(Objects.toString(next.getPath(),"").matches("/(login|signin|404|website-login).*"))return unavailable(value,"平台跳转到了登录或不可用页面，尚未读取笔记正文。请粘贴正文或上传截图。");target=checked(next.toString());continue;}
    if(response.statusCode()!=200)return unavailable(value,"平台没有返回可读取的公开正文，可能需要在小红书内打开。请粘贴正文或上传截图。");
    if(!response.headers().firstValue("content-type").orElse("").toLowerCase(Locale.ROOT).contains("text/html"))return unavailable(value,"该链接没有返回笔记网页，请补充攻略正文或截图。");
    var result=parse(new String(response.body(),StandardCharsets.UTF_8),target.toString());if(result.status().equals("READY"))remember(cacheKey,result);return result;
   }
   return unavailable(value,"分享链接跳转未完成，请重新复制笔记分享链接或补充正文。");
  }catch(InterruptedException e){Thread.currentThread().interrupt();return unavailable(value,"读取已中断，请重试或补充正文。");}
  catch(Exception e){return unavailable(value,"链接正文未读取成功，请粘贴笔记正文或上传截图后继续。");}
  finally{requests.release();}
 }
 private synchronized Result cached(String key){var item=cache.get(key);if(item==null)return null;if(item.expires()<System.nanoTime()){cache.remove(key);return null;}return item.result();}
 private synchronized void remember(String key,Result result){if(cache.size()>=32)cache.remove(cache.keySet().iterator().next());cache.put(key,new Cached(result,System.nanoTime()+TimeUnit.MINUTES.toNanos(5)));}
 Result parse(String html,String url){
  // Prefer the note body from the page state. It is parsed as JSON, never evaluated.
  var state=Pattern.compile("(?:window\\.)?__INITIAL_STATE__\\s*=\\s*(\\{.*?\\})\\s*;?\\s*</script>",Pattern.DOTALL).matcher(html);
  if(state.find())try{
   String raw=undefinedToNull(state.group(1).replaceFirst(";\\s*$",""));
   var noteMap=json.readTree(raw).path("note").path("noteDetailMap");
   String noteId=URI.create(url).getPath().replaceFirst("/$", "").replaceFirst(".*/", "");
   var entries=noteMap.fields();while(entries.hasNext()){var entry=entries.next();if(url.contains("xiaohongshu.com")&&!entry.getKey().equals(noteId))continue;if(!url.contains("xiaohongshu.com")&&noteMap.size()!=1)continue;var note=entry.getValue().path("note");String title=note.path("title").asText("").strip(),desc=note.path("desc").asText("").strip();if(desc.length()>=12)return ready(title,desc,url);}
  }catch(Exception ignored){}
  // OpenGraph descriptions on login pages may be platform boilerplate, not the note.
  // Only accept explicitly structured article content as an alternative.
  var scripts=Pattern.compile("<script\\b[^>]*type\\s*=\\s*['\"]application/ld\\+json['\"][^>]*>(.*?)</script>",Pattern.CASE_INSENSITIVE|Pattern.DOTALL).matcher(html);
  while(scripts.find())try{var root=json.readTree(scripts.group(1));var nodes=root.isArray()?root:json.createArrayNode().add(root);for(var item:nodes){String type=item.path("@type").asText("");String body=item.path("articleBody").asText("").strip();if(Set.of("Article","BlogPosting","SocialMediaPosting").contains(type)&&body.length()>=12)return ready(item.path("headline").asText(""),body,url);}}catch(Exception ignored){}
  return unavailable(url,"网页未提供可确认的笔记正文。请从小红书复制正文或上传截图，分享标题不会被当成已读完整攻略。");
 }
 private Result ready(String title,String body,String url){String text=(title.isBlank()?"":title+"\n")+body;boolean truncated=text.length()>6000;return new Result("READY",title.substring(0,Math.min(120,title.length())),text.substring(0,Math.min(6000,text.length())),url,"小红书",Instant.now().toString(),truncated?"已读取公开笔记正文，保留前6000字。请核对后确认地点。":"已读取公开笔记正文，请核对提取出的地点。");}
 private Result unavailable(String url,String message){return new Result("NEEDS_CONTENT","","",url,"小红书",Instant.now().toString(),message);}
 static String undefinedToNull(String text){return Pattern.compile("\"(?:\\\\.|[^\"\\\\])*\"|\\bundefined\\b").matcher(text).replaceAll(m->m.group().equals("undefined")?"null":java.util.regex.Matcher.quoteReplacement(m.group()));}
 private static final class LimitedBody implements HttpResponse.BodySubscriber<byte[]> {
  final HttpResponse.BodySubscriber<byte[]> delegate=HttpResponse.BodySubscribers.ofByteArray();Flow.Subscription subscription;int bytes;
  public CompletionStage<byte[]> getBody(){return delegate.getBody();}
  public void onSubscribe(Flow.Subscription s){subscription=s;delegate.onSubscribe(s);}
  public void onNext(List<ByteBuffer> chunks){for(var b:chunks){bytes+=b.remaining();if(bytes>MAX_BYTES){subscription.cancel();delegate.onError(new java.io.IOException("Page exceeds limit"));return;}}delegate.onNext(chunks);}
  public void onError(Throwable error){delegate.onError(error);}public void onComplete(){delegate.onComplete();}
 }
}
