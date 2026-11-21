"""
Optional audio module: voice stress features from an earnings call recording you supply.

    python audio_features.py path/to/call.mp3

Whisper turns the audio into text (which can then be scored by stress.py's lexicon and FinBERT),
and librosa measures voice signals often linked with stress:
  * pitch variability (std of fundamental frequency, Hz)
  * speaking rate (words per second, from the Whisper transcript)
  * pause share (share of time that is silence)
  * loudness variability (std of RMS energy)
Not run in GitHub Actions: no free, licence-clean set of earnings call recordings is available.
"""
import json
import sys
from pathlib import Path

import numpy as np


def voice_features(path, whisper_model="base"):
    import librosa
    import whisper

    y, sr = librosa.load(path, sr=16000, mono=True)
    duration = len(y) / sr
    f0, voiced, _ = librosa.pyin(y, fmin=65, fmax=400, sr=sr, frame_length=2048)
    f0 = f0[voiced & ~np.isnan(f0)]
    speech = librosa.effects.split(y, top_db=30)
    speech_time = sum(e - s for s, e in speech) / sr
    rms = librosa.feature.rms(y=y)[0]

    text = whisper.load_model(whisper_model).transcribe(str(path))["text"]
    words = len(text.split())
    return {
        "file": Path(path).name, "duration_sec": round(duration, 1),
        "pitch_mean_hz": round(float(np.mean(f0)), 1) if len(f0) else None,
        "pitch_std_hz": round(float(np.std(f0)), 1) if len(f0) else None,
        "words_per_sec": round(words / max(speech_time, 1), 2),
        "pause_share_%": round(100 * (1 - speech_time / duration), 1),
        "loudness_std": round(float(np.std(rms)), 4),
        "transcript": text,
    }


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit("usage: python audio_features.py call.mp3")
    feats = voice_features(sys.argv[1])
    out = Path(__file__).parent / "outputs" / (Path(sys.argv[1]).stem + "_voice.json")
    out.write_text(json.dumps(feats, indent=2))
    print(json.dumps({k: v for k, v in feats.items() if k != "transcript"}, indent=2))
