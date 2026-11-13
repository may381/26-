"""Local CPU speech service. Bind to loopback; P2 integration is a separate step."""
import io
import logging
import os
import threading
from contextlib import asynccontextmanager
from pathlib import Path

import av
import numpy as np
import sherpa_onnx
import soundfile as sf
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, Field

MODEL_ROOT = Path(os.environ["SPEECH_MODEL_DIR"])
ASR_DIR = MODEL_ROOT / "sherpa-onnx-sense-voice-zh-en-ja-ko-yue-int8-2024-07-17"
TTS_DIR = MODEL_ROOT / "kokoro-multi-lang-v1_1"
lock = threading.Lock()
recognizer = None
tts = None
load_error = None


@asynccontextmanager
async def lifespan(app):
    global recognizer, tts, load_error
    try:
        recognizer = sherpa_onnx.OfflineRecognizer.from_sense_voice(
            model=str(ASR_DIR / "model.int8.onnx"), tokens=str(ASR_DIR / "tokens.txt"),
            num_threads=2, provider="cpu", language="auto", use_itn=True,
        )
        config = sherpa_onnx.OfflineTtsConfig(
            model=sherpa_onnx.OfflineTtsModelConfig(
                kokoro=sherpa_onnx.OfflineTtsKokoroModelConfig(
                    model=str(TTS_DIR / "model.onnx"), voices=str(TTS_DIR / "voices.bin"),
                    tokens=str(TTS_DIR / "tokens.txt"), data_dir=str(TTS_DIR / "espeak-ng-data"),
                    dict_dir=str(TTS_DIR / "dict"),
                    lexicon=",".join(str(TTS_DIR / f) for f in ("lexicon-us-en.txt", "lexicon-zh.txt")),
                ), num_threads=2, provider="cpu",
            ), max_num_sentences=1,
            rule_fsts=",".join(str(TTS_DIR / f) for f in ("phone-zh.fst", "date-zh.fst", "number-zh.fst")),
        )
        if not config.validate():
            raise ValueError("Invalid TTS model configuration")
        tts = sherpa_onnx.OfflineTts(config)
    except Exception as exc:
        load_error = type(exc).__name__
        logging.exception("Speech models failed to load")
    yield


app = FastAPI(title="P2 local speech", lifespan=lifespan)


@app.get("/health")
def health():
    ready = recognizer is not None and tts is not None
    return JSONResponse(status_code=200 if ready else 503, content={
        "status": "UP" if ready else "NOT_READY", "asr": recognizer is not None,
        "tts": tts is not None, "loadError": load_error, "provider": "cpu",
    })


def acquire():
    if recognizer is None or tts is None:
        raise HTTPException(503, "Speech models are not ready")
    if not lock.acquire(blocking=False):
        raise HTTPException(429, "Speech worker busy; retry later")


@app.post("/transcriptions")
def transcribe(audio: UploadFile = File(...)):
    acquire()
    try:
        payload = audio.file.read(10 * 1024 * 1024 + 1)
        if not payload or len(payload) > 10 * 1024 * 1024:
            raise HTTPException(400, "Audio must be between 1 byte and 10 MiB")
        chunks = []
        count = 0
        try:
            with av.open(io.BytesIO(payload)) as container:
                resampler = av.AudioResampler(format="fltp", layout="mono", rate=16000)
                for frame in container.decode(audio=0):
                    for converted in resampler.resample(frame):
                        samples = converted.to_ndarray().reshape(-1)
                        count += samples.size
                        if count > 60 * 16000:
                            raise HTTPException(400, "Audio duration exceeds 60 seconds")
                        chunks.append(samples)
                for frame in resampler.resample(None):
                    samples = frame.to_ndarray().reshape(-1)
                    count += samples.size
                    chunks.append(samples)
        except HTTPException:
            raise
        except Exception:
            raise HTTPException(400, "Audio could not be decoded")
        if not chunks or count > 60 * 16000:
            raise HTTPException(400, "Audio is empty or too long")
        stream = recognizer.create_stream()
        stream.accept_waveform(16000, np.concatenate(chunks))
        recognizer.decode_stream(stream)
        text = stream.result.text.strip()
        if not text:
            raise HTTPException(422, "No speech recognized")
        return {"text": text}
    finally:
        lock.release()


class Synthesis(BaseModel):
    text: str = Field(min_length=1, max_length=2000)
    speechRate: float = Field(default=1.0, ge=0.5, le=1.5)


@app.post("/syntheses")
def synthesize(request: Synthesis):
    if not request.text.strip():
        raise HTTPException(400, "Text is blank")
    acquire()
    try:
        audio = tts.generate(request.text, sid=3, speed=request.speechRate)
        if len(audio.samples) == 0:
            raise HTTPException(502, "No audio generated")
        output = io.BytesIO()
        sf.write(output, audio.samples, audio.sample_rate, format="WAV", subtype="PCM_16")
        return Response(output.getvalue(), media_type="audio/wav", headers={"Cache-Control": "no-store"})
    finally:
        lock.release()
