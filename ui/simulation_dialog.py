# ui/simulation_dialog.py

import os
import time
from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QFrame,
    QScrollArea,
    QWidget
)
from PySide6.QtCore import Qt
from cryptix_engine.simulation import calculate_simulation
from cryptix_engine.constants import algorithm_name, ALGO_AES, ALGO_CHACHA, ALGO_XCHACHA
from cryptix_engine.assessment import estimate_entropy
from utils.performance import get_hardware_profile

class SimulationDialog(QDialog):
    def __init__(self, parent, file_path, password, keyfile_path, algorithm):
        super().__init__(parent)
        self.setWindowTitle("Pre-Flight Encryption Plan")
        self.setMinimumWidth(550)
        self.setMinimumHeight(580)
        self.setStyleSheet(parent.styleSheet()) # Inherit standard dark styling

        # Store parameters
        self.file_path = file_path
        self.password = password
        self.keyfile_path = keyfile_path
        self.algorithm = algorithm

        # Resolve total input size and name
        self.total_size = 0
        self.filename = "container"
        if isinstance(file_path, list):
            if len(file_path) == 1:
                self.filename = os.path.basename(file_path[0])
                self.total_size = os.path.getsize(file_path[0]) if os.path.isfile(file_path[0]) else 0
            else:
                self.filename = f"{len(file_path)}_files_batch"
                for path in file_path:
                    if os.path.isfile(path):
                        self.total_size += os.path.getsize(path)
        elif os.path.isdir(file_path):
            self.filename = os.path.basename(file_path) + ".zip"
            # Walk directory to calculate total size
            for root, _, files in os.walk(file_path):
                for f in files:
                    self.total_size += os.path.getsize(os.path.join(root, f))
        elif os.path.isfile(file_path):
            self.filename = os.path.basename(file_path)
            self.total_size = os.path.getsize(file_path)

        # Retrieve Hardware Profile
        self.profile = get_hardware_profile()

        # Run Engine Simulation
        self.report = calculate_simulation(
            file_size_bytes=self.total_size,
            algorithm=self.algorithm,
            filename=self.filename,
            profile=self.profile
        )

        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(14)
        layout.setContentsMargins(25, 20, 25, 20)

        # Title Header
        title_label = QLabel("📋 ENCRYPTION PLAN & SIMULATION")
        title_label.setStyleSheet("font-size: 16px; font-weight: bold; color: #00F0FF; letter-spacing: 1px;")
        layout.addWidget(title_label)

        # Divider
        divider = QFrame()
        divider.setFrameShape(QFrame.Shape.HLine)
        divider.setStyleSheet("background-color: #262F3F; max-height: 1px;")
        layout.addWidget(divider)

        # ---- 1. CHECKLIST PANEL ----
        checklist_box = QVBoxLayout()
        checklist_box.setSpacing(6)

        # Target file checklist line
        size_mb = self.total_size / (1024 * 1024)
        target_line = QLabel(f"✓ Target Loaded: {self.filename} ({size_mb:.2f} MB)")
        target_line.setStyleSheet("color: #00FF66; font-weight: bold;")
        checklist_box.addWidget(target_line)

        # Password entropy check
        entropy = estimate_entropy(self.password)
        pass_line = QLabel(f"✓ Password Evaluated: {entropy:.2f} bits of entropy")
        pass_line.setStyleSheet("color: #00FF66; font-weight: bold;")
        checklist_box.addWidget(pass_line)

        # Keyfile presence line
        key_status = f"✓ Keyfile Bound: {os.path.basename(self.keyfile_path)}" if self.keyfile_path else "✓ No Keyfile (Password Only)"
        key_line = QLabel(key_status)
        key_line.setStyleSheet("color: #00FF66; font-weight: bold;")
        checklist_box.addWidget(key_line)

        # Algorithm selection
        algo_line = QLabel(f"✓ Cryptographic Protocol: {algorithm_name(self.algorithm)}")
        algo_line.setStyleSheet("color: #00FF66; font-weight: bold;")
        checklist_box.addWidget(algo_line)

        layout.addLayout(checklist_box)

        # Frame separating metrics
        divider2 = QFrame()
        divider2.setFrameShape(QFrame.Shape.HLine)
        divider2.setStyleSheet("background-color: #262F3F; max-height: 1px;")
        layout.addWidget(divider2)

        # ---- 2. PERFORMANCE METRICS PANEL ----
        metrics_layout = QVBoxLayout()
        metrics_layout.setSpacing(8)

        # Time estimate with custom color matching
        time_label = QLabel(f"⏱ Estimated Execution Time: {self.report.estimated_time_s}s")
        time_label.setStyleSheet("font-size: 14px; font-weight: bold; color: #E2E8F0;")
        metrics_layout.addWidget(time_label)

        # Output Size
        output_size_mb = self.report.estimated_output_size_bytes / (1024 * 1024)
        size_label = QLabel(f"📦 Estimated Container Size: {output_size_mb:.2f} MB")
        size_label.setStyleSheet("color: #A0AEC0;")
        metrics_layout.addWidget(size_label)

        # RAM Usage
        mem_label = QLabel(f"💾 Maximum Memory Peak: ~{self.report.estimated_memory_mb} MB")
        mem_label.setStyleSheet("color: #A0AEC0;")
        metrics_layout.addWidget(mem_label)

        layout.addLayout(metrics_layout)

        # ---- 3. CONFIDENCE PANEL ----
        confidence_layout = QHBoxLayout()
        confidence_label = QLabel("Simulation Confidence: ")
        confidence_label.setStyleSheet("color: #A0AEC0; font-weight: bold;")
        confidence_layout.addWidget(confidence_label)

        # Stars representation
        if self.report.confidence_level == "High":
            stars = "★★★★★"
            color = "#00FF66"  # Bright Green
        elif self.report.confidence_level == "Medium":
            stars = "★★★☆☆"
            color = "#FFA500"  # Orange
        else:
            stars = "★☆☆☆☆"
            color = "#FF3B3B"  # Red

        stars_label = QLabel(stars)
        stars_label.setStyleSheet(f"font-size: 16px; font-weight: bold; color: {color};")
        confidence_layout.addWidget(stars_label)
        confidence_layout.addStretch()

        layout.addLayout(confidence_layout)

        # Reasons explanation
        reasons_text = "\n".join([f"• {reason}" for reason in self.report.confidence_reasons])
        reasons_label = QLabel(reasons_text)
        reasons_label.setStyleSheet("color: gray; font-size: 11px; font-style: italic;")
        reasons_label.setWordWrap(True)
        layout.addWidget(reasons_label)

        # Notes
        notes_text = "\n".join([f"Note: {note}" for note in self.report.notes])
        notes_label = QLabel(notes_text)
        notes_label.setStyleSheet("color: #00F0FF; font-size: 11px;")
        notes_label.setWordWrap(True)
        layout.addWidget(notes_label)

        # ---- 4. COLLAPSIBLE SECURITY EXPLAINER PANEL ----
        self.explainer_btn = QPushButton("📖 Explain Security Primitives")
        self.explainer_btn.setStyleSheet("color: #00F0FF; background-color: #131822; border: 1px solid #262F3F; text-align: left; padding: 6px;")
        self.explainer_btn.clicked.connect(self.toggle_explainer)
        layout.addWidget(self.explainer_btn)

        # Scroll Area holding the explanatory text
        self.explainer_area = QScrollArea()
        self.explainer_area.setWidgetResizable(True)
        self.explainer_area.setStyleSheet("border: 1px solid #262F3F; background-color: #0B0F19;")
        self.explainer_area.hide()

        explainer_content = QWidget()
        explainer_text_layout = QVBoxLayout(explainer_content)
        explainer_text_layout.setSpacing(10)

        # Argon2id explanation
        kdf_title = QLabel("Why Argon2id?")
        kdf_title.setStyleSheet("color: #00F0FF; font-weight: bold;")
        kdf_desc = QLabel("Argon2id is a memory-hard key derivation function. It requires significant RAM (100MB) and CPU cycles to derive a key, mathematically destroying any economic viability of high-speed GPU/ASIC brute-force dictionary attacks.")
        kdf_desc.setWordWrap(True)
        kdf_desc.setStyleSheet("color: #E2E8F0; font-size: 11px;")
        explainer_text_layout.addWidget(kdf_title)
        explainer_text_layout.addWidget(kdf_desc)

        # AEAD explanation
        aead_title = QLabel("Why AEAD (Authenticated Encryption)?")
        aead_title.setStyleSheet("color: #00F0FF; font-weight: bold;")
        aead_desc = QLabel("AEAD binds an integrity tag to the ciphertext. Any modification to the encrypted container, headers, or original filename is detected immediately during key evaluation. If tampering is detected, decryption stops and zero data is released.")
        aead_desc.setWordWrap(True)
        aead_desc.setStyleSheet("color: #E2E8F0; font-size: 11px;")
        explainer_text_layout.addWidget(aead_title)
        explainer_text_layout.addWidget(aead_desc)

        # Protocol explanation
        proto_title = QLabel(f"Why {algorithm_name(self.algorithm)}?")
        proto_title.setStyleSheet("color: #00F0FF; font-weight: bold;")
        if self.algorithm == ALGO_AES:
            proto_desc = "AES-256-GCM is the industry gold standard. It executes at hardware speed on CPUs supporting AES-NI instructions, offering ultra-fast throughput."
        elif self.algorithm == ALGO_CHACHA:
            proto_desc = "ChaCha20-Poly1305 is incredibly secure and fast on hardware lacking AES-NI acceleration instructions. It uses standard 96-bit nonces."
        else:
            proto_desc = "XChaCha20-Poly1305 extends the nonce to 192-bits (24 bytes). This completely eliminates the mathematical risk of any random nonce/IV reuse collision, making it highly robust."
        
        proto_desc_label = QLabel(proto_desc)
        proto_desc_label.setWordWrap(True)
        proto_desc_label.setStyleSheet("color: #E2E8F0; font-size: 11px;")
        explainer_text_layout.addWidget(proto_title)
        explainer_text_layout.addWidget(proto_desc_label)

        self.explainer_area.setWidget(explainer_content)
        layout.addWidget(self.explainer_area)

        # ---- 5. TAKE-OFF ACTIONS ----
        button_box = QHBoxLayout()
        button_box.setSpacing(12)

        self.launch_btn = QPushButton("🚀 CONFIRM & LAUNCH ENCRYPTION")
        self.launch_btn.setStyleSheet("""
            QPushButton {
                background-color: #00AAFF;
                color: #FFFFFF;
                font-weight: bold;
                border: 1px solid #00F0FF;
                padding: 10px;
            }
            QPushButton:hover {
                background-color: #00F0FF;
                color: #000000;
            }
        """)
        self.launch_btn.clicked.connect(self.accept)

        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        cancel_btn.setStyleSheet("padding: 10px;")

        button_box.addWidget(self.launch_btn)
        button_box.addWidget(cancel_btn)
        layout.addLayout(button_box)

    def toggle_explainer(self):
        if self.explainer_area.isVisible():
            self.explainer_area.hide()
            self.explainer_btn.setText("📖 Explain Security Primitives")
            self.adjustSize()
        else:
            self.explainer_area.show()
            self.explainer_btn.setText("📕 Hide Explanations")
            self.adjustSize()