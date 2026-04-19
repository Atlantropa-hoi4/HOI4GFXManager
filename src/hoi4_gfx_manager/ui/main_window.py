"""메인 애플리케이션 윈도우 (GFXManager).

UI 조립과 서비스 호출을 담당하며, 비즈니스 로직은 services/ 모듈에 있다.
"""

import json
import os
import shutil
import subprocess
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

from PIL import Image
from PyQt6.QtCore import Qt, QSettings, QTimer
from PyQt6.QtGui import QAction, QColor, QDragEnterEvent, QDropEvent, QPixmap
from PyQt6.QtWidgets import (
    QApplication, QCheckBox, QDialog, QFileDialog, QGroupBox, QHBoxLayout,
    QLabel, QLineEdit, QMainWindow, QMenu, QMessageBox, QProgressBar,
    QPushButton, QSplitter, QStatusBar, QTabWidget, QTextEdit, QToolBar,
    QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget, QInputDialog,
)

from ..services.analysis import AnalysisWorker
from ..services.gfx_repository import (
    remove_gfx_from_file, save_gfx_to_file, scan_mod_folder,
    update_gfx_texture_path,
)
from .dialogs import (
    BatchConvertDialog, BatchImportDialog, DragDropDialog, FocusShineDialog,
    GFXEditDialog, ProjectManagerDialog,
)
from .theme import DARK_STYLESHEET, IMAGE_EXTENSIONS, IMAGE_PLACEHOLDER_STYLE
from .tree_widget import GFXTreeWidget

_HOI4_MOD_DEFAULT = r"~\Documents\Paradox Interactive\Hearts of Iron IV\mod"
_FILE_EXTENSIONS = ("*.txt", "*.gui", "*.mod", "*.pdx", "*.interface",
                    "*.gfx", "*.lua", "*.yml", "*.yaml")


