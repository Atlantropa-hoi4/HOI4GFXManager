"""폴더 전체 이미지를 일괄 임포트하는 다이얼로그."""

import os
from pathlib import Path

from PyQt6.QtWidgets import (
    QCheckBox, QComboBox, QDialog, QDialogButtonBox, QFileDialog, QFormLayout,
    QGroupBox, QHBoxLayout, QLabel, QLineEdit, QPushButton, QRadioButton,
    QTextEdit, QVBoxLayout,
)


class BatchImportDialog(QDialog):
    """여러 이미지를 한 번에 GFX로 등록."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("일괄 임포트")
        self.setModal(True)
        self.resize(600, 400)

        layout = QVBoxLayout()
        self.setLayout(layout)

        folder_layout = QHBoxLayout()
        self.folder_edit = QLineEdit()
        self.folder_btn = QPushButton("폴더 선택...")
        self.folder_btn.clicked.connect(self.select_folder)
        folder_layout.addWidget(QLabel("소스 폴더:"))
        folder_layout.addWidget(self.folder_edit)
        folder_layout.addWidget(self.folder_btn)
        layout.addLayout(folder_layout)

        options_group = QGroupBox("옵션")
        options_layout = QFormLayout()
        options_group.setLayout(options_layout)

        self.prefix_edit = QLineEdit("GFX_")
        options_layout.addRow("GFX 이름 접두사:", self.prefix_edit)

        self.target_gfx_combo = QComboBox()
        options_layout.addRow("대상 GFX 파일:", self.target_gfx_combo)

        self.recursive_cb = QCheckBox()
        self.recursive_cb.setChecked(True)
        options_layout.addRow("하위 폴더 포함:", self.recursive_cb)

        layout.addWidget(options_group)

        path_group = QGroupBox("이미지 파일 저장 경로")
        path_layout = QVBoxLayout()
        path_group.setLayout(path_layout)

        save_option_layout = QHBoxLayout()
        self.copy_to_mod_rb = QRadioButton("모드 폴더로 복사")
        self.copy_to_mod_rb.setChecked(True)
        self.use_original_path_rb = QRadioButton("원본 경로 사용")
        save_option_layout.addWidget(self.copy_to_mod_rb)
        save_option_layout.addWidget(self.use_original_path_rb)
        path_layout.addLayout(save_option_layout)

        self.dest_folder_layout = QHBoxLayout()
        self.dest_folder_edit = QLineEdit("gfx/interface")
        self.dest_folder_btn = QPushButton("찾아보기...")
        self.dest_folder_btn.clicked.connect(self.select_dest_folder)
        self.dest_folder_layout.addWidget(QLabel("저장 폴더 (모드 폴더 기준):"))
        self.dest_folder_layout.addWidget(self.dest_folder_edit)
        self.dest_folder_layout.addWidget(self.dest_folder_btn)
        path_layout.addLayout(self.dest_folder_layout)

        self.copy_to_mod_rb.toggled.connect(self.on_save_option_changed)
        self.use_original_path_rb.toggled.connect(self.on_save_option_changed)

        layout.addWidget(path_group)

        self.preview_text = QTextEdit()
        self.preview_text.setReadOnly(True)
        layout.addWidget(QLabel("미리보기:"))
        layout.addWidget(self.preview_text)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self.folder_edit.textChanged.connect(self.update_preview)
        self.prefix_edit.textChanged.connect(self.update_preview)
        self.dest_folder_edit.textChanged.connect(self.update_preview)

    def _mod_folder(self):
        parent = self.parent()
        return getattr(parent, "mod_folder_path", None) if parent else None

    def select_folder(self):
        default_path = os.path.expanduser(r"~\Documents\Paradox Interactive\Hearts of Iron IV\mod")
        if not os.path.exists(default_path):
            default_path = os.path.expanduser("~/Documents")

        folder = QFileDialog.getExistingDirectory(self, "소스 폴더 선택", default_path)
        if folder:
            self.folder_edit.setText(folder)

    def select_dest_folder(self):
        mod_folder = self._mod_folder()
        default_path = mod_folder or os.path.expanduser("~/Documents")

        folder = QFileDialog.getExistingDirectory(self, "저장 폴더 선택", default_path)
        if not folder:
            return
        if mod_folder:
            try:
                relative_path = os.path.relpath(folder, mod_folder)
                if relative_path.startswith(".."):
                    self.dest_folder_edit.setText(folder)
                else:
                    self.dest_folder_edit.setText(relative_path)
                return
            except ValueError:
                pass
        self.dest_folder_edit.setText(folder)

    def on_save_option_changed(self):
        is_copy_mode = self.copy_to_mod_rb.isChecked()
        for i in range(self.dest_folder_layout.count()):
            widget = self.dest_folder_layout.itemAt(i).widget()
            if widget:
                widget.setEnabled(is_copy_mode)
        self.update_preview()

    def update_preview(self):
        folder = self.folder_edit.text()
        prefix = self.prefix_edit.text()

        if not folder or not os.path.exists(folder):
            self.preview_text.clear()
            return

        lines = ["생성될 GFX 항목들:\n"]

        image_extensions = [".dds", ".png", ".jpg", ".jpeg", ".bmp", ".tga"]
        image_files = []
        for ext in image_extensions:
            pattern = f"**/*{ext}" if self.recursive_cb.isChecked() else f"*{ext}"
            image_files.extend(list(Path(folder).glob(pattern)))

        for image_file in image_files[:20]:
            relative_path = image_file.relative_to(folder)
            gfx_name = f"{prefix}{relative_path.stem}"
            if self.copy_to_mod_rb.isChecked():
                dest_path = os.path.join(self.dest_folder_edit.text(), image_file.name).replace("\\", "/")
                lines.append(f"- {gfx_name} → {dest_path}")
            else:
                lines.append(f"- {gfx_name} → {relative_path}")

        if len(image_files) > 20:
            lines.append(f"\n... 및 {len(image_files) - 20}개 더")

        self.preview_text.setText("\n".join(lines))

    def get_data(self):
        return {
            "folder": self.folder_edit.text(),
            "prefix": self.prefix_edit.text(),
            "target_gfx_file": self.target_gfx_combo.currentText(),
            "recursive": self.recursive_cb.isChecked(),
            "copy_to_mod": self.copy_to_mod_rb.isChecked(),
            "dest_folder": self.dest_folder_edit.text(),
        }
