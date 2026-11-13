package cn.yinling.guide;

import com.fasterxml.jackson.databind.*;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;
import java.net.*;
import java.net.http.*;
import java.time.*;
import java.util.*;

@Service
public class AmapPlaces {
    private static final org.slf4j.Logger log=org.slf4j.LoggerFactory.getLogger(AmapPlaces.class);
    private final String key;
    private record RecentPlace(Place place,long expires){}
    private final Map<String,RecentPlace> recentPlaces=new java.util.concurrent.ConcurrentHashMap<>();
    private final ObjectMapper mapper;
    private final HttpClient client=HttpClient.newBuilder().connectTimeout(Duration.ofSeconds(5)).build();
    public AmapPlaces(@Value("${amap.web-key:}") String key,ObjectMapper mapper){this.key=key;this.mapper=mapper;}
    public record Place(String id,String name,String address,String type,String location,String hours,List<String> photos,String mapUrl,String city){
        public Place(String id,String name,String address,String type,String location,String hours,List<String> photos,String mapUrl){this(id,name,address,type,location,hours,photos,mapUrl,null);}
    }
    static String enc(String s){return URLEncoder.encode(s,java.nio.charset.StandardCharsets.UTF_8);}
    public List<Place> search(String query,String city){
        if(query==null||query.isBlank()||query.length()>100||city==null||city.length()>40)throw new IllegalArgumentException();
        var results=request("text","keywords="+enc(query)+"&city="+enc(city)+"&offset=5&page=1");
        rememberPlaces(results);return results;
    }
    public List<Place> planCandidates(String city){
        if(city==null||city.isBlank()||city.length()>40)throw new IllegalArgumentException();
        var results=request("text","keywords="+enc("风景名胜")+"&city="+enc(city)+"&citylimit=true&offset=20&page=1");
        var unique=new LinkedHashMap<String,Place>();
        for(var p:results)unique.putIfAbsent(p.id(),p);
        var points=List.copyOf(unique.values());rememberPlaces(points);return points;
    }
    public Place detail(String id){
        if(id==null||!id.matches("[A-Za-z0-9]{5,40}"))throw new IllegalArgumentException();
        var recent=recentPlaces.get(id);if(recent!=null&&recent.expires()>System.currentTimeMillis())return recent.place();
        var places=request("detail","id="+enc(id));
        rememberPlaces(places);
        if(places.isEmpty())throw new OllamaClient.Unavailable("高德未返回这个地点，请重新搜索选择。");
        return places.get(0);
    }
    private void rememberPlaces(List<Place> places){
        recentPlaces.entrySet().removeIf(e->e.getValue().expires()<System.currentTimeMillis());
        if(recentPlaces.size()>100)recentPlaces.clear();
        for(var place:places)recentPlaces.put(place.id(),new RecentPlace(place,System.currentTimeMillis()+120000));
    }
    private List<Place> request(String operation,String args){
        return parse(fetch("place/"+operation,"extensions=all&"+args));
    }
    private JsonNode fetch(String path,String args){
        if(key.isBlank())throw new OllamaClient.Unavailable("尚未配置高德 Web 服务 Key。");
        try{
            var uri=URI.create("https://restapi.amap.com/v3/"+path+"?key="+enc(key)+"&"+args);
            var request=HttpRequest.newBuilder(uri).timeout(Duration.ofSeconds(12)).GET().build();
            HttpResponse<String> response;
            try{response=client.send(request,HttpResponse.BodyHandlers.ofString());}
            catch(java.io.IOException first){log.warn("AMap transient failure path={} type={}; retry once",path,first.getClass().getSimpleName());response=client.send(request,HttpResponse.BodyHandlers.ofString());}
            if(response.statusCode()!=200)throw new OllamaClient.Unavailable("高德服务暂时不可用，请稍后重试。");
            var root=mapper.readTree(response.body());
            if(!"1".equals(root.path("status").asText()))throw new OllamaClient.Unavailable("高德查询失败（"+root.path("infocode").asText("未知")+"），请检查 Key 权限及配额。");
            return root;
        }catch(OllamaClient.Unavailable ex){throw ex;}
        catch(InterruptedException ex){Thread.currentThread().interrupt();throw new OllamaClient.Unavailable("地点查询已中断，请重试。");}
        catch(java.net.http.HttpTimeoutException ex){log.warn("AMap timeout path={} type={}",path,ex.getClass().getSimpleName());throw new OllamaClient.Unavailable("高德地点服务响应超时，已重试一次，请稍后重新生成。");}
        catch(java.io.IOException ex){log.warn("AMap network/response failure path={} type={}",path,ex.getClass().getSimpleName());throw new OllamaClient.Unavailable("高德连接或响应异常，已重试网络请求；请稍后重试。");}
        catch(Exception ex){log.warn("AMap unexpected failure path={} type={}",path,ex.getClass().getSimpleName());throw new OllamaClient.Unavailable("高德数据处理失败，请稍后重试。");}
    }
    public JsonNode districts(String code){
        if(!code.matches("中国|[0-9]{6}"))throw new IllegalArgumentException();
        return fetch("config/district","keywords="+enc(code)+"&subdistrict=1&extensions=base").path("districts");
    }
    public Map<String,String> locate(double longitude,double latitude){
        if(!Double.isFinite(longitude)||!Double.isFinite(latitude)||Math.abs(longitude)>180||Math.abs(latitude)>90)throw new IllegalArgumentException();
        String converted=fetch("assistant/coordinate/convert","locations="+longitude+","+latitude+"&coordsys=gps").path("locations").asText();
        if(!converted.matches("[0-9.]+,[0-9.]+"))throw new OllamaClient.Unavailable("暂不支持该区域的定位解析，请手动选城市。");
        var geo=fetch("geocode/regeo","location="+enc(converted)+"&extensions=base").path("regeocode");
        var address=geo.path("addressComponent");
        String city=value(address,"city");if(city.isEmpty())city=value(address,"province");
        return Map.of("province",value(address,"province"),"city",city,"adcode",value(address,"adcode"),"address",value(geo,"formatted_address"),"location",converted,"source","AMAP");
    }
    public List<Place> nearby(String id,String category){
        var types=Map.of("景点","110000","美食","050000","饮品","050500","住宿","100000","卫生间","200300","机场","150100");
        if(!types.containsKey(category))throw new IllegalArgumentException();
        var center=detail(id);
        if(!center.location().matches("[0-9.]+,[0-9.]+"))throw new OllamaClient.Unavailable("地点没有有效坐标。");
        var found=request("around","location="+enc(center.location())+"&types="+types.get(category)+"&radius=3000&sortrule=distance&offset=8&page=1");rememberPlaces(found);return found;
    }
    public Map<String,Object> weather(String id){
        var place=detail(id);
        var geo=fetch("geocode/regeo","location="+enc(place.location())+"&extensions=base");
        String code=geo.path("regeocode").path("addressComponent").path("adcode").asText();
        if(!code.matches("[0-9]{6}"))throw new OllamaClient.Unavailable("未能确定地点的天气区域。");
        var live=fetch("weather/weatherInfo","city="+code+"&extensions=base").path("lives");
        var forecast=fetch("weather/weatherInfo","city="+code+"&extensions=all").path("forecasts");
        return Map.of("source","AMAP","retrievedAt",Instant.now().toString(),"lives",live,"forecasts",forecast);
    }
    public Map<String,Object> transport(String fromId,String toId,String mode){
        if(fromId.equals(toId))throw new IllegalArgumentException();
        var from=detail(fromId);var to=detail(toId);
        return transportPoints(from,to,mode);
    }
    public Map<String,Object> transportFromGps(double longitude,double latitude,String toId,String mode){
        var located=locate(longitude,latitude);
        var from=new Place("current-location","我的位置",located.get("address"),"当前位置",located.get("location"),"",List.of(),"",located.get("city"));
        return transportPoints(from,detail(toId),mode);
    }
    private Map<String,Object> transportPoints(Place from,Place to,String mode){
        String args="origin="+enc(from.location())+"&destination="+enc(to.location());
        String path;
        switch(mode){
          case "walking" -> path="direction/walking";
          case "driving" -> path="direction/driving";
          case "transit" -> {path="direction/transit/integrated";var geo=fetch("geocode/regeo","location="+enc(from.location())+"&extensions=base");String city=geo.path("regeocode").path("addressComponent").path("citycode").asText();if(city.isBlank())throw new OllamaClient.Unavailable("无法确定公交查询城市。");var targetGeo=fetch("geocode/regeo","location="+enc(to.location())+"&extensions=base");String targetCity=targetGeo.path("regeocode").path("addressComponent").path("citycode").asText();args+="&city="+enc(city)+"&cityd="+enc(targetCity)+"&strategy=0";}
          default -> throw new IllegalArgumentException();
        }
        var root=fetch(path,args);var route=root.path("route");var list=route.path(mode.equals("transit")?"transits":"paths");
        return Map.of("source","AMAP","retrievedAt",Instant.now().toString(),"origin",from,"destination",to,"mode",mode,"options",list);
    }
    public byte[] mapImage(String id,int zoom){return mapImage(id,zoom,"");}
    public byte[] mapImage(String id,int zoom,String nearbyIds){
        if(zoom<8||zoom>18)throw new IllegalArgumentException();
        var place=detail(id);
        if(!place.location().matches("[0-9.]+,[0-9.]+"))throw new OllamaClient.Unavailable("该地点暂无有效地图坐标。");
        String markers="mid,,A:"+place.location();
        if(nearbyIds!=null&&!nearbyIds.isBlank()){
            String[] ids=nearbyIds.split(",");if(ids.length>8)throw new IllegalArgumentException();
            for(int n=0;n<ids.length;n++){var point=detail(ids[n]);if(point.location().matches("[0-9.]+,[0-9.]+"))markers+="|mid,0x222222,"+(n+1)+":"+point.location();}
        }
        try{
            var uri=URI.create("https://restapi.amap.com/v3/staticmap?key="+enc(key)+"&location="+enc(place.location())+"&zoom="+zoom+"&size=430*780&scale=1&markers="+enc(markers));
            var response=client.send(HttpRequest.newBuilder(uri).timeout(Duration.ofSeconds(15)).GET().build(),HttpResponse.BodyHandlers.ofByteArray());
            String type=response.headers().firstValue("Content-Type").orElse("");
            if(response.statusCode()!=200||!type.startsWith("image/"))throw new OllamaClient.Unavailable("地图预览暂不可用，请稍后重试。");
            return response.body();
        }catch(InterruptedException e){Thread.currentThread().interrupt();throw new OllamaClient.Unavailable("地图加载中断。");}
        catch(OllamaClient.Unavailable e){throw e;}
        catch(Exception e){throw new OllamaClient.Unavailable("地图加载失败，请检查网络。");}
    }
    static String value(JsonNode p,String field){var v=p.path(field);return v.isTextual()?v.asText():"";}
    static List<Place> parse(JsonNode root){
        var result=new ArrayList<Place>();
        for(var p:root.path("pois")){
            var photos=new ArrayList<String>();
            for(var photo:p.path("photos")){
                String url=value(photo,"url");
                try{var u=URI.create(url);if(Set.of("http","https").contains(u.getScheme())&&u.getHost()!=null&&u.getUserInfo()==null)photos.add(url);}catch(Exception ignored){}
                if(photos.size()==3)break;
            }
            String id=value(p,"id"),name=value(p,"name");
            if(id.isBlank()||name.isBlank())continue;
            String city=value(p,"cityname");
            if(city.isBlank()&&Set.of("北京市","上海市","天津市","重庆市").contains(value(p,"pname")))city=value(p,"pname");
            result.add(new Place(id,name,value(p,"pname")+value(p,"cityname")+value(p,"adname")+value(p,"address"),value(p,"type"),value(p,"location"),value(p.path("business"),"opentime_today"),List.copyOf(photos),"https://uri.amap.com/marker?poiid="+enc(id)+"&src=yinling-a1&callnative=0",city));
        }
        return List.copyOf(result);
    }
}
