
import os
import requests
from utils.helpers import evaluate_password_strength
from core.logger import read_secure_log, log_event, clear_secure_log
from PySide6.QtWidgets import QComboBox, QGridLayout
from core.file_handler import (
    encrypt_path,
    decrypt_path,
    verify_path,
    ALGO_AES,
    ALGO_CHACHA,
    ALGO_XCHACHA,
    AuthenticationError
)
from cryptix_engine.reports import IntegrityReport

from utils.settings import load_settings, save_settings

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
from cryptix_engine.container import analyze_container_structure
from cryptix_engine.constants import algorithm_name
from cryptix_engine.container import parse_header
from cryptix_engine.aead import verify_stream
from cryptix_engine.kdf import derive_key
from cryptix_engine.exceptions import AuthenticationError
from io import BytesIO
from cryptix_engine.container import generate_fingerprint




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
    finished = Signal(object)
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
        self.return_report = False

    def run(self):
        try:
            if self.mode == "benchmark":
                from utils.performance import run_calibration
                profile = run_calibration()
                result = (
                    f"Performance Calibration Complete!\n\n"
                    f"Argon2id KDF Latency: {profile.kdf_latency_s} s\n"
                    f"AES-256-GCM Speed: {profile.aes_mb_s} MB/s\n"
                    f"ChaCha20-Poly1305 Speed: {profile.chacha_mb_s} MB/s\n\n"
                    f"These hardware metrics have been cached for Simulation Mode."
                )
                self.finished.emit(result)
                return

            result = None

            if self.mode == "encrypt":
                if isinstance(self.file_path, list):
                    results = []
                    for path in self.file_path:
                        r = encrypt_path(
                            path,
                            self.password,
                            self.keyfile_data,
                            self.algorithm,
                            progress_callback=self.progress.emit,
                            secure_delete_original=self.secure_delete
                        )
                        results.append(r)

                    if len(results) == 1:
                        result = f"{os.path.basename(self.file_path[0])} encrypted successfully."
                    else:
                        result = f"{len(results)} files encrypted successfully."
                else:
                    result = encrypt_path(
                        self.file_path,
                        self.password,
                        self.keyfile_data,
                        self.algorithm,
                        progress_callback=self.progress.emit,
                        secure_delete_original=self.secure_delete
                    )

            elif self.mode == "decrypt":
                if isinstance(self.file_path, list):
                    results = []
                    for path in self.file_path:
                        r = decrypt_path(
                            path,
                            self.password,
                            self.keyfile_data,
                            progress_callback=self.progress.emit,
                            secure_delete_encrypted=self.secure_delete_encrypted
                        )
                        results.append(r)

                    if len(results) == 1:
                        result = f"{os.path.basename(self.file_path[0])} decrypted successfully."
                    else:
                        result = f"{len(results)} files decrypted successfully."
                else:
                    result = decrypt_path(
                        self.file_path,
                        self.password,
                        self.keyfile_data,
                        progress_callback=self.progress.emit,
                        secure_delete_encrypted=self.secure_delete_encrypted
                    )

            elif self.mode == "verify":
                if isinstance(self.file_path, list):
                    results = []
                    for path in self.file_path:
                        r = verify_path(
                            path,
                            self.password,
                            self.keyfile_data,
                            progress_callback=self.progress.emit,
                            return_report=self.return_report
                        )
                        results.append(r)

                    if len(results) == 1:
                        result = results[0]
                    else:
                        result = results  # we won’t handle multi-report UI yet
                else:
                    result = verify_path(
                        self.file_path,
                        self.password,
                        self.keyfile_data,
                        progress_callback=self.progress.emit,
                        return_report=self.return_report
                    )

            # Clear sensitive reference
            self.password = None

            self.finished.emit(result)

        except Exception as e:
            self.error.emit(e)  # <-- Now passing the actual Error Object
