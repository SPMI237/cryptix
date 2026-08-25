# ui/tamper_lab_dialog.py

import os
from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QFrame,
    QScrollArea,
    QWidget,
    QRadioButton,
    QButtonGroup,
    QTableWidget,
    QTableWidgetItem,
    QMessageBox,
    QHeaderView,
    QTextEdit
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from cryptix_academy.sandbox import (
    TamperLabSandbox,
    locate_filename_offset,
    NoOpExperiment,
    CiphertextTamperExperiment,
    MetadataTamperExperiment,
    VersionTamperExperiment,
    AlgorithmTamperExperiment,
    TruncationExperiment,
    TagTamperExperiment
)
from cryptix_engine.constants import algorithm_name

class TamperLabDialog(QDialog):
    def __init__(self, parent):
        super().__init__(parent)
        self.setWindowTitle("Cryptix Laboratory - The Tamper Lab")
        self.setMinimumWidth(820)
        self.setMinimumHeight(680)
        self.setStyleSheet(parent.styleSheet()) # Inherit dark theme styling

        # Initialize the volatile in-memory sandbox
        self.sandbox = TamperLabSandbox()

        # Build list of available experiments
        self.experiments = [
            NoOpExperiment(),
            CiphertextTamperExperiment(),
            MetadataTamperExperiment(),
            VersionTamperExperiment(),
            AlgorithmTamperExperiment(),
            TruncationExperiment(),
            TagTamperExperiment()
        ]
        self.active_experiment = self.experiments[0]

        self.init_ui()

    def init_ui(self):
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(16)

        # =========================================================
        # LEFT COLUMN (Control Panel & Container Structure)
        # =========================================================
        left_column = QVBoxLayout()
        left_column.setSpacing(12)

        # Lab Title
        title_label = QLabel("🧪 THE TAMPER LAB")
        title_label.setStyleSheet("font-size: 16px; font-weight: bold; color: #00F0FF; letter-spacing: 1px;")
        left_column.addWidget(title_label)

        desc_label = QLabel("Attack the temporary container in memory. Watch the actual Cryptix verification logic defend it in real-time.")
        desc_label.setWordWrap(True)
        desc_label.setStyleSheet("color: #A0AEC0; font-size: 11px; font-style: italic;")
        left_column.addWidget(desc_label)

        # --- 1. CONTAINER STRUCTURE CARD ---
        structure_card = QFrame()
        structure_card.setStyleSheet("border: 1px solid #262F3F; background-color: #0F131C; border-radius: 4px;")
        card_layout = QVBoxLayout(structure_card)
        card_layout.setSpacing(6)
        card_layout.setContentsMargins(12, 12, 12, 12)

        card_title = QLabel("📦 IN-MEMORY CONTAINER STRUCTURE")
        card_title.setStyleSheet("color: #00F0FF; font-weight: bold; font-size: 11px; border: none;")
        card_layout.addWidget(card_title)

        # Separator inside card
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("background-color: #262F3F; max-height: 1px; border: none;")
        card_layout.addWidget(sep)

        # Sizing details - derived from the real container layout, never hard-coded.
        # Layout: MAGIC(4) + VERSION(1) + ALGO(1) + SALT(16) + IV(iv_len) + TAG(16)
        #         + FILENAME_LENGTH(4) + FILENAME + CIPHERTEXT
        size_bytes = len(self.sandbox.original_container)
        iv_len = 24 if self.sandbox.algorithm == 3 else 12
        filename_offset = locate_filename_offset(bytes(self.sandbox.original_container))
        ciphertext_size = size_bytes - (filename_offset + 4) - len(self.sandbox.filename.encode("utf-8"))

        self.struct_magic = QLabel("• MAGIC HEADER:  GCA1 (4 bytes)")
        self.struct_version = QLabel("• FORMAT VERSION: 01 (1 byte)")
        self.struct_algo = QLabel(f"• ALGO IDENTIFIER: {algorithm_name(self.sandbox.algorithm)}")
        self.struct_salt = QLabel("• KEY SALT:       16 bytes (Random)")
        self.struct_iv = QLabel(f"• NONCE / IV:      {iv_len} bytes (Random)")
        self.struct_tag = QLabel("• AUTH TAG:       16 bytes (Progressive MAC)")
        self.struct_filename = QLabel(f"• METADATA:       {self.sandbox.filename} ({len(self.sandbox.filename.encode('utf-8'))} bytes)")
        self.struct_cipher = QLabel(f"• CIPHERTEXT:     {ciphertext_size} bytes")

        for lbl in (
            self.struct_magic, self.struct_version, self.struct_algo,
            self.struct_salt, self.struct_iv, self.struct_tag,
            self.struct_filename, self.struct_cipher
        ):
            lbl.setStyleSheet("color: #E2E8F0; font-family: Consolas, monospace; font-size: 11px; border: none;")
            card_layout.addWidget(lbl)

        left_column.addWidget(structure_card)

        # --- 2. EXPERIMENT SELECTOR LIST ---
        selector_card = QFrame()
        selector_card.setStyleSheet("border: 1px solid #262F3F; background-color: #0F131C; border-radius: 4px;")
        selector_layout = QVBoxLayout(selector_card)
        selector_layout.setSpacing(6)
        selector_layout.setContentsMargins(12, 12, 12, 12)

        selector_title = QLabel("🔬 CHOOSE ATTACK EXPERIMENT")
        selector_title.setStyleSheet("color: #00F0FF; font-weight: bold; font-size: 11px; border: none;")
        selector_layout.addWidget(selector_title)

        # Separator inside card
        sep2 = QFrame()
        sep2.setFrameShape(QFrame.Shape.HLine)
        sep2.setStyleSheet("background-color: #262F3F; max-height: 1px; border: none;")
        selector_layout.addWidget(sep2)

        self.exp_group = QButtonGroup(self)
        for idx, exp in enumerate(self.experiments):
            rad = QRadioButton(exp.name)
            rad.setStyleSheet("""
                QRadioButton {
                    color: #A0AEC0;
                    font-weight: bold;
                    font-size: 11px;
                    border: none;
                }
                QRadioButton::indicator {
                    width: 12px;
                    height: 12px;
                }
                QRadioButton::indicator:checked {
                    background-color: #00F0FF;
                }
            """)
            if idx == 0:
                rad.setChecked(True)
            self.exp_group.addButton(rad, idx)
            selector_layout.addWidget(rad)

        self.exp_group.idClicked.connect(self.select_experiment)

        left_column.addWidget(selector_card)

        # Action Buttons
        self.run_btn = QPushButton("💥 RUN TAMPER EXPERIMENT")
        self.run_btn.setStyleSheet("""
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
        self.run_btn.clicked.connect(self.execute_active_experiment)
        left_column.addWidget(self.run_btn)

        main_layout.addLayout(left_column, 2)

        # =========================================================
        # RIGHT COLUMN (Terminal, Hex Inspector & Socratic results)
        # =========================================================
        right_column = QVBoxLayout()
        right_column.setSpacing(12)

        # --- 1. VERIFICATION TERMINAL ---
        terminal_card = QFrame()
        terminal_card.setStyleSheet("border: 1px solid #262F3F; background-color: #0B0F19; border-radius: 4px;")
        term_layout = QVBoxLayout(terminal_card)
        term_layout.setContentsMargins(12, 12, 12, 12)
        term_layout.setSpacing(6)

        term_title = QLabel("🖥️ LIVE CRYPTIX VERIFICATION TRACE")
        term_title.setStyleSheet("color: #00F0FF; font-weight: bold; font-size: 11px; border: none;")
        term_layout.addWidget(term_title)

        self.terminal_area = QTextEdit()
        self.terminal_area.setReadOnly(True)
        self.terminal_area.setStyleSheet("""
            QTextEdit {
                background-color: #05070F;
                border: 1px solid #1C222E;
                color: #00FF66;
                font-family: 'Consolas', monospace;
                font-size: 11px;
                line-height: 140%;
            }
        """)
        term_layout.addWidget(self.terminal_area)
        self.terminal_area.setText("[!] Volatile In-Memory Sandbox Initialized.\n[!] Control Group 'No-Op' active — untampered baseline container loaded.\n[!] Ready for experiment execution.")

        right_column.addWidget(terminal_card, 2)

        # --- 2. HEX / BEFORE-AFTER INSPECTOR ---
        hex_card = QFrame()
        hex_card.setStyleSheet("border: 1px solid #262F3F; background-color: #0F131C; border-radius: 4px;")
        hex_layout = QVBoxLayout(hex_card)
        hex_layout.setContentsMargins(12, 12, 12, 12)
        hex_layout.setSpacing(6)

        hex_title = QLabel("🔍 BYTE-LEVEL BEFORE/AFTER HEX INSPECTOR")
        hex_title.setStyleSheet("color: #00F0FF; font-weight: bold; font-size: 11px; border: none;")
        hex_layout.addWidget(hex_title)

        self.hex_table = QTableWidget()
        self.hex_table.setColumnCount(4)
        self.hex_table.setHorizontalHeaderLabels(["OFFSET", "BEFORE (Original)", "AFTER (Tampered)", "STATUS"])
        self.hex_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.hex_table.setStyleSheet("""
            QTableWidget {
                background-color: #05070F;
                border: 1px solid #1C222E;
                color: #E2E8F0;
                font-family: 'Consolas', monospace;
                font-size: 10px;
            }
            QHeaderView::section {
                background-color: #131822;
                color: #00F0FF;
                border: 1px solid #1C222E;
                padding: 4px;
                font-weight: bold;
            }
        """)
        self.hex_table.setRowCount(0)
        hex_layout.addWidget(self.hex_table)

        right_column.addWidget(hex_card, 2)

        # --- 3. EDUCATIONAL ASSESSMENT CARD ---
        assessment_card = QFrame()
        assessment_card.setStyleSheet("border: 1px solid #262F3F; background-color: #0F131C; border-radius: 4px;")
        assess_layout = QVBoxLayout(assessment_card)
        assess_layout.setContentsMargins(12, 12, 12, 12)
        assess_layout.setSpacing(4)

        assess_title = QLabel("🛡️ SECURITY PROPERTY ASSESSMENT")
        assess_title.setStyleSheet("color: #00F0FF; font-weight: bold; font-size: 11px; border: none;")
        assess_layout.addWidget(assess_title)

        self.assess_exp = QLabel("Expected Outcome: Container must authenticate and decrypt successfully.")
        self.assess_act = QLabel("Actual Outcome:   Not Run")
        self.assess_res = QLabel("Assessment:       WAITING")

        for lbl in (self.assess_exp, self.assess_act, self.assess_res):
            lbl.setWordWrap(True)
            lbl.setStyleSheet("color: #E2E8F0; font-family: Consolas, monospace; font-size: 11px; border: none;")
            assess_layout.addWidget(lbl)

        right_column.addWidget(assessment_card, 1)

        main_layout.addLayout(right_column, 3)

    def select_experiment(self, idx):
        self.active_experiment = self.experiments[idx]
        self.assess_exp.setText(f"Expected Outcome: {self.active_experiment.expected_security}")
        self.assess_act.setText("Actual Outcome:   Not Run")
        self.assess_res.setText("Assessment:       WAITING")
        self.assess_res.setStyleSheet("color: #E2E8F0; font-family: Consolas, monospace; font-size: 11px; border: none;")

    def execute_active_experiment(self):
        # 1. Trigger volatile sandbox run
        tampered_bytes, trace = self.sandbox.run_experiment(self.active_experiment)

        # 2. Build Terminal Trace Log
        term_text = f"[!] Volatile In-Memory Sandbox Initialized.\n"
        term_text += f"[!] Running Experiment: '{self.active_experiment.name}'...\n"
        term_text += f"[!] Objective: {self.active_experiment.objective}\n"
        term_text += f"--------------------------------------------------\n"
        term_text += f"🔍 EXECUTING DECRYPTION PIPELINE TRACE:\n"

        for step in trace.steps:
            icon = "✓" if step.status == "SUCCESS" else "❌"
            term_text += f"{icon}  [{step.stage}]: {step.message}\n"
            term_text += f"    └─ Detail: {step.technical_detail}\n"

        term_text += f"--------------------------------------------------\n"

        # Identify which defensive layer decided the outcome (Layer 1 parser vs Layer 2 AEAD)
        if trace.success:
            layer_line = "Defense Layer Engaged: NONE — container fully authenticated."
        elif trace.rejection_layer == "STRUCTURAL":
            layer_line = "Defense Layer Engaged: Layer 1 — Structural Format Validation (parser rejection)."
        else:
            layer_line = "Defense Layer Engaged: Layer 2 — Cryptographic AEAD Verification (authentication failure)."

        boundary_icon = "✓" if trace.security_preserved else "🚨"
        term_text += f"{boundary_icon}  SECURITY RESULT: {trace.assessment}\n"
        term_text += f"    └─ {layer_line}\n"
        term_text += f"    └─ Plaintext Release: {'PERMITTED (authentication passed)' if trace.released_plaintext else 'BLOCKED (0 bytes written)'}"

        self.terminal_area.setText(term_text)

        # 3. Build Hex Difference Table
        diffs = TamperLabSandbox.compare_containers(self.sandbox.original_container, tampered_bytes)
        self.hex_table.setRowCount(len(diffs))

        for row, d in enumerate(diffs):
            # Set items
            self.hex_table.setItem(row, 0, QTableWidgetItem(d["offset"]))
            self.hex_table.setItem(row, 1, QTableWidgetItem(d["before"]))
            self.hex_table.setItem(row, 2, QTableWidgetItem(d["after"]))
            
            status_item = QTableWidgetItem(d["status"])
            status_color = QColor("#FF3B3B") if d["status"] == "MODIFIED" else QColor("#FFA500")
            status_item.setForeground(status_color)
            self.hex_table.setItem(row, 3, status_item)

            # Center text inside table cells
            for col in range(4):
                self.hex_table.item(row, col).setTextAlignment(Qt.AlignCenter)

        # 4. Update Educational Assessment Labels
        self.assess_exp.setText(f"Expected Outcome: {self.active_experiment.expected_security}")
        
        if trace.success:
            actual_status = "Verification passed — authenticated container accepted."
        elif trace.rejection_layer == "STRUCTURAL":
            actual_status = "STRUCTURAL REJECTION — refused by the format parser (Layer 1), before any key processing."
        else:
            actual_status = "CRYPTOGRAPHIC FAILURE — AEAD authentication failed (Layer 2); decryption aborted."
        self.assess_act.setText(f"Actual Outcome:   {actual_status}")

        self.assess_res.setText(f"Assessment:       {trace.assessment}")
        res_color = "#00FF66" if trace.security_preserved else "#FF3B3B"
        self.assess_res.setStyleSheet(f"color: {res_color}; font-family: Consolas, monospace; font-size: 11px; border: none; font-weight: bold;")
