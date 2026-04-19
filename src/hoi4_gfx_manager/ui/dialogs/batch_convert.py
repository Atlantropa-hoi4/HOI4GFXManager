"""GFX 일괄 변환 다이얼로그."""

import os
from pathlib import Path

from PyQt6.QtWidgets import (
    QApplication, QComboBox, QDialog, QFileDialog, QFormLayout, QGroupBox,
    QHBoxLayout, QLabel, QLineEdit, QListWidget, QMessageBox, QProgressBar,
    QPushButton, QSpinBox, QTextEdit, QVBoxLayout,
)

from ...services.image_conversion import ImageConverter


class BatchConvertDialog(QDialog):
    """이미지 파일을 다른 포맷으로 일괄 변환."""

    def __init__(self, parent=None, mod_folder_path=None):
        super().__init__(parent)
        self.setWindowTitle("GFX 일괄 변환 도구")
        self.setModal(True)
        self.resize(700, 500)
        self.mod_folder_path = mod_folder_path
        self.converter = ImageConverter()
        self.selected_files = []

        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout()
        self.setLayout(layout)

        desc_label = QLabel(
            "\n이미지 파일을 다른 포맷으로 일괄 변환합니다.\n"
            "DDS 변환 시 HOI4에 최적화된 포맷을 사용합니다.\n        "
        )
        desc_label.setWordWrap(True)
        layout.addWidget(desc_label)

        file_group = QGroupBox("변환할 파일 선택")
        file_layout = QVBoxLayout()
        file_group.setLayout(file_layout)

        file_btn_layout = QHBoxLayout()
        self.add_files_btn = QPushButton("파일 추가")
        self.add_files_btn.clicked.connect(self.add_files)
        self.add_folder_btn = QPushButton("폴더 추가")
        self.add_folder_btn.clicked.connect(self.add_folder)
        self.clear_btn = QPushButton("목록 지우기")
        self.clear_btn.clicked.connect(self.clear_files)

        file_btn_layout.addWidget(self.add_files_btn)
        file_btn_layout.addWidget(self.add_folder_btn)
        file_btn_layout.addWidget(self.clear_btn)
        file_btn_layout.addStretch()

        file_layout.addLayout(file_btn_layout)

        self.file_list = QListWidget()
        self.file_list.setMaximumHeight(150)
        file_layout.addWidget(self.file_list)

        layout.addWidget(file_group)

        settings_group = QGroupBox("변환 설정")
        settings_layout = QFormLayout()
        settings_group.setLayout(settings_layout)

        self.output_dir_edit = QLineEdit()
        output_btn = QPushButton("찾아보기")
        output_btn.clicked.connect(self.browse_output_dir)
        output_layout = QHBoxLayout()
        output_layout.addWidget(self.output_dir_edit)
        output_layout.addWidget(output_btn)
        settings_layout.addRow("출력 폴더:", output_layout)

        self.format_combo = QComboBox()
        self.format_combo.addItems(["PNG", "JPG", "DDS", "BMP"])
        self.format_combo.setCurrentText("DDS")
        self.format_combo.currentTextChanged.connect(self.on_format_changed)
        settings_layout.addRow("출력 포맷:", self.format_combo)

        self.dds_format_combo = QComboBox()
        for format_name in ImageConverter.DDS_FORMATS.keys():
            self.dds_format_combo.addItem(format_name)
        self.dds_format_combo.setCurrentText("B8G8R8A8 (Linear, A8R8G8B8)")
        settings_layout.addRow("DDS 포맷:", self.dds_format_combo)

        self.quality_spin = QSpinBox()
        self.quality_spin.setRange(1, 100)
        self.quality_spin.setValue(95)
        self.quality_spin.setSuffix("%")
        settings_layout.addRow("JPG 품질:", self.quality_spin)

        layout.addWidget(settings_group)

        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)

        self.result_text = QTextEdit()
        self.result_text.setMaximumHeight(100)
        self.result_text.setVisible(False)
        layout.addWidget(self.result_text)

        button_layout = QHBoxLayout()
        self.convert_btn = QPushButton("변환 시작")
        self.convert_btn.clicked.connect(self.start_conversion)
        close_btn = QPushButton("닫기")
        close_btn.clicked.connect(self.close)
        button_layout.addWidget(self.convert_btn)
        button_layout.addStretch()
        button_layout.addWidget(close_btn)
        layout.addLayout(button_layout)

        self.on_format_changed("DDS")

        if self.mod_folder_path:
            self.output_dir_edit.setText(os.path.join(self.mod_folder_path, "gfx", "interface"))

    def on_format_changed(self, format_name):
        self.dds_format_combo.setVisible(format_name == "DDS")
        self.quality_spin.setVisible(format_name == "JPG")

    def _default_path(self):
        return self.mod_folder_path or os.path.expanduser("~/Documents")

    def add_files(self):
        files, _ = QFileDialog.getOpenFileNames(
            self, "변환할 이미지 파일 선택", self._default_path(),
            "이미지 파일 (*.png *.jpg *.jpeg *.bmp *.tiff *.tga);;모든 파일 (*)",
        )
        for file in files:
            if file not in self.selected_files:
                self.selected_files.append(file)
                self.file_list.addItem(os.path.basename(file))

    def add_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "이미지 폴더 선택", self._default_path())
        if not folder:
            return
        extensions = [".png", ".jpg", ".jpeg", ".bmp", ".tiff", ".tga"]
        for ext in extensions:
            for file_path in Path(folder).rglob(f"*{ext}"):
                file_str = str(file_path)
                if file_str not in self.selected_files:
                    self.selected_files.append(file_str)
                    self.file_list.addItem(os.path.relpath(file_str, folder))

    def clear_files(self):
        self.selected_files.clear()
        self.file_list.clear()

    def browse_output_dir(self):
        folder = QFileDialog.getExistingDirectory(self, "출력 폴더 선택", self._default_path())
        if folder:
            self.output_dir_edit.setText(folder)

    def start_conversion(self):
        if not self.selected_files:
            QMessageBox.warning(self, "경고", "변환할 파일을 선택해주세요.")
            return

        output_dir = self.output_dir_edit.text().strip()
        if not output_dir:
            QMessageBox.warning(self, "경고", "출력 폴더를 선택해주세요.")
            return

        os.makedirs(output_dir, exist_ok=True)

        output_format = self.format_combo.currentText()
        dds_format = ImageConverter.DDS_FORMATS[self.dds_format_combo.currentText()]
        quality = self.quality_spin.value()

        self.progress_bar.setVisible(True)
        self.progress_bar.setMaximum(len(self.selected_files))
        self.progress_bar.setValue(0)
        self.result_text.setVisible(True)
        self.result_text.clear()
        self.convert_btn.setEnabled(False)

        results = self.converter.batch_convert(
            self.selected_files, output_dir, output_format, dds_format, quality
        )

        success_count = 0
        error_count = 0
        lines = ["=== 변환 결과 ===\n"]
        for i, result in enumerate(results):
            self.progress_bar.setValue(i + 1)
            QApplication.processEvents()
            in_name = os.path.basename(result["input"])
            if result["success"]:
                success_count += 1
                lines.append(f"✓ {in_name} → {os.path.basename(result['output'])}")
            else:
                error_count += 1
                lines.append(f"✗ {in_name}: {result['error']}")

        lines.append(f"\n성공: {success_count}개, 실패: {error_count}개")
        self.result_text.setText("\n".join(lines))

        self.convert_btn.setEnabled(True)

        if error_count == 0:
            QMessageBox.information(self, "완료", f"모든 파일이 성공적으로 변환되었습니다.\n변환된 파일: {success_count}개")
        else:
            QMessageBox.warning(self, "변환 완료", f"변환이 완료되었습니다.\n성공: {success_count}개, 실패: {error_count}개")
