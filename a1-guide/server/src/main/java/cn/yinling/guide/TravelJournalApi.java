package cn.yinling.guide;

import com.fasterxml.jackson.databind.ObjectMapper;
import jakarta.validation.Valid;
import jakarta.validation.constraints.*;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.server.ResponseStatusException;
import org.springframework.http.HttpStatus;
import java.nio.file.*;
import java.time.*;
import java.util.*;

/** Cookie-owned, self-reported journal. Never a P2 Trip or confirmed long-term memory. */
@RestController
public class TravelJournalApi {
 private final DraftStorage drafts; private final ObjectMapper mapper;
 private final Path root;
 @org.springframework.beans.factory.annotation.Autowired
 public TravelJournalApi(DraftStorage drafts,ObjectMapper mapper){this(drafts,mapper,Path.of("data","travel-journals"));}
 TravelJournalApi(DraftStorage drafts,ObjectMapper mapper,Path root){this.drafts=drafts;this.mapper=mapper;this.root=root.toAbsolutePath();}
 public record Entry(String draftId,LocalDate date,Map<String,String> marks,String feedback,int version,Instant updatedAt,String source){}
 public record Update(@NotNull LocalDate date,@NotNull @Size(max=8) Map<@NotBlank String,@Pattern(regexp="visited|skip") String> marks,@NotNull @Size(max=500) String feedback,@Min(0) int expectedVersion){}
 private TravelDraftApi.Draft owned(String owner,String id){var draft=drafts.load(owner);if(draft==null||!draft.id().equals(id))throw new ResponseStatusException(HttpStatus.NOT_FOUND,"未找到当前浏览器所属的已保存草案");return draft;}
 private Path file(String owner,String id,LocalDate date){UUID.fromString(owner);return root.resolve(owner+"-"+date+".json");}
 private Entry load(Path file,String id,LocalDate date){try{if(!Files.exists(file))return new Entry(id,date,Map.of(),"",0,null,"USER_REPORTED");if(Files.size(file)>65536)throw new IllegalStateException();var entry=mapper.readValue(file.toFile(),Entry.class);if(!entry.draftId().equals(id))return new Entry(id,date,Map.of(),"",0,null,"USER_REPORTED");return entry;}catch(Exception e){throw new OllamaClient.Unavailable("游览记录读取失败，请勿覆盖旧记录。");}}
 @GetMapping("/api/a1/travel-drafts/{id}/journal")
 public synchronized AgentApi.Envelope get(@PathVariable String id,@RequestParam LocalDate date,@CookieValue(value="a1-draft-owner",required=false) String owner){var draft=owned(owner,id);if(draft.days().stream().noneMatch(d->d.date().equals(date)))throw new IllegalArgumentException();return AgentApi.Envelope.ok(load(file(owner,id,date),id,date));}
 @PutMapping("/api/a1/travel-drafts/{id}/journal")
 public synchronized AgentApi.Envelope save(@PathVariable String id,@Valid @RequestBody Update update,@CookieValue(value="a1-draft-owner",required=false) String owner){
  var draft=owned(owner,id);var day=draft.days().stream().filter(d->d.date().equals(update.date())).findFirst().orElseThrow(IllegalArgumentException::new);
  var ids=new HashSet<String>();day.places().forEach(p->ids.add(p.id()));if(!ids.containsAll(update.marks().keySet()))throw new IllegalArgumentException();
  var file=file(owner,id,update.date());var old=load(file,id,update.date());if(old.version()!=update.expectedVersion())throw new ResponseStatusException(HttpStatus.CONFLICT,"记录已更新，请先恢复服务器记录再修改");
  var entry=new Entry(id,update.date(),Map.copyOf(update.marks()),update.feedback(),old.version()+1,Instant.now(),"USER_REPORTED");
  try{Files.createDirectories(root);var temp=Files.createTempFile(root,"journal-",".tmp");try{mapper.writeValue(temp.toFile(),entry);try{Files.move(temp,file,StandardCopyOption.ATOMIC_MOVE,StandardCopyOption.REPLACE_EXISTING);}catch(AtomicMoveNotSupportedException e){Files.move(temp,file,StandardCopyOption.REPLACE_EXISTING);}}finally{Files.deleteIfExists(temp);}}catch(Exception e){throw new OllamaClient.Unavailable("游览记录保存失败，未确认写入成功。");}
  return AgentApi.Envelope.ok(entry);
 }
}
