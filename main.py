
import sys
from PySide6.QtWidgets import QDialog, QTextEdit
from core.logger import read_secure_log
from PySide6.QtWidgets import QApplication, QSplashScreen
from PySide6.QtGui import QPixmap
from PySide6.QtCore import Qt, QTimer
from ui.main_window import MainWindow


def main():
    app = QApplication(sys.argv)

    splash = QSplashScreen(QPixmap(400, 200))
    splash.setStyleSheet(
        "background-color: #0B0F19; color: #00F0FF; font-size: 16px;"
    )
    splash.showMessage(
        "CRYPTIX\nInitializing Secure Modules...",
        Qt.AlignmentFlag.AlignCenter,
        Qt.GlobalColor.cyan
    )
    splash.show()

    window = MainWindow()

    QTimer.singleShot(1500, splash.close)
    QTimer.singleShot(1500, window.show)

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
