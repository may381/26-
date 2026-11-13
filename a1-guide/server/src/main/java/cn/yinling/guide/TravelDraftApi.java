package cn.yinling.guide;
import org.springframework.web.bind.annotation.*;
import jakarta.servlet.http.HttpSession;
import jakarta.validation.Valid;
import jakarta.validation.constraints.*;
import java.time.*;
import java.util.*;
@RestController
public class TravelDraftApi {
 private final AmapPlaces places;
 private final DraftStorage storage;
 public TravelDraftApi(AmapPlaces places,DraftStorage storage){this.places=places;this.storage=storage;}
 static final class CityMismatch extends IllegalArgumentException {
  CityMismatch(){super("选入地点的所属城市与目的地不一致，请核对城市或移除跨城地点。");}
 }
 static void checkCity(AmapPlaces.Place place,String destination){
  if(place.city()!=null&&!place.city().isBlank()&&!place.city().strip().replaceFirst("市$","").equals(destination.strip().replaceFirst("市$","")))throw new CityMismatch();
 }
 // Compatibility for already-open preview pages; other unknown fields remain rejected.
 @com.fasterxml.jackson.annotation.JsonIgnoreProperties({"dateConfirmed","step"})
 public record Request(@NotBlank @Size(max=40) String destination,@NotNull LocalDate startDate,@Min(1) @Max(4) int days,@Min(10) @Max(120) int walkMinutes,@NotBlank @Pattern(regexp="独自出游|家人同行|朋友同行") String companions,Boolean avoidSteps,@Size(max=20) @Pattern(regexp="frequent|standard|rare") String restFrequency,@Size(max=20) @Pattern(regexp="transit|taxi|self-drive") String travelMode,@Size(max=20) @Pattern(regexp="slow|steady|active") String pace,@Size(max=8) List<@NotBlank @Pattern(regexp="[A-Za-z0-9]{5,40}") String> importedPlaceIds){}
 public record Day(LocalDate date,List<AmapPlaces.Place> places,List<TripPlanner.Slot> timeline,List<String> reasons){}
 public record Draft(String id,String title,Request preferences,List<Day> days,String source,String retrievedAt,String status,int version){
  public Draft { version=Math.max(1,version); }
  public Draft(String id,String title,Request preferences,List<Day> days,String source,String retrievedAt,String status){this(id,title,preferences,days,source,retrievedAt,status,1);}
 }
 @PostMapping("/api/a1/travel-drafts")
 public AgentApi.Envelope create(@Valid @RequestBody Request input,HttpSession session){return build(input,session,event->{});}
 private AgentApi.Envelope build(Request input,HttpSession session,java.util.function.Consumer<Map<String,Object>> progress){
  if(input.startDate().isBefore(LocalDate.now(ZoneId.of("Asia/Shanghai"))))throw new IllegalArgumentException();
  progress.accept(Map.of("stage","searching","message","正在搜索攻略信息…","query",input.destination()));
  boolean imported=input.importedPlaceIds()!=null&&!input.importedPlaceIds().isEmpty();
  var candidates=imported?input.importedPlaceIds().stream().distinct().map(places::detail).toList():places.planCandidates(input.destination());
  if(imported)candidates.forEach(place->checkCity(place,input.destination()));
  if(candidates.isEmpty())throw new OllamaClient.Unavailable("没有查到目的地的景点，请核对城市名称后重试。");
  var preview=candidates.stream().limit(3).map(AmapPlaces.Place::name).toList();
  progress.accept(Map.of("stage","searched","message","搜索地点："+input.destination()+" "+String.join("、",preview)+(candidates.size()>3?" 等":"")+"，共 "+candidates.size()+" 个","count",candidates.size()));
  var photoCount=candidates.stream().mapToInt(p->p.photos().size()).sum();
  progress.accept(Map.of("stage","details","message","已核对 "+candidates.size()+" 个地点的名称与地址，其中 "+photoCount+" 张照片可用"));
  progress.accept(Map.of("stage","organizing","message","正在按 "+input.days()+" 天与您设定的体力偏好安排行程…"));
  var grouped=TripPlanner.group(candidates,input,imported);
  progress.accept(Map.of("stage","grouped","message","已按坐标邻近关系分组，选入 "+grouped.stream().mapToInt(List::size).sum()+" 个地点；正在查询交通"));
  var planner=new TripPlanner(places);
  var tasks=new ArrayList<java.util.concurrent.CompletableFuture<Day>>();
  for(int d=0;d<input.days();d++){final int day=d;tasks.add(java.util.concurrent.CompletableFuture.supplyAsync(()->planner.schedule(input.startDate().plusDays(day),grouped.get(day),input,progress)));}
  var days=tasks.stream().map(java.util.concurrent.CompletableFuture::join).toList();
  progress.accept(Map.of("stage","timeline","message","已排出 "+days.size()+" 天时间轴，包含建议游玩、午餐与休息时间"));
  var draft=new Draft(UUID.randomUUID().toString(),input.destination()+" · "+input.days()+"日慢游草案",input,List.copyOf(days),"AMAP",Instant.now().toString(),"DRAFT");
  progress.accept(Map.of("stage","done","message","草案已生成；可查看每日推荐依据、交通估算和待确认事项"));
  session.setAttribute("a1.travelDraft",draft);return AgentApi.Envelope.ok(draft);
 }
 @PostMapping(value="/api/a1/travel-drafts/stream",produces="text/event-stream")
 public org.springframework.web.servlet.mvc.method.annotation.SseEmitter stream(@Valid @RequestBody Request input,HttpSession session){
  if(input.startDate().isBefore(LocalDate.now(ZoneId.of("Asia/Shanghai"))))throw new IllegalArgumentException();
  var emitter=new org.springframework.web.servlet.mvc.method.annotation.SseEmitter(180000L);
  java.util.concurrent.CompletableFuture.runAsync(()->{try{
   var result=build(input,session,event->{try{emitter.send(org.springframework.web.servlet.mvc.method.annotation.SseEmitter.event().name("progress").data(event));}catch(Exception e){throw new IllegalStateException("Stream closed");}});
   emitter.send(org.springframework.web.servlet.mvc.method.annotation.SseEmitter.event().name("result").data(result));emitter.complete();
  }catch(Exception ex){try{emitter.send(org.springframework.web.servlet.mvc.method.annotation.SseEmitter.event().name("failure").data(Map.of("message",ex instanceof OllamaClient.Unavailable||ex instanceof CityMismatch?ex.getMessage():"草案生成未完成，请重试")));emitter.complete();}catch(Exception ignored){emitter.completeWithError(ex);}}});
  return emitter;
 }
 @GetMapping("/api/a1/travel-drafts/current")
 public org.springframework.http.ResponseEntity<AgentApi.Envelope> current(HttpSession session,@CookieValue(value="a1-draft-owner",required=false) String owner){var draft=session.getAttribute("a1.travelDraft");if(draft==null){draft=storage.load(owner);if(draft!=null)session.setAttribute("a1.travelDraft",draft);}if(draft==null)return org.springframework.http.ResponseEntity.status(404).body(new AgentApi.Envelope("NOT_FOUND","本次会话暂无行程草案",null));return org.springframework.http.ResponseEntity.ok(AgentApi.Envelope.ok(draft));}

