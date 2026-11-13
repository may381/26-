package cn.yinling.guide;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.springframework.stereotype.Service;
import java.nio.file.*;
import java.util.UUID;
@Service
public class DraftStorage {
 private final ObjectMapper mapper;
 private final Path root;
 private static final long MAX_BYTES=8*1024*1024;
 @org.springframework.beans.factory.annotation.Autowired
 public DraftStorage(ObjectMapper mapper){this(mapper,Path.of("data","travel-drafts"));}
 DraftStorage(ObjectMapper mapper,Path root){this.mapper=mapper;this.root=root.toAbsolutePath();}
 private Path file(String owner){UUID.fromString(owner);return root.resolve(owner+".json");}
 public synchronized void save(String owner,TravelDraftApi.Draft draft){try{Files.createDirectories(root);Path temp=Files.createTempFile(root,"draft-",".tmp");try{mapper.writeValue(temp.toFile(),draft);if(Files.size(temp)>MAX_BYTES)throw new java.io.IOException("draft too large");try{Files.move(temp,file(owner),StandardCopyOption.ATOMIC_MOVE,StandardCopyOption.REPLACE_EXISTING);}catch(AtomicMoveNotSupportedException unsupported){Files.move(temp,file(owner),StandardCopyOption.REPLACE_EXISTING);}}finally{Files.deleteIfExists(temp);}}catch(Exception e){throw new OllamaClient.Unavailable("草案保存失败，请重试。");}}
 public synchronized TravelDraftApi.Draft load(String owner){if(owner==null)return null;try{var path=file(owner);if(!Files.exists(path)||Files.size(path)>MAX_BYTES)return null;return mapper.readValue(path.toFile(),TravelDraftApi.Draft.class);}catch(Exception e){return null;}}
}
