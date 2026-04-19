"""Focus GFX Shine 생성 다이얼로그."""

import os

from PyQt6.QtWidgets import (
    QApplication, QDialog, QFileDialog, QFormLayout, QHBoxLayout, QLabel,
    QLineEdit, QMessageBox, QPushButton, QTextEdit, QVBoxLayout,
)

from ...services.focus_shine import FocusGFXShineGenerator


class FocusShineDialog(QDialog):
    """Goals GFX에 누락된 shine 효과를 생성한다."""

    _HOI4_MOD_DEFAULT = r"~\Documents\Paradox Interactive\Hearts of Iron IV\mod"

    def __init__(self, parent=None, mod_folder_path=None):
        super().__init__(parent)
        self.setWindowTitle("Focus GFX Shine 생성기")
        self.setModal(True)
        self.resize(600, 400)
        self.generator = FocusGFXShineGenerator()
        self.mod_folder_path = mod_folder_path

        layout = QVBoxLayout()
        self.setLayout(layout)

        desc_label = QLabel(
            "\nFocus tree의 GFX 파일에서 누락된 shine 효과를 자동으로 생성합니다.\n"
            "Goals GFX 파일과 Goals Shine GFX 파일을 선택하세요.\n        "
        )
        desc_label.setWordWrap(True)
        layout.addWidget(desc_label)

        form_layout = QFormLayout()

        self.goals_file_edit = QLineEdit()
        goals_browse_btn = QPushButton("찾아보기")
        goals_browse_btn.clicked.connect(self.browse_goals_file)
        goals_layout = QHBoxLayout()
        goals_layout.addWidget(self.goals_file_edit)
        goals_layout.addWidget(goals_browse_btn)
        form_layout.addRow("Goals GFX 파일:", goals_layout)

        self.shine_file_edit = QLineEdit()
        shine_browse_btn = QPushButton("찾아보기")
        shine_browse_btn.clicked.connect(self.browse_shine_file)
        shine_layout = QHBoxLayout()
        shine_layout.addWidget(self.shine_file_edit)
        shine_layout.addWidget(shine_browse_btn)
        form_layout.addRow("Goals Shine GFX 파일:", shine_layout)

        layout.addLayout(form_layout)

        self.result_text = QTextEdit()
        self.result_text.setReadOnly(True)
        self.result_text.setMaximumHeight(150)
        layout.addWidget(QLabel("결과:"))
        layout.addWidget(self.result_text)

        button_layout = QHBoxLayout()
        self.generate_btn = QPushButton("Shine 생성")
        self.generate_btn.clicked.connect(self.generate_shine)
        button_layout.addWidget(self.generate_btn)
        close_btn = QPushButton("닫기")
        close_btn.clicked.connect(self.close)
        button_layout.addWidget(close_btn)
        layout.addLayout(button_layout)

    def _default_path(self):
        default_path = self.mod_folder_path or os.path.expanduser(self._HOI4_MOD_DEFAULT)
        if not os.path.exists(default_path):
            default_path = os.path.expanduser("~/Documents")
        return default_path

    def _pick_gfx_file(self, title, line_edit):
        file_path, _ = QFileDialog.getOpenFileName(
            self, title, self._default_path(),
            "GFX 파일 (*.gfx);;모든 파일 (*)",
        )
        if not file_path:
            return
        if self.mod_folder_path and file_path.startswith(self.mod_folder_path):
            line_edit.setText(os.path.relpath(file_path, self.mod_folder_path))
        else:
            line_edit.setText(file_path)

    def browse_goals_file(self):
        self._pick_gfx_file("Goals GFX 파일 선택", self.goals_file_edit)

    def browse_shine_file(self):
        self._pick_gfx_file("Goals Shine GFX 파일 선택", self.shine_file_edit)

    def _resolve(self, path):
        if self.mod_folder_path and not os.path.isabs(path):
            return os.path.join(self.mod_folder_path, path)
        return path

    def generate_shine(self):
        goals_file = self.goals_file_edit.text().strip()
        shine_file = self.shine_file_edit.text().strip()

        if not goals_file or not shine_file:
            QMessageBox.warning(self, "경고", "Goals 파일과 Shine 파일을 모두 선택해주세요.")
            return

        goals_file = self._resolve(goals_file)
        shine_file = self._resolve(shine_file)

        if not os.path.exists(goals_file):
            QMessageBox.warning(self, "경고", f"Goals 파일을 찾을 수 없습니다: {goals_file}")
            return
        if not os.path.exists(shine_file):
            QMessageBox.warning(self, "경고", f"Shine 파일을 찾을 수 없습니다: {shine_file}")
            return

        self.result_text.setText("Shine 효과를 생성 중...")
        self.generate_btn.setEnabled(False)
        QApplication.processEvents()

        try:
            result = self.generator.process_files(goals_file, shine_file)

            if not result["success"]:
                error_msg = f"오류가 발생했습니다: {result['error']}"
                self.result_text.setText(error_msg)
                QMessageBox.critical(self, "오류", result["error"])
                return

            if result["added_count"] > 0:
                lines = [
                    f"성공적으로 {result['added_count']}개의 shine 효과를 생성했습니다!",
                    "",
                    "추가된 항목들:",
                ]
                lines.extend(f"  - {name}_shine" for name in result["missing_shine"])
                self.result_text.setText("\n".join(lines))
                QMessageBox.information(self, "완료", f"{result['added_count']}개의 shine 효과가 생성되었습니다.")
            else:
                self.result_text.setText("ℹ️ 추가할 shine 효과가 없습니다. 모든 항목이 이미 존재합니다.")
                QMessageBox.information(self, "완료", "추가할 shine 효과가 없습니다.")

        except Exception as e:
            error_msg = f"예상치 못한 오류: {e}"
            self.result_text.setText(error_msg)
            QMessageBox.critical(self, "오류", str(e))

        finally:
            self.generate_btn.setEnabled(True)
