# ui/tamper_lab_dialog.py

import os
import textwrap
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
    QTextEdit,
    QComboBox
)
from PySide6.QtCore import Qt, QTimer, QPoint
from PySide6.QtGui import QColor
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QGraphicsOpacityEffect
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
from cryptix_academy.tamper_pedagogy import (
    TamperChallengeSession,
    get_challenge_for_experiment,
    apply_challenge_outcome
)
from cryptix_academy.progress import ProgressStore
from cryptix_engine.constants import algorithm_name

class TamperLabDialog(QDialog):
    def __init__(self, parent, progress=None, audio=None):
        super().__init__(parent)
        self.setWindowTitle("Cryptix Laboratory - The Tamper Lab")
        self.setMinimumWidth(940)
        self.setMinimumHeight(560)

        # Open at a size that always fits the available screen
        screen_geom = QGuiApplication.primaryScreen().availableGeometry()
        self.resize(
            min(1120, screen_geom.width() - 100),
            min(880, screen_geom.height() - 100)
        )
        self.setStyleSheet(parent.styleSheet()) # Inherit dark theme styling

        # Shared Academy progress (passed by the gateway; loaded standalone if absent)
        self.progress = progress if progress is not None else ProgressStore.load_progress()

        # Stage 6C: shared audio service (the Academy owns the session)
        from audio.playback import SoundService
        self.audio = audio if audio is not None else SoundService(self)

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

        # Stage 6B scientific method session:
        # Prediction -> Experiment -> Investigation -> Matching -> Reveal
        self.session = TamperChallengeSession(
            get_challenge_for_experiment(self.active_experiment.name)
        )

        self.init_ui()
        self.reset_challenge_cycle()

    # Stage 7A.1 - stepper chip labels (display form with emojis, plain names)
    STEPPER_STAGES = ["🔮 PREDICT", "⚔️ EXPERIMENT", "🔍 INVESTIGATE", "🔗 MATCH", "📖 REVEAL"]
    STEPPER_NAMES = ["PREDICT", "EXPERIMENT", "INVESTIGATE", "MATCH", "REVEAL"]
    _CHIP_STYLES = {
        "pending": "color: #6B7A90; font-size: 11px; font-weight: bold; border: none; padding: 2px 6px;",
        "active": "color: #00F0FF; font-size: 11px; font-weight: bold; border: 1px solid #00F0FF; border-radius: 3px; padding: 2px 8px; background-color: #101A24;",
        "done": "color: #00FF66; font-size: 11px; font-weight: bold; border: none; padding: 2px 6px;",
    }

    def init_ui(self):
        # Stage 7A.1: outer layout hosts the stage stepper above both columns
        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(20, 12, 20, 14)
        outer_layout.setSpacing(10)
        outer_layout.addWidget(self._build_stage_stepper())

        main_layout = QHBoxLayout()
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(16)

        # =========================================================
        # LEFT COLUMN (Control Panel & Container Structure)
        # =========================================================
        left_column = QVBoxLayout()
        left_column.setSpacing(12)

        # Stage 6C: shared audio controls (toggles mirror the Academy session)
        audio_toggle_style = """
            QPushButton { padding: 3px; font-size: 13px; }
            QPushButton:checked { background-color: #00F0FF; }
        """
        audio_row = QHBoxLayout()
        self.sfx_toggle = QPushButton("🔊")
        self.sfx_toggle.setCheckable(True)
        self.sfx_toggle.setChecked(self.audio.audio_settings()["sfx_enabled"])
        self.sfx_toggle.setFixedWidth(36)
        self.sfx_toggle.setToolTip("Sound effects on/off")
        self.sfx_toggle.setStyleSheet(audio_toggle_style)
        self.sfx_toggle.clicked.connect(lambda checked: self.audio.update_setting("sfx_enabled", checked))
        audio_row.addWidget(self.sfx_toggle)

        self.music_toggle = QPushButton("🎵")
        self.music_toggle.setCheckable(True)
        self.music_toggle.setChecked(self.audio.audio_settings()["music_enabled"])
        self.music_toggle.setFixedWidth(36)
        self.music_toggle.setToolTip("Laboratory ambience on/off")
        self.music_toggle.setStyleSheet(audio_toggle_style)
        self.music_toggle.clicked.connect(self.toggle_lab_music)
        audio_row.addWidget(self.music_toggle)

        audio_row.addStretch()
        left_column.addLayout(audio_row)

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

        # --- 3. SCIENTIFIC METHOD: PREDICTION CARD (Stage 6B) ---
        prediction_card = QFrame()
        prediction_card.setStyleSheet("border: 1px solid #262F3F; background-color: #0F131C; border-radius: 4px;")
        predict_layout = QVBoxLayout(prediction_card)
        predict_layout.setSpacing(6)
        predict_layout.setContentsMargins(12, 12, 12, 12)

        predict_title = QLabel("🔮 PREDICTION — STATE YOUR HYPOTHESIS")
        predict_title.setStyleSheet("color: #00F0FF; font-weight: bold; font-size: 11px; border: none;")
        predict_layout.addWidget(predict_title)

        flow_label = QLabel("Predict → Experiment → Investigate → Match → Reveal")
        flow_label.setStyleSheet("color: #A0AEC0; font-size: 10px; font-style: italic; border: none;")
        predict_layout.addWidget(flow_label)

        reward_label = QLabel("🎯 Rewards: correct prediction +10 XP · 3/3 matching +15 XP")
        reward_label.setStyleSheet("color: #FFD700; font-size: 10px; border: none;")
        predict_layout.addWidget(reward_label)

        sep3 = QFrame()
        sep3.setFrameShape(QFrame.Shape.HLine)
        sep3.setStyleSheet("background-color: #262F3F; max-height: 1px; border: none;")
        predict_layout.addWidget(sep3)

        self.predict_question = QLabel("")
        self.predict_question.setWordWrap(True)
        self.predict_question.setStyleSheet("color: #E2E8F0; font-size: 11px; border: none;")
        predict_layout.addWidget(self.predict_question)

        self.predict_group = QButtonGroup(self)
        self.predict_radios = []
        for idx in range(4):
            rad = QRadioButton()
            rad.setStyleSheet("""
                QRadioButton {
                    color: #A0AEC0;
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
                QRadioButton:disabled {
                    color: #6B7A90;
                }
            """)
            rad.toggled.connect(self._on_prediction_radio_toggled)
            self.predict_group.addButton(rad, idx)
            predict_layout.addWidget(rad)
            self.predict_radios.append(rad)

        self.predict_btn = QPushButton("🔮 RECORD PREDICTION")
        self.predict_btn.setStyleSheet("""
            QPushButton {
                background-color: #1A2332;
                color: #00F0FF;
                font-weight: bold;
                border: 1px solid #00F0FF;
                padding: 8px;
            }
            QPushButton:hover {
                background-color: #00F0FF;
                color: #000000;
            }
            QPushButton:disabled {
                color: #6B7A90;
                border-color: #262F3F;
            }
        """)
        self.predict_btn.clicked.connect(self.record_prediction_action)
        predict_layout.addWidget(self.predict_btn)

        left_column.addWidget(prediction_card)

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
        self.run_btn.setEnabled(False)  # Stage 6B: locked until a prediction is recorded
        left_column.addWidget(self.run_btn)

        # Left column scrolls on short screens so Record Prediction / Run stay reachable
        left_container = QWidget()
        left_container.setLayout(left_column)
        left_scroll = QScrollArea()
        left_scroll.setWidget(left_container)
        left_scroll.setWidgetResizable(True)
        left_scroll.setFrameShape(QFrame.Shape.NoFrame)
        left_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        main_layout.addWidget(left_scroll, 2)

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
        self.terminal_area.setMinimumHeight(110)  # allows compression on short screens
        self.terminal_area.setText("[!] Volatile In-Memory Sandbox Initialized.\n[!] Control Group 'No-Op' active — untampered baseline container loaded.\n[!] Ready for experiment execution.")

        right_column.addWidget(terminal_card, 0)  # Stage 7A: natural height keeps the reveal scrollable into view

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
        self.hex_table.setMinimumHeight(90)  # allows compression on short screens

        right_column.addWidget(hex_card, 0)

        # --- 3. EDUCATIONAL ASSESSMENT CARD ---
        assessment_card = QFrame()
        assessment_card.setStyleSheet("border: 1px solid #262F3F; background-color: #0F131C; border-radius: 4px;")
        assess_layout = QVBoxLayout(assessment_card)
        assess_layout.setContentsMargins(12, 12, 12, 12)
        assess_layout.setSpacing(4)

        assess_title = QLabel("🛡️ SECURITY PROPERTY ASSESSMENT")
        assess_title.setStyleSheet("color: #00F0FF; font-weight: bold; font-size: 11px; border: none;")
        assess_layout.addWidget(assess_title)

        # Stage 7A.2: layer identity chip (amber Layer 1 / cyan Layer 2 / green verified)
        self.layer_chip = QLabel("")
        self.layer_chip.hide()
        assess_layout.addWidget(self.layer_chip)

        self.assess_exp = QLabel("Expected Outcome: Container must authenticate and decrypt successfully.")
        self.assess_act = QLabel("Actual Outcome:   Not Run")
        self.assess_res = QLabel("Assessment:       WAITING")

        for lbl in (self.assess_exp, self.assess_act, self.assess_res):
            lbl.setWordWrap(True)
            lbl.setStyleSheet("color: #E2E8F0; font-family: Consolas, monospace; font-size: 11px; border: none;")
            assess_layout.addWidget(lbl)

        right_column.addWidget(assessment_card, 0)

        # --- 4. SCIENTIFIC METHOD: MATCHING & REVEAL CARD (Stage 6B) ---
        matching_card = QFrame()
        matching_card.setStyleSheet("border: 1px solid #262F3F; background-color: #0F131C; border-radius: 4px;")
        match_layout = QVBoxLayout(matching_card)
        match_layout.setContentsMargins(12, 12, 12, 12)
        match_layout.setSpacing(6)

        match_title = QLabel("🔗 MATCHING — INTERPRET THE EVIDENCE")
        match_title.setStyleSheet("color: #00F0FF; font-weight: bold; font-size: 11px; border: none;")
        match_layout.addWidget(match_title)

        sep5 = QFrame()
        sep5.setFrameShape(QFrame.Shape.HLine)
        sep5.setStyleSheet("background-color: #262F3F; max-height: 1px; border: none;")
        match_layout.addWidget(sep5)

        self.match_rows = []  # list of (prompt_label, combo)
        for _ in range(3):
            row = QHBoxLayout()
            prompt_lbl = QLabel("")
            prompt_lbl.setStyleSheet("color: #E2E8F0; font-family: Consolas, monospace; font-size: 11px; border: none;")
            combo = QComboBox()
            combo.setStyleSheet("""
                QComboBox {
                    background-color: #131822;
                    color: #E2E8F0;
                    border: 1px solid #262F3F;
                    padding: 4px;
                    font-family: Consolas, monospace;
                    font-size: 11px;
                }
                QComboBox:disabled {
                    color: #6B7A90;
                }
                QComboBox QAbstractItemView {
                    background-color: #131822;
                    color: #E2E8F0;
                    selection-background-color: #00F0FF;
                    selection-color: #000000;
                }
            """)
            row.addWidget(prompt_lbl, 1)
            row.addWidget(combo, 2)
            match_layout.addLayout(row)
            self.match_rows.append((prompt_lbl, combo))

        self.match_submit_btn = QPushButton("🔗 SUBMIT MATCHING")
        self.match_submit_btn.setStyleSheet("""
            QPushButton {
                background-color: #1A2332;
                color: #00F0FF;
                font-weight: bold;
                border: 1px solid #00F0FF;
                padding: 8px;
            }
            QPushButton:hover {
                background-color: #00F0FF;
                color: #000000;
            }
            QPushButton:disabled {
                color: #6B7A90;
                border-color: #262F3F;
            }
        """)
        self.match_submit_btn.setEnabled(False)
        self.match_submit_btn.clicked.connect(self.submit_matching_action)
        match_layout.addWidget(self.match_submit_btn)

        self.reveal_label = QLabel("")
        self.reveal_label.setWordWrap(True)
        self.reveal_label.setStyleSheet("color: #E2E8F0; font-family: Consolas, monospace; font-size: 11px; border: none;")
        match_layout.addWidget(self.reveal_label)

        right_column.addWidget(matching_card, 0)
        right_column.addStretch(1)

        # Right column scrolls on short screens (e.g. once the reveal text appears)
        right_container = QWidget()
        right_container.setLayout(right_column)
        right_scroll = QScrollArea()
        right_scroll.setWidget(right_container)
        right_scroll.setWidgetResizable(True)
        right_scroll.setFrameShape(QFrame.Shape.NoFrame)
        right_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.right_scroll = right_scroll  # Stage 7A: reveal auto-scroll target
        main_layout.addWidget(right_scroll, 3)

        # Stage 7A.1: columns live under the stepper
        outer_layout.addLayout(main_layout)

        # Stage 7A.6: Enter follows the gated primary action
        from PySide6.QtGui import QShortcut, QKeySequence
        self._enter_shortcuts = []
        for seq in ("Return", "Enter"):
            sc = QShortcut(QKeySequence(seq), self)
            sc.activated.connect(self._enter_primary)
            self._enter_shortcuts.append(sc)

    # =========================================================
    # Stage 6C - Audio (mechanical register: the machinery reports)
    # =========================================================
    def showEvent(self, event):
        super().showEvent(event)
        if not getattr(self, "_audio_announced", False):
            self._audio_announced = True
            self.audio.emit("lab_opened")
            self.audio.transition_to("lab_loop")

    def toggle_lab_music(self, checked):
        self.audio.update_setting("music_enabled", checked)
        if checked:
            self.audio.transition_to("lab_loop")
        else:
            self.audio.stop_ambience()

    def select_experiment(self, idx):
        self.active_experiment = self.experiments[idx]
        self.audio.emit("experiment_selected")
        self.reset_challenge_cycle()
        self.assess_exp.setText(f"Expected Outcome: {self.active_experiment.expected_security}")
        self.assess_act.setText("Actual Outcome:   Not Run")
        self.assess_res.setText("Assessment:       WAITING")
        self.assess_res.setStyleSheet("color: #E2E8F0; font-family: Consolas, monospace; font-size: 11px; border: none;")

    # =========================================================
    # Stage 6B - Scientific Method Cycle
    # (UI renders state; the pedagogy engine owns correctness & reveal timing)
    # =========================================================
    # =========================================================
    # Stage 7A.1 - Scientific method stage stepper
    # Pure presentation: consumes TamperChallengeSession.state only and
    # adds no logic or state of its own.
    # =========================================================
    def _build_stage_stepper(self):
        stepper = QFrame()
        stepper.setStyleSheet("border: 1px solid #262F3F; background-color: #0F131C; border-radius: 4px;")
        row = QHBoxLayout(stepper)
        row.setContentsMargins(12, 8, 12, 8)
        row.setSpacing(6)

        self.stepper_chips = []
        for i, label in enumerate(self.STEPPER_STAGES):
            chip = QLabel(label)
            chip.setProperty("state", "pending")
            row.addWidget(chip)
            self.stepper_chips.append(chip)
            if i < len(self.STEPPER_STAGES) - 1:
                arrow = QLabel("→")
                arrow.setStyleSheet("color: #4A5568; font-size: 11px; border: none;")
                row.addWidget(arrow)
        row.addStretch()
        return stepper

    def update_stage_stepper(self):
        """Maps the pedagogy session state onto chip states (no logic of its own)."""
        state = self.session.state
        if state == TamperChallengeSession.STATE_PREDICTION:
            profile = ["active", "pending", "pending", "pending", "pending"]
        elif state == TamperChallengeSession.STATE_ARMED:
            profile = ["done", "active", "pending", "pending", "pending"]
        elif state == TamperChallengeSession.STATE_MATCHING:
            # Evidence renders before the session enters MATCHING,
            # so INVESTIGATE is already complete at this point.
            profile = ["done", "done", "done", "active", "pending"]
        else:  # STATE_REVEALED
            profile = ["done", "done", "done", "done", "active"]

        for idx, (chip, chip_state) in enumerate(zip(self.stepper_chips, profile)):
            chip.setProperty("state", chip_state)
            chip.setStyleSheet(self._CHIP_STYLES[chip_state])
            chip.setText(
                f"✓ {self.STEPPER_NAMES[idx]}" if chip_state == "done"
                else self.STEPPER_STAGES[idx]
            )

    def _fly_xp(self, amount):
        """Stage 7A.4: '+N XP' rises and fades near the assessment card."""
        fly = QLabel(f"+{amount} XP", self)
        fly.setStyleSheet("color: #00FF66; font-size: 14px; font-weight: bold; background: transparent; border: none;")
        effect = QGraphicsOpacityEffect(fly)
        fly.setGraphicsEffect(effect)
        start = self.assess_res.mapTo(self, QPoint(0, 0))
        fly.move(start)
        fly.show()
        fly.raise_()

        steps, state = 18, {"i": 0}
        timer = QTimer(self)
        timer.setInterval(50)

        def tick():
            state["i"] += 1
            frac = state["i"] / steps
            try:
                fly.move(start + QPoint(0, -int(30 * frac)))
                effect.setOpacity(1.0 - frac)
            except RuntimeError:
                timer.stop()
                return
            if state["i"] >= steps:
                timer.stop()
                fly.hide()
                fly.deleteLater()

        timer.timeout.connect(tick)
        timer.start()
        self._fly_timer = timer

    def _enter_primary(self):
        """Stage 7A.6: Enter triggers the action the SESSION gate currently
        allows (buttons may stay enabled for free re-runs; the pedagogy
        state machine is authoritative)."""
        state = self.session.state
        if state == TamperChallengeSession.STATE_PREDICTION:
            self.record_prediction_action()
        elif state == TamperChallengeSession.STATE_ARMED:
            self.execute_active_experiment()
        elif state == TamperChallengeSession.STATE_MATCHING:
            self.submit_matching_action()

    def update_layer_chip(self, trace):
        """Stage 7A.2: glanceable defense-layer identity, driven exclusively
        by trace.rejection_layer / trace.success (never re-derived)."""
        if trace.success:
            if self.active_experiment.is_control_group:
                self.layer_chip.setText("✓ VERIFIED — BASELINE HOLDS")
                color = "#00FF66"
            else:
                self.layer_chip.hide()
                return
        elif trace.rejection_layer == "STRUCTURAL":
            self.layer_chip.setText("LAYER 1 — STRUCTURAL VALIDATION")
            color = "#FFA500"
        elif trace.rejection_layer == "CRYPTOGRAPHIC":
            self.layer_chip.setText("LAYER 2 — AEAD VERIFICATION")
            color = "#00F0FF"
        else:
            self.layer_chip.hide()
            return
        self.layer_chip.setStyleSheet(
            f"color: {color}; border: 1px solid {color}; border-radius: 3px; "
            "padding: 3px 8px; font-size: 11px; font-weight: bold;"
        )
        self.layer_chip.show()

    def reset_challenge_cycle(self):
        """Binds the pedagogy session to the active experiment and re-locks the cycle."""
        challenge = get_challenge_for_experiment(self.active_experiment.name)
        self.session.reset(challenge)
        self.update_stage_stepper()

        # Prediction card refresh
        self.predict_question.setText(challenge.prediction_question)
        self.predict_group.setExclusive(False)
        for idx, rad in enumerate(self.predict_radios):
            # QRadioButton cannot word-wrap; wrap manually so long options
            # stay fully readable inside the narrow left column
            rad.setText(textwrap.fill(challenge.prediction_options[idx], width=44))
            rad.setChecked(False)
            rad.setEnabled(True)
        self.predict_group.setExclusive(True)
        self.predict_btn.setEnabled(True)

        # Run locked until a new prediction exists
        self.run_btn.setEnabled(False)

        # Matching card refresh (locked until the experiment ran)
        for (prompt_lbl, combo), item in zip(self.match_rows, challenge.matching_items):
            prompt_lbl.setText(item.prompt)
            combo.clear()
            combo.addItems(item.options)
            combo.setCurrentIndex(0)
            combo.setEnabled(False)
        self.match_submit_btn.setEnabled(False)
        self.reveal_label.setText("")
        self.layer_chip.hide()
        self.layer_chip.setText("")

        self.terminal_area.setText(
            "[!] Volatile In-Memory Sandbox Initialized.\n"
            f"[!] Experiment '{self.active_experiment.name}' loaded. State your prediction first.\n"
            "[!] Cycle: Predict → Experiment → Investigate → Match → Reveal."
        )

    def _on_prediction_radio_toggled(self):
        pass  # selection highlight only; correctness is judged exclusively by the pedagogy engine

    def record_prediction_action(self):
        idx = self.predict_group.checkedId()
        if idx == -1:
            self.terminal_area.append("[!] Select a prediction option first — the laboratory requires a hypothesis.")
            return
        if self.session.record_prediction(idx):
            for rad in self.predict_radios:
                rad.setEnabled(False)
            self.predict_btn.setEnabled(False)
            self.run_btn.setEnabled(True)
            self.audio.emit("prediction_recorded")
            self.update_stage_stepper()
            self.terminal_area.append("[✓] Prediction recorded. Experiment unlocked — run it to gather evidence.")
        else:
            self.terminal_area.append("[!] Prediction already recorded for this cycle.")

    def submit_matching_action(self):
        selections = [combo.currentIndex() for _, combo in self.match_rows]
        if not self.session.submit_matching(selections):
            return  # invalid submission (engine rejected); cycle state unchanged
        self.update_stage_stepper()

        # Lock matching inputs — the reveal is one-shot per cycle
        for _, combo in self.match_rows:
            combo.setEnabled(False)
        self.match_submit_btn.setEnabled(False)

        # Persist outcome into the academy profile (XP awarded exactly once)
        awarded = apply_challenge_outcome(self.progress, self.session)
        ProgressStore.save_progress(self.progress)

        # Stage 6C: feedback + reward registers at reveal.
        # sequence() staggers the sounds - simultaneous QSoundEffects can
        # kill the audio session on the FFmpeg backend.
        verdict_event = "prediction_correct" if self.session.prediction_verdict else "prediction_incorrect"
        match_event = "matching_correct" if all(self.session.matching_results) else "matching_incorrect"
        reveal_events = [verdict_event, match_event, "challenge_completed"]
        if awarded > 0:
            reveal_events.append("xp_awarded")
            self._fly_xp(awarded)  # Stage 7A.4: only actual awards animate
        self.audio.sequence(*reveal_events)

        self.render_reveal(awarded)

        # Stage 7A: bring the reveal into view the moment it appears.
        # The reveal sits at the bottom of the column - scrolling to the
        # bottom is deterministic (ensureWidgetVisible can settle mid-range).
        from PySide6.QtCore import QTimer as _QTim

        def _scroll_reveal_to_bottom():
            # Finalize the layout first: the scrollbar range is not yet
            # updated when the timer fires, and a stale maximum would land
            # the scroll mid-content instead of at the reveal.
            self.right_scroll.widget().adjustSize()
            sb = self.right_scroll.verticalScrollBar()
            sb.setValue(sb.maximum())

        _QTim.singleShot(0, _scroll_reveal_to_bottom)

    def render_reveal(self, awarded):
        challenge = self.session.challenge

        # Prediction verdict (with per-option feedback for wrong hypotheses)
        if self.session.prediction_verdict:
            pred_html = "🔮 Prediction: <b>CORRECT (+10 XP)</b>"
        else:
            feedback = challenge.prediction_feedback.get(str(self.session.predicted_index), "")
            pred_html = f"🔮 Prediction: <b>INCORRECT</b> — {feedback}"

        # Matching results with the correct answers
        match_lines = []
        for item, result in zip(challenge.matching_items, self.session.matching_results):
            icon = "✓" if result else "❌"
            match_lines.append(f"{icon} {item.prompt}: {item.options[item.correct]}")
        match_html = "<br>".join(match_lines)

        repeat_note = " (already completed — no repeat XP)" if awarded == 0 else ""
        xp_html = f"⭐ XP Earned: <b>+{awarded}</b>{repeat_note}"

        self.reveal_label.setText(
            f"{pred_html}<br>{match_html}<br><br>"
            f"📖 <b>Explanation:</b> {self.session.explanation}<br><br>{xp_html}"
        )

        score = sum(self.session.matching_results)
        self.terminal_area.append("--------------------------------------------------")
        self.terminal_area.append(
            f"📖 REVEAL — Prediction: {'CORRECT' if self.session.prediction_verdict else 'INCORRECT'} | "
            f"Matching: {score}/3 | XP: +{awarded}{repeat_note}"
        )

    def execute_active_experiment(self):
        # 1. Trigger volatile sandbox run
        self.audio.emit("experiment_started")
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
        self.update_layer_chip(trace)
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

        # Stage 6B: advance the scientific method cycle (Prediction -> Experiment done)
        if self.session.record_experiment_run():
            for _, combo in self.match_rows:
                combo.setEnabled(True)
            self.match_submit_btn.setEnabled(True)
            self.update_stage_stepper()
            self.terminal_area.append(
                "[✓] Investigation unlocked: examine the trace and hex evidence above, then complete the matching."
            )

        # Stage 6C: mechanical register - the machinery reports which layer answered
        if self.active_experiment.is_control_group and trace.success:
            self.audio.emit("control_group_success")
        elif trace.rejection_layer == "STRUCTURAL":
            self.audio.emit("structural_rejection")
        elif trace.rejection_layer == "CRYPTOGRAPHIC":
            self.audio.emit("cryptographic_rejection")
