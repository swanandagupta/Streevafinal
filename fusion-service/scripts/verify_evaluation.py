"""
STREEVA — Phase 1D Evaluation Metric Verification Script.

Inspects and evaluates the EXACT final unseen-speaker test set using:
1. The exact same deterministic speaker split (random.seed(42), 8 held-out test actors).
2. The final saved TFLite model: 'fusion-service/models/audio_distress.tflite'.
3. Validates TN, FP, FN, TP, Accuracy, Precision, Recall, F1, ROC-AUC, FPR.
4. Checks mathematical consistency: TN + FP + FN + TP == len(test_samples).
"""

import os
import sys
import glob
import wave
import json
import random
import numpy as np

# Ensure app package is reachable
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.edge.audio_preprocessor import extract_log_mel_spectrogram

try:
    import tensorflow as tf
    tflite = tf.lite
except ImportError:
    import tflite_runtime.interpreter as tflite

from sklearn.metrics import (
    accuracy_score, precision_score, recall_score,
    f1_score, roc_auc_score, confusion_matrix
)

# 1. Reproduce identical dataset split
random.seed(42)
np.random.seed(42)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data", "raw", "ASVP-ESD")
TFLITE_PATH = os.path.join(BASE_DIR, "models", "audio_distress.tflite")

wav_files = glob.glob(os.path.join(DATA_DIR, "**", "*.wav"), recursive=True)
print(f"Total audio files found: {len(wav_files)}")

EMOTION_DISTRESS_CODES = {"06", "11"}
NON_SPEECH_DISTRESS_SUBTYPES = {"16", "36", "14", "44"}

actor_files = {}
all_samples = []

for f in wav_files:
    fname = os.path.basename(f)
    parts = fname.replace(".wav", "").split("-")
    if len(parts) >= 6:
        emotion_code = parts[2]
        actor = parts[5]
        subtype_code = parts[9].split()[0] if len(parts) >= 10 else ""

        is_distress = (
            emotion_code in EMOTION_DISTRESS_CODES or
            subtype_code in NON_SPEECH_DISTRESS_SUBTYPES
        )

        sample = {
            "path": f,
            "filename": fname,
            "actor": actor,
            "is_distress": int(is_distress),
            "subtype": subtype_code,
            "emotion": emotion_code
        }
        all_samples.append(sample)
        actor_files.setdefault(actor, []).append(sample)

unique_actors = sorted(list(actor_files.keys()))
random.shuffle(unique_actors)
n_actors = len(unique_actors)
n_train = int(n_actors * 0.70)
n_val = int(n_actors * 0.15)

train_actors = set(unique_actors[:n_train])
val_actors = set(unique_actors[n_train:n_train + n_val])
test_actors = set(unique_actors[n_train + n_val:])

test_samples = [s for s in all_samples if s["actor"] in test_actors]
total_distress = sum(s["is_distress"] for s in test_samples)
total_non_distress = len(test_samples) - total_distress

print(f"\nHeld-out Test Set Statistics (Zero Speaker Leakage):")
print(f"  Test Actors ({len(test_actors)}): {sorted(list(test_actors))}")
print(f"  Total Test Samples: {len(test_samples)}")
print(f"  - Distress Samples:     {total_distress} ({total_distress/len(test_samples)*100:.2f}%)")
print(f"  - Non-Distress Samples: {total_non_distress} ({total_non_distress/len(test_samples)*100:.2f}%)")

# 2. Extract features for test set
print(f"\nExtracting Log-Mel Spectrogram features for {len(test_samples)} test samples...")
X_test = []
y_test = []

for s in test_samples:
    path = s["path"]
    try:
        with wave.open(path, "rb") as w:
            sr = w.getframerate()
            n_frames = w.getnframes()
            data = w.readframes(n_frames)
            audio = np.frombuffer(data, dtype=np.int16).astype(np.float32) / 32768.0

        if sr != 16000:
            audio = np.interp(
                np.linspace(0, len(audio), int(len(audio) * 16000 / sr)),
                np.arange(len(audio)),
                audio
            )
        target_samples = 16000
        if len(audio) > target_samples:
            if s["is_distress"]:
                energy = audio ** 2
                best_idx = 0
                max_e = -1
                for offset in range(0, len(audio) - target_samples, 2000):
                    e = np.sum(energy[offset:offset + target_samples])
                    if e > max_e:
                        max_e = e
                        best_idx = offset
                audio = audio[best_idx:best_idx + target_samples]
            else:
                audio = audio[:target_samples]
        elif len(audio) < target_samples:
            audio = np.pad(audio, (0, target_samples - len(audio)), mode='constant')

        spec = extract_log_mel_spectrogram(audio)
        X_test.append(spec)
        y_test.append(s["is_distress"])
    except Exception as e:
        print(f"Error processing {path}: {e}")

