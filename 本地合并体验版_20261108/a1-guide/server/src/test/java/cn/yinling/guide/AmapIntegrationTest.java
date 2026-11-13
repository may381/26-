package cn.yinling.guide;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.mock.mockito.MockBean;
import org.springframework.test.web.servlet.MockMvc;
import java.util.List;
import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.Mockito.*;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.*;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.*;
@SpringBootTest
@AutoConfigureMockMvc
class AmapIntegrationTest {
 @Autowired MockMvc mvc;
 @MockBean AmapPlaces places;
 @MockBean OllamaClient model;
 @Test void realPlaceEvidenceNeverFallsBackToMock()throws Exception{
  var p=new AmapPlaces.Place("B123456","真实景点","真实地址","景点","112,28","",List.of(),"https://uri.amap.com/marker?poiid=B123456");
  when(places.detail("B123456")).thenReturn(p);
  mvc.perform(post("/api/agent/messages").contentType("application/json").content("{\"userId\":\"u100\",\"text\":\"介绍这里\",\"context\":{\"location\":\"amap:B123456\"}}"))
   .andExpect(status().isOk()).andExpect(jsonPath("$.data.tools[0].result.source").value("AMAP"))
   .andExpect(jsonPath("$.data.tools[0].result.places[0].name").value("真实景点"));
 }
 @Test void helpDoesNotCallMaps()throws Exception{
  mvc.perform(post("/api/agent/messages").contentType("application/json").content("{\"userId\":\"u100\",\"text\":\"求助\",\"context\":{\"location\":\"amap:B123456\"}}"))
   .andExpect(jsonPath("$.data.intent").value("help"));verifyNoInteractions(places);
 }
 /** 「选择并询问」发出的"介绍一下X"必须落到已选地点详情，不能被地点提取拦截成一次新的搜索。 */
 @Test void askingAboutTheSelectedPlaceGivesDetailInsteadOfSearchingAgain()throws Exception{
  var p=new AmapPlaces.Place("B123456","真实景点","真实地址","景点","112,28","",List.of(),"https://uri.amap.com/marker?poiid=B123456");
  when(places.detail("B123456")).thenReturn(p);
  mvc.perform(post("/api/agent/messages").contentType("application/json")
    .content("{\"userId\":\"u100\",\"text\":\"介绍一下真实景点，请根据查到的资料回答。\",\"context\":{\"location\":\"amap:B123456\"}}"))
   .andExpect(status().isOk())
   .andExpect(jsonPath("$.data.tools[0].tool").value("place.detail"))
   .andExpect(jsonPath("$.data.tools[0].result.queryPlace").doesNotExist())
   .andExpect(jsonPath("$.data.tools[0].result.places[0].name").value("真实景点"));
  verify(places,never()).search(anyString(),anyString());
 }
 @Test void parseOptionalFieldsAndRejectUnsafePhotos()throws Exception{
  var root=new ObjectMapper().readTree("{\"pois\":[{\"id\":\"B123456\",\"name\":\"地点\",\"address\":[],\"photos\":[{\"url\":\"javascript:bad\"},{\"url\":\"https://example.com/a.jpg\"}]}]}");
  var p=AmapPlaces.parse(root).get(0);assertEquals(1,p.photos().size());assertEquals("",p.address());assertTrue(p.mapUrl().startsWith("https://uri.amap.com/"));
 }
 @Test void placeCityComesFromSourceAndMunicipalityFallback()throws Exception{
  var root=new ObjectMapper().readTree("{\"pois\":[{\"id\":\"B123456\",\"name\":\"地点\",\"cityname\":\"长沙市\"},{\"id\":\"B123457\",\"name\":\"地点2\",\"pname\":\"北京市\",\"cityname\":[]}]}");
  var points=AmapPlaces.parse(root);
  assertEquals("长沙市",points.get(0).city());assertEquals("北京市",points.get(1).city());
 }
}
