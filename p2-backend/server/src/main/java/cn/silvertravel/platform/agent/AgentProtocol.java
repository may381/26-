package cn.silvertravel.platform.agent;

import com.fasterxml.jackson.annotation.JsonIgnore;
import com.fasterxml.jackson.annotation.JsonIgnoreProperties;
import com.fasterxml.jackson.databind.JsonNode;
import io.swagger.v3.oas.annotations.media.Schema;
import jakarta.validation.Valid;
import jakarta.validation.constraints.*;
import java.util.List;

public final class AgentProtocol {
    private AgentProtocol() {}

    public enum Intent {
        tourism,
        health,
        fraud,
        care,
        culture,
        community,
        volunteer,
        ability,
        help
    }

    public enum HandoffTarget {
        family,
        scenic,
        official
    }

    public record Context(
            @Size(min = 1, max = 36) String tripId, @Size(min = 1, max = 128) String location) {}

    public record Input(@NotBlank @Size(max = 2000) String text) {}

    public record Message(
            @Schema(
                            requiredMode = Schema.RequiredMode.REQUIRED,
                            allowableValues = {"3.0"},
                            example = "3.0")
                    String protocolVersion,
            @NotBlank @Size(max = 128) String userId,
            @NotNull @Valid Input input,
            Intent intent,
            @Valid Context context) {
        public Message(String userId, String text, Intent intent, Context context) {
            this("3.0", userId, new Input(text), intent, context);
        }

        public String text() {
            return input == null ? null : input.text();
        }
    }

    public record ToolInput(@NotBlank @Size(max = 64) String tool, @NotNull JsonNode args) {}

    public record ToolRequest(
            @Schema(
                            requiredMode = Schema.RequiredMode.REQUIRED,
                            allowableValues = {"3.0"},
                            example = "3.0")
                    String protocolVersion,
            @NotNull @Valid ToolInput input) {
        public ToolRequest(String tool, JsonNode args) {
            this("3.0", new ToolInput(tool, args));
        }

        public String tool() {
            return input == null ? null : input.tool();
        }

        public JsonNode args() {
            return input == null ? null : input.args();
        }
    }

    @JsonIgnoreProperties(ignoreUnknown = true)
    public record ToolCall(String tool, JsonNode args, JsonNode result) {}

    @JsonIgnoreProperties(ignoreUnknown = true)
    public record Handoff(
            @Pattern(regexp = "human_handoff") @NotNull String type,
            @NotNull HandoffTarget to,
            @NotBlank @Size(max = 500) String reason) {}

    @JsonIgnoreProperties(ignoreUnknown = true)
    public record ReplyContent(
            @NotBlank @Size(max = 4000) String text,
            @NotNull @DecimalMin("0.5") @DecimalMax("1.5") Double speechRate,
            String audioUrl) {}

    @JsonIgnoreProperties(ignoreUnknown = true)
    public record Reply(
            @NotNull Intent intent,
            @NotNull @Valid ReplyContent reply,
            @NotNull @Size(max = 10) List<ToolCall> tools,
            @Valid Handoff handoff) {
        public Reply(
                Intent intent,
                String text,
                Double rate,
                String audio,
                List<ToolCall> tools,
                Handoff handoff) {
            this(intent, new ReplyContent(text, rate, audio), tools, handoff);
        }

        public String text() {
            return reply == null ? null : reply.text();
        }

        public Double speechRate() {
            return reply == null ? null : reply.speechRate();
        }

        public String audioUrl() {
            return reply == null ? null : reply.audioUrl();
        }
    }

    public record WireMessage(
            String protocolVersion,
            String userId,
            Input input,
            Intent intent,
            Context context,
            String toolContextToken,
            @JsonIgnore String traceId) {
        public WireMessage(
                String userId,
                String text,
                Intent intent,
                Context context,
                String token,
                String traceId) {
            this("3.0", userId, new Input(text), intent, context, token, traceId);
        }

        public String text() {
            return input == null ? null : input.text();
        }

        @Override
        public String toString() {
            return "WireMessage[redacted]";
        }
    }
}
