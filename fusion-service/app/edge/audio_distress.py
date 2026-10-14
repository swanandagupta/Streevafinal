"""
STREEVA Distress Audio Detection Engine (Phase 1D).

Detects distress vocalizations (screams, panic cries, acute pain) from short audio windows
using an exported 2D-CNN TFLite model, temporal exponential smoothing, and hysteresis.

PRIVACY GUARANTEE:
Processes audio windows strictly in-memory. Raw audio samples are discarded immediately
after Mel spectrogram extraction. No microphone audio is stored to disk or uploaded to clouds.
"""

from __future__ import annotations

import os
import io
import base64
import wave
import math
import numpy as np
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple, Union
from pydantic import BaseModel, Field, computed_field

from .audio_preprocessor import extract_log_mel_spectrogram

try:
    import tflite_runtime.interpreter as tflite
except ImportError:
    try:
        import tensorflow as tf
        tflite = tf.lite
    except ImportError:
        tflite = None


class DistressAudioState(str, Enum):
    """Lifecycle states for distress audio detection."""
    NORMAL = "NORMAL"
    POSSIBLE_DISTRESS = "POSSIBLE_DISTRESS"
    DISTRESS_DETECTED = "DISTRESS_DETECTED"
    RECOVERED = "RECOVERED"


class AudioDistressConfig(BaseModel):
    """
    Tunable configuration parameters for temporal distress audio aggregation.
    
    Defaults:
    - distress_probability_threshold: 0.60 (confidence boundary for distress vocalization).
    - window_duration_seconds: 1.0 s (temporal analysis window).
    - consecutive_distress_windows_required: 3 windows (requires 3s of persistent vocal distress).
    - recovery_windows_required: 2 windows (requires 2 consecutive normal windows to clear).
    - smoothing_alpha: 0.5 (exponential moving average weight on latest frame).
    - recovery_probability_threshold: 0.40 (hysteresis ceiling for clearing distress).
    """
    distress_probability_threshold: float = Field(
        default=0.60,
        description="Probability threshold above which an audio window is flagged as distress."
    )
    possible_distress_threshold: float = Field(
        default=0.35,
        description="Probability threshold above which an audio window is flagged as possible distress."
    )
    recovery_probability_threshold: float = Field(
        default=0.40,
        description="Probability threshold below which recovery from distress is initiated (hysteresis)."
    )
    window_duration_seconds: float = Field(
        default=1.0,
        description="Duration of each incoming audio window in seconds."
    )
    consecutive_distress_windows_required: int = Field(
        default=3,
        description="Consecutive distress windows required to confirm DISTRESS_DETECTED state."
    )
    recovery_windows_required: int = Field(
        default=2,
        description="Consecutive non-distress windows required to return to NORMAL state."
    )
    smoothing_alpha: float = Field(
        default=0.5,
        description="Exponential moving average factor for score temporal smoothing."
    )
    model_path: Optional[str] = Field(
        default=None,
        description="Optional custom path to TFLite model."
    )

    def __init__(self, **data):
        # Support aliases
        if "distress_threshold" in data and "distress_probability_threshold" not in data:
            data["distress_probability_threshold"] = data.pop("distress_threshold")
        if "recovery_threshold" in data and "recovery_probability_threshold" not in data:
            data["recovery_probability_threshold"] = data.pop("recovery_threshold")
        if "consecutive_windows_required" in data and "consecutive_distress_windows_required" not in data:
            data["consecutive_distress_windows_required"] = data.pop("consecutive_windows_required")
        super().__init__(**data)


class AudioDistressEvent(BaseModel):
    """
    Structured telemetry event emitted for each evaluated audio window.
    """
    event_type: str = "AUDIO_DISTRESS"
    is_distress: bool = Field(
        ...,
        description="True only if the current state is DISTRESS_DETECTED."
    )
    state: DistressAudioState = Field(
        ...,
        description="Current state in the distress audio state machine."
    )
    distress_score: float = Field(
        ...,
        description="Temporally smoothed distress risk score scaled from 0.0 to 100.0."
    )
    raw_probability: float = Field(
        ...,
        description="Raw output probability (0.0 to 1.0) from the CNN model for the current window."
    )
    confidence: float = Field(
        ...,
        description="Heuristic confidence score (0.0 to 1.0) combining model clarity and temporal stability."
    )
    consecutive_distress_count: int = Field(
        ...,
        description="Number of consecutive distress windows observed."
    )
    duration_s: float = Field(
        default=1.0,
        description="Duration of the evaluated audio frame in seconds."
    )
    timestamp: Optional[datetime] = Field(
        default=None,
        description="Timestamp of the evaluated audio window."
    )
    details: Optional[str] = Field(
        default=None,
        description="Human-readable context or explanation of the detection state."
    )

    @computed_field
    @property
    def raw_distress_probability(self) -> float:
        """Alias for raw_probability."""
        return self.raw_probability

    @computed_field
    @property
    def consecutive_distress_windows(self) -> int:
        """Alias for consecutive_distress_count."""
        return self.consecutive_distress_count


