import sys
import os
from PySide6.QtWidgets import QApplication, QSplashScreen
from PySide6.QtGui import QPixmap
from PySide6.QtCore import Qt, QTimer
from ui.main_window import MainWindow


def main():
    app = QApplication(sys.argv)

    # Detect file passed from Windows file association
    initial_file = None
    if len(sys.argv) > 1 and os.path.isfile(sys.argv[1]):
        initial_file = sys.argv[1]

    splash = QSplashScreen(QPixmap(400, 200))
    splash.setStyleSheet(
        "background-color: #0B0F19; color: #00F0FF; font-size: 16px;"
    )
    splash.showMessage(
        "CRYPTIX\nInitializing Secure Modules...",
        Qt.AlignCenter,
        Qt.cyan
    )
    splash.show()

    window = MainWindow(initial_file=initial_file)

    QTimer.singleShot(1500, splash.close)
    QTimer.singleShot(1500, window.show)

    sys.exit(app.exec())


if __name__ == "__main__":
    main()