class GFXManager(QMainWindow):
    """HOI4 GFX 통합 관리 메인 윈도우."""

    def __init__(self):
        super().__init__()
        self.mod_folder_path = None
        self.gfx_data = {}
        self.orphaned_gfx = set()
        self.missing_definitions = set()
        self.duplicate_definitions = {}
        self.used_gfx = set()
        self.usage_locations = {}
        self.analysis_worker = None

        self.settings = QSettings("HOI4GFXManager", "Settings")
        self.projects = self._load_projects()
        self.dark_mode = self.settings.value("dark_mode", False, type=bool)

        self.setAcceptDrops(True)

        self._init_ui()
        self._apply_theme()

        self.status_timer = QTimer()
        self.status_timer.timeout.connect(self._update_status)
        self.status_timer.start(1000)

    # ----- UI 조립 -----

    def _init_ui(self):
        self.setWindowTitle("HOI4 GFX 통합 관리 도구")
        self.setGeometry(100, 100, 1400, 900)

        self._create_menus()
        self._create_toolbar()

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout()
        central_widget.setLayout(main_layout)

        control_panel = QHBoxLayout()
        main_layout.addLayout(control_panel)

        self.search_field = QLineEdit()
        self.search_field.setPlaceholderText("GFX 이름 검색...")
        self.search_field.setMaximumWidth(300)
        self.search_field.textChanged.connect(self._filter_gfx_list)
        control_panel.addWidget(self.search_field)
        control_panel.addStretch()

        tab_widget = QTabWidget()
        main_layout.addWidget(tab_widget)

        main_tab = QWidget()
        tab_widget.addTab(main_tab, "GFX 목록")
        self._setup_main_tab(main_tab)

        analysis_tab = QWidget()
        tab_widget.addTab(analysis_tab, "분석 결과")
        self._setup_analysis_tab(analysis_tab)

        project_tab = QWidget()
        tab_widget.addTab(project_tab, "프로젝트")
        self._setup_project_tab(project_tab)

        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        main_layout.addWidget(self.progress_bar)

        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("준비")

    def _create_menus(self):
        menubar = self.menuBar()

        file_menu = menubar.addMenu("파일")
        open_action = QAction("모드 폴더 열기", self)
        open_action.triggered.connect(self.open_mod_folder)
        file_menu.addAction(open_action)
        file_menu.addSeparator()
        export_action = QAction("분석 결과 내보내기", self)
        export_action.triggered.connect(self.export_analysis)
        file_menu.addAction(export_action)

        edit_menu = menubar.addMenu("편집")
        add_gfx_action = QAction("새 GFX 추가", self)
        add_gfx_action.triggered.connect(self.add_gfx)
        edit_menu.addAction(add_gfx_action)
        batch_import_action = QAction("일괄 임포트", self)
        batch_import_action.triggered.connect(self.batch_import)
        edit_menu.addAction(batch_import_action)

        tools_menu = menubar.addMenu("도구")
        analyze_action = QAction("전체 분석 실행", self)
        analyze_action.triggered.connect(self.run_full_analysis)
        tools_menu.addAction(analyze_action)
        tools_menu.addSeparator()
        focus_shine_action = QAction("Focus GFX Shine 생성", self)
        focus_shine_action.triggered.connect(self.open_focus_shine_generator)
        tools_menu.addAction(focus_shine_action)
        batch_convert_action = QAction("GFX 일괄 변환", self)
        batch_convert_action.triggered.connect(self.open_batch_converter)
        tools_menu.addAction(batch_convert_action)

        view_menu = menubar.addMenu("보기")
        theme_action = QAction("다크 모드 전환", self)
        theme_action.triggered.connect(self._toggle_theme)
        view_menu.addAction(theme_action)

    def _create_toolbar(self):
        toolbar = QToolBar()
        self.addToolBar(toolbar)
        toolbar.addAction("폴더 열기", self.open_mod_folder)
        toolbar.addAction("분석 실행", self.run_full_analysis)
        toolbar.addSeparator()
        toolbar.addAction("GFX 추가", self.add_gfx)
        toolbar.addAction("일괄 임포트", self.batch_import)
        toolbar.addSeparator()
        toolbar.addAction("프로젝트 관리", self.manage_projects)

    def _setup_main_tab(self, tab):
        layout = QVBoxLayout()
        tab.setLayout(layout)

        filter_group = QGroupBox("필터 옵션")
        filter_group.setMaximumHeight(60)
        filter_layout = QHBoxLayout()
        filter_layout.setContentsMargins(5, 5, 5, 5)
        filter_group.setLayout(filter_layout)

        self.show_valid_cb = QCheckBox("정상")
        self.show_valid_cb.setChecked(True)
        self.show_valid_cb.toggled.connect(self._filter_gfx_list)
        filter_layout.addWidget(self.show_valid_cb)

        self.show_missing_cb = QCheckBox("파일 없음")
        self.show_missing_cb.setChecked(True)
        self.show_missing_cb.toggled.connect(self._filter_gfx_list)
        filter_layout.addWidget(self.show_missing_cb)

        self.show_orphaned_cb = QCheckBox("미사용")
        self.show_orphaned_cb.setChecked(True)
        self.show_orphaned_cb.toggled.connect(self._filter_gfx_list)
        filter_layout.addWidget(self.show_orphaned_cb)

        self.show_duplicate_cb = QCheckBox("중복")
        self.show_duplicate_cb.setChecked(True)
        self.show_duplicate_cb.toggled.connect(self._filter_gfx_list)
        filter_layout.addWidget(self.show_duplicate_cb)

        filter_layout.addStretch()
        layout.addWidget(filter_group)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        layout.addWidget(splitter)

        left_widget = QWidget()
        left_layout = QVBoxLayout()
        left_widget.setLayout(left_layout)

        self.gfx_tree = GFXTreeWidget()
        self.gfx_tree.setHeaderLabels(["Name", "Status", "File", "Type"])
        self.gfx_tree.itemClicked.connect(self._on_gfx_selected)
        self.gfx_tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.gfx_tree.customContextMenuRequested.connect(self._show_context_menu)
        self.gfx_tree.file_dropped.connect(self._handle_tree_drop)
        self.gfx_tree.setToolTip(
            "이미지 파일을 드래그하여 GFX를 관리하세요:\n"
            "• 파일 노드에 드롭: 자동으로 새 GFX 추가\n"
            "• GFX 노드에 드롭: 기존 GFX 텍스처 교체\n"
            "• Ctrl+드롭: 수동으로 설정하여 추가"
        )
        left_layout.addWidget(self.gfx_tree)

        btn_layout = QHBoxLayout()
        self.edit_gfx_btn = QPushButton("편집")
        self.edit_gfx_btn.clicked.connect(self.edit_selected_gfx)
        self.edit_gfx_btn.setEnabled(False)
        self.delete_gfx_btn = QPushButton("삭제")
        self.delete_gfx_btn.clicked.connect(self.delete_selected_gfx)
        self.delete_gfx_btn.setEnabled(False)
        btn_layout.addWidget(self.edit_gfx_btn)
        btn_layout.addWidget(self.delete_gfx_btn)
        left_layout.addLayout(btn_layout)

        splitter.addWidget(left_widget)

        right_widget = QWidget()
        right_layout = QVBoxLayout()
        right_widget.setLayout(right_layout)

        self.image_label = QLabel("GFX를 선택하면 이미지가 표시됩니다")
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_label.setStyleSheet(IMAGE_PLACEHOLDER_STYLE)
        self.image_label.setMinimumSize(400, 300)
        right_layout.addWidget(self.image_label)

        self.info_text = QTextEdit()
        self.info_text.setReadOnly(True)
        self.info_text.setMaximumHeight(150)
        right_layout.addWidget(self.info_text)

        splitter.addWidget(right_widget)
        splitter.setSizes([400, 800])

    def _setup_analysis_tab(self, tab):
        layout = QVBoxLayout()
        tab.setLayout(layout)

        stats_group = QGroupBox("분석 통계")
        stats_layout = QHBoxLayout()
        stats_group.setLayout(stats_layout)

        self.total_gfx_label = QLabel("총 GFX: 0개")
        self.valid_gfx_label = QLabel("정상: 0개")
        self.error_gfx_label = QLabel("오류: 0개")
        self.orphaned_gfx_label = QLabel("미사용: 0개")

        stats_layout.addWidget(self.total_gfx_label)
        stats_layout.addWidget(QLabel("|"))
        stats_layout.addWidget(self.valid_gfx_label)
        stats_layout.addWidget(QLabel("|"))
        stats_layout.addWidget(self.error_gfx_label)
        stats_layout.addWidget(QLabel("|"))
        stats_layout.addWidget(self.orphaned_gfx_label)
        stats_layout.addStretch()

        layout.addWidget(stats_group)

        self.analysis_text = QTextEdit()
        self.analysis_text.setReadOnly(True)
        layout.addWidget(self.analysis_text)

    def _setup_project_tab(self, tab):
        layout = QVBoxLayout()
        tab.setLayout(layout)

        self.project_tree = QTreeWidget()
        self.project_tree.setHeaderLabels(["프로젝트", "경로", "저장 시간"])
        layout.addWidget(self.project_tree)

        btn_layout = QHBoxLayout()
        save_project_btn = QPushButton("현재 프로젝트 저장")
        save_project_btn.clicked.connect(self.save_current_project)
        btn_layout.addWidget(save_project_btn)
        layout.addLayout(btn_layout)

        self._update_project_tree()

    # ----- 테마 -----

    def _apply_theme(self):
        self.setStyleSheet(DARK_STYLESHEET if self.dark_mode else "")

    def _toggle_theme(self):
        self.dark_mode = not self.dark_mode
        self.settings.setValue("dark_mode", self.dark_mode)
        self._apply_theme()

    # ----- 모드 폴더 / 스캔 -----

    def open_mod_folder(self):
        default_path = os.path.expanduser(_HOI4_MOD_DEFAULT)
        if not os.path.exists(default_path):
            default_path = os.path.expanduser("~/Documents")

        folder_path = QFileDialog.getExistingDirectory(self, "HOI4 모드 폴더 선택", default_path)
        if folder_path:
            self.mod_folder_path = folder_path
            self.scan_gfx_files()

    def scan_gfx_files(self):
        if not self.mod_folder_path:
            return

        self.gfx_tree.clear()

        try:
            gfx_data, duplicates, gfx_files = scan_mod_folder(self.mod_folder_path)
        except Exception as e:
            QMessageBox.critical(self, "오류", f"GFX 파일 스캔 중 오류: {e}")
            return

        if not gfx_files:
            QMessageBox.information(self, "알림", "선택한 폴더에서 .gfx 파일을 찾을 수 없습니다.")
            self.gfx_data = {}
            return

        self.gfx_data = gfx_data
        self.duplicate_definitions = duplicates

        self._update_gfx_list()
        self._update_statistics_cards()
        self.status_bar.showMessage(
            f"{len(gfx_files)}개의 .gfx 파일에서 {len(self.gfx_data)}개의 GFX를 찾았습니다."
        )

    # ----- 트리 렌더링 -----

    def _update_gfx_list(self):
        self.gfx_tree.clear()
        search_text = self.search_field.text().lower()

        file_groups = {}
        for name, info in self.gfx_data.items():
            if search_text and search_text not in name.lower():
                continue

            status = info["status"]
            if status == "valid" and not self.show_valid_cb.isChecked():
                continue
            if status == "missing_file" and not self.show_missing_cb.isChecked():
                continue
            if status == "duplicate" and not self.show_duplicate_cb.isChecked():
                continue
            if name in self.orphaned_gfx and not self.show_orphaned_cb.isChecked():
                continue

            file_source = os.path.basename(info["file_source"])
            file_groups.setdefault(file_source, []).append((name, info))

        for file_source in sorted(file_groups):
            file_type = self._infer_file_type(file_source)
            file_item = QTreeWidgetItem([file_source, "", "", file_type])
            file_item.setExpanded(True)

            for name, info in sorted(file_groups[file_source]):
                status = info["status"]
                if status == "missing_file":
                    status_text = "ERROR"
                elif status == "duplicate":
                    status_text = "DUPLICATE"
                elif name in self.orphaned_gfx:
                    status_text = "UNUSED"
                else:
                    status_text = "OK"

                gfx_item = QTreeWidgetItem([name, status_text, info["relative_path"], "GFX"])

                if status == "missing_file":
                    color = QColor(255, 200, 200)
                elif status == "duplicate":
                    color = QColor(255, 255, 200)
                elif name in self.orphaned_gfx:
                    color = QColor(200, 200, 255)
                else:
                    color = None

                if color is not None:
                    gfx_item.setBackground(0, color)
                    gfx_item.setBackground(1, color)

                file_item.addChild(gfx_item)

            self.gfx_tree.addTopLevelItem(file_item)

        self.gfx_tree.expandAll()
        for col in range(4):
            self.gfx_tree.resizeColumnToContents(col)

    @staticmethod
    def _infer_file_type(file_source):
        lower = file_source.lower()
        if "interface" in lower:
            return "INTERFACE"
        if "common" in lower:
            return "COMMON"
        if "events" in lower:
            return "EVENTS"
        if "decisions" in lower:
            return "DECISIONS"
        return "FILE"

    def _filter_gfx_list(self):
        self._update_gfx_list()

    def _on_gfx_selected(self, item, column=0):
        if not item.parent():
            self.edit_gfx_btn.setEnabled(False)
            self.delete_gfx_btn.setEnabled(False)
            self.image_label.setText("GFX 항목을 선택해주세요")
            self.info_text.clear()
            return

        gfx_name = item.text(0)
        gfx_info = self.gfx_data.get(gfx_name)

        self.edit_gfx_btn.setEnabled(True)
        self.delete_gfx_btn.setEnabled(True)

        if not gfx_info:
            self.image_label.setText("이미지 경로를 찾을 수 없습니다")
            self.info_text.clear()
            return

        info_lines = [
            f"GFX 이름: {gfx_name}",
            f"파일 소스: {gfx_info['file_source']}",
            f"텍스처 경로: {gfx_info['relative_path']}",
            f"상태: {gfx_info['status']}",
        ]
        if gfx_name in self.usage_locations:
            info_lines.append(f"사용처: {len(self.usage_locations[gfx_name])}개 파일")
            for location in self.usage_locations[gfx_name][:5]:
                info_lines.append(f"  - {location}")
            if len(self.usage_locations[gfx_name]) > 5:
                info_lines.append(f"  ... 및 {len(self.usage_locations[gfx_name]) - 5}개 더")
        else:
            info_lines.append("사용처: 없음 (미사용 GFX)")

        self.info_text.setText("\n".join(info_lines))

        texture_path = gfx_info["texturefile"]
        if not os.path.exists(texture_path):
            self.image_label.setText(f"이미지 파일이 존재하지 않습니다:\n{texture_path}")
            return

        try:
            with Image.open(texture_path) as img:
                if img.mode != "RGB":
                    img = img.convert("RGB")
                temp_path = "temp_preview.png"
                img.save(temp_path, "PNG")
                pixmap = QPixmap(temp_path)
                label_size = self.image_label.size()
                scaled_pixmap = pixmap.scaled(
                    label_size.width() - 10,
                    label_size.height() - 10,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
                self.image_label.setPixmap(scaled_pixmap)
                if os.path.exists(temp_path):
                    os.remove(temp_path)
        except Exception as e:
            self.image_label.setText(f"이미지를 불러올 수 없습니다:\n{e}")

    # ----- 분석 -----

    def run_full_analysis(self):
        if not self.mod_folder_path or not self.gfx_data:
            QMessageBox.warning(self, "경고", "먼저 모드 폴더를 선택하고 GFX 파일을 스캔해주세요.")
            return

        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)

        self.analysis_worker = AnalysisWorker(self.mod_folder_path, self.gfx_data)
        self.analysis_worker.progress_updated.connect(self.progress_bar.setValue)
        self.analysis_worker.analysis_complete.connect(self._on_analysis_complete)
        self.analysis_worker.start()

    def _on_analysis_complete(self, results):
        self.orphaned_gfx = results["orphaned_gfx"]
        self.missing_definitions = results["missing_definitions"]
        self.duplicate_definitions = results["duplicate_definitions"]
        self.used_gfx = results["used_gfx"]
        self.usage_locations = results["usage_locations"]

        self._update_statistics_cards()
        self.analysis_text.setText(self._generate_analysis_report(results))
        self._update_gfx_list()
        self.progress_bar.setVisible(False)

        QMessageBox.information(self, "분석 완료", "전체 분석이 완료되었습니다.")

    def _update_statistics_cards(self):
        total = len(self.gfx_data)
        valid = sum(1 for info in self.gfx_data.values() if info["status"] == "valid")
        error = sum(1 for info in self.gfx_data.values() if info["status"] in ("missing_file", "duplicate"))
        orphaned = len(self.orphaned_gfx)

        self.total_gfx_label.setText(f"총 GFX: {total}개")
        self.valid_gfx_label.setText(f"정상: {valid}개")
        self.error_gfx_label.setText(f"오류: {error}개")
        self.orphaned_gfx_label.setText(f"미사용: {orphaned}개")

    def _count_code_files(self):
        total = 0
        for ext in _FILE_EXTENSIONS:
            total += sum(1 for _ in Path(self.mod_folder_path).rglob(ext))
        return total

    def _generate_analysis_report(self, results):
        parts = []
        parts.append("=== HOI4 GFX 사용처 분석 리포트 ===\n")
        parts.append(f"분석 일시: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        parts.append(f"모드 경로: {self.mod_folder_path}")

        code_files_count = results.get("code_files_count", self._count_code_files())
        parts.append(f"검사된 파일: {code_files_count}개")
        parts.append(
            "검사 파일 형식: "
            + ", ".join(ext.replace("*", "") for ext in _FILE_EXTENSIONS)
            + "\n"
        )

        file_stats = {}
        for info in self.gfx_data.values():
            key = os.path.basename(info["file_source"])
            stats = file_stats.setdefault(key, {"total": 0, "valid": 0, "error": 0})
            stats["total"] += 1
            if info["status"] == "valid":
                stats["valid"] += 1
            else:
                stats["error"] += 1

        valid_gfx = sum(1 for info in self.gfx_data.values() if info["status"] == "valid")
        invalid_gfx = sum(1 for info in self.gfx_data.values() if info["status"] != "valid")
        usage_rate = (len(self.used_gfx) / len(self.gfx_data) * 100) if self.gfx_data else 0

        parts.append("=== 전체 통계 ===")
        parts.append("┌────────────────────────────────────────┐")
        parts.append(f"│ 전체 GFX 정의: {len(self.gfx_data):>15}개 │")
        parts.append(f"│  ├─ 정상 GFX: {valid_gfx:>17}개 │")
        parts.append(f"│  └─ 오류 GFX: {invalid_gfx:>17}개 │")
        parts.append(f"│ 사용 중인 GFX: {len(self.used_gfx):>15}개 │")
        parts.append("│  (자기 파일 참조 제외)          │")
        parts.append(f"│ 미사용 GFX: {len(self.orphaned_gfx):>18}개 │")
        parts.append(f"│ 사용률: {usage_rate:>23.1f}% │")
        parts.append("│                                      │")
        parts.append(f"│ 누락된 정의: {len(self.missing_definitions):>17}개 │")
        parts.append(f"│ 중복 정의: {len(self.duplicate_definitions):>20}개 │")
        parts.append("└────────────────────────────────────────┘\n")

        if file_stats:
            parts.append("=== 파일별 통계 ===")
            for file_name, stats in sorted(file_stats.items()):
                lower = file_name.lower()
                tag = "INTERFACE" if "interface" in lower else "COMMON" if "common" in lower else "FILE"
                parts.append(f"[{tag}] {file_name}:")
                parts.append(f"   ├─ 총 개수: {stats['total']}개")
                parts.append(f"   ├─ 정상: {stats['valid']}개")
                parts.append(f"   └─ 오류: {stats['error']}개\n")

        if self.orphaned_gfx:
            parts.append(f"=== 미사용 GFX 분석 ({len(self.orphaned_gfx)}개) ===")
            parts.append("삭제를 고려할 수 있는 미사용 GFX 목록:\n")
            orphaned_by_file = {}
            for gfx in self.orphaned_gfx:
                if gfx in self.gfx_data:
                    key = os.path.basename(self.gfx_data[gfx]["file_source"])
                    orphaned_by_file.setdefault(key, []).append(gfx)
            for file_name, gfx_list in sorted(orphaned_by_file.items()):
                parts.append(f"[{file_name}] ({len(gfx_list)}개):")
                for gfx in sorted(gfx_list):
                    parts.append(f"  • {gfx}")
                parts.append("")

        if self.missing_definitions:
            parts.append("누락된 GFX 정의 (추가 필요):")
            for gfx in sorted(self.missing_definitions):
                parts.append(f"  - {gfx}")
            parts.append("")

        if self.duplicate_definitions:
            parts.append("중복 정의된 GFX:")
            for gfx, files in self.duplicate_definitions.items():
                parts.append(f"  - {gfx}:")
                for file in files:
                    parts.append(f"    * {file}")
            parts.append("")

        if self.usage_locations:
            usage_counts = sorted(
                ((gfx, len(locations)) for gfx, locations in self.usage_locations.items()),
                key=lambda x: x[1], reverse=True,
            )
            parts.append("=== 많이 사용되는 GFX TOP 20 ===")
            for i, (gfx, count) in enumerate(usage_counts[:20], 1):
                parts.append(f"{i:2d}. {gfx} - {count}개 파일에서 사용")
            parts.append("")

        missing_files = [name for name, info in self.gfx_data.items() if info["status"] == "missing_file"]
        if missing_files:
            parts.append(f"=== 텍스처 파일 누락 ({len(missing_files)}개) ===")
            parts.append("수정이 필요한 GFX 목록:\n")
            for gfx in sorted(missing_files):
                parts.append(f"  ✗ {gfx}")
                parts.append(f"    경로: {self.gfx_data[gfx]['relative_path']}")
                if gfx in self.usage_locations:
                    parts.append(f"    사용처: {len(self.usage_locations[gfx])}개 파일")
                parts.append("")

        parts.append("=== 추천 사항 ===")
        if self.orphaned_gfx:
            parts.append(f"• {len(self.orphaned_gfx)}개의 미사용 GFX 삭제 검토")
        if missing_files:
            parts.append(f"• {len(missing_files)}개의 누락된 텍스처 파일 복구")
        if self.duplicate_definitions:
            parts.append(f"• {len(self.duplicate_definitions)}개의 중복 정의 정리")
        if not (self.orphaned_gfx or missing_files or self.duplicate_definitions):
            parts.append("✓ 모든 GFX가 올바르게 설정되어 있습니다!")

        parts.append("\n=== 보고서 끝 ===")
        return "\n".join(parts)

    # ----- 컨텍스트 메뉴 & GFX 편집 -----

    def _show_context_menu(self, position):
        item = self.gfx_tree.itemAt(position)
        if not (item and item.parent()):
            return
        menu = QMenu()
        edit_action = menu.addAction("편집")
        edit_action.triggered.connect(self.edit_selected_gfx)
        delete_action = menu.addAction("삭제")
        delete_action.triggered.connect(self.delete_selected_gfx)
        menu.addSeparator()
        open_file_action = menu.addAction("GFX 파일 열기")
        open_file_action.triggered.connect(self._open_gfx_file)
        open_texture_action = menu.addAction("텍스처 폴더 열기")
        open_texture_action.triggered.connect(self._open_texture_folder)
        menu.exec(self.gfx_tree.mapToGlobal(position))

    def _populate_gfx_file_combo(self, combo):
        gfx_files = list(Path(self.mod_folder_path).rglob("*.gfx"))
        relative_paths = [os.path.relpath(str(f), self.mod_folder_path) for f in gfx_files]
        combo.addItems(relative_paths)
        return gfx_files

    def add_gfx(self):
        if not self.mod_folder_path:
            QMessageBox.warning(self, "경고", "먼저 모드 폴더를 선택해주세요.")
            return

        dialog = GFXEditDialog(self)
        self._populate_gfx_file_combo(dialog.gfx_file_combo)

        if dialog.exec() == QDialog.DialogCode.Accepted:
            data = dialog.get_data()
            if data["name"] and data["texture_path"] and data["gfx_file"]:
                self._save_gfx(data["name"], data["texture_path"], data["gfx_file"])
                self.scan_gfx_files()

    def edit_selected_gfx(self):
        current_item = self.gfx_tree.currentItem()
        if not (current_item and current_item.parent()):
            return

        gfx_name = current_item.text(0)
        gfx_info = self.gfx_data.get(gfx_name)
        if not gfx_info:
            return

        dialog = GFXEditDialog(self, gfx_name, gfx_info["relative_path"], True)
        self._populate_gfx_file_combo(dialog.gfx_file_combo)

        if dialog.exec() == QDialog.DialogCode.Accepted:
            data = dialog.get_data()
            if data["name"] and data["texture_path"] and data["gfx_file"]:
                self._remove_gfx(gfx_name, gfx_info["file_source"])
                self._save_gfx(data["name"], data["texture_path"], data["gfx_file"])
                self.scan_gfx_files()

    def delete_selected_gfx(self):
        current_item = self.gfx_tree.currentItem()
        if not (current_item and current_item.parent()):
            return

        gfx_name = current_item.text(0)
        gfx_info = self.gfx_data.get(gfx_name)
        if not gfx_info:
            return

        if gfx_name in self.usage_locations and self.usage_locations[gfx_name]:
            usage_count = len(self.usage_locations[gfx_name])
            reply = QMessageBox.question(
                self, "삭제 확인",
                f"'{gfx_name}'은(는) {usage_count}개의 파일에서 사용 중입니다.\n정말 삭제하시겠습니까?",
            )
        else:
            reply = QMessageBox.question(self, "삭제 확인", f"'{gfx_name}'을(를) 삭제하시겠습니까?")

        if reply == QMessageBox.StandardButton.Yes:
            self._remove_gfx(gfx_name, gfx_info["file_source"])
            self.scan_gfx_files()

    def _save_gfx(self, name, texture_path, gfx_file):
        try:
            if not os.path.isabs(gfx_file):
                gfx_file = os.path.join(self.mod_folder_path, gfx_file)

            if os.path.isabs(texture_path):
                rel_path = os.path.relpath(texture_path, self.mod_folder_path).replace("\\", "/")
            else:
                rel_path = texture_path.replace("\\", "/")

            save_gfx_to_file(gfx_file, name, rel_path)
        except Exception as e:
            QMessageBox.critical(self, "오류", f"GFX 저장 중 오류: {e}")

    def _remove_gfx(self, name, gfx_file):
        try:
            remove_gfx_from_file(gfx_file, name)
        except Exception as e:
            QMessageBox.critical(self, "오류", f"GFX 삭제 중 오류: {e}")

    # ----- 일괄 임포트 -----

    def batch_import(self):
        if not self.mod_folder_path:
            QMessageBox.warning(self, "경고", "먼저 모드 폴더를 선택해주세요.")
            return

        dialog = BatchImportDialog(self)
        self._populate_gfx_file_combo(dialog.target_gfx_combo)

        if dialog.exec() == QDialog.DialogCode.Accepted:
            self._perform_batch_import(dialog.get_data())

    def _perform_batch_import(self, data):
        try:
            folder = Path(data["folder"])
            prefix = data["prefix"]
            target_file = data["target_gfx_file"]
            recursive = data["recursive"]
            copy_to_mod = data.get("copy_to_mod", False)
            dest_folder = data.get("dest_folder", "")

            image_extensions = [".dds", ".png", ".jpg", ".jpeg", ".bmp", ".tga"]
            image_files = []
            for ext in image_extensions:
                pattern = f"**/*{ext}" if recursive else f"*{ext}"
                image_files.extend(list(folder.glob(pattern)))

            if not image_files:
                QMessageBox.information(self, "알림", "선택한 폴더에서 지원되는 이미지 파일을 찾을 수 없습니다.")
                return

            copied_files = 0
            failed_copies = []

            for image_file in image_files:
                relative_path = image_file.relative_to(folder)
                gfx_name = f"{prefix}{relative_path.stem}"

                if copy_to_mod and self.mod_folder_path:
                    try:
                        dest_path = Path(self.mod_folder_path) / dest_folder / image_file.name
                        dest_path.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(image_file, dest_path)
                        mod_relative = os.path.relpath(str(dest_path), self.mod_folder_path).replace("\\", "/")
                        copied_files += 1
                    except Exception as e:
                        failed_copies.append(f"{image_file.name}: {e}")
                        full_path = str(image_file)
                        if self.mod_folder_path in full_path:
                            mod_relative = os.path.relpath(full_path, self.mod_folder_path).replace("\\", "/")
                        else:
                            mod_relative = full_path.replace("\\", "/")
                else:
                    full_path = str(image_file)
                    if self.mod_folder_path and self.mod_folder_path in full_path:
                        mod_relative = os.path.relpath(full_path, self.mod_folder_path).replace("\\", "/")
                    else:
                        mod_relative = full_path.replace("\\", "/")

                self._save_gfx(gfx_name, mod_relative, target_file)

            self.scan_gfx_files()

            message = f"{len(image_files)}개의 GFX가 추가되었습니다."
            if copy_to_mod:
                message += f"\n복사된 파일: {copied_files}개"
                if failed_copies:
                    message += f"\n복사 실패: {len(failed_copies)}개"
                    if len(failed_copies) <= 5:
                        message += "\n" + "\n".join(failed_copies)

            QMessageBox.information(self, "완료", message)

        except Exception as e:
            QMessageBox.critical(self, "오류", f"일괄 임포트 중 오류: {e}")

    # ----- 외부 도구 -----

    def open_focus_shine_generator(self):
        dialog = FocusShineDialog(self, self.mod_folder_path)
        dialog.exec()

    def open_batch_converter(self):
        dialog = BatchConvertDialog(self, self.mod_folder_path)
        dialog.exec()

    def export_analysis(self):
        if not hasattr(self, "analysis_text") or not self.analysis_text.toPlainText():
            QMessageBox.warning(self, "경고", "내보낼 분석 결과가 없습니다.")
            return

        file_path, _ = QFileDialog.getSaveFileName(
            self, "분석 결과 저장",
            f"gfx_analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
            "텍스트 파일 (*.txt)",
        )

        if file_path:
            try:
                with open(file_path, "w", encoding="utf-8") as f:
                    f.write(self.analysis_text.toPlainText())
                QMessageBox.information(self, "완료", f"분석 결과가 저장되었습니다:\n{file_path}")
            except Exception as e:
                QMessageBox.critical(self, "오류", f"파일 저장 중 오류: {e}")

    # ----- 프로젝트 -----

    def manage_projects(self):
        dialog = ProjectManagerDialog(self, self.projects)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            if dialog.selected_project:
                path = dialog.selected_project["path"]
                if os.path.exists(path):
                    self.mod_folder_path = path
                    self.scan_gfx_files()
                else:
                    QMessageBox.warning(self, "경고", "프로젝트 경로가 존재하지 않습니다.")
            self.projects = dialog.projects
            self._save_projects()
            self._update_project_tree()

    def save_current_project(self):
        if not self.mod_folder_path:
            QMessageBox.warning(self, "경고", "저장할 프로젝트가 없습니다.")
            return
        name, ok = QInputDialog.getText(self, "프로젝트 저장", "프로젝트 이름:")
        if ok and name:
            self.projects[name] = {
                "path": self.mod_folder_path,
                "saved_at": datetime.now().isoformat(),
            }
            self._save_projects()
            self._update_project_tree()

    def _update_project_tree(self):
        self.project_tree.clear()
        for name, info in self.projects.items():
            self.project_tree.addTopLevelItem(
                QTreeWidgetItem([name, info["path"], info.get("saved_at", "Unknown")])
            )

    def _load_projects(self):
        projects_str = self.settings.value("projects", "{}")
        try:
            return json.loads(projects_str)
        except Exception:
            return {}

    def _save_projects(self):
        self.settings.setValue("projects", json.dumps(self.projects))

    # ----- 파일/폴더 열기 -----

    def _current_gfx_info(self):
        current_item = self.gfx_tree.currentItem()
        if not (current_item and current_item.parent()):
            return None, None
        gfx_name = current_item.text(0)
        return gfx_name, self.gfx_data.get(gfx_name)

    @staticmethod
    def _open_in_shell(path):
        if sys.platform == "win32":
            os.startfile(path)
        else:
            subprocess.call(["xdg-open", path])

    def _open_gfx_file(self):
        _, gfx_info = self._current_gfx_info()
        if not gfx_info:
            return
        try:
            self._open_in_shell(gfx_info["file_source"])
        except Exception as e:
            QMessageBox.warning(self, "오류", f"파일을 열 수 없습니다: {e}")

    def _open_texture_folder(self):
        _, gfx_info = self._current_gfx_info()
        if not gfx_info:
            return
        try:
            self._open_in_shell(os.path.dirname(gfx_info["texturefile"]))
        except Exception as e:
            QMessageBox.warning(self, "오류", f"폴더를 열 수 없습니다: {e}")

    # ----- 드래그 앤 드롭 -----

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            for url in event.mimeData().urls():
                if url.toLocalFile().lower().endswith(IMAGE_EXTENSIONS):
                    event.acceptProposedAction()
                    return
        event.ignore()

    def dropEvent(self, event: QDropEvent):
        if not self.mod_folder_path:
            QMessageBox.warning(self, "경고", "먼저 모드 폴더를 선택해주세요.")
            event.ignore()
            return

        if not event.mimeData().hasUrls():
            event.ignore()
            return

        image_files = [
            url.toLocalFile() for url in event.mimeData().urls()
            if url.toLocalFile().lower().endswith(IMAGE_EXTENSIONS)
        ]

        if image_files:
            self._process_dropped_images(image_files)
            event.acceptProposedAction()
        else:
            event.ignore()

    def _process_dropped_images(self, image_files):
        gfx_files = list(Path(self.mod_folder_path).rglob("*.gfx"))
        if not gfx_files:
            QMessageBox.warning(self, "경고", "프로젝트에서 .gfx 파일을 찾을 수 없습니다.")
            return

        success_count = 0
        relative_paths = [os.path.relpath(str(f), self.mod_folder_path) for f in gfx_files]

        for image_file in image_files:
            dialog = DragDropDialog(self, image_file)
            dialog.gfx_file_combo.addItems(relative_paths)

            if dialog.exec() == QDialog.DialogCode.Accepted:
                data = dialog.get_data()
                if self._add_gfx_from_dragdrop(data):
                    success_count += 1

        if success_count > 0:
            self.scan_gfx_files()
            QMessageBox.information(self, "완료", f"{success_count}개의 GFX가 성공적으로 추가되었습니다.")

    def _add_gfx_from_dragdrop(self, data):
        try:
            name = data["name"]
            target_folder = data["target_folder"]
            gfx_file = data["gfx_file"]
            source_file = data["source_file"]

            if not all([name, target_folder, gfx_file, source_file]):
                QMessageBox.warning(self, "오류", "모든 필드를 입력해주세요.")
                return False

            target_full_path = os.path.join(self.mod_folder_path, target_folder)
            os.makedirs(target_full_path, exist_ok=True)

            filename = os.path.basename(source_file)
            dest_file = os.path.join(target_full_path, filename)
            shutil.copy2(source_file, dest_file)

            relative_path = f"{target_folder}{filename}".replace("\\", "/")
            self._save_gfx(name, relative_path, gfx_file)
            return True

        except Exception as e:
            QMessageBox.critical(self, "오류", f"GFX 추가 중 오류가 발생했습니다: {e}")
            return False

    def _handle_tree_drop(self, file_path, target_item):
        if not self.mod_folder_path:
            QMessageBox.warning(self, "경고", "먼저 모드 폴더를 선택해주세요.")
            return

        if target_item.parent():
            self._handle_gfx_replacement(file_path, target_item)
        else:
            modifiers = QApplication.keyboardModifiers()
            if modifiers & Qt.KeyboardModifier.ControlModifier:
                self._handle_new_gfx_manual(file_path, target_item)
            else:
                self._handle_new_gfx_auto(file_path, target_item)

    def _resolve_gfx_file_for_file_item(self, file_item):
        file_source = file_item.text(0)
        for info in self.gfx_data.values():
            if info["file_source"] == file_source:
                return info["file_source"]
        return None

    def _handle_new_gfx_manual(self, file_path, file_item):
        gfx_file_path = self._resolve_gfx_file_for_file_item(file_item)
        if not gfx_file_path:
            QMessageBox.warning(self, "오류", "대상 GFX 파일을 찾을 수 없습니다.")
            return

        dialog = DragDropDialog(self, file_path)
        self._populate_gfx_file_combo(dialog.gfx_file_combo)

        gfx_relative_path = os.path.relpath(gfx_file_path, self.mod_folder_path)
        for i in range(dialog.gfx_file_combo.count()):
            if gfx_relative_path == dialog.gfx_file_combo.itemText(i):
                dialog.gfx_file_combo.setCurrentIndex(i)
                break

        if dialog.exec() == QDialog.DialogCode.Accepted:
            data = dialog.get_data()
            data["source_file"] = file_path
            if self._add_gfx_from_dragdrop(data):
                self.scan_gfx_files()
                QMessageBox.information(self, "완료", f"새 GFX '{data['name']}'가 성공적으로 추가되었습니다.")

    def _handle_gfx_replacement(self, file_path, gfx_item):
        gfx_name = gfx_item.text(0)
        gfx_info = self.gfx_data.get(gfx_name)
        if not gfx_info:
            QMessageBox.warning(self, "오류", "선택된 GFX 정보를 찾을 수 없습니다.")
            return

        result = QMessageBox.question(
            self, "GFX 교체 확인",
            f"'{gfx_name}'의 텍스처를 새 이미지로 교체하시겠습니까?\n\n"
            f"현재: {gfx_info['relative_path']}\n"
            f"새 파일: {os.path.basename(file_path)}",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if result != QMessageBox.StandardButton.Yes:
            return

        current_texture_path = os.path.join(self.mod_folder_path, gfx_info["relative_path"])
        target_folder = os.path.dirname(current_texture_path)

        try:
            original_ext = os.path.splitext(gfx_info["relative_path"])[1]
            new_ext = os.path.splitext(file_path)[1]
            if original_ext.lower() == new_ext.lower():
                dest_filename = os.path.basename(gfx_info["relative_path"])
            else:
                base_name = os.path.splitext(os.path.basename(gfx_info["relative_path"]))[0]
                dest_filename = base_name + new_ext

            dest_path = os.path.join(target_folder, dest_filename)
            shutil.copy2(file_path, dest_path)

            new_relative_path = os.path.relpath(dest_path, self.mod_folder_path).replace("\\", "/")
            if new_relative_path != gfx_info["relative_path"]:
                update_gfx_texture_path(gfx_info["file_source"], gfx_name, new_relative_path)

            self.scan_gfx_files()
            QMessageBox.information(self, "완료", f"'{gfx_name}' 텍스처가 성공적으로 교체되었습니다.")

        except Exception as e:
            QMessageBox.critical(self, "오류", f"파일 교체 중 오류가 발생했습니다: {e}")

    def _handle_new_gfx_auto(self, file_path, file_item):
        gfx_file_path = self._resolve_gfx_file_for_file_item(file_item)
        if not gfx_file_path:
            QMessageBox.warning(self, "오류", "대상 GFX 파일을 찾을 수 없습니다.")
            return

        try:
            filename = Path(file_path).stem
            gfx_name = f"GFX_{filename}"

            original_name = gfx_name
            counter = 1
            while gfx_name in self.gfx_data:
                gfx_name = f"{original_name}_{counter}"
                counter += 1

            target_folder = (
                self._find_common_texture_folder(gfx_file_path)
                or os.path.join(os.path.dirname(gfx_file_path), "gfx")
            )
            os.makedirs(target_folder, exist_ok=True)

            filename_with_ext = os.path.basename(file_path)
            dest_file = os.path.join(target_folder, filename_with_ext)
            shutil.copy2(file_path, dest_file)

            relative_path = os.path.relpath(dest_file, self.mod_folder_path).replace("\\", "/")
            gfx_relative_path = os.path.relpath(gfx_file_path, self.mod_folder_path)
            self._save_gfx(gfx_name, relative_path, gfx_relative_path)

            self.scan_gfx_files()

            QMessageBox.information(
                self, "GFX 추가 완료",
                f"새 GFX가 자동으로 추가되었습니다:\n\n이름: {gfx_name}\n파일: {relative_path}",
            )

        except Exception as e:
            QMessageBox.critical(self, "오류", f"자동 GFX 추가 중 오류가 발생했습니다: {e}")

    def _find_common_texture_folder(self, gfx_file_path):
        folders = []
        for info in self.gfx_data.values():
            if info["file_source"] == gfx_file_path and info["status"] == "valid":
                texture_folder = os.path.dirname(
                    os.path.join(self.mod_folder_path, info["relative_path"])
                )
                if os.path.exists(texture_folder):
                    folders.append(texture_folder)
        if not folders:
            return None
        return Counter(folders).most_common(1)[0][0]

    # ----- 상태바 -----

    def _update_status(self):
        if self.mod_folder_path:
            status_text = (
                f"GFX: {len(self.gfx_data)}개 | "
                f"미사용: {len(self.orphaned_gfx)}개 | "
                f"누락: {len(self.missing_definitions)}개 | 드래그 앤 드롭 지원"
            )
            self.status_bar.showMessage(status_text)
        else:
            self.status_bar.showMessage("모드 폴더를 선택해주세요")