# =========================================================
# Main Window (CRYPTIX CORE Application)
# =========================================================
class MainWindow(QMainWindow):
    def __init__(self, initial_file=None):
        super().__init__()

        self.version = "1.4.0"
        self.setWindowTitle("Cryptix Core")
        import sys
        import os
        from PySide6.QtGui import QIcon

        if getattr(sys, 'frozen', False):
          base_path = sys._MEIPASS
        else:
          base_path = os.path.abspath(".")

        icon_path = os.path.join(base_path, "cryptix.ico")
        self.setWindowIcon(QIcon(icon_path))
        self.resize(650, 600)

       

        self.file_path = None
        self.settings = load_settings()
        if initial_file and os.path.isfile(initial_file):
            self.file_path = initial_file
        self.keyfile_path = None # New: keyfile_path
        self.failed_attempts = 0
        self.lock_seconds_remaining = 0
        self.is_locked = False
        self.last_integrity_report = None

        self.drag_active = False
        
        self.lock_timer = QTimer()
        self.lock_timer.timeout.connect(self.update_countdown)

        self.init_ui()
        QTimer.singleShot(2000, self.check_for_updates)
        if "hardware_profile" not in self.settings:
            QTimer.singleShot(3500, self.prompt_calibration)
        self.setAcceptDrops(True)

    def show_audit_log(self):
        log_content = read_secure_log()

        dialog = QDialog(self)
        dialog.setWindowTitle("Cryptix Core - Encrypted Audit Log")
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
        # --- Drag Overlay ---
        self.drag_overlay = QLabel("Drop File Here", central_widget)
        self.drag_overlay.setAlignment(Qt.AlignCenter)
        self.drag_overlay.setStyleSheet("""
            QLabel {
                background-color: rgba(11, 15, 25, 180);
                border: 2px dashed #00F0FF;
                color: #00F0FF;
                font-size: 22px;
                font-weight: bold;
            }
        """)
        self.drag_overlay.hide()

        layout = QVBoxLayout()
        layout.setSpacing(12)
        layout.setContentsMargins(30, 20, 30, 20)
        central_widget.setLayout(layout)

        header_container = QHBoxLayout()

