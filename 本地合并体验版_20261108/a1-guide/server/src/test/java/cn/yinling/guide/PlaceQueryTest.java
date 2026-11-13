package cn.yinling.guide;
import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.*;
class PlaceQueryTest {
 @Test void extractsExplicitPlaces(){assertEquals("广东省阳江市",PlaceQuery.extract("我想了解了解广东省阳江市"));assertEquals("海陵岛",PlaceQuery.extract("介绍一下海陵岛"));assertEquals("岳麓山",PlaceQuery.extract("岳麓山"));}
 @Test void ordinaryConversationIsNotAPlace(){assertNull(PlaceQuery.extract("你好，你知道我是谁吗"));assertNull(PlaceQuery.extract("这里有什么故事？"));assertNull(PlaceQuery.extract("详细讲讲"));assertNull(PlaceQuery.extract("我想了解这里"));}
}
