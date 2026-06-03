from email.mime import message
import os
from turtle import title
from utils.helpers import evaluate_password_strength
from core.logger import read_secure_log, log_event, clear_secure_log
from PySide6.QtWidgets import QComboBox, QGridLayout
from core.file_handler import encrypt_path, decrypt_path, ALGO_AES, ALGO_CHACHA
from core.file_handler import encrypt_path, decrypt_path, verify_path
from core.file_handler import encrypt_path, decrypt_path, verify_path, ALGO_AES, ALGO_CHACHA, AuthenticationError

from PySide6.QtWidgets import (
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QLabel,
    QFrame,
    QLineEdit,
    QFileDialog,
    QProgressBar,
    QCheckBox,
    QMessageBox,
    QDialog,
    QTextEdit,

)

from PySide6.QtCore import (
    Qt,
    QThread,
    Signal,
    Property,
    QPropertyAnimation,
    QEasingCurve,
    QTimer,
)

from PySide6.QtGui import QPainter, QColor, QIcon



# =========================================================
# Animated Toggle (Custom Widget)
# =========================================================
class AnimatedToggle(QCheckBox):
    def __init__(self, parent=None):
        super().__init__(parent)

        self.setFixedSize(60, 28)
        self.setCursor(Qt.PointingHandCursor)

        self._circle_position = 3

        self.animation = QPropertyAnimation(self, b"circle_position")
        self.animation.setDuration(200)
        self.animation.setEasingCurve(QEasingCurve.Type.OutCubic)

        self.stateChanged.connect(self.start_transition)
        self.is_locked = False

    def start_transition(self, value):
        self.animation.stop()
        if value:
            self.animation.setStartValue(3)
            self.animation.setEndValue(self.width() - 25)
        else:
            self.animation.setStartValue(self.width() - 25)
            self.animation.setEndValue(3)
        self.animation.start()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        painter.setPen(Qt.NoPen)

        if self.isChecked():
            painter.setBrush(QColor("#00AAFF")) # Blue for ON
        else:
            painter.setBrush(QColor("#777"))     # Gray for OFF

        painter.drawRoundedRect(
            0, 0, self.width(), self.height(),
            self.height() / 2, self.height() / 2
        )

        painter.setBrush(QColor("#FFFFFF")) # White circle
        painter.drawEllipse(int(self._circle_position), 3, 22, 22)

    @Property(int)
    def circle_position(self):
        return self._circle_position

    @circle_position.setter
    def circle_position(self, pos):
        self._circle_position = pos
        self.update()


# =========================================================
# Worker Thread (for encryption/decryption)
# =========================================================
class WorkerThread(QThread):
    finished = Signal(str)
    error = Signal(object)  # <-- Changed to object
    progress = Signal(int)

    def __init__(self, mode, file_path, password,
                 keyfile_data=None, algorithm=ALGO_AES):
        super().__init__()
        self.algorithm = algorithm
        self.mode = mode
        self.file_path = file_path
        self.password = password
        self.keyfile_data = keyfile_data
        self.secure_delete = False
        self.secure_delete_encrypted = False

    def run(self):
        try:
            if self.mode == "encrypt":
                result = encrypt_path(
                    self.file_path,
                    self.password,
                    self.keyfile_data,
                    self.algorithm,
                    progress_callback=self.progress.emit,
                    secure_delete_original=self.secure_delete
                )

            elif self.mode == "decrypt":
                result = decrypt_path(
                    self.file_path,
                    self.password,
                    self.keyfile_data,
                    progress_callback=self.progress.emit,
                    secure_delete_encrypted=self.secure_delete_encrypted
                )

            elif self.mode == "verify":
                result = verify_path(
                    self.file_path,
                    self.password,
                    self.keyfile_data,
                    progress_callback=self.progress.emit
                )

            self.finished.emit(result)

        except Exception as e:
            self.error.emit(e)  # <-- Now passing the actual Error Object
