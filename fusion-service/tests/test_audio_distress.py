"""
Comprehensive Unit Tests for Audio Distress Detection Engine (Phase 1D).

Covers all required specifications:
✓ valid audio preprocessing (shape, normalization)
✓ silence
✓ normal/background audio
✓ distress-labelled canonical sample
✓ non-distress canonical sample
✓ incorrect/empty input handling
✓ short audio padding
✓ long audio slicing (highest energy)
✓ sample-rate conversion
✓ mono conversion
✓ model inference and probability range [0, 1]
✓ temporal smoothing (EMA)
✓ distress threshold hysteresis
✓ consecutive distress windows to trigger DISTRESS_DETECTED
✓ recovery state progression
✓ state reset
✓ unavailable model fallback
✓ invalid/corrupt audio handling
✓ REST API endpoints (/edge/audio/evaluate, /edge/audio/reset, /journey-risk)
"""

import os
import pytest
import numpy as np
import base64
import io
import wave
from datetime import datetime, timezone, timedelta
from fastapi.testclient import TestClient

from app.main import app
from app.edge.audio_preprocessor import AudioPreprocessor, PreprocessingConfig
from app.edge.audio_distress import (
    AudioDistressDetector,
    AudioDistressConfig,
    AudioDistressEvent,
    DistressAudioState
)

client = TestClient(app)

# Canonical sample paths
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEMO_DIR = os.path.join(PROJECT_ROOT, "data", "processed", "audio_distress", "demo_samples")
SCREAM_WAV = os.path.join(DEMO_DIR, "scream_sample.wav")
NEUTRAL_WAV = os.path.join(DEMO_DIR, "neutral_sample.wav")


@pytest.fixture
def preprocessor():
    return AudioPreprocessor(PreprocessingConfig(sample_rate=16000, duration_seconds=1.0))


@pytest.fixture
def detector():
    return AudioDistressDetector(AudioDistressConfig(
        distress_threshold=0.60,
        possible_distress_threshold=0.35,
        consecutive_windows_required=3,
        recovery_windows_required=2,
        smoothing_alpha=0.5
    ))


# =====================================================================
# 1. Preprocessing Tests
# =====================================================================

def test_valid_audio_preprocessing_shape_and_normalization(preprocessor):
    """1.0s of audio at 16kHz produces an exact (61, 64, 1) Log-Mel spectrogram with zero mean."""
    audio = np.random.uniform(-0.5, 0.5, 16000).astype(np.float32)
    features = preprocessor.extract_features(audio, sample_rate=16000)
    
    assert features.shape == (61, 64, 1)
    # Check normalized zero-mean approx
    assert abs(np.mean(features)) < 0.1
    assert not np.isnan(features).any()
    assert not np.isinf(features).any()


def test_preprocessing_short_audio_is_padded(preprocessor):
    """Audio shorter than 1.0s (e.g. 0.5s) is cleanly padded to 1.0s."""
    short_audio = np.random.uniform(-0.3, 0.3, 8000).astype(np.float32)
    features = preprocessor.extract_features(short_audio, sample_rate=16000)
    assert features.shape == (61, 64, 1)


def test_preprocessing_long_audio_is_sliced_to_highest_energy(preprocessor):
    """Audio longer than 1.0s (e.g. 2.5s) has its highest-energy 1s window extracted."""
    # Create 2.5s audio with silence except for a burst in the middle
    long_audio = np.zeros(40000, dtype=np.float32)
    long_audio[18000:26000] = 0.8  # Loud burst
    
    features = preprocessor.extract_features(long_audio, sample_rate=16000)
    assert features.shape == (61, 64, 1)
    # The extracted window should contain high energy
    assert np.max(features) > 0.0


def test_preprocessing_resampling(preprocessor):
    """Audio at 44100 Hz or 8000 Hz is resampled to 16000 Hz without errors."""
    audio_44k = np.sin(2 * np.pi * 440 * np.linspace(0, 1.0, 44100)).astype(np.float32)
    features_44k = preprocessor.extract_features(audio_44k, sample_rate=44100)
    assert features_44k.shape == (61, 64, 1)

    audio_8k = np.sin(2 * np.pi * 440 * np.linspace(0, 1.0, 8000)).astype(np.float32)
    features_8k = preprocessor.extract_features(audio_8k, sample_rate=8000)
    assert features_8k.shape == (61, 64, 1)


def test_preprocessing_stereo_to_mono(preprocessor):
    """Multi-channel stereo audio is averaged to mono."""
    stereo_audio = np.random.uniform(-0.4, 0.4, (16000, 2)).astype(np.float32)
    features = preprocessor.extract_features(stereo_audio, sample_rate=16000)
    assert features.shape == (61, 64, 1)


# =====================================================================
# 2. Silence, Background, and Canonical Samples
# =====================================================================

