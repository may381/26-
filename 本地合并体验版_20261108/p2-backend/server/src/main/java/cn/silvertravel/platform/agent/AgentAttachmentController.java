package cn.silvertravel.platform.agent;
import cn.silvertravel.platform.common.api.ApiResponse;
import java.nio.charset.StandardCharsets;
import org.springframework.context.annotation.Profile;
import org.springframework.http.*;
import org.springframework.security.core.Authentication;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.multipart.MultipartFile;
@RestController @Profile("!bootstrap")
public class AgentAttachmentController {
    private final AgentAttachmentService attachments;
    public AgentAttachmentController(AgentAttachmentService attachments){this.attachments=attachments;}
    @PostMapping(value="/api/v3/agent/attachments",consumes=MediaType.MULTIPART_FORM_DATA_VALUE)
    public ApiResponse<AgentAttachmentService.View> upload(@RequestParam String userId,@RequestParam String purpose,@RequestPart("file")MultipartFile file){return ApiResponse.ok(attachments.upload(userId,file,purpose));}
    @GetMapping("/api/v3/agent/attachments/{id}")
    public ResponseEntity<byte[]> own(@RequestParam String userId,@PathVariable String id){return response(attachments.own(userId,id));}
    @DeleteMapping("/api/v3/agent/attachments/{id}")
    public ApiResponse<Void> delete(@RequestParam String userId,@PathVariable String id){attachments.delete(userId,id);return ApiResponse.ok(null);}
    @GetMapping("/internal/agent/v3/attachments/{id}")
    public ResponseEntity<byte[]> agent(Authentication auth,@RequestHeader("X-Agent-Context")String token,@RequestParam String taskId,@PathVariable String id){return response(attachments.agent(((AgentServiceIdentity)auth.getPrincipal()).agentId(),token,taskId,id));}
    private ResponseEntity<byte[]> response(AgentAttachmentService.Binary b){return ResponseEntity.ok().contentType(MediaType.parseMediaType(b.mimeType())).cacheControl(CacheControl.noStore()).header("X-Content-Type-Options","nosniff").header(HttpHeaders.CONTENT_DISPOSITION,ContentDisposition.inline().filename(b.fileName(),StandardCharsets.UTF_8).build().toString()).body(b.bytes());}
}
