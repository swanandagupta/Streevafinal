"""
STREEVA — Phase 1D Distress Audio Detection Deterministic Replay / Demo.

Executes deterministic simulations for the 5 scenarios required by Phase 1D:
1. TEST 1 — Normal audio (Ambient background / quiet environment -> NORMAL)
2. TEST 2 — Non-distress vocal/audio (Neutral speech/ordinary vocalization -> NORMAL)
3. TEST 3 — Distress-related sample (Sustained scream: W1 -> POSSIBLE_DISTRESS, W2 -> POSSIBLE_DISTRESS, W3 -> DISTRESS_DETECTED)
4. TEST 4 — One noisy/distress-like window (Spike -> POSSIBLE_DISTRESS -> Clears to NORMAL, no confirmed distress)
5. TEST 5 — Distress followed by normal audio (DISTRESS_DETECTED -> RECOVERED -> NORMAL)
"""

import sys
import os
import numpy as np
from datetime import datetime, timezone, timedelta

# Add parent directory to sys.path to resolve 'app'
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.edge.audio_distress import (
    AudioDistressDetector,
    AudioDistressConfig,
    DistressAudioState,
    AudioDistressEvent
)

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEMO_DIR = os.path.join(PROJECT_ROOT, "data", "processed", "audio_distress", "demo_samples")
SCREAM_WAV = os.path.join(DEMO_DIR, "scream_sample.wav")
NEUTRAL_WAV = os.path.join(DEMO_DIR, "neutral_sample.wav")


def print_step(window_num: int, event: AudioDistressEvent):
    state_colors = {
        DistressAudioState.NORMAL: "\033[92m",            # Green
        DistressAudioState.POSSIBLE_DISTRESS: "\033[93m",  # Yellow
        DistressAudioState.DISTRESS_DETECTED: "\033[91m",  # Red
        DistressAudioState.RECOVERED: "\033[96m"          # Cyan
    }
    color = state_colors.get(event.state, "")
    reset = "\033[0m"

    print(
        f"  Window {window_num:02d}: {color}[{event.state.value.ljust(18)}]{reset} "
        f"Raw Prob: {event.raw_probability:05.3f} | "
        f"Score: {event.distress_score:05.1f} | "
        f"Conf: {event.confidence:04.2f} | "
        f"DistressCount: {event.consecutive_distress_count} | "
        f"{event.details}"
    )


