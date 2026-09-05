# main.py

import os
import sys

from PySide6.QtWidgets import QApplication, QMessageBox

from ui.splash import CryptixSplash, run_startup_sequence, startup_steps, fade_in_window


def main():
    app = QApplication(sys.argv)

    # Detect file passed from Windows file association
    initial_file = None
    if len(sys.argv) > 1 and os.path.isfile(sys.argv[1]):
        initial_file = sys.argv[1]

    # Real startup milestones (engine -> config -> hardware -> academy ->
    # audio -> interface). The splash lives exactly as long as they do.
    holder = {}
    steps = startup_steps(initial_file=initial_file, window_holder=holder)

    splash = CryptixSplash([s[0] for s in steps])
    splash.show()

    def on_complete():
        window = holder.get("window")
        if window is not None:
            fade_in_window(window)

    def on_critical(label, err):
        QMessageBox.critical(
            None,
            "Cryptix Core — Startup Failure",
            f"A critical component failed to initialize:\n\n"
            f"✗ {label}\n\n{err}\n\n"
            f"Cryptix Core cannot start safely."
        )
        sys.exit(1)

    run_startup_sequence(splash, steps, on_complete, on_critical)

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