# =========================================================
# Main Window (CRYPTIX Application)
# =========================================================
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.version = "1.0.0"
        self.setWindowTitle("Cryptix")
        import sys
        import os
        from PySide6.QtGui import QIcon

        if getattr(sys, 'frozen', False):
          base_path = sys._MEIPASS
        else:
          base_path = os.path.abspath(".")

        icon_path = os.path.join(base_path, "cryptix.ico")
        self.setWindowIcon(QIcon(icon_path))
        self.setGeometry(200, 200, 600, 520) # Adjusted height

       

        self.file_path = None
        self.keyfile_path = None # New: keyfile_path
        self.failed_attempts = 0
        self.lock_seconds_remaining = 0
        self.is_locked = False
        
        self.lock_timer = QTimer()
        self.lock_timer.timeout.connect(self.update_countdown)

        self.init_ui()
        self.apply_dark_theme() # Start with dark theme

    def show_audit_log(self):
        log_content = read_secure_log()

        dialog = QDialog(self)
        dialog.setWindowTitle("CRYPTIX - Secure Audit Log")
        dialog.resize(500, 450)

        layout = QVBoxLayout(dialog)

        text_area = QTextEdit()
        text_area.setReadOnly(True)
        text_area.setText(log_content)

        layout.addWidget(text_area)

        clear_button = QPushButton("Clear Audit Log")

        def clear_log_action():
            reply = QMessageBox.question(
                dialog,
                "Confirm",
                "Are you sure you want to permanently delete the audit log?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )

            if reply == QMessageBox.StandardButton.Yes:
                clear_secure_log()
                text_area.setText("Audit log cleared.")

        clear_button.clicked.connect(clear_log_action)

        layout.addWidget(clear_button)

        dialog.exec()
    def init_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        layout = QVBoxLayout()
        layout.setSpacing(12)
        layout.setContentsMargins(30, 20, 30, 20)
        central_widget.setLayout(layout)

        header_container = QHBoxLayout()

# LEFT SECTION
        left_layout = QHBoxLayout()
        title = QLabel("⚡ CRYPTIX")
        title.setStyleSheet("font-size: 20px; font-weight: bold; letter-spacing: 2px;")
        left_layout.addWidget(title)
        left_layout.setAlignment(Qt.AlignmentFlag.AlignLeft)

# CENTER SECTION
        center_layout = QHBoxLayout()
        self.algorithm_badge = QLabel("AES")
        self.algorithm_badge.setStyleSheet(
        "background-color: #00F0FF; color: #000000; padding: 4px 12px; border-radius: 3px; font-weight: bold;"
)
        center_layout.addWidget(self.algorithm_badge)
        center_layout.setAlignment(Qt.AlignCenter)

# RIGHT SECTION
        right_layout = QHBoxLayout()

        self.status_led = QLabel("● READY")
        self.status_led.setStyleSheet("color: #00FF66; font-weight: bold;")
        right_layout.addWidget(self.status_led)
        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.VLine)
        separator.setStyleSheet("color: #262F3F;")
        separator.setFixedHeight(20)
        right_layout.addWidget(separator)

        self.menu_button = QPushButton("☰")
        self.menu_button.setObjectName("menu_btn")
        self.menu_button.setFixedSize(40, 30)
        self.menu_button.clicked.connect(self.toggle_settings_panel)
        right_layout.addWidget(self.menu_button)

        right_layout.setAlignment(Qt.AlignmentFlag.AlignRight)