class AudioDistressDetector:
    """
    Stateful Distress Audio Detection Engine.
    
    Loads exported TFLite CNN model, extracts Log-Mel Spectrograms, applies
    exponential temporal smoothing, and manages the distress lifecycle state machine.
    """

    def __init__(self, config: Optional[AudioDistressConfig] = None, model_path: Optional[str] = None):
        self.config = config or AudioDistressConfig()
        if model_path is None:
            model_path = self.config.model_path
        if model_path is None:
            base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            model_path = os.path.join(base_dir, "models", "audio_distress.tflite")
            
        self.model_path = model_path
        self.interpreter = None
        self.input_details = None
        self.output_details = None
        
        self.current_state: DistressAudioState = DistressAudioState.NORMAL
        self.smoothed_prob: float = 0.0
        self.consecutive_distress: int = 0
        self.consecutive_recoveries: int = 0
        
        self.load_model()

    @property
    def smoothed_score(self) -> float:
        return float(np.clip(self.smoothed_prob * 100.0, 0.0, 100.0))

    @property
    def consecutive_distress_count(self) -> int:
        return self.consecutive_distress

    @property
    def consecutive_normal_count(self) -> int:
        return self.consecutive_recoveries

    @property
    def model(self):
        return self.interpreter

    def load_model(self) -> None:
        """Loads the exported TFLite model."""
        if tflite is None:
            return
        if not os.path.exists(self.model_path):
            return

        try:
            self.interpreter = tflite.Interpreter(model_path=self.model_path)
            self.interpreter.allocate_tensors()
            self.input_details = self.interpreter.get_input_details()
            self.output_details = self.interpreter.get_output_details()
        except Exception:
            self.interpreter = None

    def reset(self) -> None:
        """Resets state machine and smoothing history to NORMAL."""
        self.current_state = DistressAudioState.NORMAL
        self.smoothed_prob = 0.0
        self.consecutive_distress = 0
        self.consecutive_recoveries = 0

    def process_audio_window(
        self,
        audio: Optional[Union[np.ndarray, List[float]]] = None,
        audio_data: Optional[Union[np.ndarray, List[float]]] = None,
        base64_audio: Optional[str] = None,
        file_path: Optional[str] = None,
        sample_rate: int = 16000,
        timestamp: Optional[datetime] = None
    ) -> AudioDistressEvent:
        """
        Processes a 1.0-second audio window in-memory.
        Raw audio is discarded after feature extraction.

        Args:
            audio: 1D array of float32 samples (in [-1.0, 1.0]).
            audio_data: Alias for audio.
            base64_audio: Base64-encoded PCM or WAV string.
            file_path: Optional path to WAV file.
            sample_rate: Audio sampling frequency (default 16000 Hz).
            timestamp: Observation datetime.

        Returns:
            AudioDistressEvent.
        """
        obs_time = timestamp or datetime.now(timezone.utc)

        # 1. Resolve Audio Input Source
        raw_audio = None
        if audio is not None:
            raw_audio = audio
        elif audio_data is not None:
            raw_audio = audio_data
        elif file_path is not None:
            if not os.path.exists(file_path):
                raise ValueError(f"Audio file not found: {file_path}")
            try:
                with wave.open(file_path, "rb") as wf:
                    channels = wf.getnchannels()
                    sr = wf.getframerate()
                    n_frames = wf.getnframes()
                    raw_bytes = wf.readframes(n_frames)
                    dt = np.int16 if wf.getsampwidth() == 2 else np.uint8
                    samples = np.frombuffer(raw_bytes, dtype=dt).astype(np.float32)
                    if wf.getsampwidth() == 2:
                        samples /= 32768.0
                    if channels > 1:
                        samples = samples.reshape(-1, channels).mean(axis=1)
                    if sr != 16000:
                        from scipy import signal
                        samples = signal.resample(samples, int(len(samples) * (16000 / sr)))
                    raw_audio = samples
            except Exception as e:
                raise ValueError(f"Error reading WAV file {file_path}: {e}")
        elif base64_audio is not None:
            try:
                decoded_bytes = base64.b64decode(base64_audio)
                try:
                    with wave.open(io.BytesIO(decoded_bytes), "rb") as wf:
                        channels = wf.getnchannels()
                        sr = wf.getframerate()
                        b = wf.readframes(wf.getnframes())
                        samples = np.frombuffer(b, dtype=np.int16).astype(np.float32) / 32768.0
                        if channels > 1:
                            samples = samples.reshape(-1, channels).mean(axis=1)
                        if sr != 16000:
                            from scipy import signal
                            samples = signal.resample(samples, int(len(samples) * (16000 / sr)))
                        raw_audio = samples
                except Exception:
                    # Fallback to raw 16-bit PCM bytes
                    raw_audio = np.frombuffer(decoded_bytes, dtype=np.int16).astype(np.float32) / 32768.0
            except Exception as e:
                raise ValueError(f"Failed to decode base64 audio: {e}")

        if raw_audio is None or len(raw_audio) == 0:
            raise ValueError("No valid audio provided. Must supply audio, audio_data, base64_audio, or file_path.")

        if isinstance(raw_audio, list):
            raw_audio = np.array(raw_audio, dtype=np.float32)

        # 2. Peak Energy Window Selection if longer than target duration
        target_len = int(sample_rate * self.config.window_duration_seconds)
        if len(raw_audio) > target_len:
            step = max(1, (len(raw_audio) - target_len) // 10)
            best_start = 0
            max_energy = -1.0
            for start in range(0, len(raw_audio) - target_len + 1, step):
                window = raw_audio[start:start + target_len]
                energy = float(np.sum(window ** 2))
                if energy > max_energy:
                    max_energy = energy
                    best_start = start
            raw_audio = raw_audio[best_start:best_start + target_len]

        # 3. Model Inference or Silence Handling
        if np.all(raw_audio == 0.0) or np.max(np.abs(raw_audio)) < 1e-5:
            # Pure silence
            raw_prob = 0.01
        else:
            mel_spec = extract_log_mel_spectrogram(
                audio=raw_audio,
                sample_rate=sample_rate,
                target_duration_s=self.config.window_duration_seconds
            )
            raw_prob = self._predict_prob(mel_spec)

        # 4. Temporal Smoothing (Exponential Moving Average)
        alpha = self.config.smoothing_alpha
        self.smoothed_prob = (alpha * raw_prob) + ((1.0 - alpha) * self.smoothed_prob)
        distress_score = float(np.clip(self.smoothed_prob * 100.0, 0.0, 100.0))

        # 5. State Machine Lifecycle with Hysteresis
        details = ""
        thresh = self.config.distress_probability_threshold
        rec_thresh = self.config.recovery_probability_threshold

        if self.current_state == DistressAudioState.NORMAL:
            self.consecutive_recoveries = 0
            if raw_prob >= thresh:
                self.consecutive_distress = 1
                if self.config.consecutive_distress_windows_required <= 1:
                    self.current_state = DistressAudioState.DISTRESS_DETECTED
                    details = f"Distress vocalization detected (p={raw_prob:.2f})."
                else:
                    self.current_state = DistressAudioState.POSSIBLE_DISTRESS
                    details = (
                        f"Possible distress vocalization (p={raw_prob:.2f}). "
                        f"Window 1 of {self.config.consecutive_distress_windows_required} required."
                    )
            else:
                self.consecutive_distress = 0
                details = f"Normal acoustic environment (distress p={raw_prob:.2f})."

        elif self.current_state == DistressAudioState.POSSIBLE_DISTRESS:
            if raw_prob >= thresh:
                self.consecutive_distress += 1
                if self.consecutive_distress >= self.config.consecutive_distress_windows_required:
                    self.current_state = DistressAudioState.DISTRESS_DETECTED
                    details = (
                        f"Sustained distress confirmed (p={raw_prob:.2f}, score={distress_score:.1f}) "
                        f"after {self.consecutive_distress} consecutive windows."
                    )
                else:
                    details = (
                        f"Distress vocalization sustained (p={raw_prob:.2f}). "
                        f"Window {self.consecutive_distress} of {self.config.consecutive_distress_windows_required} required."
                    )
            elif raw_prob < rec_thresh:
                # Transitory sound dissipated
                self.current_state = DistressAudioState.NORMAL
                self.consecutive_distress = 0
                details = f"Spike dissipated (p={raw_prob:.2f}). Cleared to NORMAL."
            else:
                details = f"Audio in hysteresis buffer (p={raw_prob:.2f}). Retaining POSSIBLE_DISTRESS."

        elif self.current_state == DistressAudioState.DISTRESS_DETECTED:
            if raw_prob < rec_thresh:
                self.consecutive_recoveries = 1
                if self.config.recovery_windows_required <= 1:
                    self.current_state = DistressAudioState.NORMAL
                    self.consecutive_distress = 0
                    self.consecutive_recoveries = 0
                    details = f"Distress cleared (p={raw_prob:.2f}). State returned to NORMAL."
                else:
                    self.current_state = DistressAudioState.RECOVERED
                    details = f"Acoustic recovery initiated (p={raw_prob:.2f} < {rec_thresh:.2f})."
            else:
                self.consecutive_recoveries = 0
                self.consecutive_distress += 1
                details = f"Distress persists (p={raw_prob:.2f}, score={distress_score:.1f})."

        elif self.current_state == DistressAudioState.RECOVERED:
            if raw_prob < rec_thresh:
                self.consecutive_recoveries += 1
                if self.consecutive_recoveries >= self.config.recovery_windows_required:
                    self.current_state = DistressAudioState.NORMAL
                    self.consecutive_distress = 0
                    self.consecutive_recoveries = 0
                    details = f"Distress cleared after recovery verification. State returned to NORMAL."
                else:
                    details = f"Recovery observation {self.consecutive_recoveries} of {self.config.recovery_windows_required}."
            elif raw_prob >= thresh:
                # Flapped back to distress
                self.current_state = DistressAudioState.DISTRESS_DETECTED
                self.consecutive_recoveries = 0
                details = f"Distress vocalization resumed (p={raw_prob:.2f}) during recovery."
            else:
                details = f"Recovery buffer (p={raw_prob:.2f})."

        # 6. Confidence Computation (Heuristic confidence combining probability and persistence)
        confidence = self._compute_heuristic_confidence(
            raw_prob=raw_prob,
            smoothed_prob=self.smoothed_prob,
            state=self.current_state
        )

        return AudioDistressEvent(
            is_distress=(self.current_state == DistressAudioState.DISTRESS_DETECTED),
            state=self.current_state,
            distress_score=round(distress_score, 1),
            raw_probability=round(raw_prob, 3),
            confidence=round(confidence, 2),
            consecutive_distress_count=self.consecutive_distress,
            duration_s=self.config.window_duration_seconds,
            timestamp=obs_time,
            details=details
        )

    def _predict_prob(self, mel_spec: np.ndarray) -> float:
        """Runs TFLite model or heuristic fallback."""
        if self.interpreter is not None:
            try:
                inp_data = np.expand_dims(mel_spec, axis=0).astype(np.float32)
                self.interpreter.set_tensor(self.input_details[0]['index'], inp_data)
                self.interpreter.invoke()
                out_data = self.interpreter.get_tensor(self.output_details[0]['index'])
                return float(out_data[0][0])
            except Exception:
                pass

        # Heuristic acoustic fallback (spectral energy concentration in 1-4 kHz range)
        high_freq_energy = np.mean(mel_spec[:, 20:50, 0])
        total_energy = np.mean(mel_spec[:, :, 0]) + 1e-6
        ratio = high_freq_energy / total_energy
        return float(np.clip(ratio * 0.5, 0.05, 0.90))

    def _compute_heuristic_confidence(
        self,
        raw_prob: float,
        smoothed_prob: float,
        state: DistressAudioState
    ) -> float:
        """
        Calculates heuristic confidence score in [0.0, 1.0].
        Distinguishes clear probability signals from boundary ambiguities.
        """
        # Distance from ambiguous 0.5 boundary
        boundary_clarity = abs(raw_prob - 0.5) * 2.0  # 0.0 at p=0.5, 1.0 at p=0.0 or 1.0

        if state == DistressAudioState.DISTRESS_DETECTED:
            persistence = min(1.0, self.consecutive_distress / max(1, self.config.consecutive_distress_windows_required))
            return max(0.65, min(0.98, (0.5 * boundary_clarity) + (0.3 * persistence) + 0.2))
        elif state == DistressAudioState.POSSIBLE_DISTRESS:
            return max(0.40, min(0.80, (0.6 * boundary_clarity) + 0.2))
        elif state == DistressAudioState.RECOVERED:
            return 0.75
        else:  # NORMAL
            return max(0.70, min(0.98, (0.5 * boundary_clarity) + 0.45))

    detect = process_audio_window