# LEFT SECTION
        left_layout = QHBoxLayout()
        title = QLabel("🛡 CRYPTIX CORE")
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
        self.settings_panel.setFixedWidth(300)
        self.settings_panel.setFixedHeight(260)

        settings_layout = QVBoxLayout()
        self.settings_panel.setLayout(settings_layout)

     # Encryption Method Selector
        self.algorithm_selector = QComboBox()
        self.algorithm_selector.addItem("AES-256-GCM", ALGO_AES)
        self.algorithm_selector.addItem("ChaCha20-Poly1305", ALGO_CHACHA)
        self.algorithm_selector.addItem("XChaCha20-Poly1305", ALGO_XCHACHA)
        self.algorithm_selector.currentIndexChanged.connect(self.update_algorithm_badge)
        settings_layout.addWidget(QLabel("Encryption Method"))
        settings_layout.addWidget(self.algorithm_selector)

        # Dark Mode Toggle
        self.theme_toggle = AnimatedToggle()
        self.theme_toggle.setChecked(True)
        self.theme_toggle.stateChanged.connect(self.toggle_theme)
        settings_layout.addWidget(QLabel("Dark Mode"))
        settings_layout.addWidget(self.theme_toggle)

        # Learning Mode Toggle
        self.learning_toggle = AnimatedToggle()
        self.learning_toggle.setChecked(False)
        self.learning_toggle.stateChanged.connect(self.toggle_learning_mode)
        settings_layout.addWidget(QLabel("Learning Mode (Academy)"))
        settings_layout.addWidget(self.learning_toggle)

        # About Button
        self.about_button = QPushButton("About Cryptix Core")
        self.about_button.setStyleSheet("color: #00F0FF;")
        self.about_button.clicked.connect(self.show_about_dialog)
        settings_layout.addWidget(self.about_button)

        self.benchmark_button = QPushButton("Run Performance Benchmark")
        self.benchmark_button.setStyleSheet("color: #00F0FF;")
        self.benchmark_button.clicked.connect(self.start_benchmark)
        settings_layout.addWidget(self.benchmark_button)
        # Subtitle
        subtitle = QLabel("AES‑256 GCM Secure Encryption")
        subtitle.setStyleSheet("color: gray; font-size: 11px;")
        layout.addWidget(subtitle)

        # File selection
        subtitle = QLabel(f"Cryptix Core  |  AES‑256 GCM & ChaCha20  |  v{self.version}")
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
        self.generate_password_button = QPushButton("🔑")
        self.generate_password_button.setFixedWidth(40)
        self.generate_password_button.setToolTip("Generate Secure Password")
        self.generate_password_button.clicked.connect(self.generate_password)
        password_row.addWidget(self.generate_password_button)
        divider1 = QFrame()
        divider1.setFrameShape(QFrame.Shape.HLine)
        divider1.setStyleSheet("background-color: #262F3F; max-height: 1px;")
        layout.addWidget(divider1)

       # Strength bars (vertical beside password)

        layout.addLayout(password_row)
        # --- Password Strength Bar (full width below password) ---
        # --- Password Strength Bar (short and aligned left) ---
        self.strength_bar = QProgressBar()
        self.strength_bar.setRange(0, 100)
        self.strength_bar.setValue(0)
        self.strength_bar.setFixedHeight(6)
        self.strength_bar.setFixedWidth(120)   # Adjust width here (try 100–150)
        self.strength_bar.setTextVisible(False)
        self.strength_bar.hide()  # Hidden by default

        strength_row = QHBoxLayout()
        strength_row.addWidget(self.strength_bar)
        strength_row.addStretch()  # Keeps it aligned left

        layout.addLayout(strength_row)
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
            "Secure Delete After Decryption"
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

        # Persist settings when changed
        self.theme_toggle.stateChanged.connect(self.persist_settings)
        self.algorithm_selector.currentIndexChanged.connect(self.persist_settings)
        self.secure_delete_checkbox.stateChanged.connect(self.persist_settings)
        self.secure_delete_after_decrypt_checkbox.stateChanged.connect(self.persist_settings)
        self.learning_toggle.stateChanged.connect(self.persist_settings)

        # Pre-Flight Intelligence Row
        preflight_layout = QHBoxLayout()
        preflight_layout.setSpacing(10)

        self.simulate_button = QPushButton("📊 Run Pre-Flight Simulation")
        self.simulate_button.setToolTip("Estimate time, container sizing, and memory peaks before encryption.")
        self.simulate_button.setEnabled(False)
        self.simulate_button.clicked.connect(self.start_simulation)
        self.simulate_button.setStyleSheet("color: #00F0FF; border: 1px dashed #262F3F;")

        self.assess_button = QPushButton("🛡️ Open Security Advisor")
        self.assess_button.setToolTip("Evaluate password entropy and security risk profiles.")
        self.assess_button.clicked.connect(self.start_assessment)
        self.assess_button.setStyleSheet("color: #00FF66; border: 1px dashed #262F3F;")

        preflight_layout.addWidget(self.simulate_button)
        preflight_layout.addWidget(self.assess_button)
        layout.addLayout(preflight_layout)

        # Divider between Pre-Flight and Core Action buttons
        divider3 = QFrame()
        divider3.setFrameShape(QFrame.Shape.HLine)
        divider3.setStyleSheet("background-color: #262F3F; max-height: 1px;")
        layout.addWidget(divider3)

        # Core Action Buttons (Encrypt/Decrypt/Verify/Analyze)
        button_layout = QHBoxLayout()
        button_layout.setSpacing(8)

        self.encrypt_button = QPushButton("Encrypt")
        self.decrypt_button = QPushButton("Decrypt")
        self.verify_button = QPushButton("Verify")
        self.analyze_button = QPushButton("Analyze")

        self.encrypt_button.clicked.connect(self.start_encrypt)
        self.decrypt_button.clicked.connect(self.start_decrypt)
        self.verify_button.clicked.connect(self.start_verify)
        self.analyze_button.clicked.connect(self.start_analyze)

        self.encrypt_button.setEnabled(False)
        self.decrypt_button.setEnabled(False)
        self.verify_button.setEnabled(False)
        self.analyze_button.setEnabled(False)

        button_layout.addWidget(self.encrypt_button)
        button_layout.addWidget(self.decrypt_button)
        button_layout.addWidget(self.verify_button)
        button_layout.addWidget(self.analyze_button)
        
        layout.addLayout(button_layout)

        # Processing progress bar (visible only during process)
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)

        # Status label
        self.status_label = QLabel("")
        self.status_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.status_label)

        # Cryptix Academy Button (Hidden by default, shown when learning mode toggle is on)
        self.academy_button = QPushButton("🎓 Open Cryptix Academy")
        self.academy_button.setStyleSheet("color: #00F0FF; background-color: #131822; border: 1px solid #00F0FF; font-weight: bold; padding: 10px;")
        self.academy_button.clicked.connect(self.start_academy)
        self.academy_button.hide()
        layout.addWidget(self.academy_button)

        # View Audit Log Button
        self.view_log_button = QPushButton("View Secure Audit Log")
        self.view_log_button.clicked.connect(self.show_audit_log)
        layout.addWidget(self.view_log_button)
        # Handle file passed via file association
        if self.file_path:
            self.file_label.setText(f"Selected: {os.path.basename(self.file_path)}")
            self.validate_inputs()

        self.update_algorithm_badge()

        # Apply saved settings
        if self.settings.get("dark_mode", True):
            self.theme_toggle.setChecked(True)
            self.apply_dark_theme()
        else:
            self.theme_toggle.setChecked(False)
            self.apply_light_theme()

        saved_algorithm = self.settings.get("algorithm")
        if saved_algorithm:
            index = self.algorithm_selector.findData(saved_algorithm)
            if index != -1:
                self.algorithm_selector.setCurrentIndex(index)

        self.secure_delete_checkbox.setChecked(
            self.settings.get("secure_delete_encrypt", False)
        )

        self.secure_delete_after_decrypt_checkbox.setChecked(
            self.settings.get("secure_delete_decrypt", False)
        )

        self.learning_toggle.setChecked(
            self.settings.get("learning_mode", False)
        )
        self.toggle_learning_mode()

        self.drag_overlay.resize(self.centralWidget().size())

    def start_benchmark(self):
        self.worker = WorkerThread("benchmark", None, None)
        self.worker.finished.connect(self.on_benchmark_result)
        self.worker.error.connect(self.on_error)
        self.worker.start()    

    def generate_password(self):
        import secrets
        import string

        alphabet = string.ascii_letters + string.digits + "!@#$%^&*()_+-="
        password = ''.join(secrets.choice(alphabet) for _ in range(20))

        self.password_input.setText(password)
        self.confirm_input.setText(password)

    # Make password visible temporarily
        self.password_input.setEchoMode(QLineEdit.EchoMode.Normal)
        self.confirm_input.setEchoMode(QLineEdit.EchoMode.Normal)
        self.show_password.setChecked(True)

    def show_about_dialog(self):
       dialog = QDialog(self)
       dialog.setWindowTitle("About Cryptix Core")
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
        <h2 style="color:#00F0FF;">CRYPTIX CORE v{self.version}</h2>

        <b>Platform:</b><br>
        Cryptix Core is the desktop application of the Cryptix Platform.<br>
        It is powered by the Cryptix Engine.<br><br>

        <b>Core Capabilities:</b><br>
        • File & Folder Encryption<br>
        • Container Structure Analysis<br>
        • Authenticated Container Analysis<br>
        • Deterministic Container Fingerprint<br>
        • Security Advisor (Pre‑Encryption Assessment)<br>
        • Pre-Flight Simulation Mode (Hardware Calibration)<br><br>

        <b>Cryptographic Primitives:</b><br>
        • AES‑256‑GCM (AEAD, 12-byte nonce)<br>
        • ChaCha20‑Poly1305 (AEAD, 12-byte nonce)<br>
        • XChaCha20‑Poly1305 (Collision-Resistant AEAD, 24-byte nonce)<br>
        • Argon2id (100MB memory‑hard key derivation)<br><br>

        <b>Explainable Security Principle:</b><br>
        Every cryptographic decision made by Cryptix Core can be explained.<br>
        The engine produces structured security facts; the application presents them clearly.<br><br>

        <b>Security Boundaries:</b><br>
        Cryptix Core protects against offline access and tampering.<br>
        It does <b>NOT</b> protect against active malware or OS compromise.<br><br>

        <hr>
        <hr>
        <b>Author:</b><br>
        Michel Idriss<br><br>

        <b>Project:</b><br>
        Cryptix Platform<br><br>

        <hr>
        <center>© 2026 Cryptix Platform</center>
        """)

       layout.addWidget(about_text)

       close_button = QPushButton("Close")
       close_button.setMinimumHeight(32)
       close_button.clicked.connect(dialog.close)
       layout.addWidget(close_button)

       dialog.exec()

    def check_for_updates(self):
        try:
            response = requests.get(
                "https://api.github.com/repos/SPMI237/cryptix/releases/latest",
                timeout=5
            )

            if response.status_code == 200:
                latest_version = response.json()["tag_name"].lstrip("v")
                current_version = self.version

                if latest_version != current_version:
                    reply = QMessageBox.information(
                        self,
                        "Update Available",
                        f"A new version of Cryptix Core (v{latest_version}) is available.\n\nVisit download page?",
                        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
                    )

                    if reply == QMessageBox.StandardButton.Yes:
                        import webbrowser
                        webbrowser.open("https://github.com/SPMI237/cryptix/releases")

        except Exception:
            pass  # Fail silently if no internet or error   

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


    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
            self.drag_overlay.resize(self.centralWidget().size())
            self.drag_overlay.raise_()   # ✅ Bring overlay to front
            self.drag_overlay.show()
        else:
            event.ignore()

    def dragLeaveEvent(self, event):
        self.drag_overlay.hide()

    def dropEvent(self, event):
        urls = event.mimeData().urls()
        if urls:
            file_path = urls[0].toLocalFile()
            if os.path.exists(file_path):
                self.file_path = file_path
                self.file_label.setText(f"Selected: {os.path.basename(file_path)}")
                self.validate_inputs()

        self.drag_overlay.hide()        

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, "drag_overlay"):
            self.drag_overlay.resize(self.centralWidget().size()) 

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
        self.simulate_button.setEnabled(bool(encrypt_valid))
        if isinstance(self.file_path, list):
            enable_analyze = (
                len(self.file_path) == 1 and
                str(self.file_path[0]).endswith(".cryptix")
            )
        else:
            enable_analyze = (
                self.file_path and
                str(self.file_path).endswith(".cryptix")
            )

        self.analyze_button.setEnabled(bool(enable_analyze))
    def update_strength(self):
        password = self.password_input.text()

        if not password:
            self.strength_bar.hide()
            self.strength_bar.setValue(0)
            return

        self.strength_bar.show()

        strength = evaluate_password_strength(password)

    # Map strength to percentage
        if strength == 0:
            score = 0
        elif strength == 1:
            score = 25
        elif strength == 2:
            score = 50
        elif strength == 3:
            score = 75
        else:
            score = 100

        self.strength_bar.setValue(score)

    # Color selection
        if score <= 25:
            color = "#FF3B3B"
        elif score <= 50:
            color = "#FFA500"
        elif score <= 75:
            color = "#00FF66"
        else:
            color = "#00CC00"

        self.strength_bar.setStyleSheet(f"""
            QProgressBar {{
                background-color: #131822;
                border: 1px solid #262F3F;
                border-radius: 2px;
            }}
            QProgressBar::chunk {{
                background-color: {color};
            }}
        """)
     
    def toggle_password_visibility(self):
     mode = (
        QLineEdit.EchoMode.Normal
        if self.show_password.isChecked()
        else QLineEdit.EchoMode.Password
    )
     self.password_input.setEchoMode(mode)
     self.confirm_input.setEchoMode(mode)

    def persist_settings(self):
        # Load existing settings first to preserve other keys (like hardware_profile and learning_profile)
        data = load_settings()
        data["dark_mode"] = self.theme_toggle.isChecked()
        data["learning_mode"] = self.learning_toggle.isChecked()
        data["algorithm"] = self.algorithm_selector.currentData()
        data["secure_delete_encrypt"] = self.secure_delete_checkbox.isChecked()
        data["secure_delete_decrypt"] = self.secure_delete_after_decrypt_checkbox.isChecked()
        save_settings(data)
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
        self.worker.return_report = True

        self.worker.progress.connect(self.update_progress)
        self.worker.finished.connect(self.on_success)
        self.worker.error.connect(self.on_error)

        self.worker.start()

    def start_analyze(self):
        from cryptix_engine.container import analyze_container_structure

        if isinstance(self.file_path, list):
            target = self.file_path[0]
        else:
            target = self.file_path

        try:
            with open(target, "rb") as f:
                report = analyze_container_structure(f)

            dialog = QDialog(self)
            dialog.setWindowTitle("Container Analysis")
            dialog.setMinimumWidth(450)

            layout = QVBoxLayout(dialog)

            structure_text = f"""
    Container Analysis (Structure Only)

    Container Detected: {report.container_detected}
    Header Valid: {report.header_valid}
    Format Version: {report.format_version}
    Algorithm: {algorithm_name(report.algorithm)}
    Compatible With Engine: {report.compatible}

    Integrity: Not Verified
    (Authentication required for integrity validation)

    Notes: {', '.join(report.notes) if report.notes else 'None'}
    """

            label = QLabel(structure_text)
            label.setAlignment(Qt.AlignLeft)
            layout.addWidget(label)

            button_layout = QHBoxLayout()

            auth_btn = QPushButton("Authenticate Container")
            close_btn = QPushButton("Close")

            button_layout.addWidget(auth_btn)
            button_layout.addWidget(close_btn)

            layout.addLayout(button_layout)

            auth_btn.clicked.connect(lambda: self.authenticate_container(dialog, target))
            close_btn.clicked.connect(dialog.accept)

            dialog.exec()

        except Exception as e:
            QMessageBox.critical(self, "Analysis Failed", str(e)) 

    def start_assessment(self):
        from cryptix_engine.assessment import collect_security_facts, generate_security_advice
        from cryptix_engine.constants import algorithm_name

        password = self.password_input.text()
        keyfile_present = bool(self.keyfile_path)
        algorithm = self.algorithm_selector.currentData()

        facts = collect_security_facts(password, keyfile_present, algorithm)
        advice = generate_security_advice(facts)

        dialog = QDialog(self)
        dialog.setWindowTitle("Security Advisor")
        dialog.setMinimumWidth(500)

        layout = QVBoxLayout(dialog)

        # ---- BASIC SECTION ----
        basic_text = f"""
    Security Advisor

    Password Entropy: {facts.password_entropy_bits} bits
    Keyfile Present: {facts.keyfile_present}
    Algorithm: {algorithm_name(facts.algorithm)}

    Argon2id:
    Memory: {facts.argon2_memory_mb} MB
    Iterations: {facts.argon2_time_cost}
    Parallelism: {facts.argon2_parallelism}

    Risk Profile:
    {advice["risk_profile"]}

    Recommendations:
    {', '.join(advice["recommendations"]) if advice["recommendations"] else 'None'}
    """

        basic_label = QLabel(basic_text)
        basic_label.setAlignment(Qt.AlignLeft)
        layout.addWidget(basic_label)

        # ---- EXPANDABLE SECTION ----
        extra_text = f"""
    Cryptix Core Guarantees

    ✓ Metadata authenticated
    ✓ Ciphertext authenticated
    ✓ Fail‑closed decryption
    ✓ No silent corruption

    Cryptix Core Does NOT Guarantee

    ✗ Protection against malware
    ✗ Password recovery
    ✗ Protection if password and keyfile stolen together
    """

        extra_label = QLabel(extra_text)
        extra_label.setAlignment(Qt.AlignLeft)
        extra_label.setVisible(False)
        layout.addWidget(extra_label)

        # ---- BUTTONS ----
        button_layout = QHBoxLayout()
        toggle_btn = QPushButton("Show More")
        close_btn = QPushButton("Close")

        button_layout.addWidget(toggle_btn)
        button_layout.addWidget(close_btn)
        layout.addLayout(button_layout)

        def toggle_section():
            if extra_label.isVisible():
                extra_label.setVisible(False)
                toggle_btn.setText("Show More")
                dialog.adjustSize()  # force shrink
            else:
                extra_label.setVisible(True)
                toggle_btn.setText("Show Less")
                dialog.adjustSize()  # force expand

        toggle_btn.clicked.connect(toggle_section)
        close_btn.clicked.connect(dialog.accept)

        dialog.exec()     
        
    def on_benchmark_result(self, result):
        QMessageBox.information(self, "Benchmark Complete", result)    

    def update_progress(self, value):
        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(value)

    def set_ui_busy_state(self, busy):
        self.encrypt_button.setEnabled(not busy)
        self.decrypt_button.setEnabled(not busy)
        self.simulate_button.setEnabled(not busy)
        
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
        self.failed_attempts = 0

        if not self.is_locked:
            self.set_ui_state("READY")

        self.status_led.setStyleSheet("color: #00FF66; font-weight: bold;")
        self.set_ui_busy_state(False)
        self.validate_inputs()

        # Secure wipe password fields
        self.password_input.clear()
        self.confirm_input.clear()
        if hasattr(self.worker, "password"):
            self.worker.password = None

        # Reset keyfile UI & state
        self.keyfile_path = None
        self.use_keyfile_checkbox.setChecked(False)
        self.keyfile_button.setText("Select Keyfile")
        self.keyfile_button.setEnabled(False)

        action = self.worker.mode.upper()
        log_event(f"{action} SUCCESS", f"Target: {result}")

        if self.worker.mode == "verify":
            if isinstance(result, IntegrityReport):
                self.last_integrity_report = result

            dialog = QDialog(self)
            dialog.setWindowTitle("Verification Result")
            dialog.setMinimumWidth(400)

            layout = QVBoxLayout(dialog)

            message = QLabel("File integrity verified successfully.")
            message.setAlignment(Qt.AlignCenter)
            layout.addWidget(message)

            button_layout = QHBoxLayout()
            show_details_btn = QPushButton("Show Details")
            close_btn = QPushButton("Close")

            button_layout.addWidget(show_details_btn)
            button_layout.addWidget(close_btn)
            layout.addLayout(button_layout)

            show_details_btn.clicked.connect(self.show_integrity_details)
            close_btn.clicked.connect(dialog.accept)

            dialog.exec()
            return

        # Default success popup for encrypt/decrypt
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

        if self.worker.mode == "verify":
            QMessageBox.critical(self, "Verification Failed", "Integrity check failed — file may be tampered or password incorrect.")
        else:
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
        elif algo == ALGO_CHACHA:
            self.algorithm_badge.setText("CHACHA")
            self.algorithm_badge.setStyleSheet(
                "background-color: #00FF66; color: #000000; padding: 4px 8px; border-radius: 3px; font-weight: bold;"
            )
        else:
            self.algorithm_badge.setText("XCHACHA")
            self.algorithm_badge.setStyleSheet(
                "background-color: #D300FF; color: #000000; padding: 4px 8px; border-radius: 3px; font-weight: bold;"
            )

    def select_file(self):
        file_paths, _ = QFileDialog.getOpenFileNames(self, "Select Files")
        if file_paths:
            self.file_path = file_paths
            if len(file_paths) == 1:
                self.file_label.setText(f"Selected file: {os.path.basename(file_paths[0])}")
            else:
                self.file_label.setText(f"Selected {len(file_paths)} files")
            self.validate_inputs()


    def select_folder(self):
        folder_path = QFileDialog.getExistingDirectory(self, "Select Folder")
        if folder_path:
            self.file_path = folder_path
            self.file_label.setText(f"Selected folder: {os.path.basename(folder_path)}")
            self.validate_inputs()

    def show_integrity_details(self):
        if not self.last_integrity_report:
            return

        report = self.last_integrity_report

        details = f"""
    Integrity Report

    Schema Version: {report.schema_version}
    Container Valid: {report.container_valid}
    Version Supported: {report.version_supported}
    Algorithm Supported: {report.algorithm_supported}
    Metadata Authenticated: {report.metadata_authenticated}
    Ciphertext Authenticated: {report.ciphertext_authenticated}
    Failure Stage: {report.failure_stage}
    Notes: {', '.join(report.notes) if report.notes else 'None'}
    """

        QMessageBox.information(self, "Integrity Details", details)      

    def authenticate_container(self, parent_dialog, target_path):
        # Custom password dialog
        password_dialog = QDialog(self)
        password_dialog.setWindowTitle("Enter Password")
        password_dialog.setMinimumWidth(350)

        layout = QVBoxLayout(password_dialog)

        password_input = QLineEdit()
        password_input.setEchoMode(QLineEdit.Password)
        password_input.setPlaceholderText("Enter password")
        layout.addWidget(password_input)

        button_layout = QHBoxLayout()
        ok_btn = QPushButton("Authenticate")
        cancel_btn = QPushButton("Cancel")
        button_layout.addWidget(ok_btn)
        button_layout.addWidget(cancel_btn)
        layout.addLayout(button_layout)

        ok_btn.clicked.connect(password_dialog.accept)
        cancel_btn.clicked.connect(password_dialog.reject)

        if password_dialog.exec() != QDialog.Accepted:
            return

        password = password_input.text()

        try:
            # Read full file for fingerprint
            with open(target_path, "rb") as f:
                container_bytes = f.read()

            fingerprint = generate_fingerprint(container_bytes)

            # Parse header and ciphertext
            with open(target_path, "rb") as f:
                header_data = parse_header(f)
                ciphertext = f.read()

            algorithm = header_data["algorithm"]
            salt = header_data["salt"]
            iv = header_data["iv"]
            tag = header_data["tag"]
            filename_bytes = header_data["filename_bytes"]

            key = derive_key(password, salt, None)

            with BytesIO(ciphertext) as input_stream:
                report = verify_stream(
                    input_stream,
                    key,
                    algorithm,
                    salt,
                    iv,
                    tag,
                    filename_bytes,
                    return_report=True
                )

            QMessageBox.information(
                self,
                "Authenticated Analysis",
                f"""
            Authenticated Container Analysis

            Algorithm: {algorithm_name(algorithm)}
            Metadata Authenticated: {report.metadata_authenticated}
            Ciphertext Authenticated: {report.ciphertext_authenticated}

            Container Fingerprint:
            {fingerprint}

            Failure Stage: {report.failure_stage}
            Notes: {', '.join(report.notes) if report.notes else 'None'}
            """
            )

        except AuthenticationError:
            QMessageBox.critical(
                self,
                "Authentication Failed",
                "Authentication failed.\nThe password may be incorrect or the container was modified."
            )
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))      


    def select_image(self):
        file_paths, _ = QFileDialog.getOpenFileNames(
            self,
            "Select Images",
            "",
            "Images (*.png *.jpg *.jpeg *.bmp *.gif)"
        )
        if file_paths:
            self.file_path = file_paths
            if len(file_paths) == 1:
                self.file_label.setText(f"Selected image: {os.path.basename(file_paths[0])}")
            else:
                self.file_label.setText(f"Selected {len(file_paths)} images")
            self.validate_inputs()

    def start_simulation(self):
        from ui.simulation_dialog import SimulationDialog

        dialog = SimulationDialog(
            parent=self,
            file_path=self.file_path,
            password=self.password_input.text(),
            keyfile_path=self.keyfile_path,
            algorithm=self.algorithm_selector.currentData()
        )
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.start_encrypt()

    def prompt_calibration(self):
        self.raise_()
        self.activateWindow()
        reply = QMessageBox.question(
            self,
            "Performance Calibration",
            "This is your first time launching Cryptix Core.\n\n"
            "Would you like to run a Performance Calibration? "
            "This measures your local CPU and storage throughput, "
            "allowing Simulation Mode to be highly accurate (+/- 5% precision) on YOUR computer.\n\n"
            "This takes about 5 seconds.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.start_benchmark()

    def start_academy(self):
        from ui.academy_dialog import AcademyDialog
        dialog = AcademyDialog(self)
        dialog.exec()

    def toggle_learning_mode(self):
        is_on = self.learning_toggle.isChecked()
        self.academy_button.setVisible(is_on)
        self.persist_settings()

