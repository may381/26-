package cn.silvertravel.platform.media;

import cn.silvertravel.platform.common.api.BusinessException;
import cn.silvertravel.platform.speech.SpeechAudioStore;
import cn.silvertravel.platform.trip.TravelRecordModels.BinaryMedia;
import io.swagger.v3.oas.annotations.security.SecurityRequirements;
import java.util.UUID;
import org.springframework.context.annotation.Profile;
import org.springframework.core.io.ByteArrayResource;
import org.springframework.http.ResponseEntity;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.security.access.AccessDeniedException;
import org.springframework.web.bind.annotation.*;

@RestController
@Profile("!bootstrap")
public class SignedMediaController {
    private final MediaSigner signer;
    private final SpeechAudioStore audio;
    private final JdbcTemplate jdbc;

    public SignedMediaController(MediaSigner signer, SpeechAudioStore audio, JdbcTemplate jdbc) {
        this.signer = signer;
        this.audio = audio;
        this.jdbc = jdbc;
    }

    @GetMapping("/api/v3/media/signed/{id}")
    @SecurityRequirements
    public ResponseEntity<ByteArrayResource> read(
            @PathVariable UUID id,
            @RequestParam MediaSigner.Kind kind,
            @RequestParam long exp,
            @RequestParam String sig) {
        String mediaId = id.toString();
        if (!signer.valid(kind, mediaId, exp, sig)) {
            throw new AccessDeniedException("媒体链接无效或已过期");
        }
        if (kind == MediaSigner.Kind.SPEECH) {
            return BinaryMediaResponse.of(audio.readSigned(mediaId));
        }
        var rows =
                jdbc.query(
                        """
                SELECT m.content,m.mime_type,m.file_name FROM trip_media m
                JOIN trip t ON t.id=m.trip_id AND t.user_id=m.user_id
                WHERE m.id=? AND t.status<>'CANCELLED'
                """,
                        (rs, n) ->
                                new BinaryMedia(
                                        rs.getBytes("content"),
                                        rs.getString("mime_type"),
                                        rs.getString("file_name")),
                        mediaId);
        if (rows.isEmpty()) throw BusinessException.notFound("游览附件不存在");
        return BinaryMediaResponse.of(rows.getFirst());
    }
}