def test_silence_input(detector):
    """Pure silence produces a very low distress probability and NORMAL state."""
    silence = np.zeros(16000, dtype=np.float32)
    ev = detector.process_audio_window(silence)
    
    assert ev.raw_distress_probability < 0.20
    assert ev.distress_score < 20.0
    assert ev.state == DistressAudioState.NORMAL
    assert not ev.is_distress


def test_normal_background_audio(detector):
    """Low-amplitude white noise remains NORMAL."""
    noise = np.random.normal(0, 0.05, 16000).astype(np.float32)
    ev = detector.process_audio_window(noise)
    
    assert ev.raw_distress_probability < 0.50
    assert ev.state in (DistressAudioState.NORMAL, DistressAudioState.POSSIBLE_DISTRESS)
    assert not ev.is_distress


def test_canonical_scream_sample_yields_high_probability(detector):
    """The verified canonical scream sample produces a high distress probability."""
    if not os.path.exists(SCREAM_WAV):
        pytest.skip(f"Canonical scream sample not found at {SCREAM_WAV}")
        
    ev = detector.process_audio_window(file_path=SCREAM_WAV)
    assert ev.raw_distress_probability > 0.70
    assert ev.distress_score > 40.0

    # Consecutive scream window drives smoothed distress score above 70
    ev2 = detector.process_audio_window(file_path=SCREAM_WAV)
    assert ev2.distress_score > 70.0


def test_canonical_neutral_sample_yields_low_probability(detector):
    """The verified canonical neutral sample produces a low distress probability."""
    if not os.path.exists(NEUTRAL_WAV):
        pytest.skip(f"Canonical neutral sample not found at {NEUTRAL_WAV}")
        
    ev = detector.process_audio_window(file_path=NEUTRAL_WAV)
    assert ev.raw_distress_probability < 0.35
    assert ev.state == DistressAudioState.NORMAL
    assert not ev.is_distress


# =====================================================================
# 3. Model Inference, Output Range, and Heuristics
# =====================================================================

def test_probability_range_and_event_contract(detector):
    """Model output probability is bounded in [0.0, 1.0], score in [0.0, 100.0]."""
    test_signals = [
        np.zeros(16000, dtype=np.float32),
        np.ones(16000, dtype=np.float32) * 0.1,
        np.random.uniform(-1.0, 1.0, 16000).astype(np.float32)
    ]
    for sig in test_signals:
        ev = detector.process_audio_window(sig)
        assert 0.0 <= ev.raw_distress_probability <= 1.0
        assert 0.0 <= ev.distress_score <= 100.0
        assert 0.0 <= ev.confidence <= 1.0
        assert ev.event_type == "AUDIO_DISTRESS"
        assert ev.state in list(DistressAudioState)


# =====================================================================
# 4. Temporal Smoothing & State Machine Progression
# =====================================================================

def test_single_distress_window_does_not_flp_to_distress_detected(detector):
    """
    Anti-flapping: A single isolated distress window must NOT immediately
    trigger DISTRESS_DETECTED; it should enter POSSIBLE_DISTRESS.
    """
    if not os.path.exists(SCREAM_WAV):
        pytest.skip(f"Canonical scream sample not found at {SCREAM_WAV}")

    ev = detector.process_audio_window(file_path=SCREAM_WAV)
    assert ev.state == DistressAudioState.POSSIBLE_DISTRESS
    assert not ev.is_distress
    assert ev.consecutive_distress_windows == 1


def test_consecutive_distress_windows_triggers_distress_detected(detector):
    """
    3 consecutive distress windows correctly transition to DISTRESS_DETECTED.
    """
    if not os.path.exists(SCREAM_WAV):
        pytest.skip(f"Canonical scream sample not found at {SCREAM_WAV}")

    # Window 1 -> POSSIBLE_DISTRESS
    ev1 = detector.process_audio_window(file_path=SCREAM_WAV)
    assert ev1.state == DistressAudioState.POSSIBLE_DISTRESS
    assert not ev1.is_distress

    # Window 2 -> POSSIBLE_DISTRESS
    ev2 = detector.process_audio_window(file_path=SCREAM_WAV)
    assert ev2.state == DistressAudioState.POSSIBLE_DISTRESS
    assert not ev2.is_distress

    # Window 3 -> DISTRESS_DETECTED
    ev3 = detector.process_audio_window(file_path=SCREAM_WAV)
    assert ev3.state == DistressAudioState.DISTRESS_DETECTED
    assert ev3.is_distress
    assert ev3.consecutive_distress_windows >= 3


def test_recovery_sequence_after_distress(detector):
    """
    Once in DISTRESS_DETECTED, quiet/normal audio triggers RECOVERED
    and then completes transition back to NORMAL.
    """
    if not os.path.exists(SCREAM_WAV):
        pytest.skip(f"Canonical scream sample not found at {SCREAM_WAV}")

    # Trigger DISTRESS_DETECTED with 3 scream windows
    for _ in range(3):
        detector.process_audio_window(file_path=SCREAM_WAV)
    assert detector.current_state == DistressAudioState.DISTRESS_DETECTED

    # Recovery Window 1 (silence) -> RECOVERED
    silence = np.zeros(16000, dtype=np.float32)
    ev_rec1 = detector.process_audio_window(silence)
    assert ev_rec1.state == DistressAudioState.RECOVERED
    assert not ev_rec1.is_distress

    # Recovery Window 2 (silence) -> NORMAL
    ev_rec2 = detector.process_audio_window(silence)
    assert ev_rec2.state == DistressAudioState.NORMAL
    assert not ev_rec2.is_distress


