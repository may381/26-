package cn.silvertravel.platform.agent;

import cn.silvertravel.platform.common.api.BusinessException;
import cn.silvertravel.platform.security.BusinessAccessPolicy;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.awt.image.BufferedImage;
import java.io.*;
import java.sql.Timestamp;
import java.time.Instant;
import java.util.*;
import javax.imageio.*;
import javax.imageio.stream.ImageInputStream;
import org.springframework.context.annotation.Profile;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.security.access.AccessDeniedException;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.multipart.MultipartFile;

@Service @Profile("!bootstrap")
public class AgentAttachmentService {
    private final java.util.concurrent.Semaphore decodeSlots=new java.util.concurrent.Semaphore(2);
    public record View(String attachmentId,String mimeType,long sizeBytes,String state,Instant expiresAt,int width,int height,String purpose) {}
    public record Binary(byte[] bytes,String mimeType,String fileName) {}
    private final JdbcTemplate jdbc;private final BusinessAccessPolicy access;private final AgentInvocationAccess invocations;private final ObjectMapper json;
    public AgentAttachmentService(JdbcTemplate jdbc,BusinessAccessPolicy access,AgentInvocationAccess invocations,ObjectMapper json){this.jdbc=jdbc;this.access=access;this.invocations=invocations;this.json=json;}
    @Transactional
    public View upload(String user,MultipartFile file,String purpose){
        access.requireElderOwner(user);if(!Set.of("fraud_analysis","travel_reference").contains(purpose))throw BusinessException.invalid("purpose只支持fraud_analysis或travel_reference");
        if(file==null||file.isEmpty()||file.getSize()>10L*1024*1024)throw BusinessException.invalid("图片最多10MiB");
        if(!decodeSlots.tryAcquire())throw BusinessException.conflict("图片处理繁忙，请稍后重试");
        byte[] sanitized;int width,height;String mime;
        try{
            byte[] input;try(var in=file.getInputStream()){input=in.readNBytes(10*1024*1024+1);}if(input.length>10*1024*1024)throw new IOException();
            boolean png=input.length>=8&&(input[0]&255)==137&&input[1]==80&&input[2]==78&&input[3]==71;
            boolean jpeg=input.length>=3&&(input[0]&255)==255&&(input[1]&255)==216&&(input[2]&255)==255;
            if(!png&&!jpeg)throw new IOException();mime=png?"image/png":"image/jpeg";
            try(ImageInputStream image=ImageIO.createImageInputStream(new ByteArrayInputStream(input))){
                var readers=ImageIO.getImageReaders(image);if(!readers.hasNext())throw new IOException();ImageReader reader=readers.next();
                try{reader.setInput(image,true,true);width=reader.getWidth(0);height=reader.getHeight(0);if(width<1||height<1||width>10000||height>10000||(long)width*height>20000000L)throw new IOException();
                    BufferedImage decoded=reader.read(0);ByteArrayOutputStream out=new ByteArrayOutputStream();if(!ImageIO.write(decoded,png?"png":"jpeg",out))throw new IOException();sanitized=out.toByteArray();decoded.flush();
                }finally{reader.dispose();}
            }
        }catch(IOException|RuntimeException invalid){throw BusinessException.invalid("图片必须为可解码的JPEG/PNG，最长边不超过10000且总像素不超过2000万");}finally{decodeSlots.release();}
        if(sanitized.length>10*1024*1024)throw BusinessException.invalid("重新编码后图片超过10MiB");
        jdbc.update("INSERT IGNORE INTO elder_memory_revision(user_id,revision) VALUES (?,0)",user);jdbc.queryForObject("SELECT revision FROM elder_memory_revision WHERE user_id=? FOR UPDATE",Long.class,user);
        Long bytes=jdbc.queryForObject("SELECT COALESCE(SUM(size_bytes),0) FROM agent_attachment WHERE user_id=? AND state='READY' AND expires_at>?",Long.class,user,Timestamp.from(Instant.now()));if(bytes+sanitized.length>50L*1024*1024)throw BusinessException.conflict("当前有效图片总量超过50MiB，请先删除旧图片");
        String id=UUID.randomUUID().toString();Instant now=Instant.now(),expiry=now.plusSeconds(86400);jdbc.update("INSERT INTO agent_attachment VALUES (?,?,?,?,?,?,?,'READY',?,?,?)",id,user,purpose,mime,sanitized.length,width,height,sanitized,Timestamp.from(now),Timestamp.from(expiry));return new View(id,mime,sanitized.length,"READY",expiry,width,height,purpose);
    }
    public void validate(String user,List<String> ids){
        if(ids==null)return;if(ids.size()>4||new HashSet<>(ids).size()!=ids.size())throw BusinessException.invalid("每条消息最多4个不同附件");
        for(String id:ids){var rows=jdbc.queryForList("SELECT id FROM agent_attachment WHERE id=? AND user_id=? AND state='READY' AND expires_at>? FOR SHARE",id,user,Timestamp.from(Instant.now()));if(rows.size()!=1)throw BusinessException.notFound("附件不存在、已过期或不属于本人");}
    }
    public void bind(String task,String user,List<String> ids){validate(user,ids);if(ids!=null)for(String id:ids)jdbc.update("INSERT IGNORE INTO agent_task_attachment VALUES (?,?)",task,id);}
    public void message(String id,List<String> refs){if(refs!=null)for(String ref:refs)jdbc.update("INSERT INTO agent_message_attachment VALUES (?,?)",id,ref);}
    public List<String> messageRefs(String id){return jdbc.queryForList("SELECT b.attachment_id FROM agent_message_attachment b JOIN agent_attachment a ON a.id=b.attachment_id WHERE b.message_id=? AND a.state='READY' AND a.expires_at>?",String.class,id,Timestamp.from(Instant.now()));}
    @Transactional(readOnly=true)
    public Binary own(String user,String id){access.requireElderOwner(user);return binary(user,id);}
    @Transactional
    public Binary agent(String caller,String token,String task,String id){
        var t=invocations.require(caller,token,task);
        // Only A1 may process travel/fraud images in this batch; delegation of image access is not implicit.
        if(!"a1".equals(caller)||jdbc.queryForObject("SELECT COUNT(*) FROM agent_task_attachment WHERE task_id=? AND attachment_id=?",Integer.class,task,id)!=1)throw new AccessDeniedException("附件未授权给本任务");
        String request=jdbc.queryForObject("SELECT request_json FROM agent_invocation WHERE id=?",String.class,t.get("invocation_id"));boolean allowed=false;try{for(var ref:json.readTree(request).path("input").path("attachmentIds"))if(id.equals(ref.asText()))allowed=true;}catch(IOException e){throw new IllegalStateException(e);}if(!allowed)throw new AccessDeniedException("附件不在本轮调用范围");
        Binary data=binary(t.get("user_id").toString(),id);jdbc.update("INSERT IGNORE INTO agent_attachment_read VALUES (?,?,?)",t.get("invocation_id"),id,Timestamp.from(Instant.now()));return data;
    }
    private Binary binary(String user,String id){var rows=jdbc.queryForList("SELECT mime_type,content FROM agent_attachment WHERE id=? AND user_id=? AND state='READY' AND expires_at>?",id,user,Timestamp.from(Instant.now()));if(rows.isEmpty())throw BusinessException.notFound("附件不存在或已失效");var row=rows.getFirst();String mime=row.get("mime_type").toString();return new Binary((byte[])row.get("content"),mime,id+("image/png".equals(mime)?".png":".jpg"));}
    public boolean stale(String task){return jdbc.queryForObject("SELECT COUNT(*) FROM agent_task_attachment b JOIN agent_attachment a ON a.id=b.attachment_id WHERE b.task_id=? AND (a.state<>'READY' OR a.expires_at<=?)",Integer.class,task,Timestamp.from(Instant.now()))>0;}
    public void assertFresh(String task){for(var row:jdbc.queryForList("SELECT a.state,a.expires_at FROM agent_task_attachment b JOIN agent_attachment a ON a.id=b.attachment_id WHERE b.task_id=? FOR SHARE",task))if(!"READY".equals(row.get("state"))||!((Timestamp)row.get("expires_at")).toInstant().isAfter(Instant.now()))throw BusinessException.conflict("附件已删除或过期");}
    @Transactional
    public void delete(String user,String id){access.requireElderOwner(user);if(jdbc.update("UPDATE agent_attachment SET state='DELETED',content=NULL WHERE id=? AND user_id=?",id,user)!=1)throw BusinessException.notFound("附件不存在");}
    @Scheduled(fixedDelay=60000)
    @Transactional
    public void expire(){jdbc.update("UPDATE agent_attachment SET state='EXPIRED',content=NULL WHERE state='READY' AND expires_at<=?",Timestamp.from(Instant.now()));}
}
