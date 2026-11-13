package cn.yinling.guide;

import jakarta.validation.Valid;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Size;
import jakarta.servlet.http.HttpSession;
import org.springframework.web.bind.annotation.*;

@RestController
public class AgentApi {
    private final GuideService service;
    public AgentApi(GuideService service) { this.service = service; }

    public record Context(@Size(max=100) String tripId, @Size(max=100) String location) {}
    public record Message(@NotBlank @Size(max=100) String userId,
                          @NotBlank @Size(max=2000) String text,
                          @Size(max=30) String intent, @Valid Context context) {}
    public record Envelope(String code, String message, Object data) {
        static Envelope ok(Object data) { return new Envelope("OK", "成功", data); }
    }

    @PostMapping("/api/agent/messages")
    public Envelope message(@Valid @RequestBody Message input, HttpSession session) {
        ConversationBook book;
        synchronized(session) {
            book=(ConversationBook)session.getAttribute("a1.conversations");
            if(book==null) { book=new ConversationBook(); session.setAttribute("a1.conversations",book); }
        }
        var turn=book.begin(input.userId(),input.context()==null?null:input.context().tripId());
        var answer=service.answer(input,turn.state());
        book.commit(turn);
        return Envelope.ok(answer);
    }
}
