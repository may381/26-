package cn.yinling.guide;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import org.springframework.web.server.ResponseStatusException;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.nio.file.Path;
import java.time.LocalDate;
import java.util.*;
import static org.junit.jupiter.api.Assertions.*;
class TravelJournalTest {
 @TempDir Path root;
 @Test void ownershipPersistenceAndVersionConflict(){
  var mapper=new ObjectMapper().findAndRegisterModules();var drafts=new DraftStorage(mapper,root.resolve("drafts"));var api=new TravelJournalApi(drafts,mapper,root.resolve("journals"));
  String owner=UUID.randomUUID().toString();var date=LocalDate.of(2026,11,3);
  var draft=new TravelDraftApi.Draft("test","测试",null,List.of(new TravelDraftApi.Day(date,List.of(),List.of(),List.of())),"USER","2026-11-02T00:00:00Z","DRAFT",1);drafts.save(owner,draft);
  assertThrows(ResponseStatusException.class,()->api.get("test",date,null));
  api.save("test",new TravelJournalApi.Update(date,Map.of(),"想多休息",0),owner);
  var reloaded=new TravelJournalApi(drafts,mapper,root.resolve("journals"));
  var entry=(TravelJournalApi.Entry)reloaded.get("test",date,owner).data();assertEquals(1,entry.version());assertEquals("想多休息",entry.feedback());
  assertThrows(ResponseStatusException.class,()->api.save("test",new TravelJournalApi.Update(date,Map.of(),"覆盖",0),owner));
  assertThrows(IllegalArgumentException.class,()->api.save("test",new TravelJournalApi.Update(date,Map.of("unknown","visited"),"",1),owner));
 }
}
