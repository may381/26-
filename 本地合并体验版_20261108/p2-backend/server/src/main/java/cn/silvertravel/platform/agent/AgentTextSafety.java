package cn.silvertravel.platform.agent;

/** Text validity checks; this does not establish factual accuracy or replace content moderation. */
final class AgentTextSafety {
    private AgentTextSafety() {}

    static boolean valid(String text) {
        if (text == null || text.isEmpty()) return false;
        boolean visible = false;
        for (int offset = 0; offset < text.length(); ) {
            char unit = text.charAt(offset);
            if (Character.isHighSurrogate(unit)) {
                if (offset + 1 >= text.length()
                        || !Character.isLowSurrogate(text.charAt(offset + 1))) return false;
            } else if (Character.isLowSurrogate(unit)) return false;
            int point = text.codePointAt(offset);
            int type = Character.getType(point);
            // Permit ordinary line breaks/tabs, but reject hidden control and bidi overrides.
            if ((Character.isISOControl(point) && point != '\n' && point != '\r' && point != '\t')
                    || (point >= 0x202A && point <= 0x202E)
                    || (point >= 0x2066 && point <= 0x2069)
                    || point == 0xFFFD) return false;
            if (!Character.isWhitespace(point)
                    && !Character.isSpaceChar(point)
                    && type != Character.FORMAT
                    && type != Character.NON_SPACING_MARK
                    && type != Character.COMBINING_SPACING_MARK
                    && type != Character.ENCLOSING_MARK) visible = true;
            offset += Character.charCount(point);
        }
        return visible;
    }
}
