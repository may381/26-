"""Run against the local real model service; writes generated audio outside Git."""
import argparse
import json
from pathlib import Path
import requests

parser = argparse.ArgumentParser()
parser.add_argument("--data-root", required=True)
parser.add_argument("--url", default="http://127.0.0.1:18010")
args = parser.parse_args()
root = Path(args.data_root)
health = requests.get(args.url + "/health", timeout=10)
health.raise_for_status()
print("Health:", health.json())
audio = requests.post(args.url + "/syntheses", json={
    "text": "您好，前方有休息座椅，请注意休息。", "speechRate": 0.9,
}, timeout=120)
audio.raise_for_status()
assert audio.content[:4] == b"RIFF" and audio.content[8:12] == b"WAVE"
output = root / "smoke-generated.wav"
output.write_bytes(audio.content)
sample = root / "models/sherpa-onnx-sense-voice-zh-en-ja-ko-yue-int8-2024-07-17/test_wavs/zh.wav"
with sample.open("rb") as f:
    result = requests.post(args.url + "/transcriptions", files={"audio": ("zh.wav", f, "audio/wav")}, timeout=120)
result.raise_for_status()
assert result.json()["text"].strip()
print("ASR:", json.dumps(result.json(), ensure_ascii=False))
with output.open("rb") as f:
    loop = requests.post(args.url + "/transcriptions", files={"audio": ("generated.wav", f, "audio/wav")}, timeout=120)
loop.raise_for_status()
assert "休息" in loop.json()["text"], loop.json()
print("TTS to ASR:", json.dumps(loop.json(), ensure_ascii=False))
bad = requests.post(args.url + "/syntheses", json={"text": " ", "speechRate": 1.0}, timeout=10)
assert bad.status_code == 400
bad = requests.post(args.url + "/transcriptions", files={"audio": ("bad.wav", b"not audio", "audio/wav")}, timeout=10)
assert bad.status_code == 400
print("PASS: real ASR, real TTS, round-trip and invalid-input checks. Audio:", output)
