package cn.yinling.guide;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.Test;
import org.springframework.mock.web.MockMultipartFile;
import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.Mockito.*;

class GuideImportApiTest {
 @Test void publicLinkReadingIsSeparateFromModelClaims(){
  var reader=mock(GuideLinkReader.class);var model=mock(OllamaClient.class);String url="https://xhslink.cn/o/example";
  when(reader.read(url)).thenReturn(new GuideLinkReader.Result("NEEDS_CONTENT","","",url,"小红书","2026-10-28T00:00:00Z","请补充正文"));
  var api=new GuideImportApi(model,new ObjectMapper(),reader);var data=new ObjectMapper().valueToTree(api.readLink(new GuideImportApi.LinkInput(url)));
  assertEquals("NEEDS_CONTENT",data.at("/data/status").asText());verify(reader).read(url);verifyNoInteractions(model);
 }
 @Test void linkAloneIsNeverClaimedAsFetched(){
  var model=mock(OllamaClient.class);var api=new GuideImportApi(model,new ObjectMapper(),mock(GuideLinkReader.class));
  var data=new ObjectMapper().valueToTree(api.analyze(new GuideImportApi.Input("https://xhslink.com/o/test")));
  assertEquals("NEEDS_CONTENT",data.at("/data/status").asText());assertFalse(data.at("/data/linkFetched").asBoolean());verifyNoInteractions(model);
 }
 @Test void extractedNamesMustActuallyAppearInUserText(){
  var model=mock(OllamaClient.class);var api=new GuideImportApi(model,new ObjectMapper(),mock(GuideLinkReader.class));
  when(model.extractTravel(anyString())).thenReturn("{\"destination\":\"阳江\",\"places\":[\"海陵岛\",\"不存在的景区\",\"海陵岛\"]}");
  var data=new ObjectMapper().valueToTree(api.analyze(new GuideImportApi.Input("我准备去阳江旅游，想去海陵岛走走看看。")));
  assertEquals("REVIEW",data.at("/data/status").asText());assertEquals(1,data.at("/data/places").size());assertEquals("海陵岛",data.at("/data/places/0").asText());
 }
 @Test void unreadableModelOutputFailsInsteadOfFabricating(){
  var model=mock(OllamaClient.class);when(model.extractTravel(anyString())).thenReturn("invalid json");
  assertThrows(OllamaClient.Unavailable.class,()->new GuideImportApi(model,new ObjectMapper(),mock(GuideLinkReader.class)).analyze(new GuideImportApi.Input("我准备去阳江旅游，想去海陵岛走走看看。")));
 }
 @Test void nonImageUploadIsRejectedBeforeLaunchingOcr(){
  var api=new GuideImportApi(mock(OllamaClient.class),new ObjectMapper(),mock(GuideLinkReader.class));
  assertThrows(IllegalArgumentException.class,()->api.ocr(new MockMultipartFile("file","fake.png","image/png","not an image".getBytes())));
 }
}
