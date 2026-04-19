"""드래그 앤 드롭을 지원하는 GFX 트리 위젯."""

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import QTreeWidget, QTreeWidgetItem

from .theme import IMAGE_EXTENSIONS


class GFXTreeWidget(QTreeWidget):
    """파일 노드 / GFX 노드로 구성된 트리. 이미지 드롭 이벤트를 시그널로 전달."""

    file_dropped = pyqtSignal(str, QTreeWidgetItem)

    def __init__(self):
        super().__init__()
        self.setAcceptDrops(True)
        self.setDragDropMode(QTreeWidget.DragDropMode.DropOnly)

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            for url in event.mimeData().urls():
                file_path = url.toLocalFile()
                if file_path.lower().endswith(IMAGE_EXTENSIONS):
                    event.acceptProposedAction()
                    return
        event.ignore()

    def dragMoveEvent(self, event):
        if not event.mimeData().hasUrls():
            event.ignore()
            return
        item = self.itemAt(event.position().toPoint())
        if item:
            event.acceptProposedAction()
            self.setCurrentItem(item)
        else:
            event.ignore()

    def dropEvent(self, event):
        if not event.mimeData().hasUrls():
            event.ignore()
            return
        item = self.itemAt(event.position().toPoint())
        if not item:
            event.ignore()
            return
        for url in event.mimeData().urls():
            file_path = url.toLocalFile()
            if file_path.lower().endswith(IMAGE_EXTENSIONS):
                self.file_dropped.emit(file_path, item)
                break
        event.acceptProposedAction()
