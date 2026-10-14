"""
Audio preprocessing and Log-Mel Spectrogram extraction.
Runs on numpy and scipy for lightweight edge inference matching the training pipeline.
"""

import math
from dataclasses import dataclass
from typing import Optional, Union
import numpy as np
from scipy import signal


@dataclass
class PreprocessingConfig:
    sample_rate: int = 16000
    duration_seconds: float = 1.0
    n_mels: int = 64
    n_fft: int = 512
    hop_length: int = 256
    lower_edge_hz: float = 80.0
    upper_edge_hz: float = 7600.0


class AudioPreprocessor:
    """
    Object-oriented wrapper for audio normalization, resampling, and Log-Mel extraction.
    """
    def __init__(self, config: Optional[PreprocessingConfig] = None):
        self.config = config or PreprocessingConfig()
        self.mel_filterbank = create_mel_filterbank(
            num_mel_bins=self.config.n_mels,
            fft_size=self.config.n_fft,
            sample_rate=self.config.sample_rate,
            lower_edge_hz=self.config.lower_edge_hz,
            upper_edge_hz=self.config.upper_edge_hz
        )

    def extract_features(
        self,
        audio: np.ndarray,
        sample_rate: Optional[int] = None
    ) -> np.ndarray:
        sr = sample_rate or self.config.sample_rate
        
        # 1. Convert multi-channel to mono
        if audio.ndim > 1:
            audio = np.mean(audio, axis=-1)

        # 2. Resample if necessary
        if sr != self.config.sample_rate:
            target_samples = int(len(audio) * (self.config.sample_rate / sr))
            audio = signal.resample(audio, target_samples)
            sr = self.config.sample_rate

        # 3. Peak energy window selection if audio exceeds target duration
        target_samples = int(self.config.sample_rate * self.config.duration_seconds)
        if len(audio) > target_samples:
            step = max(1, (len(audio) - target_samples) // 10)
            best_start = 0
            max_energy = -1.0
            for start in range(0, len(audio) - target_samples + 1, step):
                window = audio[start:start + target_samples]
                energy = float(np.sum(window ** 2))
                if energy > max_energy:
                    max_energy = energy
                    best_start = start
            audio = audio[best_start:best_start + target_samples]

        return extract_log_mel_spectrogram(
            audio=audio,
            sample_rate=self.config.sample_rate,
            target_duration_s=self.config.duration_seconds,
            n_mels=self.config.n_mels,
            n_fft=self.config.n_fft,
            hop_length=self.config.hop_length,
            mel_filterbank=self.mel_filterbank
        )


def create_mel_filterbank(
    num_mel_bins: int = 64,
    fft_size: int = 512,
    sample_rate: int = 16000,
    lower_edge_hz: float = 80.0,
    upper_edge_hz: float = 7600.0
) -> np.ndarray:
    """
    Constructs a triangular Mel filterbank matrix of shape (num_fft_bins, num_mel_bins).
    """
    def hz_to_mel(hz):
        return 2595.0 * np.log10(1.0 + hz / 700.0)

    def mel_to_hz(mel):
        return 700.0 * (10.0 ** (mel / 2595.0) - 1.0)

    num_fft_bins = (fft_size // 2) + 1
    lower_mel = hz_to_mel(lower_edge_hz)
    upper_mel = hz_to_mel(upper_edge_hz)
    mel_points = np.linspace(lower_mel, upper_mel, num_mel_bins + 2)
    hz_points = mel_to_hz(mel_points)

    bin_points = np.floor((fft_size + 1) * hz_points / sample_rate).astype(int)
    bin_points = np.clip(bin_points, 0, num_fft_bins - 1)

    weights = np.zeros((num_fft_bins, num_mel_bins), dtype=np.float32)
    for m in range(1, num_mel_bins + 1):
        f_m_minus = bin_points[m - 1]
        f_m = bin_points[m]
        f_m_plus = bin_points[m + 1]

        if f_m > f_m_minus:
            weights[f_m_minus:f_m, m - 1] = (
                (np.arange(f_m_minus, f_m) - f_m_minus) / (f_m - f_m_minus)
            )
        if f_m_plus > f_m:
            weights[f_m:f_m_plus, m - 1] = (
                (f_m_plus - np.arange(f_m, f_m_plus)) / (f_m_plus - f_m)
            )

    return weights


# Cache default 16kHz Mel filterbank
_DEFAULT_MEL_FILTERBANK = create_mel_filterbank(64, 512, 16000)


def extract_log_mel_spectrogram(
    audio: np.ndarray,
    sample_rate: int = 16000,
    target_duration_s: float = 1.0,
    n_mels: int = 64,
    n_fft: int = 512,
    hop_length: int = 256,
    mel_filterbank: np.ndarray = None
) -> np.ndarray:
    """
    Converts 1D audio waveform into normalized Log-Mel Spectrogram of shape (num_frames, n_mels, 1).

    Args:
        audio: 1D numpy array of float32 samples.
        sample_rate: Target sample rate (16000 Hz).
        target_duration_s: Window duration in seconds (1.0 s -> 16000 samples).
        n_mels: Number of Mel frequency bands.
        n_fft: FFT window size.
        hop_length: Frame advance.
        mel_filterbank: Precomputed Mel filterbank matrix.

    Returns:
        3D numpy array of shape (61, 64, 1) normalized to zero-mean unit-variance.
    """
    target_length = int(sample_rate * target_duration_s)

    # 1. Ensure 1D float32
    if audio.ndim > 1:
        audio = np.mean(audio, axis=1)  # Convert multi-channel to mono
    audio = audio.astype(np.float32)

    # 2. Pad or truncate to target duration
    if len(audio) < target_length:
        pad_width = target_length - len(audio)
        audio = np.pad(audio, (0, pad_width), mode='constant')
    elif len(audio) > target_length:
        audio = audio[:target_length]

    # 3. Compute Short-Time Fourier Transform (STFT)
    _, _, zxx = signal.stft(
        audio,
        fs=sample_rate,
        nperseg=n_fft,
        noverlap=n_fft - hop_length,
        nfft=n_fft,
        boundary=None,
        padded=False
    )
    # Magnitude spectrum: shape (num_fft_bins, num_frames)
    magnitude_spec = np.abs(zxx)

    # 4. Apply Mel Filterbank
    fb = mel_filterbank if mel_filterbank is not None else _DEFAULT_MEL_FILTERBANK
    # (num_frames, num_fft_bins) @ (num_fft_bins, num_mel_bins) -> (num_frames, num_mel_bins)
    mel_spec = np.dot(magnitude_spec.T, fb)

    # 5. Log-Mel Compression
    log_mel = np.log(np.maximum(mel_spec, 1e-6))

    # 6. Standardization / Normalization
    mean = np.mean(log_mel)
    std = np.std(log_mel) + 1e-6
    normalized_mel = (log_mel - mean) / std

    # Output shape: (frames, mels, 1)
    return np.expand_dims(normalized_mel.astype(np.float32), axis=-1)
