package cn.silvertravel.platform.speech;

/**
 * Replace this boundary when the team selects a real speech provider. Never retain recordings here.
 */
public interface SpeechProvider {
    String transcribe(byte[] audio, String contentType);

    byte[] synthesize(String text, double speechRate);

    boolean simulated();
}
