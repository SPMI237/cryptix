# audio_check.py - Standalone Cryptix audio diagnostic (run, listen, read output).
#
# Usage (from your project root, with your venv active):
#
#     python audio_check.py
#
# What it does:
#   1. Prints whether QtMultimedia is importable and which themes were found
#   2. Plays every event sound ONE BY ONE (0.7s apart) - you should hear 16 blips
#   3. Starts the Academy ambience loop for 8 seconds - you should hear the pad
#   4. Fades in/out via timer ramps and prints the final report
#
# If any step prints an error or you hear nothing, send the full output back.

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QTimer

from audio.playback import SoundService, _QT_AVAILABLE, LAYER_VERSION
from audio import sound_manager as sm


def main():
    app = QApplication([])
    print("=" * 60)
    print("CRYPTIX AUDIO DIAGNOSTIC")
    print("=" * 60)
    print("Audio layer version     :", LAYER_VERSION)
    print("QtMultimedia importable :", _QT_AVAILABLE)
    print("Themes found            :", sm.list_themes() or "NONE (run: python -m audio.make_sounds)")

    service = SoundService()
    print("Effective audio settings:", service.audio_settings())

    if not _QT_AVAILABLE:
        print("\nRESULT: QtMultimedia is NOT available in this environment.")
        print("Fix: pip install --force-reinstall PySide6==6.11.1")
        return

    if not sm.list_themes():
        print("\nRESULT: no themes - generate them first with:")
        print("    python -m audio.make_sounds")
        return

    events = sorted(sm.EVENTS.keys())
    print(f"\n[1/3] Playing all {len(events)} event sounds, one per 0.7s ...")
    for i, event in enumerate(events):
        QTimer.singleShot(i * 700, lambda e=event: (service.emit(e), print("   played:", e)))

    t_ambience = len(events) * 700 + 800
    QTimer.singleShot(
        t_ambience,
        lambda: print("\n[2/3] Starting Academy ambience for 8 seconds (fade-in, then fade-out) ..."),
    )
    QTimer.singleShot(t_ambience + 100, lambda: service.start_ambience("academy_loop"))
    QTimer.singleShot(t_ambience + 4100, lambda: print("   (ambience should be audible right now)"))
    QTimer.singleShot(t_ambience + 7000, lambda: service.stop_ambience())

    def finish():
        print("\n[3/3] Done.")
        print("RESULT: if you heard the 16 event sounds AND the ambience pad,")
        print("audio is fully functional. If some parts were silent, note which.")
        app.quit()

    QTimer.singleShot(t_ambience + 8200, finish)
    app.exec()


if __name__ == "__main__":
    main()