# ADD TO MAIN HEADER
        header_container.addLayout(left_layout, 1)
        header_container.addLayout(center_layout, 1)
        header_container.addLayout(right_layout, 1)

        layout.addLayout(header_container)
        divider1 = QFrame()
        divider1.setFrameShape(QFrame.Shape.HLine)
        divider1.setStyleSheet("background-color: #262F3F; max-height: 1px;")
        layout.addWidget(divider1)

        # Settings Panel (Hidden by default)
        self.settings_panel = QWidget()
        self.settings_panel.setObjectName("settings_hud") 
        self.settings_panel.setVisible(False)
        self.settings_panel.setParent(self)
        self.settings_panel.setFixedWidth(250)
        self.settings_panel.setFixedHeight(150)

        settings_layout = QVBoxLayout()
        self.settings_panel.setLayout(settings_layout)

     # Encryption Method Selector
        self.algorithm_selector = QComboBox()
        self.algorithm_selector.addItem("AES-256-GCM", ALGO_AES)
        self.algorithm_selector.addItem("ChaCha20-Poly1305", ALGO_CHACHA)
        self.algorithm_selector.currentIndexChanged.connect(self.update_algorithm_badge)
        settings_layout.addWidget(QLabel("Encryption Method"))
        settings_layout.addWidget(self.algorithm_selector)

    # Dark Mode Toggle
        self.theme_toggle = AnimatedToggle()
        self.theme_toggle.setChecked(True)
        self.theme_toggle.stateChanged.connect(self.toggle_theme)
        settings_layout.addWidget(QLabel("Dark Mode"))
        settings_layout.addWidget(self.theme_toggle)

    # About Button
        self.about_button = QPushButton("About Cryptix")
        self.about_button.clicked.connect(self.show_about_dialog)
        settings_layout.addWidget(self.about_button)
        # Subtitle
        subtitle = QLabel("AES‑256 GCM Secure Encryption")
        subtitle.setStyleSheet("color: gray; font-size: 11px;")
        layout.addWidget(subtitle)

        # File selection
        subtitle = QLabel(f"AES‑256 GCM & ChaCha20 Secure Encryption  |  v{self.version}")
        subtitle.setStyleSheet("color: gray; font-size: 11px;")
        layout.addWidget(subtitle)

        selection_layout = QHBoxLayout()
        selection_layout.setSpacing(10)

        self.select_file_button = QPushButton("📄 FILE")
        self.select_file_button.clicked.connect(self.select_file)

        self.select_folder_button = QPushButton("📁 FOLDER")
        self.select_folder_button.clicked.connect(self.select_folder)

        self.select_image_button = QPushButton("🖼 IMAGE")
        self.select_image_button.clicked.connect(self.select_image)

        for btn in (
         self.select_file_button,
         self.select_folder_button,
         self.select_image_button,
    ):
         btn.setMinimumHeight(36)

        selection_layout.addWidget(self.select_file_button)
        selection_layout.addWidget(self.select_folder_button)
        selection_layout.addWidget(self.select_image_button)

        layout.addLayout(selection_layout)

        # Selected target display
        self.file_label = QLabel("No target selected")
        self.file_label.setStyleSheet("color: #A0AEC0; font-style: italic;")
        layout.addWidget(self.file_label)
        # --------------------------
        # Password + Strength Layout
        # --------------------------
        password_row = QHBoxLayout()

        self.password_input = QLineEdit()
        self.password_input.setPlaceholderText("Enter Password")
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.password_input.textChanged.connect(self.validate_inputs)
        self.password_input.textChanged.connect(self.update_strength)

        password_row.addWidget(self.password_input)
        divider1 = QFrame()
        divider1.setFrameShape(QFrame.Shape.HLine)
        divider1.setStyleSheet("background-color: #262F3F; max-height: 1px;")
        layout.addWidget(divider1)

       # Strength bars (vertical beside password)
        strength_layout = QVBoxLayout()
        strength_layout.setSpacing(4)

        self.bar1 = QFrame()
        self.bar2 = QFrame()
        self.bar3 = QFrame()

        for bar in (self.bar1, self.bar2, self.bar3):
         bar.setFixedHeight(6)
         bar.setFixedWidth(30)
         bar.setStyleSheet("background-color: lightgray; border-radius: 3px;")
        strength_layout.addWidget(bar)

        password_row.addLayout(strength_layout)

        layout.addLayout(password_row)

        # Confirm password input
        self.confirm_input = QLineEdit()
        self.confirm_input.setPlaceholderText("Confirm Password")
        self.confirm_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.confirm_input.textChanged.connect(self.validate_inputs)
        layout.addWidget(self.confirm_input)

        # --- Checkboxes ---
        self.show_password = QCheckBox("Show Password")
        self.show_password.stateChanged.connect(self.toggle_password_visibility)

        self.secure_delete_checkbox = QCheckBox("Secure Delete After Encryption")

        self.use_keyfile_checkbox = QCheckBox("Use Keyfile")
        self.use_keyfile_checkbox.stateChanged.connect(self.toggle_keyfile_option)

        self.secure_delete_after_decrypt_checkbox = QCheckBox(
            "Secure Delete Encrypted File After Decryption"
        )

