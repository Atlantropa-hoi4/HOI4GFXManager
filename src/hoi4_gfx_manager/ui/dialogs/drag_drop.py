"""드래그 앤 드롭으로 추가할 GFX 설정 다이얼로그."""

import os
from pathlib import Path

from PIL import Image
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import (
    QComboBox, QDialog, QDialogButtonBox, QFileDialog, QFormLayout,
    QHBoxLayout, QLabel, QLineEdit, QPushButton,
)


class DragDropDialog(QDialog):
    """드롭된 이미지로 새 GFX를 추가할 때 이름/경로/대상 파일을 확정."""

    _HOI4_MOD_DEFAULT = r"~\Documents\Paradox Interactive\Hearts of Iron IV\mod"

    def __init__(self, parent=None, image_file_path=""):
        super().__init__(parent)
        self.setWindowTitle("새 GFX 추가")
        self.setModal(True)
        self.resize(500, 400)
        self.image_file_path = image_file_path

        layout = QFormLayout()
        self.setLayout(layout)

        self.source_label = QLabel(f"원본 파일: {os.path.basename(image_file_path)}")
        layout.addRow(self.source_label)

        filename = Path(image_file_path).stem
        self.name_edit = QLineEdit(f"GFX_{filename}")
        layout.addRow("GFX 이름:", self.name_edit)

        target_layout = QHBoxLayout()
        self.target_edit = QLineEdit("gfx/interface/")
        self.target_browse_btn = QPushButton("찾기...")
        self.target_browse_btn.clicked.connect(self.browse_target_folder)
        target_layout.addWidget(self.target_edit)
        target_layout.addWidget(self.target_browse_btn)
        layout.addRow("저장할 폴더:", target_layout)

        self.gfx_file_combo = QComboBox()
        layout.addRow("저장할 GFX 파일:", self.gfx_file_combo)

        self.preview_label = QLabel()
        self.preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview_label.setMaximumHeight(150)
        self.preview_label.setStyleSheet("border: 1px solid gray;")
        layout.addRow("미리보기:", self.preview_label)
        self.load_preview()

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)

    def _mod_folder(self):
        parent = self.parent()
        return getattr(parent, "mod_folder_path", None) if parent else None

    def browse_target_folder(self):
        mod_folder = self._mod_folder()
        default_path = mod_folder or os.path.expanduser(self._HOI4_MOD_DEFAULT)
        if not os.path.exists(default_path):
            default_path = os.path.expanduser("~/Documents")

        folder = QFileDialog.getExistingDirectory(self, "저장할 폴더 선택", default_path)
        if not folder:
            return
        if mod_folder:
            try:
                rel_path = os.path.relpath(folder, mod_folder)
                self.target_edit.setText(rel_path.replace(os.sep, "/") + "/")
                return
            except ValueError:
                pass
        self.target_edit.setText(folder.replace(os.sep, "/") + "/")

    def load_preview(self):
        try:
            with Image.open(self.image_file_path) as img:
                if img.mode != "RGB":
                    img = img.convert("RGB")
                temp_path = "temp_dragdrop_preview.png"
                img.save(temp_path, "PNG")
                pixmap = QPixmap(temp_path)
                scaled_pixmap = pixmap.scaled(
                    120, 120,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
                self.preview_label.setPixmap(scaled_pixmap)
                if os.path.exists(temp_path):
                    os.remove(temp_path)
        except Exception as e:
            self.preview_label.setText(f"미리보기 로드 실패: {e}")

    def get_data(self):
        return {
            "name": self.name_edit.text().strip(),
            "target_folder": self.target_edit.text().strip(),
            "gfx_file": self.gfx_file_combo.currentText(),
            "source_file": self.image_file_path,
        }