def run_demo():
    print("=" * 95)
    print(" STREEVA — PHASE 1D DISTRESS AUDIO DETECTION DETERMINISTIC REPLAY")
    print("=" * 95)

    config = AudioDistressConfig(
        distress_threshold=0.60,
        possible_distress_threshold=0.35,
        recovery_threshold=0.40,
        consecutive_windows_required=3,
        recovery_windows_required=2,
        smoothing_alpha=0.5
    )
    detector = AudioDistressDetector(config=config)

    # -------------------------------------------------------------
    # SCENARIO 1: Normal Audio (Ambient Noise / Silence)
    # -------------------------------------------------------------
    print("\n" + "-" * 95)
    print(" SCENARIO 1: Normal Audio (Ambient Background / Quiet Room)")
    print(" Description: 5 consecutive 1-second windows of ambient room noise (~0.02 amplitude).")
    print(" Expected: Model raw probability < 0.25, score stays < 20.0, state stays NORMAL.")
    print("-" * 95)

    detector.reset()
    base_time = datetime(2026, 9, 12, 14, 0, 0, tzinfo=timezone.utc)
    for i in range(5):
        noise = np.random.normal(0, 0.02, 16000).astype(np.float32)
        ev = detector.process_audio_window(noise, timestamp=base_time + timedelta(seconds=i))
        print_step(i + 1, ev)
        assert ev.state == DistressAudioState.NORMAL
        assert not ev.is_distress
    print("  >>> PASS: Normal audio remained in NORMAL state throughout.")

    # -------------------------------------------------------------
    # SCENARIO 2: Non-Distress Vocal / Audio
    # -------------------------------------------------------------
    print("\n" + "-" * 95)
    print(" SCENARIO 2: Non-Distress Vocalization (Neutral Speech / Ordinary Audio)")
    print(f" Source: ASVP-ESD Neutral Vocalization Sample ({os.path.basename(NEUTRAL_WAV)})")
    print(" Description: 4 consecutive windows of ordinary speech.")
    print(" Expected: Model identifies non-distress speech (p < 0.35), state remains NORMAL.")
    print("-" * 95)

    detector.reset()
    for i in range(4):
        ev = detector.process_audio_window(file_path=NEUTRAL_WAV, timestamp=base_time + timedelta(seconds=i))
        print_step(i + 1, ev)
        assert ev.state == DistressAudioState.NORMAL
        assert not ev.is_distress
    print("  >>> PASS: Non-distress vocal audio correctly classified without false alarm.")

    # -------------------------------------------------------------
    # SCENARIO 3: Distress-Related Sample (Sustained Scream)
    # -------------------------------------------------------------
    print("\n" + "-" * 95)
    print(" SCENARIO 3: Distress-Related Sample (Sustained Vocal Distress / Scream)")
    print(f" Source: ASVP-ESD Fear Scream Sample ({os.path.basename(SCREAM_WAV)})")
    print(" Description: 3 consecutive 1-second windows of genuine scream audio.")
    print(" Expected: W1 -> POSSIBLE_DISTRESS, W2 -> POSSIBLE_DISTRESS, W3 -> DISTRESS_DETECTED.")
    print("-" * 95)

    detector.reset()
    ev1 = detector.process_audio_window(file_path=SCREAM_WAV, timestamp=base_time)
    print_step(1, ev1)
    assert ev1.state == DistressAudioState.POSSIBLE_DISTRESS
    assert not ev1.is_distress

    ev2 = detector.process_audio_window(file_path=SCREAM_WAV, timestamp=base_time + timedelta(seconds=1))
    print_step(2, ev2)
    assert ev2.state == DistressAudioState.POSSIBLE_DISTRESS
    assert not ev2.is_distress

    ev3 = detector.process_audio_window(file_path=SCREAM_WAV, timestamp=base_time + timedelta(seconds=2))
    print_step(3, ev3)
    assert ev3.state == DistressAudioState.DISTRESS_DETECTED
    assert ev3.is_distress
    print("  >>> PASS: Sustained distress progressed through state machine to DISTRESS_DETECTED.")

    # -------------------------------------------------------------
    # SCENARIO 4: One Noisy / Distress-Like Window (Anti-Flapping Protection)
    # -------------------------------------------------------------
    print("\n" + "-" * 95)
    print(" SCENARIO 4: One Noisy / Distress-Like Window (Anti-Flapping / Transient Shock)")
    print(" Description: Window 1 is a loud scream; Window 2 immediately returns to quiet ambient.")
    print(" Expected: W1 enters POSSIBLE_DISTRESS, W2 dissipates to NORMAL. NO DISTRESS_DETECTED.")
    print("-" * 95)

    detector.reset()
    # Window 1: High probability scream spike
    ev_spike = detector.process_audio_window(file_path=SCREAM_WAV, timestamp=base_time)
    print_step(1, ev_spike)
    assert ev_spike.state == DistressAudioState.POSSIBLE_DISTRESS
    assert not ev_spike.is_distress

    # Window 2: Quiet ambient noise
    ev_clear = detector.process_audio_window(np.zeros(16000, dtype=np.float32), timestamp=base_time + timedelta(seconds=1))
    print_step(2, ev_clear)
    assert ev_clear.state == DistressAudioState.NORMAL
    assert not ev_clear.is_distress
    print("  >>> PASS: Isolated transient sound dissipated cleanly; avoided false-positive trigger.")

    # -------------------------------------------------------------
    # SCENARIO 5: Distress Followed by Normal Audio (Recovery Sequence)
    # -------------------------------------------------------------
    print("\n" + "-" * 95)
    print(" SCENARIO 5: Distress Followed by Normal Audio (Recovery Progression)")
    print(" Description: 3 scream windows (reach DISTRESS_DETECTED) followed by quiet audio.")
    print(" Expected: DISTRESS_DETECTED -> RECOVERED -> NORMAL.")
    print("-" * 95)

    detector.reset()
    # 3 distress windows
    for i in range(3):
        detector.process_audio_window(file_path=SCREAM_WAV, timestamp=base_time + timedelta(seconds=i))
    assert detector.current_state == DistressAudioState.DISTRESS_DETECTED
    print("  [Confirmed DISTRESS_DETECTED state reached]")

    # Recovery Window 1 (silence) -> RECOVERED
    ev_rec1 = detector.process_audio_window(np.zeros(16000, dtype=np.float32), timestamp=base_time + timedelta(seconds=3))
    print_step(4, ev_rec1)
    assert ev_rec1.state == DistressAudioState.RECOVERED
    assert not ev_rec1.is_distress

    # Recovery Window 2 (silence) -> NORMAL
    ev_rec2 = detector.process_audio_window(np.zeros(16000, dtype=np.float32), timestamp=base_time + timedelta(seconds=4))
    print_step(5, ev_rec2)
    assert ev_rec2.state == DistressAudioState.NORMAL
    assert not ev_rec2.is_distress
    print("  >>> PASS: Post-distress acoustic recovery completed (DISTRESS_DETECTED -> RECOVERED -> NORMAL).")

    print("\n" + "=" * 95)
    print(" ALL 5 PHASE 1D REPLAY SCENARIOS COMPLETED AND VERIFIED SUCCESSFULLY!")
    print("=" * 95)


if __name__ == "__main__":
    run_demo()
