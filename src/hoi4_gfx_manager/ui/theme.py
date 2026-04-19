"""테마 스타일시트."""

DARK_STYLESHEET = """
QMainWindow {
    background-color: #2b2b2b;
    color: #ffffff;
}
QWidget {
    background-color: #2b2b2b;
    color: #ffffff;
}
QListWidget, QTextEdit, QLineEdit {
    background-color: #3c3c3c;
    border: 1px solid #555555;
    color: #ffffff;
}
QPushButton {
    background-color: #404040;
    border: 1px solid #555555;
    padding: 5px;
    color: #ffffff;
}
QPushButton:hover {
    background-color: #505050;
}
QMenuBar {
    background-color: #2b2b2b;
    color: #ffffff;
}
QMenuBar::item:selected {
    background-color: #404040;
}
"""

IMAGE_PLACEHOLDER_STYLE = """
QLabel {
    border: 2px dashed #ccc;
    border-radius: 8px;
    padding: 20px;
    color: #666;
    font-size: 14px;
    background-color: #f9f9f9;
}
"""

IMAGE_EXTENSIONS = (".dds", ".png", ".jpg", ".jpeg", ".bmp", ".tga")