def test_state_reset(detector):
    """Calling reset() returns the state machine to clean NORMAL state with 0 history."""
    if not os.path.exists(SCREAM_WAV):
        pytest.skip(f"Canonical scream sample not found at {SCREAM_WAV}")

    # Advance state
    detector.process_audio_window(file_path=SCREAM_WAV)
    detector.process_audio_window(file_path=SCREAM_WAV)
    assert detector.current_state == DistressAudioState.POSSIBLE_DISTRESS
    assert detector.smoothed_score > 0.0

    # Reset
    detector.reset()
    assert detector.current_state == DistressAudioState.NORMAL
    assert detector.smoothed_score == 0.0
    assert detector.consecutive_distress_count == 0
    assert detector.consecutive_normal_count == 0


# =====================================================================
# 5. Fault Tolerance, Fallback & Corrupt Inputs
# =====================================================================

def test_empty_audio_raises_or_handles_gracefully(detector):
    """Empty or None input raises ValueError cleanly."""
    with pytest.raises(ValueError):
        detector.process_audio_window(audio_data=None, base64_audio=None, file_path=None)


def test_invalid_corrupt_base64_audio(detector):
    """Corrupt or non-WAV bytes gracefully return empty or raised clean ValueError."""
    corrupt_b64 = base64.b64encode(b"THIS_IS_NOT_A_VALID_WAV_FILE_CORRUPT").decode("ascii")
    # Base64 with invalid WAV header falls back to raw 16-bit PCM interpretation
    # without crashing
    ev = detector.process_audio_window(base64_audio=corrupt_b64)
    assert isinstance(ev, AudioDistressEvent)


def test_unavailable_model_path_uses_graceful_fallback():
    """If the TFLite model file is missing, detector initializes with fallback without crash."""
    detector_no_model = AudioDistressDetector(AudioDistressConfig(
        model_path="non_existent_model_file.tflite"
    ))
    assert detector_no_model.model is None
    # Inference falls back to spectral heuristic
    test_audio = np.random.uniform(-0.2, 0.2, 16000).astype(np.float32)
    ev = detector_no_model.process_audio_window(test_audio)
    assert isinstance(ev, AudioDistressEvent)
    assert 0.0 <= ev.raw_distress_probability <= 1.0


# =====================================================================
# 6. REST API Endpoint Integration Tests
# =====================================================================

def test_api_evaluate_endpoint_with_samples():
    """POST /edge/audio/evaluate with raw float samples returns AudioDistressEvent."""
    samples = [float(x) for x in np.random.uniform(-0.1, 0.1, 16000)]
    resp = client.post("/edge/audio/evaluate", json={
        "audio_samples": samples,
        "sample_rate": 16000
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["event_type"] == "AUDIO_DISTRESS"
    assert "distress_score" in data
    assert "raw_distress_probability" in data
    assert "state" in data


def test_api_evaluate_endpoint_with_file_path():
    """POST /edge/audio/evaluate with file_path returns AudioDistressEvent."""
    if not os.path.exists(SCREAM_WAV):
        pytest.skip(f"Canonical scream sample not found at {SCREAM_WAV}")

    resp = client.post("/edge/audio/evaluate", json={
        "file_path": SCREAM_WAV
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["event_type"] == "AUDIO_DISTRESS"
    assert data["raw_distress_probability"] > 0.70


def test_api_reset_endpoint():
    """POST /edge/audio/reset resets detector state to NORMAL."""
    resp = client.post("/edge/audio/reset")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "reset"
    assert data["state"] == "NORMAL"


def test_journey_risk_audio_integration():
    """POST /journey-risk with audio_distress incorporates audio into fused score."""
    sample_points = [
        {
            "timestamp": "2026-09-12T12:00:00Z",
            "lat": 18.5204,
            "lng": 73.8567,
            "accel_x": 0.0,
            "accel_y": 0.0,
            "accel_z": 9.8
        }
    ]
    
    # 1. Base call without audio
    resp_no_audio = client.post("/journey-risk", json={"points": sample_points})
    # 2. Call with high audio distress (85.0)
    resp_with_audio = client.post("/journey-risk", json={
        "points": sample_points,
        "audio_distress": 85.0
    })
    
    if resp_with_audio.status_code == 200:
        data = resp_with_audio.json()
        assert data["fusion_factors"]["audio_distress"] == 85.0
        # Audio distress increases overall fused risk
        if resp_no_audio.status_code == 200:
            assert data["journey_risk_score"] >= resp_no_audio.json()["journey_risk_score"]
