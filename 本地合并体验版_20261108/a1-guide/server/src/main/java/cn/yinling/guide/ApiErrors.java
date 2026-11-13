package cn.yinling.guide;

import org.slf4j.LoggerFactory;
import org.springframework.http.ResponseEntity;
import org.springframework.http.converter.HttpMessageNotReadableException;
import org.springframework.web.bind.MethodArgumentNotValidException;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.servlet.resource.NoResourceFoundException;

@RestControllerAdvice
public class ApiErrors {
    @ExceptionHandler(org.springframework.web.server.ResponseStatusException.class)
    ResponseEntity<AgentApi.Envelope> status(org.springframework.web.server.ResponseStatusException ex) {
        String code=ex.getStatusCode().value()==409?"CONFLICT":ex.getStatusCode().value()==404?"NOT_FOUND":"INVALID_ARGUMENT";
        return ResponseEntity.status(ex.getStatusCode()).body(new AgentApi.Envelope(code,ex.getReason()==null?"请求未完成":ex.getReason(),null));
    }
    @ExceptionHandler(TravelDraftApi.CityMismatch.class)
    ResponseEntity<AgentApi.Envelope> cityMismatch(Exception ex) {
        return ResponseEntity.badRequest().body(new AgentApi.Envelope("INVALID_ARGUMENT",
            "选入地点的所属城市与目的地不一致。请核对城市，移除跨城地点或分别安排行程。",null));
    }
    @ExceptionHandler(OllamaClient.Unavailable.class)
    ResponseEntity<AgentApi.Envelope> upstream(OllamaClient.Unavailable ex) {
        return ResponseEntity.status(502).body(new AgentApi.Envelope("UPSTREAM_ERROR", ex.getMessage(), null));
    }
    @ExceptionHandler({IllegalArgumentException.class, MethodArgumentNotValidException.class,
        HttpMessageNotReadableException.class})
    ResponseEntity<AgentApi.Envelope> invalid(Exception ex,jakarta.servlet.http.HttpServletRequest request) {
        if(request.getRequestURI().startsWith("/api/a1/guide-imports"))
            return ResponseEntity.badRequest().body(new AgentApi.Envelope("INVALID_ARGUMENT",
                "请提供有效的小红书笔记链接、6000字以内的正文，或4MB以内的PNG/JPG截图。",null));
        if(request.getRequestURI().startsWith("/api/a1/travel-drafts"))
            return ResponseEntity.badRequest().body(new AgentApi.Envelope("INVALID_ARGUMENT",
                "出游参数不正确，请重新确认目的地、出发日期和1—4天的行程天数，再重试生成。",null));
        return ResponseEntity.badRequest().body(new AgentApi.Envelope("INVALID_ARGUMENT",
            "请检查 userId、text、intent 和 context；文字限 2000 字，位置使用景点 ID。", null));
    }
    @ExceptionHandler(NoResourceFoundException.class)
    ResponseEntity<AgentApi.Envelope> missing(Exception ex) {
        return ResponseEntity.status(404).body(new AgentApi.Envelope("NOT_FOUND", "接口或页面不存在", null));
    }
    @ExceptionHandler(Exception.class)
    ResponseEntity<AgentApi.Envelope> unexpected(Exception ex) {
        LoggerFactory.getLogger(ApiErrors.class).error("Request failed", ex);
        return ResponseEntity.internalServerError().body(new AgentApi.Envelope("INTERNAL_ERROR", "服务暂时不可用，请稍后再试", null));
    }
}