 public record EditDay(@NotNull LocalDate date,@NotNull @Size(max=8) List<@NotBlank @Size(max=40) String> placeIds){}
 public record Edit(@NotBlank String id,@NotBlank @Size(max=100) String title,@NotNull @Size(min=1,max=4) List<@Valid EditDay> days,@Min(1) Integer expectedVersion){}
 @PutMapping("/api/a1/travel-drafts/current")
 public org.springframework.http.ResponseEntity<AgentApi.Envelope> save(@Valid @RequestBody Edit edit,HttpSession session,@CookieValue(value="a1-draft-owner",required=false) String owner){
  synchronized(session){
  var base=(Draft)session.getAttribute("a1.travelDraft");if(base==null)base=storage.load(owner);
  if(base==null||!base.id().equals(edit.id()))return org.springframework.http.ResponseEntity.status(409).body(new AgentApi.Envelope("CONFLICT","草案已变化，请恢复后再修改",null));
  if(edit.expectedVersion()!=null&&edit.expectedVersion()!=base.version())return org.springframework.http.ResponseEntity.status(409).body(new AgentApi.Envelope("CONFLICT","草案已在其他页面更新，请恢复最新草案再修改",null));
  if(edit.days().size()!=base.days().size())throw new IllegalArgumentException();
  var days=new ArrayList<Day>();var used=new HashSet<String>();
  for(int i=0;i<edit.days().size();i++){var day=edit.days().get(i);if(!day.date().equals(base.preferences().startDate().plusDays(i)))throw new IllegalArgumentException();var points=new ArrayList<AmapPlaces.Place>();for(var id:day.placeIds()){if(!used.add(id))throw new IllegalArgumentException();var point=places.detail(id);checkCity(point,base.preferences().destination());points.add(point);}days.add(new TripPlanner(places).schedule(day.date(),List.copyOf(points),base.preferences(),event->{}));}
  var saved=new Draft(base.id(),edit.title(),base.preferences(),List.copyOf(days),base.source(),base.retrievedAt(),"DRAFT",base.version()+1);
  try{UUID.fromString(owner);}catch(Exception e){owner=UUID.randomUUID().toString();}
  storage.save(owner,saved);session.setAttribute("a1.travelDraft",saved);
  var cookie=org.springframework.http.ResponseCookie.from("a1-draft-owner",owner).httpOnly(true).sameSite("Lax").path("/").maxAge(java.time.Duration.ofDays(30)).build();
  return org.springframework.http.ResponseEntity.ok().header("Set-Cookie",cookie.toString()).body(AgentApi.Envelope.ok(saved));
  }
 }
}
