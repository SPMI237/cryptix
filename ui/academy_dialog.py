# ui/academy_dialog.py

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
    QStackedWidget,
    QMessageBox,
    QButtonGroup,
    QListWidget,
    QComboBox,
    QSlider,
    QProgressBar
)
from PySide6.QtCore import Qt, QTimer, QPoint
from PySide6.QtWidgets import QGraphicsOpacityEffect
from cryptix_academy.progress import ProgressStore
from cryptix_academy.curriculum import get_lessons, get_questions_for_lesson
from cryptix_academy.models import LearningProgress
from audio.playback import SoundService
from audio.sound_manager import merge_audio_defaults, list_themes

class AcademyDialog(QDialog):
    def __init__(self, parent, audio=None):
        super().__init__(parent)
        self.setWindowTitle("Cryptix Academy - Cybersecurity Laboratory")
        self.setMinimumWidth(700)
        self.setMinimumHeight(650)
        self.setStyleSheet(parent.styleSheet()) # Inherit dark tactical stylesheet

        # Load dynamic progress
        self.progress = ProgressStore.load_progress()
        self.lessons = get_lessons()
        self.is_review_mode = False

        # Stage 6C: audio session (the Academy owns it; the Lab only transitions)
        self.audio = audio if audio is not None else SoundService(self)
        self.audio_settings = self.audio.audio_settings()

        self.init_ui()

    def init_ui(self):
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(20, 20, 20, 20)
        self.main_layout.setSpacing(14)

        # Header Title Area
        header_layout = QHBoxLayout()
        self.title_label = QLabel("🎓 CRYPTIX ACADEMY")
        self.title_label.setStyleSheet("font-size: 16px; font-weight: bold; color: #00F0FF; letter-spacing: 1px;")
        header_layout.addWidget(self.title_label)

        header_layout.addStretch()

        self.xp_label = QLabel(f"XP: {self.progress.xp} | Level {self.progress.level}")
        self.xp_label.setStyleSheet("font-size: 13px; font-weight: bold; color: #00FF66;")
        header_layout.addWidget(self.xp_label)

        self.main_layout.addLayout(header_layout)

        # Accuracies Row
        self.accuracies_label = QLabel("")
        self.accuracies_label.setStyleSheet("font-size: 11px; color: #A0AEC0; font-weight: bold;")
        self.main_layout.addWidget(self.accuracies_label)

        # Audio Bar (Stage 6C): toggles, theme selector, master volume
        audio_bar = QHBoxLayout()
        audio_bar.setSpacing(8)

        self.sfx_toggle = QPushButton("🔊 Effects")
        self.sfx_toggle.setCheckable(True)
        self.sfx_toggle.setChecked(self.audio_settings["sfx_enabled"])
        self.sfx_toggle.setStyleSheet("""
            QPushButton { padding: 4px 10px; font-size: 11px; }
            QPushButton:checked { background-color: #00F0FF; color: #000000; font-weight: bold; }
        """)
        self.sfx_toggle.clicked.connect(self.toggle_sfx)
        audio_bar.addWidget(self.sfx_toggle)

        self.music_toggle = QPushButton("🎵 Music")
        self.music_toggle.setCheckable(True)
        self.music_toggle.setChecked(self.audio_settings["music_enabled"])
        self.music_toggle.setStyleSheet("""
            QPushButton { padding: 4px 10px; font-size: 11px; }
            QPushButton:checked { background-color: #00F0FF; color: #000000; font-weight: bold; }
        """)
        self.music_toggle.clicked.connect(self.toggle_music)
        audio_bar.addWidget(self.music_toggle)

        theme_label = QLabel("Theme:")
        theme_label.setStyleSheet("color: #A0AEC0; font-size: 11px;")
        audio_bar.addWidget(theme_label)

        self.theme_selector = QComboBox()
        available_themes = list_themes()
        if available_themes:
            for name in available_themes:
                self.theme_selector.addItem(name)
            idx = self.theme_selector.findText(self.audio_settings["theme"])
            if idx >= 0:
                self.theme_selector.setCurrentIndex(idx)
        else:
            # Actionable empty state instead of a silent blank dropdown
            self.theme_selector.addItem("⚠ No audio themes - run: python -m audio.make_sounds")
        self.theme_selector.currentTextChanged.connect(self.change_audio_theme)
        audio_bar.addWidget(self.theme_selector)

        volume_label = QLabel("Volume:")
        volume_label.setStyleSheet("color: #A0AEC0; font-size: 11px;")
        audio_bar.addWidget(volume_label)

        self.volume_slider = QSlider(Qt.Orientation.Horizontal)
        self.volume_slider.setRange(0, 100)
        self.volume_slider.setValue(int(self.audio_settings["master_volume"] * 100))
        self.volume_slider.setMaximumWidth(120)
        self.volume_slider.valueChanged.connect(self.change_master_volume)
        audio_bar.addWidget(self.volume_slider)

        audio_bar.addStretch()
        self.main_layout.addLayout(audio_bar)

        # Separator Line
        divider = QFrame()
        divider.setFrameShape(QFrame.Shape.HLine)
        divider.setStyleSheet("background-color: #262F3F; max-height: 1px;")
        self.main_layout.addWidget(divider)

        # Stacked Widget for Page Transitions
        self.stacked_widget = QStackedWidget()
        self.main_layout.addWidget(self.stacked_widget)

        # Page 1: Curriculum Dashboard
        self.dashboard_page = QWidget()
        self.init_dashboard_page()
        self.stacked_widget.addWidget(self.dashboard_page)

        # Page 2: Lesson Viewer
        self.lesson_page = QWidget()
        self.stacked_widget.addWidget(self.lesson_page)

        # Page 3: Challenge Viewer
        self.challenge_page = QWidget()
        self.stacked_widget.addWidget(self.challenge_page)

        self.stacked_widget.setCurrentIndex(0)

    # =========================================================
    # Page 1: Curriculum Dashboard
    # =========================================================
    def init_dashboard_page(self):
        dash_layout = QVBoxLayout(self.dashboard_page)
        dash_layout.setContentsMargins(0, 0, 0, 0)
        dash_layout.setSpacing(10)

        desc = QLabel("Complete lessons and interactive challenges to master cryptographic engineering.")
        desc.setStyleSheet("color: #A0AEC0; font-style: italic;")
        desc.setWordWrap(True)
        dash_layout.addWidget(desc)

        # Scrollable level list
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("border: 1px solid #262F3F; background-color: #0B0F19;")
        dash_layout.addWidget(scroll)

        scroll_content = QWidget()
        self.level_list_layout = QVBoxLayout(scroll_content)
        self.level_list_layout.setSpacing(8)
        self.level_list_layout.setContentsMargins(10, 10, 10, 10)

        self.refresh_dashboard()

        scroll.setWidget(scroll_content)

        # Bottom Actions
        bottom_box = QHBoxLayout()
        reset_btn = QPushButton("Reset Progress")
        reset_btn.setStyleSheet("color: #FF3B3B; padding: 6px;")
        reset_btn.clicked.connect(self.reset_learning_progress)
        bottom_box.addWidget(reset_btn)

        bottom_box.addStretch()

        close_btn = QPushButton("Close")
        close_btn.setMinimumWidth(100)
        close_btn.clicked.connect(self.accept)
        bottom_box.addWidget(close_btn)

        dash_layout.addLayout(bottom_box)

    def calculate_lesson_mastery(self, lesson_id: str) -> float:
        """
        Calculates diagnostic concept mastery % based on first-attempt accuracy
        over all questions inside the target lesson.
        """
        questions = get_questions_for_lesson(lesson_id)
        if not questions:
            return 0.0
        
        first_attempt_correct = 0
        for q in questions:
            q_trace = self.progress.completed_challenges.get(q.id)
            if q_trace and q_trace.get("first_attempt", False):
                first_attempt_correct += 1
                
        return (first_attempt_correct / len(questions)) * 100.0

    def refresh_dashboard(self):
        self.mastery_bars = {}
        # Clear existing items in layout
        while self.level_list_layout.count():
            item = self.level_list_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        # Repopulate list
        unlocked = True # First level is always unlocked
        for idx, lesson in enumerate(self.lessons):
            btn = QPushButton()
            btn.setMinimumHeight(55)
            btn.setStyleSheet("text-align: left; padding: 12px; font-weight: bold;")

            completed = lesson.id in self.progress.completed_lessons
            mastery = self.calculate_lesson_mastery(lesson.id)

            # Determine lock status and styling
            if completed:
                status_icon = "✓"
                status_color = "#00FF66" # Green
                btn.setEnabled(True)
            elif unlocked:
                status_icon = "🔓"
                status_color = "#00F0FF" # Cyan
                btn.setEnabled(True)
                unlocked = False # Subsequent ones remain locked until current completed
            else:
                status_icon = "🔒"
                status_color = "#4A5568" # Gray
                btn.setEnabled(False)

            btn.setText(f"{status_icon}  [Mastery: {mastery:.0f}%]  {lesson.title}")
            btn.setStyleSheet(f"""
                QPushButton {{
                    text-align: left; 
                    padding: 12px; 
                    font-weight: bold;
                    color: {status_color};
                    background-color: #131822;
                    border: 1px solid #262F3F;
                }}
                QPushButton:hover {{
                    border: 1px solid {status_color};
                }}
            """)

            # Connect transition closure
            btn.clicked.connect(lambda checked=False, l=lesson: self.open_lesson(l))
            self.level_list_layout.addWidget(btn)

            # Stage 7A.5: slim mastery bar (existing mastery data, now visual)
            bar = QProgressBar()
            bar.setRange(0, 100)
            bar.setValue(int(mastery))
            bar.setFixedHeight(6)
            bar.setTextVisible(False)
            if completed:
                bar_color = "#00FF66"   # mastered
            elif btn.isEnabled():
                bar_color = "#00F0FF"   # current (unlocked, not finished)
            else:
                bar_color = "#262F3F"   # locked
            bar.setStyleSheet(
                f"QProgressBar {{ border: none; background-color: #131822; border-radius: 3px; }}"
                f"QProgressBar::chunk {{ background-color: {bar_color}; border-radius: 3px; }}"
            )
            self.mastery_bars[lesson.id] = bar
            self.level_list_layout.addWidget(bar)

            # If the current level is completed, it unlocks the next level
            if completed:
                unlocked = True

        # If all 7 lessons are completed, unlock the advanced Tamper Lab gateway!
        all_completed = all(l.id in self.progress.completed_lessons for l in self.lessons)
        if all_completed:
            lab_btn = QPushButton("🧪 Open Advanced Tamper Lab")
            lab_btn.setMinimumHeight(55)
            lab_btn.setStyleSheet("""
                QPushButton {
                    text-align: left; 
                    padding: 12px; 
                    font-weight: bold;
                    color: #D300FF;  /* Purple highlight */
                    background-color: #131822;
                    border: 2px dashed #D300FF;
                }
                QPushButton:hover {
                    background-color: #0F131C;
                    border: 2px solid #D300FF;
                }
            """)
            lab_btn.clicked.connect(self.open_tamper_lab)
            self.level_list_layout.addWidget(lab_btn)

        self.level_list_layout.addStretch()
        self.update_xp_header()

    # =========================================================
    # Page 2: Lesson Viewer
    # =========================================================
    def open_lesson(self, lesson):
        # Clear lesson page layout
        if self.lesson_page.layout():
            QWidget().setLayout(self.lesson_page.layout()) # Destroys layout safely

        layout = QVBoxLayout(self.lesson_page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        title = QLabel(lesson.title)
        title.setStyleSheet("font-size: 15px; font-weight: bold; color: #00F0FF;")
        layout.addWidget(title)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("border: 1px solid #262F3F; background-color: #0B0F19;")
        layout.addWidget(scroll)

        content_widget = QWidget()
        text_layout = QVBoxLayout(content_widget)
        text_layout.setSpacing(10)

        # Primary content
        content_label = QLabel(lesson.content)
        content_label.setWordWrap(True)
        content_label.setStyleSheet("color: #E2E8F0; font-size: 13px; line-height: 150%;")
        text_layout.addWidget(content_label)

        # Simple explanation
        simple_title = QLabel("🟢 Simple Explanation")
        simple_title.setStyleSheet("color: #00FF66; font-weight: bold; margin-top: 10px;")
        simple_desc = QLabel(lesson.simple_explanation)
        simple_desc.setWordWrap(True)
        simple_desc.setStyleSheet("color: #A0AEC0; font-size: 12px;")
        text_layout.addWidget(simple_title)
        text_layout.addWidget(simple_desc)

        # Technical explanation
        tech_title = QLabel("🔵 Technical Explanation")
        tech_title.setStyleSheet("color: #00F0FF; font-weight: bold; margin-top: 10px;")
        tech_desc = QLabel(lesson.technical_explanation)
        tech_desc.setWordWrap(True)
        tech_desc.setStyleSheet("color: #A0AEC0; font-size: 12px;")
        text_layout.addWidget(tech_title)
        text_layout.addWidget(tech_desc)

        # Security threat explanation
        sec_title = QLabel("🔴 Security Value")
        sec_title.setStyleSheet("color: #FF3B3B; font-weight: bold; margin-top: 10px;")
        sec_desc = QLabel(lesson.security_explanation)
        sec_desc.setWordWrap(True)
        sec_desc.setStyleSheet("color: #A0AEC0; font-size: 12px;")
        text_layout.addWidget(sec_title)
        text_layout.addWidget(sec_desc)

        scroll.setWidget(content_widget)

        # Actions
        btn_box = QHBoxLayout()
        back_btn = QPushButton("← Dashboard")
        back_btn.clicked.connect(self.go_to_dashboard)
        btn_box.addWidget(back_btn)

        btn_box.addStretch()

        completed = lesson.id in self.progress.completed_lessons
        challenge_btn_text = "📖 Review Completed Challenges" if completed else "📝 Start Interactive Challenge"
        
        challenge_btn = QPushButton(challenge_btn_text)
        challenge_btn.setStyleSheet("background-color: #00AAFF; color: #FFFFFF; font-weight: bold;")
        challenge_btn.clicked.connect(lambda: self.open_challenge(lesson))
        btn_box.addWidget(challenge_btn)

        layout.addLayout(btn_box)
        self.stacked_widget.setCurrentIndex(1)

    # =========================================================
    # Page 3: Challenge Viewer
    # =========================================================
    def open_challenge(self, lesson):
        # Fetch the questions for this lesson
        questions = get_questions_for_lesson(lesson.id)
        if not questions:
            QMessageBox.information(self, "Curriculum Notification", "No challenges created for this level yet.")
            return

        # Handle review mode trigger
        self.is_review_mode = lesson.id in self.progress.completed_lessons

        if self.is_review_mode:
            # Review mode starts at first question, or keeps sequence
            if not hasattr(self, "active_question") or self.active_question.lesson_id != lesson.id:
                self.active_question = questions[0]
        else:
            # Challenge Mode loads first uncompleted question
            self.active_question = questions[0]
            for q in questions:
                if q.id not in self.progress.completed_challenges:
                    self.active_question = q
                    break

        # Instantiate Challenge Session Engine
        from cryptix_academy.engine import ChallengeSession
        self.active_session = ChallengeSession(self.active_question, lesson)

        # Rebuild challenge page layout
        if self.challenge_page.layout():
            QWidget().setLayout(self.challenge_page.layout())

        self.challenge_layout = QVBoxLayout(self.challenge_page)
        self.challenge_layout.setContentsMargins(0, 0, 0, 0)
        self.challenge_layout.setSpacing(14)

        # Question header
        mode_label = "📖 REVIEW MODE" if self.is_review_mode else f"🎓 CHALLENGE — {lesson.category}"
        category_label = QLabel(mode_label)
        category_label.setStyleSheet("color: #00F0FF; font-weight: bold; font-size: 11px;")
        self.challenge_layout.addWidget(category_label)

        # Live XP reward badge (XP transparency: what a correct answer is worth NOW)
        self.xp_reward_label = QLabel("")
        self.challenge_layout.addWidget(self.xp_reward_label)
        self.update_xp_reward_display()

        question_label = QLabel(self.active_question.question)
        question_label.setWordWrap(True)
        question_label.setStyleSheet("font-size: 14px; font-weight: bold; color: #E2E8F0;")
        self.challenge_layout.addWidget(question_label)

        # Hint Box (Show explanation immediately in Review mode, hidden in challenge mode)
        self.hint_display_label = QLabel("")
        self.hint_display_label.setWordWrap(True)
        
        if self.is_review_mode:
            self.hint_display_label.setText(f"✓ Solved Explanation: {self.active_question.explanation}")
            self.hint_display_label.setStyleSheet("color: #00FF66; background-color: #131822; padding: 10px; border: 1px dashed #00FF66; font-size: 11px;")
            self.hint_display_label.show()
        else:
            self.hint_display_label.setStyleSheet("color: #00F0FF; background-color: #131822; padding: 10px; border: 1px dashed #262F3F; font-size: 11px;")
            self.hint_display_label.hide()
        self.challenge_layout.addWidget(self.hint_display_label)

        # Render options based on Question Type
        self.options_group = QButtonGroup(self)
        self.options_buttons = []

        if self.active_question.question_type == "choice" or self.active_question.question_type == "boolean":
            # Multiple Choice or Boolean (True/False)
            options_box = QVBoxLayout()
            options_box.setSpacing(8)

            for idx, option in enumerate(self.active_question.options):
                opt_btn = QPushButton(option)
                opt_btn.setCheckable(True)
                opt_btn.setStyleSheet("""
                    QPushButton {
                        text-align: left;
                        padding: 10px;
                        background-color: #131822;
                        border: 1px solid #262F3F;
                        color: #A0AEC0;
                    }
                    QPushButton:checked {
                        border: 1px solid #00F0FF;
                        color: #00F0FF;
                        background-color: #0F131C;
                    }
                """)
                self.options_group.addButton(opt_btn, idx)
                self.options_buttons.append(opt_btn)
                options_box.addWidget(opt_btn)

                # Pre-highlight correct option in Review Mode
                if self.is_review_mode:
                    if self.active_question.question_type == "choice":
                        is_correct = (chr(65 + idx) == self.active_question.correct_answer)
                    else:
                        is_correct = (option == self.active_question.correct_answer)

                    if is_correct:
                        opt_btn.setChecked(True)
                        opt_btn.setStyleSheet("""
                            QPushButton {
                                text-align: left;
                                padding: 10px;
                                background-color: #131822;
                                border: 2px solid #00FF66;
                                color: #00FF66;
                                font-weight: bold;
                            }
                        """)
                    opt_btn.setEnabled(False) # Disable clicks

            self.challenge_layout.addLayout(options_box)

        elif self.active_question.question_type == "ordering":
            # Ordering Challenge
            self.ordering_label = QLabel("Click the items below in the correct order:")
            self.ordering_label.setStyleSheet("color: #A0AEC0; font-style: italic;")
            self.challenge_layout.addWidget(self.ordering_label)

            # Raw buttons to click
            self.order_source_layout = QHBoxLayout()
            self.order_source_layout.setSpacing(6)
            self.ordered_selection_indices = []

            for idx, option in enumerate(self.active_question.options):
                item_btn = QPushButton(option)
                item_btn.setMinimumHeight(36)
                item_btn.clicked.connect(lambda checked=False, i=idx: self.select_ordering_item(i))
                self.options_buttons.append(item_btn)
                self.order_source_layout.addWidget(item_btn)
                if self.is_review_mode:
                    item_btn.setEnabled(False)

            self.challenge_layout.addLayout(self.order_source_layout)

            # Selection Result display
            result_txt = f"Correct Sequence: [ {self.active_question.correct_answer} ]" if self.is_review_mode else "Your Sequence: [ None ]"
            self.ordering_result_label = QLabel(result_txt)
            self.ordering_result_label.setStyleSheet("color: #00F0FF; font-weight: bold; margin-top: 10px;")
            self.challenge_layout.addWidget(self.ordering_result_label)

            # Reset sequence button
            if not self.is_review_mode:
                self.clear_order_btn = QPushButton("Clear Sequence Selection")
                self.clear_order_btn.setStyleSheet("color: gray; border: 1px dashed #262F3F; padding: 4px;")
                self.clear_order_btn.clicked.connect(self.clear_ordering_sequence)
                self.challenge_layout.addWidget(self.clear_order_btn)

        # Stage 7A.3: inline wrong-answer feedback panel (no modal interruption)
        self.inline_feedback_label = QLabel("")
        self.inline_feedback_label.setWordWrap(True)
        self.inline_feedback_label.hide()
        self.challenge_layout.addWidget(self.inline_feedback_label)
        for opt_btn in getattr(self, "options_buttons", []):
            opt_btn.clicked.connect(self._clear_inline_feedback)

        # Action Buttons
        btn_box = QHBoxLayout()
        back_to_lesson_btn = QPushButton("← Lesson")
        back_to_lesson_btn.clicked.connect(lambda: self.open_lesson(lesson))
        btn_box.addWidget(back_to_lesson_btn)

        if not self.is_review_mode:
            self.hint_btn = QPushButton("💡 Request Hint")
            self.hint_btn.clicked.connect(self.request_hint_action)
            self.hint_btn.setStyleSheet("color: #00F0FF; border: 1px dashed #262F3F;")
            btn_box.addWidget(self.hint_btn)

        btn_box.addStretch()

        # Update button text for Review Mode Navigation
        if self.is_review_mode:
            current_idx = questions.index(self.active_question)
            has_next = (current_idx + 1 < len(questions))
            submit_text = "Next Question →" if has_next else "Finish Review ✓"
        else:
            submit_text = "Submit Answer"

        self.submit_btn = QPushButton(submit_text)
        self.submit_btn.setMinimumWidth(120)
        self.submit_btn.setStyleSheet("background-color: #00FF66; color: #000000; font-weight: bold;")
        self.submit_btn.clicked.connect(lambda: self.submit_answer(lesson))
        btn_box.addWidget(self.submit_btn)

        # Stage 7A.6: keyboard shortcuts (retired and rebuilt on each open_challenge)
        from PySide6.QtGui import QShortcut, QKeySequence
        for old_sc in getattr(self, "_page_shortcuts", []):
            old_sc.setEnabled(False)
            old_sc.deleteLater()
        self._page_shortcuts = []

        def _add_shortcut(seq, handler):
            sc = QShortcut(QKeySequence(seq), self)
            sc.activated.connect(handler)
            self._page_shortcuts.append(sc)

        _add_shortcut("Return", self.submit_btn.click)
        _add_shortcut("Enter", self.submit_btn.click)
        if not self.is_review_mode:
            for i in range(4):
                _add_shortcut(str(i + 1), lambda i=i: self._keyboard_select(i))
            _add_shortcut("H", self._keyboard_hint)

        self.challenge_layout.addLayout(btn_box)
        self.stacked_widget.setCurrentIndex(2)

    def request_hint_action(self):
        hint_text = self.active_session.request_next_hint()
        self.hint_display_label.setText(hint_text)
        self.hint_display_label.show()
        self.update_xp_reward_display()  # hint penalty applies immediately

        # If all hints are revealed (hint_level reaches 3), show exhaustion state
        if self.active_session.hint_level >= 3:
            self.hint_btn.setText("💡 All hints revealed")
            self.hint_btn.setEnabled(False)

    def select_ordering_item(self, idx):
        if idx not in self.ordered_selection_indices:
            self.ordered_selection_indices.append(idx)
            self.options_buttons[idx].setEnabled(False) # Disable clicked button

            # Update sequence string
            sequence_text = " → ".join([self.active_question.options[i] for i in self.ordered_selection_indices])
            self.ordering_result_label.setText(f"Your Sequence: [ {sequence_text} ]")

    def clear_ordering_sequence(self):
        self.ordered_selection_indices.clear()
        self.ordering_result_label.setText("Your Sequence: [ None ]")
        for btn in self.options_buttons:
            btn.setEnabled(True)

    def submit_answer(self, lesson):
        questions = get_questions_for_lesson(lesson.id)

        # Review Mode Navigation Handler
        if self.is_review_mode:
            current_idx = questions.index(self.active_question)
            if current_idx + 1 < len(questions):
                self.active_question = questions[current_idx + 1]
                self.open_challenge(lesson)
            else:
                # Review complete, clean memory and redirect
                delattr(self, "active_question")
                QMessageBox.information(self, "Review Complete", "You have finished reviewing all challenges for this level.")
                self.go_to_dashboard()
            return

        # 1. Parse Answer based on type
        student_answer = ""

        if self.active_question.question_type == "choice" or self.active_question.question_type == "boolean":
            checked_id = self.options_group.checkedId()
            if checked_id == -1:
                QMessageBox.warning(self, "Invalid Submission", "Please select an answer choice before submitting.")
                return
            
            # Decoupled index transmission for choices
            if self.active_question.question_type == "choice":
                student_answer = str(checked_id)
            else:
                # Boolean
                student_answer = self.active_question.options[checked_id]

        elif self.active_question.question_type == "ordering":
            if len(self.ordered_selection_indices) < len(self.active_question.options):
                QMessageBox.warning(self, "Invalid Submission", "Please order all items in the sequence before submitting.")
                return
            student_answer = ",".join([str(i) for i in self.ordered_selection_indices])

        # 2. Run Engine Evaluation
        # Increment total attempts globally
        self.progress.total_attempts += 1

        res = self.active_session.evaluate(student_answer)

        # Stage 6C: feedback register - reflecting the student's result
        self.audio.emit("question_correct" if res.correct else "question_incorrect")

        # Record pre-submission level for sequential level-up detection
        old_level = self.progress.level

        # 3. Handle result
        if res.correct:
            xp_reward = res.score
            awarded_xp = 0  # actually granted (0 on re-completion / review)
            
            # Check if this challenge is already completed to avoid duplicate farming
            if self.active_question.id not in self.progress.completed_challenges:
                self.progress.completed_challenges[self.active_question.id] = {
                    "attempts": res.attempts,
                    "hints_used": res.hint_level,
                    "xp": xp_reward,
                    "first_attempt": (res.attempts == 1)
                }
                self.progress.xp += xp_reward
                awarded_xp = xp_reward

                # Stage 6C: reward register - XP granted, challenge completed.
                # Sequenced (never simultaneous) for backend safety.
                self.audio.sequence("xp_awarded", "challenge_completed")
                
                # Increment first attempt success counter if answered correctly on first try!
                if res.attempts == 1:
                    self.progress.first_attempt_successes += 1

            # Check if all challenges of this lesson are completed to unlock next lesson
            lesson_finished = all(q.id in self.progress.completed_challenges for q in questions)
            if lesson_finished and lesson.id not in self.progress.completed_lessons:
                self.progress.completed_lessons.append(lesson.id)

            # Level directly matches the maximum sequential level milestone unlocked/reached
            current_level = 1
            for l in self.lessons:
                if l.id in self.progress.completed_lessons:
                    current_level += 1
                else:
                    break
            self.progress.level = current_level

            # Persist dynamic progress
            ProgressStore.save_progress(self.progress)

            # Instantly update XP label inside active challenge window
            self.update_xp_header()
            if awarded_xp > 0:
                self._fly_xp(awarded_xp)  # Stage 7A.4: zero-award animates nothing

            # Show Challenge Summary Dialog
            first_attempt_status = "YES" if res.attempts == 1 else "NO"
            repeat_note = "" if awarded_xp > 0 else " (already completed — no repeat XP)"
            QMessageBox.information(
                self,
                "🎯 Challenge Complete!",
                f"• Concept: {lesson.category}\n"
                f"• Attempts Made: {res.attempts}\n"
                f"• Hints Requested: {res.hint_level} / 3\n"
                f"• XP Earned: +{awarded_xp} XP{repeat_note}\n"
                f"• First-Attempt Success: {first_attempt_status}\n\n"
                f"Explanation:\n{res.explanation}"
            )

            # Check if there are more uncompleted questions in this active lesson
            uncompleted_questions = [q for q in questions if q.id not in self.progress.completed_challenges]

            if uncompleted_questions:
                # Flow smoothly to the next question of the same lesson
                self.open_challenge(lesson)
            else:
                # All questions for this lesson are complete!
                # Show Level-Up Popup if consecutive levels unlocked
                if self.progress.level > old_level:
                    unlocked_lesson = self.lessons[self.progress.level - 1] if (self.progress.level - 1) < len(self.lessons) else None
                    next_title = unlocked_lesson.title if unlocked_lesson else "Master Cryptographer"
                    QMessageBox.information(
                        self,
                        "🏆 LEVEL UP!",
                        f"CONGRATULATIONS!\n\n"
                        f"You have leveled up to Level {self.progress.level}!\n\n"
                        f"Newly Unlocked milestone:\n'{next_title}'\n\n"
                        f"Your concept mastery has been stored on your Dashboard."
                    )
                else:
                    QMessageBox.information(
                        self,
                        "🎉 Lesson Completed!",
                        f"Congratulations! You have completed all challenges for:\n'{lesson.title}'.\n\n"
                        f"Select your next task from your Dashboard!"
                    )
                self.refresh_dashboard()
                self.stacked_widget.setCurrentIndex(0)
        else:
            self.update_xp_reward_display()  # attempt tier dropped - show new worth
            self.show_inline_feedback(res.feedback)

    # =========================================================
    # Stage 6C - Audio Session (Academy owns the ambience)
    # =========================================================
    def showEvent(self, event):
        super().showEvent(event)
        if not getattr(self, "_audio_announced", False):
            self._audio_announced = True
            self.audio.emit("academy_opened")
            self.audio.start_ambience("academy_loop")
            if not list_themes():
                QMessageBox.warning(
                    self,
                    "Audio Themes Missing",
                    "No audio theme packs were found under audio/themes/.\n\n"
                    "Cryptix ships with a built-in theme generator.\n"
                    "Run this command from your project root:\n\n"
                    "    python -m audio.make_sounds\n\n"
                    "Then restart Cryptix Academy."
                )

    def done(self, result):
        try:
            self.audio.stop_ambience()
        except Exception:
            pass
        super().done(result)

    def toggle_sfx(self, checked):
        self.audio.update_setting("sfx_enabled", checked)

    def toggle_music(self, checked):
        self.audio.update_setting("music_enabled", checked)
        if checked:
            self.audio.start_ambience("academy_loop")
        else:
            self.audio.stop_ambience()

    def change_audio_theme(self, name):
        if name in list_themes():  # ignore the "no themes" hint entry
            self.audio.update_setting("theme", name)

    def change_master_volume(self, value):
        self.audio.update_setting("master_volume", value / 100.0)

    # =========================================================
    # Resets & Navigation Utilities
    # =========================================================
    def _keyboard_select(self, idx):
        """Stage 7A.6: keys 1-4 select an answer option (choice/boolean)."""
        if self.is_review_mode:
            return
        if self.active_question.question_type not in ("choice", "boolean"):
            return
        buttons = getattr(self, "options_buttons", [])
        if 0 <= idx < len(buttons) and buttons[idx].isEnabled():
            buttons[idx].click()

    def _keyboard_hint(self):
        btn = getattr(self, "hint_btn", None)
        if btn is not None and btn.isEnabled():
            self.request_hint_action()

    def _fly_xp(self, amount):
        """Stage 7A.4: '+N XP' rises ~30px and fades near the XP header.
        Purely cosmetic; fire-and-forget; never blocks (QTimer steps)."""
        fly = QLabel(f"+{amount} XP", self)
        fly.setStyleSheet("color: #00FF66; font-size: 14px; font-weight: bold; background: transparent; border: none;")
        effect = QGraphicsOpacityEffect(fly)
        fly.setGraphicsEffect(effect)
        start = self.xp_label.mapTo(self, QPoint(0, 0))
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
        self._fly_timer = timer  # keep a reference alive

    def show_inline_feedback(self, feedback):
        """Stage 7A.3: wrong answers stay in-page; the question remains active."""
        self.inline_feedback_label.setText(
            f"❌ {feedback}\nTry again — or press H for a hint."
        )
        self.inline_feedback_label.setStyleSheet(
            "background-color: #2A1215; border: 1px solid #FF3B3B; border-radius: 4px;"
            "color: #FFB4B4; padding: 10px; font-size: 12px;"
        )
        self.inline_feedback_label.show()

    def _clear_inline_feedback(self):
        if hasattr(self, "inline_feedback_label"):
            self.inline_feedback_label.hide()
            self.inline_feedback_label.setText("")

    def update_xp_reward_display(self):
        """XP transparency: live badge showing what a correct answer is
        worth RIGHT NOW (attempt tier + hint penalties factored)."""
        if not hasattr(self, "xp_reward_label"):
            return
        if self.is_review_mode:
            self.xp_reward_label.setText("📖 Review Mode — no XP awarded")
            self.xp_reward_label.setStyleSheet("color: #A0AEC0; font-size: 11px; font-weight: bold;")
            return
        xp = self.active_session.current_xp_potential()
        base = 15 if self.active_question.question_type == "ordering" else 10
        if xp >= base:
            color, note = "#00FF66", ""
        else:
            color, note = "#FFA500", " (hints and failed attempts reduce the reward)"
        self.xp_reward_label.setText(f"🎯 Worth: {xp} XP{note}")
        self.xp_reward_label.setStyleSheet(f"color: {color}; font-size: 11px; font-weight: bold;")

    def update_xp_header(self):
        self.xp_label.setText(f"XP: {self.progress.xp} | Level {self.progress.level}")
        
        # Calculate accuracies safely
        total_completed = len(self.progress.completed_challenges)
        first_attempt_pct = (self.progress.first_attempt_successes / total_completed * 100.0) if total_completed > 0 else 100.0
        completion_pct = (total_completed / self.progress.total_attempts * 100.0) if self.progress.total_attempts > 0 else 100.0

        self.accuracies_label.setText(
            f"First-Attempt Accuracy: {first_attempt_pct:.1f}%  |  Completion Accuracy: {completion_pct:.1f}%"
        )

    def go_to_dashboard(self):
        self.refresh_dashboard()
        self.stacked_widget.setCurrentIndex(0)

    def open_tamper_lab(self):
        from ui.tamper_lab_dialog import TamperLabDialog
        dialog = TamperLabDialog(self, self.progress, self.audio)
        dialog.exec()
        # Refresh academy stats — the lab may have awarded diagnostic XP (Stage 6B)
        self.update_xp_header()
        self.refresh_dashboard()
        # Stage 6C: the Lab closed — transition ambience back to the Academy
        self.audio.transition_to("academy_loop")

    def reset_learning_progress(self):
        reply = QMessageBox.question(
            self,
            "Reset Learning Progress",
            "Are you sure you want to permanently delete your Academy XP, Levels, and completed lessons?\n\nThis action cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.progress = ProgressStore.reset_progress()
            self.refresh_dashboard()
            QMessageBox.information(self, "Progress Reset", "Your Academy profile has been cleanly reset.")
