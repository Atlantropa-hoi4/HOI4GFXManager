"""GFX 편집/생성 다이얼로그."""

from PyQt6.QtWidgets import (
    QComboBox, QDialog, QDialogButtonBox, QFileDialog, QFormLayout,
    QHBoxLayout, QLineEdit, QPushButton,
)


class GFXEditDialog(QDialog):
    """spriteType의 name/texturefile/대상 .gfx 파일을 입력한다."""

    def __init__(self, parent=None, gfx_name="", texture_path="", is_edit=False):
        super().__init__(parent)
        self.setWindowTitle("GFX 편집" if is_edit else "새 GFX 추가")
        self.setModal(True)
        self.resize(500, 300)

        layout = QFormLayout()
        self.setLayout(layout)

        self.name_edit = QLineEdit(gfx_name)
        layout.addRow("GFX 이름:", self.name_edit)

        texture_layout = QHBoxLayout()
        self.texture_edit = QLineEdit(texture_path)
        self.browse_btn = QPushButton("찾기...")
        self.browse_btn.clicked.connect(self.browse_texture)
        texture_layout.addWidget(self.texture_edit)
        texture_layout.addWidget(self.browse_btn)
        layout.addRow("텍스처 파일:", texture_layout)

        self.gfx_file_combo = QComboBox()
        layout.addRow("저장할 GFX 파일:", self.gfx_file_combo)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)

    def browse_texture(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "텍스처 파일 선택", "",
            "이미지 파일 (*.dds *.png *.jpg *.jpeg *.bmp *.tga);;DDS 파일 (*.dds);;PNG 파일 (*.png);;모든 파일 (*)",
        )
        if file_path:
            self.texture_edit.setText(file_path)

    def get_data(self):
        return {
            "name": self.name_edit.text().strip(),
            "texture_path": self.texture_edit.text().strip(),
            "gfx_file": self.gfx_file_combo.currentText(),
        }
