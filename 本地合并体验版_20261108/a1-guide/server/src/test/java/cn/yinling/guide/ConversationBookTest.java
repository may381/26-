package cn.yinling.guide;

import org.junit.jupiter.api.Test;
import java.time.*;
import static org.junit.jupiter.api.Assertions.*;

class ConversationBookTest {
    static class MutableClock extends Clock {
        Instant now=Instant.parse("2026-10-26T00:00:00Z");
        public ZoneId getZone(){return ZoneOffset.UTC;}
        public Clock withZone(ZoneId zone){return this;}
        public Instant instant(){return now;}
    }
    @Test void contextsExpireAfterInactivity() {
        var clock=new MutableClock(); var book=new ConversationBook(clock);
        var t=book.begin("u1",null); t.state().discussedSpotId="spot-002"; book.commit(t);
        clock.now=clock.now.plus(Duration.ofMinutes(21));
        assertNull(book.begin("u1",null).state().discussedSpotId);
    }
    @Test void failedOrUncommittedTurnsCannotChangeContext() {
        var book=new ConversationBook(); var t=book.begin("u1",null);
        t.state().locationId="spot-002";
        assertNull(book.begin("u1",null).state().locationId);
    }
    @Test void lateModelCompletionCannotUndoNewerReset() {
        var book=new ConversationBook(); var slow=book.begin("u1",null);
        slow.state().discussedSpotId="spot-002";
        var reset=book.begin("u1",null); reset.state().reset(); book.commit(reset); book.commit(slow);
        assertNull(book.begin("u1",null).state().discussedSpotId);
    }
    @Test void scopeCountIsBounded() {
        var book=new ConversationBook(); var first=book.begin("u0",null);
        first.state().locationId="spot-002";book.commit(first);
        for(int i=1;i<=ConversationBook.MAX_SCOPES;i++) book.begin("u"+i,null);
        assertNull(book.begin("u0",null).state().locationId);
    }
    @Test void chatWindowIsBoundedAndCopiesAreIndependent() {
        var book=new ConversationBook(); var t=book.begin("u1",null);
        for(int i=0;i<8;i++) t.state().remember("问".repeat(900),"答".repeat(900));
        assertEquals(6,t.state().recent.size());
        assertTrue(t.state().recent.stream().allMatch(m->m.content().length()<=400));
        book.commit(t);var next=book.begin("u1",null);next.state().recent.clear();
        assertEquals(6,book.begin("u1",null).state().recent.size());
    }
}
