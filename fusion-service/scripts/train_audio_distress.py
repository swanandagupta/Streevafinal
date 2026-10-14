"""
STREEVA — Phase 1D Distress Audio Classifier Training & TFLite Export.

- Stratified speaker split (Zero speaker leakage between Train, Val, Test).
- Standardized Log-Mel Spectrogram inputs (61, 64, 1).
- Compact 2D-CNN optimized for edge inference.
- Evaluates Accuracy, Precision, Recall, F1, ROC-AUC, and Confusion Matrix.
- Exports 'models/audio_distress.tflite'.
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

import tensorflow as tf
from tensorflow.keras import layers, models, regularizers, callbacks
from sklearn.metrics import (
    accuracy_score, precision_score, recall_score,
    f1_score, roc_auc_score, confusion_matrix
)

# Set seeds for reproducibility
np.random.seed(42)
tf.random.set_seed(42)
random.seed(42)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data", "raw", "ASVP-ESD")
OUTPUT_DIR = os.path.join(BASE_DIR, "data", "processed", "audio_distress")
MODELS_DIR = os.path.join(BASE_DIR, "models")
os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(MODELS_DIR, exist_ok=True)
os.makedirs(os.path.join(OUTPUT_DIR, "demo_samples"), exist_ok=True)

print("=" * 80)
print(" STREEVA PHASE 1D: DISTRESS AUDIO MODEL TRAINING PIPELINE")
print("=" * 80)

# 1. Discover all audio files
wav_files = glob.glob(os.path.join(DATA_DIR, "**", "*.wav"), recursive=True)
print(f"Total .wav files: {len(wav_files)}")

EMOTION_DISTRESS_CODES = {"06", "11"}  # 06: fearful, 11: pain
NON_SPEECH_DISTRESS_SUBTYPES = {"16", "36", "14", "44"}  # 16: scream, 36: panic, 14: cry, 44: suffering

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
print(f"Unique actors found: {len(unique_actors)}")

# 2. Speaker-stratified splitting (Zero speaker leakage)
random.shuffle(unique_actors)
n_actors = len(unique_actors)
n_train = int(n_actors * 0.70)
n_val = int(n_actors * 0.15)

train_actors = set(unique_actors[:n_train])
val_actors = set(unique_actors[n_train:n_train + n_val])
test_actors = set(unique_actors[n_train + n_val:])

train_samples = [s for s in all_samples if s["actor"] in train_actors]
val_samples = [s for s in all_samples if s["actor"] in val_actors]
test_samples = [s for s in all_samples if s["actor"] in test_actors]

print(f"\nSplit organization (by Speaker ID):")
print(f"  Train: {len(train_actors)} actors, {len(train_samples)} samples (Distress: {sum(s['is_distress'] for s in train_samples)})")
print(f"  Val:   {len(val_actors)} actors, {len(val_samples)} samples (Distress: {sum(s['is_distress'] for s in val_samples)})")
print(f"  Test:  {len(test_actors)} actors, {len(test_samples)} samples (Distress: {sum(s['is_distress'] for s in test_samples)})")

# Save a few canonical test samples for deterministic demos
import shutil
demo_samples_meta = []
scream_saved = False
neutral_saved = False
laugh_saved = False

for s in test_samples:
    dst = os.path.join(OUTPUT_DIR, "demo_samples", s["filename"])
    if s["is_distress"] and "16" in s["subtype"] and not scream_saved:
        shutil.copyfile(s["path"], dst)
        demo_samples_meta.append({"type": "scream", "label": "DISTRESS", "path": dst})
        scream_saved = True
    elif not s["is_distress"] and s["emotion"] == "02" and not neutral_saved:
        shutil.copyfile(s["path"], dst)
        demo_samples_meta.append({"type": "neutral_speech", "label": "NON_DISTRESS", "path": dst})
        neutral_saved = True
    elif not s["is_distress"] and "13" in s["subtype"] and not laugh_saved:
        shutil.copyfile(s["path"], dst)
        demo_samples_meta.append({"type": "laughter", "label": "NON_DISTRESS", "path": dst})
        laugh_saved = True

with open(os.path.join(OUTPUT_DIR, "demo_samples", "demo_manifest.json"), "w") as f:
    json.dump(demo_samples_meta, f, indent=2)


# 3. Audio Loading and Feature Extraction Helper
def load_and_preprocess(sample_meta):
    path = sample_meta["path"]
    try:
        with wave.open(path, "rb") as w:
            sr = w.getframerate()
            n_frames = w.getnframes()
            data = w.readframes(n_frames)
            audio = np.frombuffer(data, dtype=np.int16).astype(np.float32) / 32768.0

        # Resample if not 16k (all ASVP are 16k)
        if sr != 16000:
            audio = np.interp(
                np.linspace(0, len(audio), int(len(audio) * 16000 / sr)),
                np.arange(len(audio)),
                audio
            )
        # Take 1.0 second slice from center or start
        target_samples = 16000
        if len(audio) > target_samples:
            # If distress, take high-energy slice
            if sample_meta["is_distress"]:
                # Find max energy frame
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
        return spec, sample_meta["is_distress"]
    except Exception as e:
        return None, None


print("\nExtracting features for training set...")
X_train, y_train = [], []
for s in train_samples:
    spec, lbl = load_and_preprocess(s)
    if spec is not None:
        X_train.append(spec)
        y_train.append(lbl)

print("Extracting features for validation set...")
X_val, y_val = [], []
for s in val_samples:
    spec, lbl = load_and_preprocess(s)
    if spec is not None:
        X_val.append(spec)
        y_val.append(lbl)

print("Extracting features for test set...")
X_test, y_test = [], []
for s in test_samples:
    spec, lbl = load_and_preprocess(s)
    if spec is not None:
        X_test.append(spec)
        y_test.append(lbl)

X_train = np.array(X_train, dtype=np.float32)
y_train = np.array(y_train, dtype=np.float32)
X_val = np.array(X_val, dtype=np.float32)
y_val = np.array(y_val, dtype=np.float32)
X_test = np.array(X_test, dtype=np.float32)
y_test = np.array(y_test, dtype=np.float32)

print(f"\nFeature matrix shapes:")
print(f"  X_train: {X_train.shape}, y_train: {y_train.shape}")
print(f"  X_val:   {X_val.shape}, y_val:   {y_val.shape}")
print(f"  X_test:  {X_test.shape}, y_test:  {y_test.shape}")

# Calculate Class Weights
n_neg = np.sum(y_train == 0)
n_pos = np.sum(y_train == 1)
total = len(y_train)
weight_0 = total / (2.0 * n_neg) if n_neg > 0 else 1.0
weight_1 = total / (2.0 * n_pos) if n_pos > 0 else 1.0
class_weight = {0: weight_0, 1: weight_1}
print(f"Computed Class Weights: Non-Distress (0)={weight_0:.2f}, Distress (1)={weight_1:.2f}")


# 4. Build Lightweight CNN Model
def build_edge_cnn_model(input_shape=(61, 64, 1)):
    model = models.Sequential([
        layers.Input(shape=input_shape),
        
        layers.Conv2D(16, (3, 3), padding='same', activation='relu'),
        layers.BatchNormalization(),
        layers.MaxPooling2D((2, 2)),
        
        layers.Conv2D(32, (3, 3), padding='same', activation='relu'),
        layers.BatchNormalization(),
        layers.MaxPooling2D((2, 2)),
        
        layers.Conv2D(64, (3, 3), padding='same', activation='relu'),
        layers.BatchNormalization(),
        layers.GlobalAveragePooling2D(),
        
        layers.Dense(32, activation='relu', kernel_regularizer=regularizers.l2(1e-4)),
        layers.Dropout(0.35),
        layers.Dense(1, activation='sigmoid')
    ])
    
    model.compile(
        optimizer=tf.keras.optimizers.Adam(learning_rate=1e-3),
        loss='binary_crossentropy',
        metrics=[
            'accuracy',
            tf.keras.metrics.Precision(name='precision'),
            tf.keras.metrics.Recall(name='recall'),
            tf.keras.metrics.AUC(name='auc')
        ]
    )
    return model


model = build_edge_cnn_model()
model.summary()

# 5. Train Model
early_stop = callbacks.EarlyStopping(
    monitor='val_loss',
    patience=5,
    restore_best_weights=True,
    verbose=1
)
reduce_lr = callbacks.ReduceLROnPlateau(
    monitor='val_loss',
    factor=0.5,
    patience=2,
    verbose=1
)

print("\nStarting model training...")
history = model.fit(
    X_train, y_train,
    validation_data=(X_val, y_val),
    epochs=15,
    batch_size=32,
    class_weight=class_weight,
    callbacks=[early_stop, reduce_lr],
    verbose=2
)

# 6. Evaluate on Held-Out Test Set (Zero Speaker Leakage)
print("\n" + "=" * 80)
print(" EVALUATION ON UNSEEN TEST SPEAKERS")
print("=" * 80)

y_pred_prob = model.predict(X_test, verbose=0).flatten()
y_pred_binary = (y_pred_prob >= 0.5).astype(int)

acc = accuracy_score(y_test, y_pred_binary)
prec = precision_score(y_test, y_pred_binary, zero_division=0)
rec = recall_score(y_test, y_pred_binary, zero_division=0)
f1 = f1_score(y_test, y_pred_binary, zero_division=0)
auc = roc_auc_score(y_test, y_pred_prob)
cm = confusion_matrix(y_test, y_pred_binary)
tn, fp, fn, tp = cm.ravel()

print(f"Test Accuracy:  {acc * 100:.2f}%")
print(f"Test Precision: {prec * 100:.2f}%")
print(f"Test Recall:    {rec * 100:.2f}%")
print(f"Test F1 Score:  {f1 * 100:.2f}%")
print(f"Test ROC-AUC:   {auc * 100:.2f}%")
print("\nConfusion Matrix:")
print(f"  True Negative  (Normal speech/audio correctly classified):   {tn}")
print(f"  False Positive (Normal audio misclassified as distress):     {fp} (FPR: {fp/(fp+tn)*100:.2f}%)")
print(f"  False Negative (Distress audio missed):                      {fn} (FNR: {fn/(fn+tp)*100:.2f}%)")
print(f"  True Positive  (Distress/scream correctly detected):         {tp}")

metrics_data = {
    "test_accuracy": float(acc),
    "test_precision": float(prec),
    "test_recall": float(rec),
    "test_f1": float(f1),
    "test_roc_auc": float(auc),
    "confusion_matrix": {
        "true_negative": int(tn),
        "false_positive": int(fp),
        "false_negative": int(fn),
        "true_positive": int(tp)
    },
    "train_samples": len(X_train),
    "val_samples": len(X_val),
    "test_samples": len(X_test),
    "unique_actors": len(unique_actors),
    "model_parameters": int(model.count_params())
}

metrics_path = os.path.join(OUTPUT_DIR, "evaluation_metrics.json")
with open(metrics_path, "w") as f:
    json.dump(metrics_data, f, indent=2)
print(f"Saved evaluation metrics to: {metrics_path}")

# 7. Save Keras Model
keras_path = os.path.join(MODELS_DIR, "audio_distress.keras")
model.save(keras_path)
print(f"Saved Keras model to: {keras_path}")

# 8. Export to TFLite
tflite_path = os.path.join(MODELS_DIR, "audio_distress.tflite")
converter = tf.lite.TFLiteConverter.from_keras_model(model)
tflite_model = converter.convert()

with open(tflite_path, "wb") as f:
    f.write(tflite_model)

tflite_size_kb = len(tflite_model) / 1024.0
print(f"Successfully exported TFLite model to: {tflite_path} ({tflite_size_kb:.1f} KB)")
print("=" * 80)
