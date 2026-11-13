package cn.yinling.guide;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.mock.mockito.MockBean;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.mock.web.MockHttpSession;
import java.util.List;
import java.time.*;
import static org.mockito.Mockito.*;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.*;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.*;
@SpringBootTest
@AutoConfigureMockMvc
class TravelDraftApiTest {
 @Autowired MockMvc mvc;
 @MockBean AmapPlaces places;
 @MockBean DraftStorage storage;
 @Test void importedPlaceFromAnotherCityIsRejected()throws Exception{
  when(places.detail("B123456")).thenReturn(new AmapPlaces.Place("B123456","Place","长沙市","Spot","112,28","",List.of(),"","长沙市"));
  String day=LocalDate.now(ZoneId.of("Asia/Shanghai")).plusDays(1).toString();
  mvc.perform(post("/api/a1/travel-drafts").contentType("application/json").content("{\"destination\":\"北京\",\"startDate\":\""+day+"\",\"days\":1,\"walkMinutes\":20,\"companions\":\"独自出游\",\"importedPlaceIds\":[\"B123456\"]}"))
    .andExpect(status().isBadRequest()).andExpect(jsonPath("$.message").value(org.hamcrest.Matchers.containsString("城市")));
  verify(storage,never()).save(anyString(),any());
 }
 @Test void citySuffixDoesNotCauseFalseMismatch(){
  var point=new AmapPlaces.Place("B123456","Place","长沙市","Spot","112,28","",List.of(),"","长沙市");
  org.junit.jupiter.api.Assertions.assertDoesNotThrow(()->TravelDraftApi.checkCity(point,"长沙"));
  org.junit.jupiter.api.Assertions.assertThrows(TravelDraftApi.CityMismatch.class,()->TravelDraftApi.checkCity(point,"长沙县"));
 }
 @Test void unsupportedPreferencesAreRejectedBeforeExternalQuery()throws Exception{
  String day=LocalDate.now(ZoneId.of("Asia/Shanghai")).plusDays(1).toString();
  for(String field:List.of("pace","restFrequency","travelMode")) {
   mvc.perform(post("/api/a1/travel-drafts").contentType("application/json").content("{\"destination\":\"Beijing\",\"startDate\":\""+day+"\",\"days\":1,\"walkMinutes\":40,\"companions\":\"独自出游\",\""+field+"\":\"unsupported\"}"))
     .andExpect(status().isBadRequest());
  }
  verifyNoInteractions(places);
 }
 @Test void staleEditorCannotOverwriteNewerDraft()throws Exception{
  var point=new AmapPlaces.Place("B123456","Place","Address","Spot","116,39","",List.of(),"");
  when(places.planCandidates("Beijing")).thenReturn(List.of(point));when(places.detail("B123456")).thenReturn(point);
  String day=LocalDate.now(ZoneId.of("Asia/Shanghai")).plusDays(1).toString();var session=new MockHttpSession();
  mvc.perform(post("/api/a1/travel-drafts").session(session).contentType("application/json").content("{\"destination\":\"Beijing\",\"startDate\":\""+day+"\",\"days\":1,\"walkMinutes\":40,\"companions\":\"独自出游\"}"));
  var draft=(TravelDraftApi.Draft)session.getAttribute("a1.travelDraft");
  String edit="{\"id\":\""+draft.id()+"\",\"title\":\"edited\",\"expectedVersion\":1,\"days\":[{\"date\":\""+day+"\",\"placeIds\":[\"B123456\"]}]}";
  mvc.perform(put("/api/a1/travel-drafts/current").session(session).contentType("application/json").content(edit)).andExpect(status().isOk()).andExpect(jsonPath("$.data.version").value(2));
  mvc.perform(put("/api/a1/travel-drafts/current").session(session).contentType("application/json").content(edit)).andExpect(status().isConflict());
  verify(storage,times(1)).save(anyString(),any());
 }
 @Test void legacyDateUiFieldsDoNotBreakDraftCreation()throws Exception{
  var p=new AmapPlaces.Place("B123456","Place","Address","Spot","116,39","",List.of(),"");
  when(places.planCandidates("Beijing")).thenReturn(List.of(p));
  String day=LocalDate.now(ZoneId.of("Asia/Shanghai")).plusDays(1).toString();
  mvc.perform(post("/api/a1/travel-drafts").contentType("application/json").content("{\"destination\":\"Beijing\",\"startDate\":\""+day+"\",\"days\":2,\"walkMinutes\":40,\"companions\":\"独自出游\",\"dateConfirmed\":true,\"step\":2}"))
   .andExpect(status().isOk()).andExpect(jsonPath("$.data.days[0].places[0].id").value("B123456"));
 }
 @Test void unknownBusinessFieldsHaveDraftSpecificError()throws Exception{
  String day=LocalDate.now(ZoneId.of("Asia/Shanghai")).plusDays(1).toString();
  mvc.perform(post("/api/a1/travel-drafts/stream").contentType("application/json").content("{\"destination\":\"Beijing\",\"startDate\":\""+day+"\",\"days\":2,\"walkMinutes\":40,\"companions\":\"独自出游\",\"unknownBusinessField\":true}"))
   .andExpect(status().isBadRequest()).andExpect(jsonPath("$.message").value(org.hamcrest.Matchers.containsString("出游参数")));
  verifyNoInteractions(places);
 }
 @Test void confirmedImportedPlacesAreUsedInsteadOfPopularCandidates()throws Exception{
  var p=new AmapPlaces.Place("B123456","Imported","Address","Spot","116,39","",List.of(),"");
  when(places.detail("B123456")).thenReturn(p);
  String day=LocalDate.now(ZoneId.of("Asia/Shanghai")).plusDays(1).toString();
  mvc.perform(post("/api/a1/travel-drafts").contentType("application/json").content("{\"destination\":\"Beijing\",\"startDate\":\""+day+"\",\"days\":2,\"walkMinutes\":20,\"companions\":\"独自出游\",\"importedPlaceIds\":[\"B123456\"]}"))
   .andExpect(status().isOk()).andExpect(jsonPath("$.data.days[0].places[0].name").value("Imported"));
  verify(places,never()).planCandidates(anyString());
 }
 @Test void realEvidenceDraftIsNotATripAndSessionIsolated()throws Exception{
  var p=new AmapPlaces.Place("B123456","Place","Address","Spot","116,39","",List.of(),"https://uri.amap.com/marker?poiid=B123456");when(places.planCandidates("Beijing")).thenReturn(List.of(p));var session=new MockHttpSession();
  String day=LocalDate.now(ZoneId.of("Asia/Shanghai")).plusDays(1).toString();
  mvc.perform(post("/api/a1/travel-drafts").session(session).contentType("application/json").content("{\"destination\":\"Beijing\",\"startDate\":\""+day+"\",\"days\":2,\"walkMinutes\":20,\"companions\":\"独自出游\"}"))
    .andExpect(status().isOk()).andExpect(jsonPath("$.data.status").value("DRAFT")).andExpect(jsonPath("$.data.days[0].places[0].id").value("B123456")).andExpect(jsonPath("$.data.days[1].places").isEmpty());
  mvc.perform(get("/api/a1/travel-drafts/current").session(session)).andExpect(status().isOk());mvc.perform(get("/api/a1/travel-drafts/current")).andExpect(status().isNotFound());
 }
 @Test void pastDateRejectedBeforeMapQuery()throws Exception{
 mvc.perform(post("/api/a1/travel-drafts").contentType("application/json").content("{\"destination\":\"Beijing\",\"startDate\":\"2000-01-01\",\"days\":2,\"walkMinutes\":20,\"companions\":\"独自出游\"}")).andExpect(status().isBadRequest());verifyNoInteractions(places);
 }
 @Test void emptySearchFailsHonestly()throws Exception{
 when(places.planCandidates("Unknown")).thenReturn(List.of());String day=LocalDate.now(ZoneId.of("Asia/Shanghai")).toString();mvc.perform(post("/api/a1/travel-drafts").contentType("application/json").content("{\"destination\":\"Unknown\",\"startDate\":\""+day+"\",\"days\":1,\"walkMinutes\":40,\"companions\":\"独自出游\"}")).andExpect(status().isBadGateway());
 }
}
