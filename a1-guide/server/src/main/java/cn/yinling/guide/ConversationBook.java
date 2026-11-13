package cn.yinling.guide;

import java.time.Clock;
import java.time.Duration;
import java.time.Instant;
import java.util.LinkedHashMap;
import java.util.ArrayList;
import java.util.List;

/** Temporary dialogue slots and a bounded in-memory conversation window. */
public final class ConversationBook {
    static final Duration TTL = Duration.ofMinutes(20);
    static final int MAX_SCOPES = 8;
    private final Clock clock;
    private final LinkedHashMap<Scope, Entry> entries = new LinkedHashMap<>(16, .75f, true);
    public ConversationBook() { this(Clock.systemUTC()); }
    ConversationBook(Clock clock) { this.clock=clock; }
    record Scope(String userId, String tripId) {}
    public enum Topic { NARRATION, TOILET, REST, WATER, EXIT, HOURS, ROUTE }
    public record ChatLine(String role,String content) {}
    public static final class State {
        String locationId, suppliedLocationId, discussedSpotId;
        String queryCity;
        Topic pending, lastTopic;
        boolean detailed;
        double speechRate=.8;
        final List<ChatLine> recent=new ArrayList<>();
        void remember(String question,String answer) {
            recent.add(new ChatLine("user",clip(question)));
            recent.add(new ChatLine("assistant",clip(answer)));
            while(recent.size()>6) recent.remove(0);
        }
        private String clip(String text) { return text.length()>400?text.substring(0,400):text; }
        State copy() {
            var s=new State(); s.locationId=locationId; s.suppliedLocationId=suppliedLocationId;
            s.queryCity=queryCity; s.discussedSpotId=discussedSpotId; s.pending=pending; s.lastTopic=lastTopic;
            s.detailed=detailed; s.speechRate=speechRate; s.recent.addAll(recent); return s;
        }
        void reset() {
            queryCity=null; locationId=null; suppliedLocationId=null; discussedSpotId=null; pending=null;
            lastTopic=null; detailed=false; speechRate=.8;
            recent.clear();
        }
    }
    private static final class Entry {
        State state=new State(); Instant touched; long revision;
        Entry(Instant now) { touched=now; }
    }
    public record Turn(Scope scope, Object identity, long revision, State state) {}
    public synchronized Turn begin(String userId,String tripId) {
        Instant now=clock.instant();
        entries.entrySet().removeIf(e->!e.getValue().touched.plus(TTL).isAfter(now));
        var scope=new Scope(userId,tripId==null || tripId.isBlank()?null:tripId);
        Entry entry=entries.computeIfAbsent(scope,k->new Entry(now)); entry.touched=now;
        while(entries.size()>MAX_SCOPES) entries.remove(entries.keySet().iterator().next());
        return new Turn(scope,entry,entry.revision,entry.state.copy());
    }
    public synchronized void commit(Turn turn) {
        Entry current=entries.get(turn.scope());
        // A late model answer cannot overwrite a newer help/reset turn.
        if(current==turn.identity() && current.revision==turn.revision()) {
            current.state=turn.state().copy(); current.revision++; current.touched=clock.instant();
        }
    }
}
