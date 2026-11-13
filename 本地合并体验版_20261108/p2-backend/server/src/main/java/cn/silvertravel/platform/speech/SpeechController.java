package cn.silvertravel.platform.speech;

import cn.silvertravel.platform.common.api.ApiResponse;
import cn.silvertravel.platform.common.api.BusinessException;
import cn.silvertravel.platform.security.BusinessAccessPolicy;
import io.swagger.v3.oas.annotations.Operation;
import jakarta.validation.Valid;
import jakarta.validation.constraints.*;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.time.Instant;
import java.util.Locale;
import java.util.UUID;
import org.springframework.beans.factory.ObjectProvider;
import org.springframework.http.MediaType;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.multipart.MultipartFile;

@RestController
@RequestMapping("/api/v3/speech")
public class SpeechController {
    private final SpeechProvider provider;
    private final BusinessAccessPolicy access;
    private final ObjectProvider<SpeechAudioStore> audioStore;

    public SpeechController(
            SpeechProvider provider,
            BusinessAccessPolicy access,
            ObjectProvider<SpeechAudioStore> audioStore) {
        this.provider = provider;
        this.access = access;
        this.audioStore = audioStore;
    }

    public record Transcription(String text) {}

    public record Synthesis(String id, String mimeType, String audioUrl, Instant expiresAt) {}

    public record SynthesisRequest(
            @NotBlank @Size(max = 2000) String text,
            @NotNull @DecimalMin("0.5") @DecimalMax("1.5") Double speechRate) {}

    @PostMapping(value = "/transcriptions", consumes = MediaType.MULTIPART_FORM_DATA_VALUE)
    @Operation(summary = "语音转文字；HTTP 模式调用真实识别，mock 返回演示文本")
    public ApiResponse<Transcription> transcribe(
            @RequestPart("audio") MultipartFile audio,
            @RequestParam(required = false) String userId)
            throws IOException {
        requireOwner(userId);
        if (audio.isEmpty() || audio.getSize() > 10 * 1024 * 1024)
            throw BusinessException.invalid("音频需为 1 字节至 10MiB");
        byte[] bytes;
        try (var input = audio.getInputStream()) {
            bytes = input.readNBytes(10 * 1024 * 1024 + 1);
        }
        if (bytes.length == 0
                || bytes.length > 10 * 1024 * 1024
                || !supported(bytes, audio.getContentType()))
            throw BusinessException.invalid("音频类型或文件头不支持，请使用 WAV、MP3、WebM、OGG 或 MP4");
        return new ApiResponse<>(
                "OK",
                message(),
                new Transcription(provider.transcribe(bytes, audio.getContentType())));
    }

    @PostMapping("/syntheses")
    @Operation(summary = "文字转语音；HTTP 模式返回短效签名地址，mock 返回空地址")
    public ApiResponse<Synthesis> synthesize(
            @Valid @RequestBody SynthesisRequest request,
            @RequestParam(required = false) String userId) {
        String owner = requireOwner(userId);
        byte[] audio = provider.synthesize(request.text(), request.speechRate());
        return new ApiResponse<>(
                "OK",
                message(),
                audio == null ? new Synthesis(null, null, null, null) : store().save(owner, audio));
    }

    @GetMapping("/syntheses/{audioId}")
    public ApiResponse<Synthesis> renew(
            @PathVariable UUID audioId, @RequestParam(required = false) String userId) {
        String owner = requireOwner(userId);
        return ApiResponse.ok(store().renew(owner, audioId.toString()));
    }

    private SpeechAudioStore store() {
        SpeechAudioStore store = audioStore.getIfAvailable();
        if (store == null) throw BusinessException.notFound("合成音频存储不可用");
        return store;
    }

    private String requireOwner(String userId) {
        String owner = userId == null ? access.currentActor().elderUserId() : userId;
        access.requireElderOwner(owner);
        return owner;
    }

    private String message() {
        return provider.simulated() ? "语音演示占位：未识别或生成真实音频" : "成功";
    }

    static boolean supported(byte[] b, String contentType) {
        if (b.length < 12 || contentType == null) return false;
        String mime = contentType.split(";", 2)[0].strip().toLowerCase(Locale.ROOT);
        return switch (mime) {
            case "audio/wav", "audio/x-wav", "audio/wave" ->
                    ascii(b, 0, "RIFF") && ascii(b, 8, "WAVE");
            case "audio/mpeg", "audio/mp3" ->
                    ascii(b, 0, "ID3") || ((b[0] & 255) == 255 && (b[1] & 224) == 224);
            case "audio/webm" ->
                    (b[0] & 255) == 0x1a
                            && (b[1] & 255) == 0x45
                            && (b[2] & 255) == 0xdf
                            && (b[3] & 255) == 0xa3;
            case "audio/ogg", "application/ogg" -> ascii(b, 0, "OggS");
            case "audio/mp4", "audio/x-m4a" -> ascii(b, 4, "ftyp");
            default -> false;
        };
    }

    private static boolean ascii(byte[] b, int start, String expected) {
        return new String(b, start, expected.length(), StandardCharsets.US_ASCII).equals(expected);
    }
}
