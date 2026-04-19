"""HOI4 GFX Manager 애플리케이션 엔트리."""

import sys

from PyQt6.QtWidgets import QApplication

from . import __version__
from .ui.main_window import GFXManager


def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setApplicationName("HOI4 GFX Manager")
    app.setApplicationVersion(__version__)
    app.setOrganizationName("HOI4 Modding Tools")

    window = GFXManager()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
