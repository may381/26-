package cn.yinling.guide;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import java.nio.file.*;
import java.time.LocalDate;
import java.util.*;
import static org.junit.jupiter.api.Assertions.*;

class DraftStorageTest {
 @TempDir Path directory;
 ObjectMapper mapper=new ObjectMapper().findAndRegisterModules();
 TravelDraftApi.Draft draft(String title,int version){
  var request=new TravelDraftApi.Request("长沙",LocalDate.of(2026,11,2),1,20,"家人同行",true,"frequent","transit","slow",null);
  return new TravelDraftApi.Draft("draft-test",title,request,List.of(),"AMAP","2026-10-31T00:00:00Z","DRAFT",version);
 }
 @Test void savedDraftSurvivesNewStorageInstanceAndOldFilesDefaultVersion()throws Exception{
  String owner=UUID.randomUUID().toString();var storage=new DraftStorage(mapper,directory);
  storage.save(owner,draft("慢游草案",2));
  assertEquals(2,new DraftStorage(mapper,directory).load(owner).version());
  Path file=directory.resolve(owner+".json");var tree=mapper.readTree(file.toFile());((com.fasterxml.jackson.databind.node.ObjectNode)tree).remove("version");mapper.writeValue(file.toFile(),tree);
  assertEquals(1,storage.load(owner).version());
 }
 @Test void failedOversizedSavePreservesPreviousDraftAndCleansTemporaryFiles()throws Exception{
  String owner=UUID.randomUUID().toString();var storage=new DraftStorage(mapper,directory);storage.save(owner,draft("原草案",1));
  assertThrows(OllamaClient.Unavailable.class,()->storage.save(owner,draft("x".repeat(9*1024*1024),2)));
  assertEquals("原草案",storage.load(owner).title());
  try(var files=Files.list(directory)){assertEquals(1,files.count());}
 }
 @Test void malformedOwnerAndCorruptedFileAreNotRestored()throws Exception{
  var storage=new DraftStorage(mapper,directory);assertNull(storage.load("../../outside"));
  String owner=UUID.randomUUID().toString();Files.writeString(directory.resolve(owner+".json"),"broken-json");assertNull(storage.load(owner));
 }
}
