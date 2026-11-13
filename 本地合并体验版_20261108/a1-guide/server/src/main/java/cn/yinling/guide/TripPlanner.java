package cn.yinling.guide;

import com.fasterxml.jackson.databind.ObjectMapper;
import java.time.*;
import java.util.*;
import java.util.function.Consumer;

/** Suggested activity times are kept separate from transport evidence. */
final class TripPlanner {
 private final AmapPlaces places;
 TripPlanner(AmapPlaces places){this.places=places;}
 record Slot(String kind,String placeId,String title,String start,String end,Integer minutes,String evidence,String note,String mode,Double distance,List<String> polyline){}
 static String mode(TravelDraftApi.Request p){return Set.of("taxi","self-drive").contains(Objects.toString(p.travelMode(),""))?"driving":"walking";}
 static int limit(TravelDraftApi.Request p){return p.walkMinutes()<=10?1:("slow".equals(p.pace())||p.walkMinutes()<=20||"家人同行".equals(p.companions()))?2:3;}
 static double distance(AmapPlaces.Place a,AmapPlaces.Place b){try{var x=a.location().split(",");var y=b.location().split(",");double lat1=Math.toRadians(Double.parseDouble(x[1])),lat2=Math.toRadians(Double.parseDouble(y[1]));double h=Math.pow(Math.sin((lat2-lat1)/2),2)+Math.cos(lat1)*Math.cos(lat2)*Math.pow(Math.sin(Math.toRadians(Double.parseDouble(y[0])-Double.parseDouble(x[0]))/2),2);return 6371*2*Math.asin(Math.sqrt(Math.min(1,h)));}catch(Exception e){return Double.POSITIVE_INFINITY;}}
 static List<List<AmapPlaces.Place>> group(List<AmapPlaces.Place> candidates,TravelDraftApi.Request p,boolean imported){
  var unique=new LinkedHashMap<String,AmapPlaces.Place>();for(var place:candidates)if(imported||!place.name().matches(".*(暂停营业|永久关闭).*"))unique.putIfAbsent(place.id(),place);
  var remaining=new ArrayList<>(unique.values());
  if(!imported&&Boolean.TRUE.equals(p.avoidSteps()))remaining.sort(Comparator.comparingInt(x->x.name().matches(".*(登山|山峰|山顶|古道|长城).*")?1:0));
  var result=new ArrayList<List<AmapPlaces.Place>>();
  int cap=imported?(int)Math.ceil((double)remaining.size()/p.days()):limit(p);
  for(int day=0;day<p.days();day++){
   var selected=new ArrayList<AmapPlaces.Place>();if(!remaining.isEmpty())selected.add(remaining.remove(0));
   while(selected.size()<cap&&!remaining.isEmpty()){
    var origin=selected.get(0);var last=selected.get(selected.size()-1);var next=remaining.stream().min(Comparator.comparingDouble(x->distance(last,x))).orElseThrow();
    double radius=mode(p).equals("driving")?25:8;
    if(!imported&&distance(origin,next)>radius)break;
    selected.add(next);remaining.remove(next);
   }
   result.add(List.copyOf(selected));
  }
  return result;
 }
 TravelDraftApi.Day schedule(LocalDate date,List<AmapPlaces.Place> points,TravelDraftApi.Request p,Consumer<Map<String,Object>> progress){
  var reasons=new ArrayList<String>();var slots=new ArrayList<Slot>();
  if(points.isEmpty())return new TravelDraftApi.Day(date,List.of(),List.of(),List.of("当天没有分配到可用地点，未生成游玩时间轴；可缩短天数、补充地点或保留为自由休息日。"));
  if(points.stream().anyMatch(point->point.city()==null||point.city().isBlank()))reasons.add("部分地点来源缺少所属城市字段，请核对地址；没有将其标为城市已验证。");
  reasons.add("当天安排 "+points.size()+" 处地点；"+(p.importedPlaceIds()!=null&&!p.importedPlaceIds().isEmpty()?"保留您确认导入的地点，若偏赶可移除后重新保存。": "根据节奏、同行人和单次步行偏好，每天最多安排 "+limit(p)+" 处。"));
  if(Boolean.TRUE.equals(p.avoidSteps()))reasons.add("按地点名称降低明显登高地点的优先级；台阶、坡度和无障碍条件尚未核实。");
  reasons.add("地点按坐标邻近关系分组；交通耗时单独查询，游玩、午餐和休息为建议安排。起点是首个景点，不含酒店往返。");
  var cursor=new Cursor(slots);int interval="frequent".equals(p.restFrequency())?20:"rare".equals(p.restFrequency())?60:40;
  interval=Math.min(interval,p.walkMinutes());int visit="slow".equals(p.pace())?90:60;
  for(int i=0;i<points.size();i++){
   var point=points.get(i);
   if(i>0){
    var from=points.get(i-1);String mode=mode(p);var leg=query(from,point,mode);
    if(mode.equals("walking")&&leg!=null&&leg.minutes>p.walkMinutes()){
     mode="transit";leg=query(from,point,mode);reasons.add(from.name()+" → "+point.name()+"：步行超过单次 "+p.walkMinutes()+" 分钟偏好，改查公共交通；接驳步行量仍需确认。");
    }
    if(leg==null){cursor.add("transport",point.id(),"前往"+point.name(),null,"UNCONFIRMED","交通未返回，后续钟点待确认，不以零分钟计算。",mode,null,List.of());cursor.known=false;}
    else {cursor.add("transport",point.id(),"前往"+point.name(),leg.minutes,"AMAP_ESTIMATE","高德交通估算，非实时出发承诺。",mode,leg.distance,leg.polyline);if(leg.minutes>90)reasons.add("该段交通超过90分钟，建议减少地点或调整住宿位置。");}
    progress.accept(Map.of("stage","transport","message","已查询 "+from.name()+" → "+point.name()+"，"+(leg==null?"耗时待确认":leg.minutes+" 分钟（高德估算）")));
   }
   int left=visit;
   while(left>0){cursor.lunch();int chunk=Math.min(interval,left);if(cursor.known&&!cursor.lunched&&cursor.at<720)chunk=Math.min(chunk,720-cursor.at);cursor.add("visit",point.id(),point.name(),chunk,"SUGGESTION","建议游玩时段；开放与预约情况待确认。",null,null,List.of());left-=chunk;if(left>0)cursor.add("rest",point.id(),"坐下休息",10,"SUGGESTION","预留休息时间；座椅位置需现场确认。",null,null,List.of());}
   cursor.add("rest",point.id(),"休息与补水",15,"SUGGESTION","家人可在此确认体力，再决定是否继续。",null,null,List.of());
  }
  if(!points.isEmpty()&&!cursor.lunched){if(cursor.known&&cursor.at<720)cursor.add("free",null,"自由活动 / 提前休息",720-cursor.at,"SUGGESTION","当天景点较少，预留弹性时间。",null,null,List.of());cursor.lunch();}
  if(!cursor.known)reasons.add("交通有未查到的路段；后续只展示建议时长，待补齐交通后再确认钟点。");
  if(cursor.at>1050)reasons.add("建议结束时间超过17:30，行程偏长，可在编辑中移除一处地点。");
  if(cursor.known&&cursor.at>=1440)reasons.add("当前安排已跨日，不能作为轻松的一日行程使用。请减少地点或增加天数；跨日钟点仅表示累计估算，不是已确认安排。");
  return new TravelDraftApi.Day(date,List.copyOf(points),List.copyOf(slots),List.copyOf(reasons));
 }
 private record Leg(int minutes,double distance,List<String> polyline){}
 private Leg query(AmapPlaces.Place from,AmapPlaces.Place to,String mode){try{
  var root=new ObjectMapper().valueToTree(places.transport(from.id(),to.id(),mode));var option=root.path("options").path(0);
  double seconds=option.path("duration").asDouble(-1),meters=option.path("distance").asDouble(-1);if(!Double.isFinite(seconds)||seconds<0||seconds>86400||!Double.isFinite(meters)||meters<0)return null;
  var lines=new ArrayList<String>();for(var step:option.path("steps")){String line=step.path("polyline").asText("");if(!line.isBlank())lines.add(line);}
  // Transit responses carry walking/bus geometry in segments, not root steps.
  for(var segment:option.path("segments")){
   for(var step:segment.path("walking").path("steps")){String line=step.path("polyline").asText("");if(!line.isBlank())lines.add(line);}
   var buses=segment.path("bus").path("buslines");
   if(buses.isArray()&&!buses.isEmpty()){String line=buses.get(0).path("polyline").asText("");if(!line.isBlank())lines.add(line);}
  }
  return new Leg(Math.max(1,(int)Math.ceil(seconds/60)),meters,List.copyOf(lines));
 }catch(Exception e){return null;}}
 private static final class Cursor {
  final List<Slot> slots;int at=570;boolean known=true,lunched=false;
  Cursor(List<Slot> slots){this.slots=slots;}
  void lunch(){if(!lunched&&(!known||at>=720)){lunched=true;add("meal",null,"午餐",60,"SUGGESTION","预留用餐时间，餐厅尚未选定。",null,null,List.of());add("rest",null,"午间休息",30,"SUGGESTION","建议坐下休息，再继续下午活动。",null,null,List.of());}}
  void add(String kind,String id,String title,Integer minutes,String evidence,String note,String mode,Double distance,List<String> line){String start=known?clock(at):null;String end=known&&minutes!=null?clock(at+minutes):null;slots.add(new Slot(kind,id,title,start,end,minutes,evidence,note,mode,distance,line));if(minutes!=null)at+=minutes;}
  static String clock(int minute){int day=minute/1440,within=minute%1440;String prefix=day==0?"":day==1?"次日 ":"第"+(day+1)+"天 ";return prefix+String.format(java.util.Locale.ROOT,"%02d:%02d",within/60,within%60);}
 }
}