# --- Options Grid (2 rows, 2 columns) ---
        options_grid = QGridLayout()
        options_grid.addWidget(self.show_password, 0, 0)
        options_grid.addWidget(self.secure_delete_checkbox, 0, 1)
        options_grid.addWidget(self.use_keyfile_checkbox, 1, 0)
        options_grid.addWidget(self.secure_delete_after_decrypt_checkbox, 1, 1)

        layout.addLayout(options_grid)

# Keyfile button
        self.keyfile_button = QPushButton("Select Keyfile")
        self.keyfile_button.setEnabled(False)
        self.keyfile_button.clicked.connect(self.select_keyfile)
        layout.addWidget(self.keyfile_button)

        

        # Buttons (Encrypt/Decrypt)
       
        button_layout = QHBoxLayout()

        self.encrypt_button = QPushButton("Encrypt")
        self.decrypt_button = QPushButton("Decrypt")
        self.verify_button = QPushButton("Verify")

        self.encrypt_button.clicked.connect(self.start_encrypt)
        self.decrypt_button.clicked.connect(self.start_decrypt)
        self.verify_button.clicked.connect(self.start_verify)

        self.encrypt_button.setEnabled(False)
        self.decrypt_button.setEnabled(False)
        self.verify_button.setEnabled(False)

        button_layout.addWidget(self.encrypt_button)
        button_layout.addWidget(self.decrypt_button)
        button_layout.addWidget(self.verify_button)

        layout.addLayout(button_layout)

        # Processing progress bar (visible only during process)
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)

        # Status label
        self.status_label = QLabel("")
        self.status_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.status_label)

        # View Audit Log Button
        self.view_log_button = QPushButton("View Secure Audit Log")
        self.view_log_button.clicked.connect(self.show_audit_log)
        layout.addWidget(self.view_log_button)

        self.update_algorithm_badge()

    def show_about_dialog(self):
       dialog = QDialog(self)
       dialog.setWindowTitle("About Cryptix")
       dialog.setMinimumWidth(600)
       dialog.setMinimumHeight(450)

       layout = QVBoxLayout(dialog)
       layout.setContentsMargins(20, 20, 20, 20)

       about_text = QTextEdit()
       about_text.setReadOnly(True)
       about_text.setStyleSheet("""
        QTextEdit {
            background-color: #0B0F19;
            border: none;
            color: #E2E8F0;
            font-family: Consolas, monospace;
            font-size: 13px;
            line-height: 150%;
        }
    """)

       about_text.setHtml(f"""
        <h2 style="color:#00F0FF;">CRYPTIX v{self.version}</h2>

        <b>Encryption Engine:</b><br>
        • AES‑256‑GCM<br>
        • ChaCha20‑Poly1305<br>
        • Argon2id (100MB memory‑hard key derivation)<br><br>

        <b>Security Features:</b><br>
        • Authenticated Encryption (AEAD)<br>
        • Metadata Authentication (AAD)<br>
        • Integrity Verification Mode<br>
        • Secure Delete Option<br>
        • Keyfile Support<br>
        • Lockout Protection (Anti‑Brute Force)<br><br>

        <b>Threat Model:</b><br>
        Cryptix protects files against unauthorized access and tampering.<br>
        It verifies integrity and detects wrong passwords or modified files.<br>
        It does <b>NOT</b> protect against full system compromise or malware.<br><br>

        <hr>
        <center>© 2026 Cryptix Project</center>
    """)

       layout.addWidget(about_text)

       close_button = QPushButton("Close")
       close_button.setMinimumHeight(32)
       close_button.clicked.connect(dialog.close)
       layout.addWidget(close_button)

       dialog.exec()

    def set_ui_state(self, state: str):
        """
        state can be:
        READY
        PROCESSING
        LOCKED
        """

        if state == "READY":
            self.encrypt_button.setEnabled(True)
            self.decrypt_button.setEnabled(True)
            self.password_input.setEnabled(True)
            self.confirm_input.setEnabled(True)
            self.use_keyfile_checkbox.setEnabled(True)

            if self.use_keyfile_checkbox.isChecked():
                self.keyfile_button.setEnabled(True)

            self.status_led.setText("● READY")
            self.status_led.setStyleSheet("color: #00FF66; font-weight: bold;")

        elif state == "PROCESSING":
            self.encrypt_button.setEnabled(False)
            self.decrypt_button.setEnabled(False)
            self.password_input.setEnabled(False)
            self.confirm_input.setEnabled(False)
            self.use_keyfile_checkbox.setEnabled(False)
            self.keyfile_button.setEnabled(False)

            self.status_led.setText("● PROCESSING")
            self.status_led.setStyleSheet("color: #FFD700; font-weight: bold;")

        elif state == "LOCKED":
            self.encrypt_button.setEnabled(False)
            self.decrypt_button.setEnabled(False)
            self.password_input.setEnabled(False)
            self.confirm_input.setEnabled(False)
            self.use_keyfile_checkbox.setEnabled(False)
            self.keyfile_button.setEnabled(False)

            self.status_led.setText("● LOCKED")
            self.status_led.setStyleSheet("color: #FF3B3B; font-weight: bold;")

    def toggle_settings_panel(self):
     if self.settings_panel.isVisible():
         self.settings_panel.hide()
     else:
        # Position under hamburger button
        button_pos = self.menu_button.mapToGlobal(self.menu_button.rect().bottomLeft())
        window_pos = self.mapFromGlobal(button_pos)

        self.settings_panel.move(window_pos.x() - 200, window_pos.y())
        self.settings_panel.show()

    # =====================================================
    # Lockout System
    # =====================================================
    def trigger_lockout(self):
        self.is_locked = True
        self.lock_seconds_remaining = 30
        self.password_input.setEnabled(False)
        self.confirm_input.setEnabled(False)
        self.decrypt_button.setEnabled(False)
        self.use_keyfile_checkbox.setEnabled(False) # Disable keyfile options during lock
        self.keyfile_button.setEnabled(False)

        self.status_label.setText(
            f"Too many failed attempts. Try again in {self.lock_seconds_remaining}s"
        )
        self.lock_timer.start(1000) # Update countdown every second
        self.set_ui_state("LOCKED")
        self.status_led.setStyleSheet("color: #FF3B3B; font-weight: bold;")

    def update_countdown(self):
     self.lock_seconds_remaining -= 1

     if self.lock_seconds_remaining <= 0:
        self.lock_timer.stop()
        self.failed_attempts = 0
        self.is_locked = False

        self.status_led.setText("● READY")
        self.status_led.setStyleSheet("color: #00FF66; font-weight: bold;")

        self.password_input.setEnabled(True)
        self.confirm_input.setEnabled(True)
        self.use_keyfile_checkbox.setEnabled(True)

        if self.use_keyfile_checkbox.isChecked():
            self.keyfile_button.setEnabled(True)

        self.status_label.setText("You may try again.")
        self.validate_inputs()

     else:
        self.status_label.setText(
            f"Too many failed attempts. Try again in {self.lock_seconds_remaining}s"
        )
    # =====================================================
    # Theme Management
    # =====================================================
    def toggle_theme(self):
        if self.theme_toggle.isChecked():
            self.apply_dark_theme()
        else:
            self.apply_light_theme()

    def apply_dark_theme(self):
        self.setStyleSheet("""
            /* --- GLOBAL APP BACKGROUND --- */
            QWidget { 
                background-color: #0B0F19; 
                color: #E2E8F0; 
                font-family: 'Consolas', 'Segoe UI', monospace;
                font-size: 13px;
            }

            /* --- INPUT FIELDS (Tactical Glow) --- */
            QLineEdit { 
                background-color: #131822; 
                border: 1px solid #262F3F; 
                padding: 8px; 
                border-radius: 2px;
                color: #00F0FF;
                font-weight: bold;
            }
            QLineEdit:focus {
                border: 1px solid #00F0FF;
                background-color: #0F131C;
            }

            /* --- BUTTONS (Hardware Style) --- */
            QPushButton { 
                background-color: #1A212D; 
                border: 1px solid #333F54; 
                padding: 8px; 
                border-radius: 2px;
                font-weight: bold;
                letter-spacing: 1px;
                color: #FFFFFF;
            }
            QPushButton:hover { 
                background-color: #242D3E; 
                border: 1px solid #00F0FF;
                color: #00F0FF;
        }
            QPushButton:pressed {
                background-color: #00F0FF;
                color: #000000;
            }
            QPushButton:disabled { 
                background-color: #0F131A; 
                border: 1px solid #1C222E;
                color: #4A5568; 
            }

            /* --- ALGORITHM DROPDOWN (QComboBox) --- */
            QComboBox {
                background-color: #131822;
                border: 1px solid #262F3F;
                padding: 6px;
                border-radius: 2px;
                color: #00F0FF;
                font-weight: bold;
            }
            QComboBox:focus {
                border: 1px solid #00F0FF;
            }
            QComboBox::drop-down {
                border-left: 1px solid #262F3F;
                width: 25px;
            }
            QComboBox QAbstractItemView {
                background-color: #131822;
                border: 1px solid #00F0FF;
                selection-background-color: #242D3E;
                selection-color: #00F0FF;
                color: #E2E8F0;
            }

            /* --- HAMBURGER MENU BUTTON --- */
            QPushButton#menu_btn {
                background-color: transparent;
                border: none;
                color: #00F0FF;
                font-size: 18px;
            }
            QPushButton#menu_btn:hover {
                background-color: #131822;
                border-radius: 2px;
            }

            /* --- SETTINGS HUD OVERLAY --- */
            QWidget#settings_hud {
                background-color: #0F131C;
                border: 1px solid #00F0FF;
                border-radius: 2px;
            }

            /* --- PROGRESS BAR (Matrix Line) --- */
            QProgressBar { 
                background-color: #131822; 
                border: 1px solid #262F3F; 
                border-radius: 2px;
                text-align: center;
                color: #FFFFFF;
                font-weight: bold;
            }
            QProgressBar::chunk { 
                background-color: #00FF66; 
            }

            /* --- CHECKBOXES --- */
            QCheckBox {
                color: #A0AEC0;
                font-weight: bold;
            }
            QCheckBox::indicator {
                width: 16px;
                height: 16px;
                background-color: #131822;
                border: 1px solid #262F3F;
                border-radius: 2px;
            }
            QCheckBox::indicator:checked {
                background-color: #00F0FF;
                border: 1px solid #00F0FF;
            }

            /* --- LABELS --- */
            QLabel {
                color: #A0AEC0;
                font-weight: bold;
            }

            /* --- AUDIT LOG DIALOG --- */
            QTextEdit {
                background-color: #0B0F19;
                border: 1px solid #00F0FF;
                color: #00FF66;
                font-family: 'Consolas', monospace;
            }
        """)

    def apply_light_theme(self):
        # Reset stylesheet to default or apply a light theme
        self.setStyleSheet("") # This will remove custom styling, revert to system default/light
        # For a custom light theme, you'd define CSS here similar to apply_dark_theme
        # Example light theme:
        # self.setStyleSheet("""
        #    QWidget { background-color: #F0F0F0; color: #121212; }
        #    QLineEdit { background-color: #FFFFFF; border: 1px solid #CCC; padding: 6px; border-radius: 4px; }
        #    QPushButton { background-color: #E0E0E0; border: 1px solid #BBB; padding: 6px; border-radius: 4px; }
        #    QPushButton:hover { background-color: #D0D0D0; }
        #    QPushButton:disabled { background-color: #F8F8F8; color: #AAA; }
        #    QProgressBar { background-color: #FFFFFF; border: 1px solid #CCC; }
        #    QProgressBar::chunk { background-color: #008CBA; }
        # """)

    # =====================================================
    # Input/Validation Logic
    # =====================================================

    def toggle_keyfile_option(self):
        enabled = self.use_keyfile_checkbox.isChecked()
        self.keyfile_button.setEnabled(enabled)
        if not enabled:
            self.keyfile_path = None # Clear keyfile path if option unchecked
            self.validate_inputs() # Re-validate buttons

    def select_keyfile(self):
        keyfile_path, _ = QFileDialog.getOpenFileName(self, "Select Keyfile")
        if keyfile_path:
            self.keyfile_path = keyfile_path
            self.keyfile_button.setText(os.path.basename(keyfile_path)) # Show keyfile name
        else:
            self.keyfile_path = None # Clear if no keyfile selected
            self.keyfile_button.setText("Select Keyfile")
            self.validate_inputs() # Re-validate buttons

    def validate_inputs(self):
        password = self.password_input.text()
        confirm_password = self.confirm_input.text()

        self.confirm_input.setStyleSheet("")

        if confirm_password and confirm_password != password:
           self.confirm_input.setStyleSheet(
           "border: 2px solid red; border-radius: 4px;"
        )

        encrypt_valid = (
        self.file_path
        and password
        and password == confirm_password
        and self.password_input.isEnabled()
    )

        decrypt_valid = (
        self.file_path
        and password
        and self.password_input.isEnabled()
    )

        self.encrypt_button.setEnabled(bool(encrypt_valid))
        self.decrypt_button.setEnabled(bool(decrypt_valid))
        self.verify_button.setEnabled(bool(self.file_path and password))
    def update_strength(self):
        password = self.password_input.text()

        for bar in (self.bar1, self.bar2, self.bar3):
            bar.setStyleSheet("background-color: lightgray; border-radius: 3px;")

        if len(password) >= 1:
            self.bar1.setStyleSheet("background-color: red; border-radius: 3px;")

        if len(password) >= 4:
            self.bar2.setStyleSheet("background-color: orange; border-radius: 3px;")

        if len(password) >= 8:
            self.bar3.setStyleSheet("background-color: green; border-radius: 3px;")
     
    def toggle_password_visibility(self):
     mode = (
        QLineEdit.EchoMode.Normal
        if self.show_password.isChecked()
        else QLineEdit.EchoMode.Password
    )
     self.password_input.setEchoMode(mode)
     self.confirm_input.setEchoMode(mode)
    # =====================================================
    # Worker Thread Management
    # =====================================================
    def start_encrypt(self):
        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.set_ui_state("PROCESSING")
        
        # Read keyfile data if selected
        keyfile_data = None
        if self.use_keyfile_checkbox.isChecked() and self.keyfile_path:
            with open(self.keyfile_path, "rb") as f:
                keyfile_data = f.read()

        algorithm = self.algorithm_selector.currentData()

        self.worker = WorkerThread(
            "encrypt",
            self.file_path,
            self.password_input.text(),
            keyfile_data,
            algorithm
        )
        self.worker.secure_delete = self.secure_delete_checkbox.isChecked()

        self.worker.progress.connect(self.update_progress)
        self.worker.finished.connect(self.on_success)
        self.worker.error.connect(self.on_error)

        self.worker.start()
    def update_progress(self, value):
        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(value)

    def start_decrypt(self):
        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.set_ui_state("PROCESSING")
        
        # Read keyfile data if selected
        keyfile_data = None
        if self.use_keyfile_checkbox.isChecked() and self.keyfile_path:
            with open(self.keyfile_path, "rb") as f:
                keyfile_data = f.read()

        self.worker = WorkerThread("decrypt", self.file_path, self.password_input.text(), keyfile_data)
        self.worker.secure_delete_encrypted = self.secure_delete_after_decrypt_checkbox.isChecked()
        self.worker.progress.connect(self.update_progress)
        self.worker.finished.connect(self.on_success)
        self.worker.error.connect(self.on_error)
        self.worker.start()

    def start_verify(self):
        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.set_ui_state("PROCESSING")

        keyfile_data = None
        if self.use_keyfile_checkbox.isChecked() and self.keyfile_path:
            with open(self.keyfile_path, "rb") as f:
                keyfile_data = f.read()

        self.worker = WorkerThread(
        "verify",
        self.file_path,
        self.password_input.text(),
        keyfile_data
    )

        self.worker.progress.connect(self.update_progress)
        self.worker.finished.connect(self.on_success)
        self.worker.error.connect(self.on_error)

        self.worker.start()

    def update_progress(self, value):
        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(value)

    def set_ui_busy_state(self, busy):
        self.encrypt_button.setEnabled(not busy)
        self.decrypt_button.setEnabled(not busy)
        
        # Updated to the 3 new buttons
        self.select_file_button.setEnabled(not busy)
        self.select_folder_button.setEnabled(not busy)
        self.select_image_button.setEnabled(not busy)
        
        self.password_input.setEnabled(not busy)
        self.confirm_input.setEnabled(not busy)
        self.use_keyfile_checkbox.setEnabled(not busy)
        self.keyfile_button.setEnabled(not busy)
        self.show_password.setEnabled(not busy)

    def on_success(self, result):
        self.progress_bar.setVisible(False)
        self.failed_attempts = 0 # Reset failed attempts on success
        self.status_label.setText(f"Success: {result}")
        if not self.is_locked:
         self.set_ui_state("READY")
        self.status_led.setStyleSheet("color: #00FF66; font-weight: bold;")
        self.set_ui_busy_state(False) # Re-enable UI
        self.validate_inputs() # Re-validate buttons based on current state
        self.keyfile_path = None


         # ---> ADD THIS LINE <---
        action = self.worker.mode.upper()
        log_event(f"{action} SUCCESS", f"Target: {result}")

         # Secure wipe password fields
        self.password_input.clear()
        self.confirm_input.clear()
        self.worker.password = None
        
       # Reset keyfile UI & state
        self.keyfile_path = None
        self.use_keyfile_checkbox.setChecked(False)
        self.keyfile_button.setText("Select Keyfile")
        self.keyfile_button.setEnabled(False)

        QMessageBox.information(self, "Success", "Operation completed successfully!")

    def on_error(self, message):
        self.progress_bar.setVisible(False)
        self.status_label.setText(f"ERROR: {str(message)}")
        self.set_ui_busy_state(False)
        self.validate_inputs()
        self.worker.password = None

        # Structured authentication failure detection
        if self.worker.mode in ["decrypt", "verify"] and isinstance(message, AuthenticationError):
            self.failed_attempts += 1
            if self.failed_attempts >= 3:
                self.trigger_lockout()

        QMessageBox.critical(self, "Error", str(message))

        # Reset keyfile UI & state
        self.keyfile_path = None
        self.use_keyfile_checkbox.setChecked(False)
        self.keyfile_button.setText("Select Keyfile")
        self.keyfile_button.setEnabled(False)
        self.password_input.clear()
        self.confirm_input.clear()

        if not self.is_locked:
            self.status_led.setText("● READY")
            self.status_led.setStyleSheet("color: #00FF66; font-weight: bold;")
    def update_algorithm_badge(self):
     algo = self.algorithm_selector.currentData()

     if algo == ALGO_AES:
        self.algorithm_badge.setText("AES")
        self.algorithm_badge.setStyleSheet(
            "background-color: #00F0FF; color: #000000; padding: 4px 8px; border-radius: 3px; font-weight: bold;"
        )
     else:
        self.algorithm_badge.setText("CHACHA")
        self.algorithm_badge.setStyleSheet(
            "background-color: #00FF66; color: #000000; padding: 4px 8px; border-radius: 3px; font-weight: bold;"
        )

    def select_file(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Select File")
        if file_path:
            self.file_path = file_path
            self.file_label.setText(f"Selected file: {os.path.basename(file_path)}")
            self.validate_inputs()


    def select_folder(self):
        folder_path = QFileDialog.getExistingDirectory(self, "Select Folder")
        if folder_path:
            self.file_path = folder_path
            self.file_label.setText(f"Selected folder: {os.path.basename(folder_path)}")
            self.validate_inputs()


    def select_image(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Image",
            "",
            "Images (*.png *.jpg *.jpeg *.bmp *.gif)"
        )
        if file_path:
            self.file_path = file_path
            self.file_label.setText(f"Selected image: {os.path.basename(file_path)}")
            self.validate_inputs()

    