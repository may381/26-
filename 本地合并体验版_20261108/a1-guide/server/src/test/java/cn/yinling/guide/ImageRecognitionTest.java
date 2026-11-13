package cn.yinling.guide;
import org.junit.jupiter.api.Test;
import static org.mockito.Mockito.*;
import static org.junit.jupiter.api.Assertions.*;
class ImageRecognitionTest {
 @Test void rejectInvalidImageBeforeCallingModel() {
  var model=mock(OllamaClient.class);var api=new ImageRecognitionApi(model);
  for(String value:new String[]{"https://example.com/a.png","data:image/png;base64,YWJj","data:image/svg+xml;base64,YWJj"}){
   assertThrows(IllegalArgumentException.class,()->api.analyze(new ImageRecognitionApi.Input(value,"这是什么？")));
  }
  verifyNoInteractions(model);
 }
 @Test void validImageIsPassedToModel()throws Exception {
  var image=new java.awt.image.BufferedImage(1,1,java.awt.image.BufferedImage.TYPE_INT_RGB);var out=new java.io.ByteArrayOutputStream();javax.imageio.ImageIO.write(image,"png",out);
  String data="data:image/png;base64,"+java.util.Base64.getEncoder().encodeToString(out.toByteArray());
  var model=mock(OllamaClient.class);when(model.recognizeImage(data,"读路牌")).thenReturn("文字较小，无法确认。");when(model.model()).thenReturn("qwen3.8-27b");
  assertEquals("OK",new ImageRecognitionApi(model).analyze(new ImageRecognitionApi.Input(data,"读路牌")).code());verify(model).recognizeImage(data,"读路牌");
 }
}
