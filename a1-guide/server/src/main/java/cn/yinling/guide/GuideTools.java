package cn.yinling.guide;
import org.springframework.stereotype.Service;
import org.springframework.web.bind.annotation.*;
import java.time.*;
import java.util.*;
import java.util.regex.Pattern;
@Service
public class GuideTools {
 private final AmapPlaces places;
 public GuideTools(AmapPlaces places){this.places=places;}
 public record Definition(String name,String description,List<String> required){}
 public List<Definition> catalog(){return List.of(new Definition("place.search","按地名查找地点，不代表用户已到达",List.of("query","city")),new Definition("place.detail","查询已确认地点资料",List.of("id")),new Definition("weather.query","查询所选地点天气及接口预报日期",List.of("id")),new Definition("place.nearby","以所选地点为中心查询设施",List.of("id","category")),new Definition("transport.query","两地点普通交通估算，不是适老路线承诺",List.of("from","to","mode")));}
 public boolean matches(String text){return has(text,"天气","下雨","温度","气温","附近","周边");}
 public GuideService.Answer answer(String text,String context,String city,double rate){
  AmapPlaces.Place place=null;var calls=new ArrayList<GuideService.Tool>();
  String query=null;
  var match=Pattern.compile("(?:明天|今天|后天)?(?:我想去|我要去|去|查询|看看)([\\p{IsHan}]{2,20}?)(?:[，,。？?]|下雨|天气|附近|周边|$)").matcher(text);
  if(match.find())query=match.group(1);
  if(query!=null){var found=places.search(query,city==null?"":city);calls.add(new GuideService.Tool("place.search",Map.of("query",query),meta(Map.of("places",found,"requiresSelection",true))));String name=query;var exact=found.stream().filter(p->p.name().equals(name)).toList();
   if(exact.size()!=1)return new GuideService.Answer("tourism",found.isEmpty()?"没有查到该地点，请补充城市或完整名称。":"请先确认下面哪个地点是您想了解的；查询天气和附近设施不需要开启定位。",rate,null,calls,null);place=exact.get(0);
  }
  if(place==null&&context!=null&&context.startsWith("amap:"))place=places.detail(context.substring(5));
  if(place==null)return new GuideService.Answer("tourism","可以查询天气和附近设施。您想了解哪个地点？直接说名称或从地点卡片选择即可；如果问的是您身边，需要先提供位置。",rate,null,calls,null);
  var lines=new ArrayList<String>();lines.add("为您查询“"+place.name()+"”：");
  if(has(text,"天气","下雨","温度","气温")){
   try{var weather=places.weather(place.id());calls.add(new GuideService.Tool("weather.query",Map.of("id",place.id()),meta(Map.of("place",place,"weather",weather))));
    com.fasterxml.jackson.databind.JsonNode forecast=(com.fasterxml.jackson.databind.JsonNode)weather.get("forecasts");
    String date=LocalDate.now(ZoneId.of("Asia/Shanghai")).plusDays(has(text,"后天")?2:has(text,"明天")?1:0).toString();com.fasterxml.jackson.databind.JsonNode cast=null;
    if(!forecast.isEmpty())for(var candidate:forecast.get(0).path("casts"))if(date.equals(candidate.path("date").asText()))cast=candidate;
    if(cast==null)lines.add("天气：接口未提供 "+date+" 的预报。");else lines.add("**"+date+" 天气**：白天"+cast.path("dayweather").asText()+"，夜间"+cast.path("nightweather").asText()+"，"+cast.path("nighttemp").asText()+"–"+cast.path("daytemp").asText()+"℃。\n预报发布于 "+forecast.get(0).path("reporttime").asText()+"，出发前请复查。");
   }catch(OllamaClient.Unavailable ex){lines.add("天气查询未完成："+ex.getMessage());calls.add(failed("weather.query",place.id(),ex.getMessage()));}
  }
  String category=has(text,"厕所","卫生间")?"卫生间":has(text,"美食","吃饭","餐厅")?"美食":has(text,"住宿","酒店")?"住宿":has(text,"机场")?"机场":has(text,"饮品","咖啡")?"饮品":null;
  if(category!=null){try{var found=places.nearby(place.id(),category);calls.add(new GuideService.Tool("place.nearby",Map.of("id",place.id(),"category",category),meta(Map.of("places",found,"center",place,"requiresSelection",true))));lines.add("**附近"+category+"**："+(found.isEmpty()?"本次未查到，不代表实际不存在。":String.join("、",found.stream().limit(3).map(AmapPlaces.Place::name).toList())+"。以所选地点为中心检索，营业情况与实际步行路线尚未核实。"));}catch(OllamaClient.Unavailable ex){lines.add("附近地点查询未完成："+ex.getMessage());calls.add(failed("place.nearby",place.id(),ex.getMessage()));}}
  if(has(text,"休息","长椅","歇"))lines.add("休息座椅：当前地图数据不能可靠确认座椅，暂无法给出最近座椅位置，需要景区设施数据。");
  if(calls.isEmpty())lines.add("您想查询附近哪类地点？可以说卫生间、美食、住宿或机场。");
  return new GuideService.Answer("tourism",String.join("\n\n",lines),rate,null,calls,null);
 }
 private Map<String,Object> meta(Map<String,Object> data){var result=new LinkedHashMap<String,Object>(data);result.put("source","AMAP");result.put("retrievedAt",Instant.now().toString());return result;}
 private GuideService.Tool failed(String name,String id,String reason){return new GuideService.Tool(name,Map.of("id",id),Map.of("source","AMAP","retrievedAt",Instant.now().toString(),"status","FAILED","message",reason));}
 private boolean has(String text,String...words){return Arrays.stream(words).anyMatch(text::contains);}
}
@RestController
class GuideToolsApi {
 private final GuideTools tools;GuideToolsApi(GuideTools tools){this.tools=tools;}
 @GetMapping("/api/a1/tools")public AgentApi.Envelope catalog(){return AgentApi.Envelope.ok(tools.catalog());}
}
