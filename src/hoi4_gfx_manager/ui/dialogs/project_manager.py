"""저장된 프로젝트 관리 다이얼로그."""

from datetime import datetime

from PyQt6.QtWidgets import (
    QDialog, QHBoxLayout, QInputDialog, QLabel, QListWidget, QMessageBox,
    QPushButton, QVBoxLayout,
)


class ProjectManagerDialog(QDialog):
    """프로젝트 저장/불러오기/삭제."""

    def __init__(self, parent=None, projects=None):
        super().__init__(parent)
        self.setWindowTitle("프로젝트 관리")
        self.setModal(True)
        self.resize(500, 400)
        self.projects = projects or {}
        self.selected_project = None

        layout = QVBoxLayout()
        self.setLayout(layout)

        self.project_list = QListWidget()
        self.update_project_list()
        layout.addWidget(QLabel("저장된 프로젝트:"))
        layout.addWidget(self.project_list)

        btn_layout = QHBoxLayout()
        self.add_btn = QPushButton("현재 프로젝트 저장")
        self.add_btn.clicked.connect(self.add_project)
        self.load_btn = QPushButton("불러오기")
        self.load_btn.clicked.connect(self.load_project)
        self.delete_btn = QPushButton("삭제")
        self.delete_btn.clicked.connect(self.delete_project)

        btn_layout.addWidget(self.add_btn)
        btn_layout.addWidget(self.load_btn)
        btn_layout.addWidget(self.delete_btn)
        layout.addLayout(btn_layout)

        close_btn = QPushButton("닫기")
        close_btn.clicked.connect(self.accept)
        layout.addWidget(close_btn)

    def update_project_list(self):
        self.project_list.clear()
        for name, info in self.projects.items():
            self.project_list.addItem(f"{name} ({info.get('path', 'Unknown')})")

    def _selected_name(self):
        current_item = self.project_list.currentItem()
        if not current_item:
            return None
        return current_item.text().split(" (")[0]

    def add_project(self):
        parent = self.parent()
        if not (parent and getattr(parent, "mod_folder_path", None)):
            return
        name, ok = QInputDialog.getText(self, "프로젝트 저장", "프로젝트 이름:")
        if ok and name:
            self.projects[name] = {
                "path": parent.mod_folder_path,
                "saved_at": datetime.now().isoformat(),
            }
            self.update_project_list()

    def load_project(self):
        name = self._selected_name()
        if not name:
            return
        self.selected_project = self.projects.get(name)
        self.accept()

    def delete_project(self):
        name = self._selected_name()
        if not name:
            return
        reply = QMessageBox.question(self, "삭제 확인", f"프로젝트 '{name}'을 삭제하시겠습니까?")
        if reply == QMessageBox.StandardButton.Yes:
            del self.projects[name]
            self.update_project_list()
