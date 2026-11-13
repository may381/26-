package cn.yinling.guide;

/** Keep application labels and fixed notices out of the text sent for rewriting. */
final class ReplyText {
    private ReplyText() {}
    static String clean(String value) {
        return value.replaceAll("【[^】]*(?:演示|本地\\s*AI)[^】]*】", "")
            .replace("未接入实时定位，不提供距离或导航承诺。", "")
            .replace("当前没有更改您的路线。", "")
            .replace("这不是实时营业状态，实际开放情况须向景区核实。", "")
            .replaceAll("(这里|此处)(?:并)?没有(?:特定的?)?(历史故事|人物传说|相关典故)", "我手头还没查到这里的$2")
            .strip();
    }
}
