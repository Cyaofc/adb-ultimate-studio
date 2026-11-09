"""Paletas y estilos del espacio de trabajo."""
from PySide6.QtGui import QColor, QPalette


def apply(window, dark):
    colors = dict(
        bg="#0b111c", panel="#111b2b", input="#0c1524", border="#26364d",
        text="#e8eef9", muted="#a9bad0", accent="#7ce8cb", strong="#133b3a",
        hover="#20334c", console="#080f1a", danger="#ffc1c4",
    ) if dark else dict(
        bg="#eef3f9", panel="#ffffff", input="#f5f8fc", border="#cad6e5",
        text="#192940", muted="#4f637d", accent="#086457", strong="#d4f0e8",
        hover="#e5edf8", console="#f3f7fc", danger="#9d263d",
    )
    palette = QPalette()
    for role, key in {
        "Window": "bg", "WindowText": "text", "Base": "input", "AlternateBase": "panel",
        "Text": "text", "Button": "panel", "ButtonText": "text", "Highlight": "strong",
        "HighlightedText": "text", "ToolTipBase": "panel", "ToolTipText": "text",
    }.items():
        palette.setColor(getattr(QPalette.ColorRole, role), QColor(colors[key]))
    window.setPalette(palette)
    sheet = """
        QMainWindow, QWidget#workspace { background: @bg; }
        QWidget { color: @text; font-size: 13px; }
        QFrame#header, QFrame#rail, QWidget#panel, QFrame#statusCard {
            background: @panel; border: 1px solid @border; border-radius: 12px;
        }
        QLabel { background: transparent; border: none; }
        QLabel#brandMark {
            color: @accent; background: @strong; border-radius: 10px;
            font: bold 19px monospace;
        }
        QLabel#brand { font-size: 21px; font-weight: 700; }
        QLabel#panelTitle { font-size: 24px; font-weight: 700; }
        QLabel#eyebrow { color: @accent; font-size: 11px; font-weight: 700; }
        QLabel#muted { color: @muted; }
        QLabel#metric { color: @text; font-size: 19px; font-weight: 700; }
        QLabel#status { color: @accent; font-weight: 700; }
        QLineEdit, QComboBox, QListWidget, QPlainTextEdit {
            background: @input; border: 1px solid @border; border-radius: 7px;
            selection-background-color: @strong; selection-color: @text;
        }
        QLineEdit, QComboBox { min-height: 30px; padding: 2px 9px; }
        QLineEdit:focus, QComboBox:focus, QPlainTextEdit:focus { border-color: @accent; }
        QComboBox::drop-down { width: 24px; border: none; }
        QComboBox QAbstractItemView { background: @panel; selection-background-color: @strong; }
        QListWidget#navigation { background: transparent; border: none; outline: none; }
        QListWidget#navigation::item { min-height: 20px; padding: 3px 8px; border-radius: 7px; }
        QListWidget#navigation::item:hover { background: @hover; }
        QListWidget#navigation::item:selected { background: @strong; color: @accent; font-weight: 700; }
        QPushButton {
            background: @input; border: 1px solid @border; border-radius: 7px;
            min-height: 29px; padding: 2px 9px;
        }
        QPushButton:hover { background: @hover; }
        QPushButton:focus { border-color: @accent; }
        QPushButton[primary="true"] { background: @strong; color: @accent; font-weight: 700; }
        QPushButton:disabled { color: @muted; border-color: @border; }
        QScrollArea { border: none; background: transparent; }
        QScrollArea > QWidget > QWidget { background: transparent; }
        QPlainTextEdit[console="true"] {
            background: @console; font-family: monospace; font-size: 12px;
        }
        QTabWidget::pane { border: 1px solid @border; border-radius: 8px; background: @panel; }
        QTabBar::tab {
            background: @input; color: @muted; padding: 7px 15px;
            border: 1px solid @border; border-top-left-radius: 7px; border-top-right-radius: 7px;
        }
        QTabBar::tab:selected { color: @accent; background: @panel; }
        QScrollBar:vertical { background: @input; width: 8px; border-radius: 4px; }
        QScrollBar:horizontal { background: @input; height: 8px; border-radius: 4px; }
        QScrollBar::handle { background: @border; min-height: 18px; min-width: 18px; border-radius: 4px; }
        QScrollBar::add-line, QScrollBar::sub-line { width: 0px; height: 0px; }
        QScrollBar::add-page, QScrollBar::sub-page { background: transparent; }
        QSplitter::handle { background: @border; margin: 2px 20px; border-radius: 2px; }
        QProgressBar { border: 1px solid @border; border-radius: 5px; height: 9px; }
        QProgressBar::chunk { background: @accent; }
    """
    for name, color in colors.items():
        sheet = sheet.replace(f"@{name}", color)
    window.setStyleSheet(sheet)
