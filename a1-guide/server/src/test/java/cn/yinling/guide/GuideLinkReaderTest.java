package cn.yinling.guide;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.*;
class GuideLinkReaderTest {
 private final GuideLinkReader reader=new GuideLinkReader(new ObjectMapper());
 private final String url="https://www.xiaohongshu.com/explore/abc123";
 @Test void noteBodyIsReadWithoutExecutingPageScripts(){
  var result=reader.parse("<script>window.__INITIAL_STATE__={\"note\":{\"noteDetailMap\":{\"abc123\":{\"note\":{\"title\":\"阳江三日游\",\"desc\":\"推荐海陵岛、十里银滩和大角湾，适合一家人慢慢玩。\",\"optional\":undefined}}}}};</script>",url);
  assertEquals("READY",result.status());assertTrue(result.text().contains("十里银滩"));assertEquals("阳江三日游",result.title());
 }
 @Test void recommendedNoteCannotReplaceTheRequestedNote(){
  var result=reader.parse("<script>window.__INITIAL_STATE__={\"note\":{\"noteDetailMap\":{\"other\":{\"note\":{\"title\":\"其他笔记\",\"desc\":\"这是一篇其他笔记中的地点，不能冒充当前笔记正文。\"}}}}}</script>",url);
  assertEquals("NEEDS_CONTENT",result.status());assertTrue(result.text().isEmpty());
 }
 @Test void loginAndMetadataDoNotPretendToBeNoteContent(){
  var result=reader.parse("<html><meta property='og:description' content='阳江海陵岛推荐十里银滩大角湾'><body>请登录小红书查看更多精彩</body></html>",url);
  assertEquals("NEEDS_CONTENT",result.status());assertTrue(result.text().isEmpty());
 }
 @Test void structuredArticleBodyCanBeRead(){
  var result=reader.parse("<script type=\"application/ld+json\">{\"@type\":\"BlogPosting\",\"headline\":\"海边攻略\",\"articleBody\":\"阳江海陵岛三日游，第一天去十里银滩，第二天去大角湾。\"}</script>",url);
  assertEquals("READY",result.status());assertTrue(result.text().contains("大角湾"));
 }
 @Test void onlyExactHttpsNoteAndShareHostsAreAllowed(){
  for(String value:new String[]{"http://127.0.0.1:8091/","https://www.xiaohongshu.com.evil.test/explore/abc123","https://user@www.xiaohongshu.com/explore/abc123","https://www.xiaohongshu.com:8443/explore/abc123","file:///etc/passwd","https://www.xiaohongshu.com/login","https://evil.test/"})assertThrows(IllegalArgumentException.class,()->GuideLinkReader.checked(value));
  assertNotNull(GuideLinkReader.checked(url+"?xsec_token=example"));assertNotNull(GuideLinkReader.checked("https://xhslink.cn/o/abc123"));
 }
 @Test void undefinedReplacementPreservesWordsInsideQuotedContent(){assertEquals("{\"body\":\"undefined\",\"other\":null}",GuideLinkReader.undefinedToNull("{\"body\":\"undefined\",\"other\":undefined}"));}
 @Test void extractedBodyIsLimitedToTheInputSize(){
  var result=reader.parse("<script type='application/ld+json'>{\"@type\":\"Article\",\"articleBody\":\""+"阳江海陵岛".repeat(1500)+"\"}</script>",url);assertEquals(6000,result.text().length());
 }
}
