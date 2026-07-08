"""
main.py
Punto di ingresso dell'app. Avvio: python main.py
"""
import sys

from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QPalette, QColor
from PySide6.QtCore import Qt

from gui.main_window import MainWindow


def apply_dark_palette(app: QApplication) -> None:
    """Forza il tema scuro indipendentemente dalle impostazioni di Windows.
    La dashboard è progettata attorno ai colori scuri — lasciarla dipendere
    dal tema di sistema causa problemi di leggibilità sul tema chiaro."""
    palette = QPalette()
    dark  = QColor(45,  45,  45)
    dark2 = QColor(30,  30,  30)
    dark3 = QColor(20,  20,  20)
    mid   = QColor(66,  66,  66)
    text  = QColor(224, 224, 224)
    bright_text = QColor(255, 255, 255)
    highlight   = QColor(25,  240, 28)   # #19F01C — verde brand
    disabled    = QColor(120, 120, 120)

    palette.setColor(QPalette.ColorRole.Window,          dark)
    palette.setColor(QPalette.ColorRole.WindowText,      text)
    palette.setColor(QPalette.ColorRole.Base,            dark2)
    palette.setColor(QPalette.ColorRole.AlternateBase,   dark3)
    palette.setColor(QPalette.ColorRole.ToolTipBase,     dark)
    palette.setColor(QPalette.ColorRole.ToolTipText,     text)
    palette.setColor(QPalette.ColorRole.Text,            text)
    palette.setColor(QPalette.ColorRole.Button,          dark)
    palette.setColor(QPalette.ColorRole.ButtonText,      text)
    palette.setColor(QPalette.ColorRole.BrightText,      bright_text)
    palette.setColor(QPalette.ColorRole.Link,            highlight)
    palette.setColor(QPalette.ColorRole.Highlight,       highlight)
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor(0, 0, 0))
    palette.setColor(QPalette.ColorRole.Mid,             mid)
    palette.setColor(QPalette.ColorRole.Shadow,          dark3)

    # Colori per i widget disabilitati
    palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.Text,       disabled)
    palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.ButtonText, disabled)
    palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.WindowText, disabled)

    app.setPalette(palette)


def main() -> None:
    app = QApplication(sys.argv)
    app.setApplicationName("Bambu Dashboard")
    app.setStyle("Fusion")  # Fusion è necessario per la palette personalizzata
    apply_dark_palette(app)

    # Icona taskbar/finestra: nell'exe la gestisce PyInstaller (risorsa PE)
    # Durante sviluppo (python main.py) la impostiamo via Qt
    if not getattr(sys, "frozen", False):
        try:
            from gui.icon_helper import make_app_icon
            app.setWindowIcon(make_app_icon())
        except Exception:
            pass

    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
