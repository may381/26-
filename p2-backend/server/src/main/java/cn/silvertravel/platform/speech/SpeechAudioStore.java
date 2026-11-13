package cn.silvertravel.platform.speech;

import cn.silvertravel.platform.common.api.BusinessException;
import cn.silvertravel.platform.media.MediaSigner;
import cn.silvertravel.platform.trip.TravelRecordModels.BinaryMedia;
import java.sql.Timestamp;
import java.time.Duration;
import java.time.Instant;
import java.util.UUID;
import org.springframework.context.annotation.Profile;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Service;

@Service
@Profile("!bootstrap")
public class SpeechAudioStore {
    private final JdbcTemplate jdbc;
    private final MediaSigner signer;

    public SpeechAudioStore(JdbcTemplate jdbc, MediaSigner signer) {
        this.jdbc = jdbc;
        this.signer = signer;
    }

    public SpeechController.Synthesis save(String userId, byte[] bytes) {
        String id = UUID.randomUUID().toString();
        Instant expires = Instant.now().plus(Duration.ofHours(24));
        jdbc.update(
                "INSERT INTO speech_audio(id,user_id,content,expires_at) VALUES (?,?,?,?)",
                id,
                userId,
                bytes,
                Timestamp.from(expires));
        return signed(id, expires);
    }

    public SpeechController.Synthesis renew(String userId, String id) {
        var rows =
                jdbc.query(
                        """
                SELECT expires_at FROM speech_audio WHERE id=? AND user_id=? AND expires_at>?
                """,
                        (rs, n) -> rs.getTimestamp("expires_at").toInstant(),
                        id,
                        userId,
                        Timestamp.from(Instant.now()));
        if (rows.isEmpty()) throw BusinessException.notFound("合成音频不存在或已过期");
        return signed(id, rows.getFirst());
    }

    public BinaryMedia readSigned(String id) {
        var rows =
                jdbc.query(
                        "SELECT content FROM speech_audio WHERE id=? AND expires_at>?",
                        (rs, n) ->
                                new BinaryMedia(rs.getBytes("content"), "audio/wav", "speech.wav"),
                        id,
                        Timestamp.from(Instant.now()));
        if (rows.isEmpty()) throw BusinessException.notFound("合成音频不存在或已过期");
        return rows.getFirst();
    }

    @Scheduled(fixedDelay = 60_000)
    public void deleteExpired() {
        jdbc.update(
                "DELETE FROM speech_audio WHERE expires_at<=? ORDER BY expires_at LIMIT 100",
                Timestamp.from(Instant.now()));
    }

    private SpeechController.Synthesis signed(String id, Instant expires) {
        var link = signer.issue(MediaSigner.Kind.SPEECH, id, expires);
        return new SpeechController.Synthesis(id, "audio/wav", link.url(), link.expiresAt());
    }
}
