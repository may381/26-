package cn.yinling.guide;
import org.junit.jupiter.api.Test;
import java.time.LocalDate;
import java.util.*;
import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.Mockito.*;

class TripPlannerTest {
 @Test void overnightScheduleUsesExplicitDayOffsetAndWarning(){
  var api=mock(AmapPlaces.class);
  when(api.transport("A","B","driving")).thenReturn(Map.of("options",List.of(Map.of("duration",72000,"distance",100000))));
  var day=new TripPlanner(api).schedule(LocalDate.now(),List.of(place("A","116,39"),place("B","116.01,39.01")),prefs("taxi","slow",20),e->{});
  assertTrue(day.timeline().stream().anyMatch(slot->slot.end()!=null&&slot.end().startsWith("次日 ")));
  assertTrue(day.reasons().stream().anyMatch(reason->reason.contains("已跨日")));
  assertTrue(day.timeline().stream().noneMatch(slot->slot.end()!=null&&slot.end().matches("(2[4-9]|[3-9][0-9]):.*")));
 }
 @Test void impossibleDurationCannotOverflowArrivalClock(){
  var api=mock(AmapPlaces.class);
  when(api.transport("A","B","driving")).thenReturn(Map.of("options",List.of(Map.of("duration",Double.MAX_VALUE,"distance",1000))));
  var day=new TripPlanner(api).schedule(LocalDate.now(),List.of(place("A","116,39"),place("B","116.01,39.01")),prefs("taxi","slow",20),e->{});
  var transport=day.timeline().stream().filter(slot->slot.kind().equals("transport")).findFirst().orElseThrow();
  assertNull(transport.minutes());assertEquals("UNCONFIRMED",transport.evidence());
  assertTrue(day.timeline().stream().filter(slot->slot.kind().equals("visit")&&slot.placeId().equals("B")).allMatch(slot->slot.start()==null));
 }
 @Test void transitMapUsesQueriedWalkingAndBusSegments(){
  var api=mock(AmapPlaces.class);
  when(api.transport("A","B","walking")).thenReturn(Map.of("options",List.of(Map.of("duration",3600,"distance",4500))));
  var segments=List.of(Map.of("walking",Map.of("steps",List.of(Map.of("polyline","116,39;116.001,39.001"))),"bus",Map.of("buslines",List.of(Map.of("polyline","116.001,39.001;116.01,39.01")))));
  when(api.transport("A","B","transit")).thenReturn(Map.of("options",List.of(Map.of("duration",900,"distance",5000,"segments",segments))));
  var day=new TripPlanner(api).schedule(LocalDate.now(),List.of(place("A","116,39"),place("B","116.01,39.01")),prefs("transit","slow",20),e->{});
  var leg=day.timeline().stream().filter(s->s.kind().equals("transport")).findFirst().orElseThrow();
  assertEquals("transit",leg.mode());assertEquals(2,leg.polyline().size());assertEquals("116.001,39.001;116.01,39.01",leg.polyline().get(1));
 }
 @Test void emptyDayDoesNotInventSchedule(){
  var day=new TripPlanner(mock(AmapPlaces.class)).schedule(LocalDate.now(),List.of(),prefs("taxi","slow",20),e->{});
  assertTrue(day.timeline().isEmpty());assertTrue(day.reasons().get(0).contains("没有分配"));
 }
 @Test void suggestedVisitDoesNotCrossLunchBoundary(){
  var api=mock(AmapPlaces.class);
  when(api.transport("A","B","driving")).thenReturn(Map.of("options",List.of(Map.of("duration",600,"distance",1000))));
  var p=new TravelDraftApi.Request("测试",LocalDate.now(),1,120,"朋友同行",false,"rare","taxi","slow",null);
  var day=new TripPlanner(api).schedule(LocalDate.now(),List.of(place("A","116,39"),place("B","116.01,39.01")),p,e->{});
  assertTrue(day.timeline().stream().noneMatch(s->s.kind().equals("visit")&&s.start()!=null&&s.start().compareTo("12:00")<0&&s.end().compareTo("12:00")>0));
 }
 private TravelDraftApi.Request prefs(String mode,String pace,int walking){return new TravelDraftApi.Request("测试城市",LocalDate.now().plusDays(1),3,walking,"家人同行",true,"frequent",mode,pace,null);}
 private AmapPlaces.Place place(String id,String location){return new AmapPlaces.Place(id,id,"地址","景点",location,"",List.of(),"");}
 @Test void nearbyPointsAreGroupedWithoutLosingConfirmedImports(){
  var a=place("A","116,39");var far=place("B","117,40");var near=place("C","116.001,39.001");
  var grouped=TripPlanner.group(List.of(a,far,near),prefs("transit","slow",20),false);
  assertEquals(List.of(a,near),grouped.get(0));assertEquals(List.of(far),grouped.get(1));
  var imported=TripPlanner.group(List.of(a,far,near),prefs("transit","slow",20),true);
  assertEquals(3,imported.stream().mapToInt(List::size).sum());
 }
 @Test void successfulTransportIncludesVisitRestAndLunchInArrivalTime(){
  var api=mock(AmapPlaces.class);when(api.transport("A","B","driving")).thenReturn(Map.of("options",List.of(Map.of("duration","1200","distance","5000","steps",List.of(Map.of("polyline","116,39;116.01,39.01"))))));
  var day=new TripPlanner(api).schedule(LocalDate.now(),List.of(place("A","116,39"),place("B","116.01,39.01")),prefs("taxi","slow",20),e->{});
  var travel=day.timeline().stream().filter(s->s.kind().equals("transport")).findFirst().orElseThrow();assertEquals("AMAP_ESTIMATE",travel.evidence());assertEquals(20,travel.minutes());assertEquals("11:55",travel.start());
  var arrival=day.timeline().stream().filter(s->s.kind().equals("visit")&&s.placeId().equals("B")).findFirst().orElseThrow();assertEquals("13:45",arrival.start());
  assertTrue(day.timeline().stream().anyMatch(s->s.kind().equals("meal")&&s.minutes()==60));assertTrue(day.timeline().stream().anyMatch(s->s.kind().equals("rest")));
 }
 @Test void missingTransportNeverBecomesZeroMinutesOrAnInventedArrival(){
  var api=mock(AmapPlaces.class);var day=new TripPlanner(api).schedule(LocalDate.now(),List.of(place("A","116,39"),place("B","116.01,39.01")),prefs("taxi","slow",20),e->{});
  var travel=day.timeline().stream().filter(s->s.kind().equals("transport")).findFirst().orElseThrow();assertNull(travel.minutes());assertEquals("UNCONFIRMED",travel.evidence());
  var arrival=day.timeline().stream().filter(s->s.kind().equals("visit")&&s.placeId().equals("B")).findFirst().orElseThrow();assertNull(arrival.start());assertNull(arrival.end());
 }
 @Test void longWalkTriggersPublicTransportQuery(){
  var api=mock(AmapPlaces.class);when(api.transport("A","B","walking")).thenReturn(Map.of("options",List.of(Map.of("duration",3600,"distance",4500))));when(api.transport("A","B","transit")).thenReturn(Map.of("options",List.of(Map.of("duration",900,"distance",5000))));
  var day=new TripPlanner(api).schedule(LocalDate.now(),List.of(place("A","116,39"),place("B","116.01,39.01")),prefs("transit","slow",20),e->{});
  assertTrue(day.timeline().stream().anyMatch(s->s.kind().equals("transport")&&s.mode().equals("transit")&&s.minutes()==15));verify(api).transport("A","B","transit");
 }
 @Test void lowerWalkingBudgetReducesDailyPlaces(){assertEquals(1,TripPlanner.limit(prefs("transit","slow",10)));assertEquals(2,TripPlanner.limit(prefs("transit","slow",20)));}
}
