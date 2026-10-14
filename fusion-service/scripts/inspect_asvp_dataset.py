"""
Inspect and validate the extracted ASVP-ESD dataset.
Parses the official Zenodo naming schema:
Modality-VocalChannel-Emotion-Intensity-Statement-Actor-Age-Source-Language-[Subtype]-[Sample].wav
"""

import os
import glob
import wave
import json
from collections import Counter

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "raw", "ASVP-ESD")
if not os.path.exists(DATA_DIR):
    # Check parent raw
    alt_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "fusion-service", "data", "raw", "ASVP-ESD")
    if os.path.exists(alt_dir):
        DATA_DIR = alt_dir

print(f"Scanning dataset in: {DATA_DIR}")

wav_files = glob.glob(os.path.join(DATA_DIR, "**", "*.wav"), recursive=True)
print(f"Total .wav files discovered: {len(wav_files)}")

EMOTION_MAP = {
    "01": "boredom",
    "02": "neutral",
    "03": "happy",
    "04": "sad",
    "05": "angry",
    "06": "fearful",
    "07": "disgust",
    "08": "surprised",
    "09": "excited",
    "10": "pleasure",
    "11": "pain",
    "12": "disappointment"
}

VOCAL_MAP = {
    "01": "speech",
    "02": "non_speech"
}

NON_SPEECH_SUBTYPE = {
    "16": "scream",
    "26": "breath",
    "36": "panic",
    "14": "cry",
    "24": "sigh",
    "34": "sniffle",
    "44": "suffering",
    "15": "rage",
    "25": "frustration",
    "13": "laugh",
    "23": "gaggle",
    "18": "surprised",
    "28": "amazed",
    "17": "disgust",
    "27": "rejection"
}

sample_rates = Counter()
channels = Counter()
durations = []
actors = Counter()
emotions = Counter()
vocal_channels = Counter()
subtypes = Counter()
languages = Counter()
streeva_distress = Counter()

corrupt_files = 0
parsed_samples = []

for idx, f in enumerate(wav_files):
    fname = os.path.basename(f)
    parts = fname.replace(".wav", "").split("-")
    
    # Check wav readability
    try:
        with wave.open(f, "rb") as w:
            sr = w.getframerate()
            ch = w.getnchannels()
            n_frames = w.getnframes()
            dur = n_frames / sr if sr > 0 else 0.0
            sample_rates[sr] += 1
            channels[ch] += 1
            durations.append(dur)
    except Exception as e:
        corrupt_files += 1
        continue

    # Parse metadata from filename
    # Minimum parts: modality, vocal, emotion, intensity, statement, actor
    if len(parts) >= 6:
        modality = parts[0]
        vocal = VOCAL_MAP.get(parts[1], parts[1])
        emotion = EMOTION_MAP.get(parts[2], parts[2])
        intensity = parts[3]
        actor = parts[5]
        
        vocal_channels[vocal] += 1
        emotions[emotion] += 1
        actors[actor] += 1
        
        # Check subtype if present
        subtype = "unknown"
        if len(parts) >= 10:
            subtype_code = parts[9].split()[0]
            subtype = NON_SPEECH_SUBTYPE.get(subtype_code, subtype_code)
            subtypes[subtype] += 1
            
        # Determine STREEVA target mapping:
        # Distress: fearful (scream, panic), pain, crying / suffering
        # Non-distress: neutral, happy, boredom, normal speech, surprised
        is_distress = False
        distress_reason = ""
        if emotion in ("fearful", "pain") or subtype in ("scream", "panic", "suffering", "cry"):
            is_distress = True
            distress_reason = f"{emotion}:{subtype}"
            streeva_distress["DISTRESS"] += 1
        else:
            is_distress = False
            distress_reason = f"{emotion}:{subtype}"
            streeva_distress["NON_DISTRESS"] += 1

        parsed_samples.append({
            "path": f,
            "filename": fname,
            "actor": actor,
            "vocal": vocal,
            "emotion": emotion,
            "subtype": subtype,
            "duration": dur,
            "sample_rate": sr,
            "is_distress": is_distress,
            "label": "DISTRESS" if is_distress else "NON_DISTRESS"
        })

print(f"\n--- DATASET INTEGRITY ---")
print(f"Readable files: {len(parsed_samples)}")
print(f"Corrupt files: {corrupt_files}")
print(f"Sample rates: {dict(sample_rates)}")
print(f"Channels: {dict(channels)}")
print(f"Durations (sec): min={min(durations):.2f}, max={max(durations):.2f}, mean={sum(durations)/len(durations):.2f}")

print(f"\n--- CLASS DISTRIBUTION ---")
print("Emotions:", dict(emotions))
print("Vocal Channels:", dict(vocal_channels))
print("Non-speech Subtypes:", dict(subtypes))
print("Total Unique Actors:", len(actors))

print(f"\n--- STREEVA BINARY MAPPING ---")
print(dict(streeva_distress))
print(f"Distress Ratio: {streeva_distress['DISTRESS'] / (len(parsed_samples) or 1) * 100:.1f}%")

# Save summary metadata
summary_path = os.path.join(os.path.dirname(DATA_DIR), "asvp_dataset_summary.json")
with open(summary_path, "w") as f:
    json.dump({
        "total_files": len(parsed_samples),
        "sample_rates": dict(sample_rates),
        "channels": dict(channels),
        "durations": {"min": min(durations), "max": max(durations), "mean": sum(durations)/len(durations)},
        "emotions": dict(emotions),
        "streeva_mapping": dict(streeva_distress),
        "unique_actors": len(actors)
    }, f, indent=2)
print(f"Summary saved to: {summary_path}")
