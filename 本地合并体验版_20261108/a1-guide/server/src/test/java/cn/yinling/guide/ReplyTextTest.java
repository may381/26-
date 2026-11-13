package cn.yinling.guide;
import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.*;
class ReplyTextTest {
    @Test void missingStoryIsNotAssertedToBeNonexistent() {
        assertEquals("我手头还没查到这里的历史故事或人物传说。",ReplyText.clean("这里没有特定的历史故事或人物传说。"));
    }
    @Test void repeatedLabelsAndNoticesDoNotRemainInBody() {
        assertEquals("可以先歇歇。",ReplyText.clean("【清风园演示资料 · 本地 AI】【清风园演示数据】可以先歇歇。未接入实时定位，不提供距离或导航承诺。当前没有更改您的路线。"));
    }
}
