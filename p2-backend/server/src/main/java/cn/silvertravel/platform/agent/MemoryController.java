package cn.silvertravel.platform.agent;
import cn.silvertravel.platform.common.api.ApiResponse;
import com.fasterxml.jackson.databind.JsonNode;
import java.util.List;
import org.springframework.context.annotation.Profile;
import org.springframework.web.bind.annotation.*;
@RestController @Profile("!bootstrap")
public class MemoryController {
    private final AgentMemoryService memory;
    public MemoryController(AgentMemoryService memory){this.memory=memory;}
    @GetMapping("/api/v3/memories")
    public ApiResponse<List<JsonNode>> list(@RequestParam String userId){return ApiResponse.ok(memory.list(userId));}
    @DeleteMapping("/api/v3/memories/{id}")
    public ApiResponse<Void> delete(@RequestParam String userId,@PathVariable String id,@RequestParam int expectedVersion){memory.delete(userId,id,expectedVersion);return ApiResponse.ok(null);}
}
