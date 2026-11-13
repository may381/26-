package cn.yinling.guide;
import java.util.regex.Pattern;
/** Conservative extraction: only explicit place requests, never infer physical position. */
final class PlaceQuery {
 static String extract(String text){
  String q=text.strip().replaceAll("[？?。！!]$","");
  var match=Pattern.compile("^(?:你好[，, ]*)?(?:我想(?:要)?(?:了解|去|看看)|帮我(?:查查|查询|找找|搜索)|请(?:介绍|查询)|介绍一下|介绍|了解一下|了解)(.+)$").matcher(q);
  if(match.matches())q=match.group(1).strip();
  else if(!q.matches("[\\p{IsHan}]{2,20}(?:省|市|县|区|岛|公园|景区|博物馆|寺|山)"))return null;
  q=q.replaceAll("^(?:一下|了解)+","").replaceAll("[，,].*$","").replaceAll("(?:怎么样|有什么好玩的|的景点|的故事|的历史|在哪里|吧|呀|呢)$","").strip();
  if(q.length()<2||q.length()>40||q.matches(".*(?:这里|那里|什么|怎么|谁|名字|称呼|自己|一下|详细|简单|语速|心情|故事|路线).*"))return null;
  return q;
 }
}
