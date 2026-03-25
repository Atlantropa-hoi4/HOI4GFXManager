import importlib
import os
import sys
import tempfile
import types
import unittest
from unittest import mock


class DummyQtClass:
    def __init__(self, *args, **kwargs):
        pass

    def __getattr__(self, name):
        return DummyQtClass()


def ensure_dependency_stubs():
    if "PyQt6" not in sys.modules:
        pyqt6_module = types.ModuleType("PyQt6")
        qtwidgets = types.ModuleType("PyQt6.QtWidgets")
        qtcore = types.ModuleType("PyQt6.QtCore")
        qtgui = types.ModuleType("PyQt6.QtGui")

        widget_names = [
            "QApplication", "QMainWindow", "QWidget", "QVBoxLayout", "QHBoxLayout",
            "QPushButton", "QListWidget", "QLabel", "QFileDialog", "QMessageBox",
            "QSplitter", "QTabWidget", "QLineEdit", "QCheckBox", "QTextEdit",
            "QListWidgetItem", "QGroupBox", "QProgressBar", "QDialog", "QFormLayout",
            "QComboBox", "QSpinBox", "QDialogButtonBox", "QTreeWidget",
            "QTreeWidgetItem", "QMenu", "QMenuBar", "QStatusBar", "QToolBar",
            "QScrollArea", "QFrame", "QRadioButton",
        ]
        core_names = ["Qt", "QThread", "QTimer", "QSettings", "QUrl", "QMimeData", "QRect", "QPoint", "QSize"]
        gui_names = [
            "QPixmap", "QColor", "QAction", "QIcon", "QPalette", "QDragEnterEvent",
            "QDropEvent", "QPainter", "QFont", "QPen", "QBrush",
        ]

        for name in widget_names:
            setattr(qtwidgets, name, DummyQtClass)
        for name in core_names:
            setattr(qtcore, name, DummyQtClass)
        for name in gui_names:
            setattr(qtgui, name, DummyQtClass)

        qtcore.pyqtSignal = lambda *args, **kwargs: None

        pyqt6_module.QtWidgets = qtwidgets
        pyqt6_module.QtCore = qtcore
        pyqt6_module.QtGui = qtgui

        sys.modules["PyQt6"] = pyqt6_module
        sys.modules["PyQt6.QtWidgets"] = qtwidgets
        sys.modules["PyQt6.QtCore"] = qtcore
        sys.modules["PyQt6.QtGui"] = qtgui

    if "cv2" not in sys.modules:
        cv2_module = types.ModuleType("cv2")
        cv2_module.COLOR_RGBA2BGRA = "rgba2bgra"
        cv2_module.COLOR_RGB2BGR = "rgb2bgr"
        cv2_module.cvtColor = lambda image, code: image
        cv2_module.imwrite = lambda path, data: False
        sys.modules["cv2"] = cv2_module

    if "numpy" not in sys.modules:
        numpy_module = types.ModuleType("numpy")
        numpy_module.array = lambda image: image
        sys.modules["numpy"] = numpy_module

    if "PIL" not in sys.modules:
        pil_module = types.ModuleType("PIL")
        image_module = types.ModuleType("PIL.Image")
        dds_module = types.ModuleType("PIL.DdsImagePlugin")

        image_module.open = lambda path: None
        image_module.new = lambda *args, **kwargs: None

        pil_module.Image = image_module
        pil_module.DdsImagePlugin = dds_module

        sys.modules["PIL"] = pil_module
        sys.modules["PIL.Image"] = image_module
        sys.modules["PIL.DdsImagePlugin"] = dds_module

    if "gui_previewer" not in sys.modules:
        previewer_module = types.ModuleType("gui_previewer")
        previewer_module.GUIPreviewWidget = DummyQtClass
        sys.modules["gui_previewer"] = previewer_module


ensure_dependency_stubs()
main = importlib.import_module("main")


class FakeImage:
    def __init__(self, mode="RGBA"):
        self.mode = mode
        self.info = {}

    def convert(self, mode):
        return FakeImage(mode=mode)


class FakeImageContext:
    def __init__(self, image):
        self.image = image

    def __enter__(self):
        return self.image

    def __exit__(self, exc_type, exc, tb):
        return False


class ImageConverterDDSTests(unittest.TestCase):
    def setUp(self):
        self.converter = main.ImageConverter()
        self.image = FakeImage()
        self.temp_dir = tempfile.TemporaryDirectory()
        self.output_path = os.path.join(self.temp_dir.name, "sample.dds")

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_save_as_dds_removes_partial_output_when_encoder_reports_failure(self):
        with mock.patch.object(main.np, "array", return_value=object()), \
             mock.patch.object(main.cv2, "cvtColor", return_value=b"converted"), \
             mock.patch.object(main.cv2, "imwrite", return_value=False):
            with self.assertRaisesRegex(RuntimeError, "OpenCV failed to write DDS data"):
                self.converter._save_as_dds(self.image, self.output_path, "RGBA")

        self.assertFalse(os.path.exists(self.output_path))

    def test_save_as_dds_rejects_non_dds_payload(self):
        def write_fake_png(path, data):
            with open(path, "wb") as output_file:
                output_file.write(b"\x89PNGfake")
            return True

        with mock.patch.object(main.np, "array", return_value=object()), \
             mock.patch.object(main.cv2, "cvtColor", return_value=b"converted"), \
             mock.patch.object(main.cv2, "imwrite", side_effect=write_fake_png):
            with self.assertRaisesRegex(RuntimeError, "non-DDS data"):
                self.converter._save_as_dds(self.image, self.output_path, "RGBA")

        self.assertFalse(os.path.exists(self.output_path))

    def test_save_as_dds_keeps_valid_dds_output(self):
        def write_valid_dds(path, data):
            with open(path, "wb") as output_file:
                output_file.write(main.ImageConverter.DDS_MAGIC + b"payload")
            return True

        with mock.patch.object(main.np, "array", return_value=object()), \
             mock.patch.object(main.cv2, "cvtColor", return_value=b"converted"), \
             mock.patch.object(main.cv2, "imwrite", side_effect=write_valid_dds):
            self.converter._save_as_dds(self.image, self.output_path, "RGBA")

        with open(self.output_path, "rb") as output_file:
            self.assertEqual(output_file.read(4), main.ImageConverter.DDS_MAGIC)

    def test_convert_image_reports_dds_failure(self):
        with mock.patch.object(main.Image, "open", return_value=FakeImageContext(self.image)), \
             mock.patch.object(main.ImageConverter, "_save_as_dds", side_effect=RuntimeError("DDS conversion failed: encoder missing")):
            success, error = self.converter.convert_image(
                "input.png",
                self.output_path,
                output_format="DDS",
                dds_format="RGBA",
            )

        self.assertFalse(success)
        self.assertIn("encoder missing", error)
        self.assertFalse(os.path.exists(self.output_path))


if __name__ == "__main__":
    unittest.main()