X_test = np.array(X_test, dtype=np.float32)
y_test = np.array(y_test, dtype=int)
print(f"Feature extraction complete. Matrix shape: {X_test.shape}, labels: {len(y_test)}")

# 3. Load TFLite Model and run inference
interpreter = tflite.Interpreter(model_path=TFLITE_PATH)
interpreter.allocate_tensors()
input_details = interpreter.get_input_details()
output_details = interpreter.get_output_details()

print(f"\nRunning TFLite model inference on {len(X_test)} samples...")
y_pred_probs = []
for i in range(len(X_test)):
    sample_in = np.expand_dims(X_test[i], axis=0)
    interpreter.set_tensor(input_details[0]['index'], sample_in)
    interpreter.invoke()
    out = interpreter.get_tensor(output_details[0]['index'])
    y_pred_probs.append(float(out[0][0]))

y_pred_probs = np.array(y_pred_probs, dtype=np.float32)
roc_auc = float(roc_auc_score(y_test, y_pred_probs))

print(f"\nModel ROC-AUC on Held-Out Test Set: {roc_auc * 100:.2f}%")

# 4. Evaluate at documented classification thresholds
thresholds = [0.35, 0.40, 0.50, 0.60]

print("\n" + "=" * 85)
print(f"{'Threshold':<10} | {'TN':<5} {'FP':<5} {'FN':<5} {'TP':<5} | {'Acc (%)':<8} {'Prec (%)':<9} {'Rec (%)':<8} {'F1 (%)':<8} {'FPR (%)':<8}")
print("=" * 85)

for thresh in thresholds:
    y_pred = (y_pred_probs >= thresh).astype(int)
    cm = confusion_matrix(y_test, y_pred)
    tn, fp, fn, tp = cm.ravel()
    
    acc = (tp + tn) / len(y_test)
    prec = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    rec = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = 2 * (prec * rec) / (prec + rec) if (prec + rec) > 0 else 0.0
    fpr = fp / (fp + tn) if (fp + tn) > 0 else 0.0
    
    # Assert mathematical consistency
    assert tn + fp + fn + tp == len(y_test), f"Sum mismatch: {tn+fp+fn+tp} != {len(y_test)}"
    assert abs(acc - accuracy_score(y_test, y_pred)) < 1e-6
    assert abs(prec - precision_score(y_test, y_pred, zero_division=0)) < 1e-6
    assert abs(rec - recall_score(y_test, y_pred, zero_division=0)) < 1e-6
    assert abs(f1 - f1_score(y_test, y_pred, zero_division=0)) < 1e-6
    
    print(f"{thresh:<10.2f} | {tn:<5} {fp:<5} {fn:<5} {tp:<5} | {acc*100:<8.2f} {prec*100:<9.2f} {rec*100:<8.2f} {f1*100:<8.2f} {fpr*100:<8.2f}")

print("=" * 85)

# Save exact verified evaluation at the canonical 0.50 threshold
y_pred_50 = (y_pred_probs >= 0.50).astype(int)
cm_50 = confusion_matrix(y_test, y_pred_50)
tn_50, fp_50, fn_50, tp_50 = cm_50.ravel()

verified_metrics = {
    "classification_threshold": 0.50,
    "test_samples": int(len(y_test)),
    "test_distress_samples": int(total_distress),
    "test_non_distress_samples": int(total_non_distress),
    "confusion_matrix": {
        "true_negative": int(tn_50),
        "false_positive": int(fp_50),
        "false_negative": int(fn_50),
        "true_positive": int(tp_50)
    },
    "sum_check": int(tn_50 + fp_50 + fn_50 + tp_50),
    "accuracy": float(accuracy_score(y_test, y_pred_50)),
    "precision": float(precision_score(y_test, y_pred_50, zero_division=0)),
    "recall": float(recall_score(y_test, y_pred_50, zero_division=0)),
    "f1_score": float(f1_score(y_test, y_pred_50, zero_division=0)),
    "roc_auc": roc_auc,
    "false_positive_rate": float(fp_50 / (fp_50 + tn_50)),
    "false_negative_rate": float(fn_50 / (fn_50 + tp_50))
}

verified_path = os.path.join(BASE_DIR, "data", "processed", "audio_distress", "verified_test_metrics.json")
with open(verified_path, "w") as f:
    json.dump(verified_metrics, f, indent=2)

print(f"\nSaved verified metrics to: {verified_path}")
