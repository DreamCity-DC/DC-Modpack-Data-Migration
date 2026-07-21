from PyQt6.QtCore import QEasingCurve, QPropertyAnimation, Qt
from PyQt6.QtGui import QColor, QCloseEvent, QShowEvent
from PyQt6.QtWidgets import (
    QDialog,
    QFrame,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


class DraggableHeader(QWidget):
    """A header area that can move its frameless top-level window."""

    def __init__(self, window):
        super().__init__()
        self._window = window
        self._drag_offset = None

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            handle = self._window.windowHandle()
            if handle is not None and handle.startSystemMove():
                self._drag_offset = None
            else:
                self._drag_offset = (
                    event.globalPosition().toPoint()
                    - self._window.frameGeometry().topLeft()
                )
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if (
            self._drag_offset is not None
            and event.buttons() & Qt.MouseButton.LeftButton
        ):
            self._window.move(event.globalPosition().toPoint() - self._drag_offset)
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        self._drag_offset = None
        super().mouseReleaseEvent(event)


class AnimatedMainWindow(QMainWindow):
    """Main-window base with short, unobtrusive fade transitions."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._fade_has_shown = False
        self._fade_closing = False
        self._fade_allow_close = False
        self._fade_animation = QPropertyAnimation(self, b"windowOpacity", self)
        self._fade_animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._fade_animation.finished.connect(self._finish_fade)

    def showEvent(self, event: QShowEvent):
        super().showEvent(event)
        if self._fade_has_shown:
            return
        self._fade_has_shown = True
        self.setWindowOpacity(0.0)
        self._fade_animation.setDuration(160)
        self._fade_animation.setStartValue(0.0)
        self._fade_animation.setEndValue(1.0)
        self._fade_animation.start()

    def closeEvent(self, event: QCloseEvent):
        if self._fade_allow_close:
            super().closeEvent(event)
            return

        event.ignore()
        if self._fade_closing:
            return
        self._fade_closing = True
        self._fade_animation.stop()
        self._fade_animation.setDuration(130)
        self._fade_animation.setStartValue(self.windowOpacity())
        self._fade_animation.setEndValue(0.0)
        self._fade_animation.start()

    def _finish_fade(self):
        if not self._fade_closing:
            return
        self._fade_allow_close = True
        self.close()


class AnimatedDialog(QDialog):
    """Dialog base that fades around its modal lifecycle."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._fade_has_shown = False
        self._fade_pending_result = None
        self._fade_animation = QPropertyAnimation(self, b"windowOpacity", self)
        self._fade_animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._fade_animation.finished.connect(self._finish_fade)

    def showEvent(self, event: QShowEvent):
        super().showEvent(event)
        if self._fade_has_shown:
            return
        self._fade_has_shown = True
        self.setWindowOpacity(0.0)
        self._fade_animation.setDuration(160)
        self._fade_animation.setStartValue(0.0)
        self._fade_animation.setEndValue(1.0)
        self._fade_animation.start()

    def done(self, result: int):
        if self._fade_pending_result is not None:
            return
        self._fade_pending_result = result
        self._fade_animation.stop()
        self._fade_animation.setDuration(130)
        self._fade_animation.setStartValue(self.windowOpacity())
        self._fade_animation.setEndValue(0.0)
        self._fade_animation.start()

    def accept(self):
        self.done(QDialog.DialogCode.Accepted.value)

    def reject(self):
        self.done(QDialog.DialogCode.Rejected.value)

    def _finish_fade(self):
        if self._fade_pending_result is None:
            return
        result = self._fade_pending_result
        self._fade_pending_result = None
        QDialog.done(self, result)


class AppMessageDialog(AnimatedDialog):
    """Reusable app-styled alert and confirmation dialog."""

    _ICON_TEXT = {
        "warning": "!",
        "error": "×",
        "success": "✓",
        "info": "i",
    }

    def __init__(
        self,
        title,
        message,
        parent=None,
        *,
        kind="info",
        confirm_text="确定",
        cancel_text=None,
    ):
        super().__init__(parent)
        if kind not in self._ICON_TEXT:
            kind = "info"

        self.setWindowTitle(title)
        self.setModal(True)
        self.setWindowFlag(Qt.WindowType.FramelessWindowHint, True)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setFixedWidth(430)

        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(14, 14, 14, 18)

        surface = QFrame()
        surface.setObjectName("messageSurface")
        shadow = QGraphicsDropShadowEffect(surface)
        shadow.setBlurRadius(16)
        shadow.setOffset(0, 3)
        shadow.setColor(QColor(16, 24, 40, 42))
        surface.setGraphicsEffect(shadow)
        outer_layout.addWidget(surface)

        layout = QVBoxLayout(surface)
        layout.setContentsMargins(26, 24, 26, 22)
        layout.setSpacing(16)

        header = DraggableHeader(self)
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(10)

        icon = QLabel(self._ICON_TEXT[kind])
        icon.setObjectName("messageIcon")
        icon.setProperty("kind", kind)
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon.setFixedSize(28, 28)
        icon.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)

        title_label = QLabel(title)
        title_label.setObjectName("messageTitle")
        title_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        header_layout.addWidget(icon)
        header_layout.addWidget(title_label)
        header_layout.addStretch()
        layout.addWidget(header)

        message_label = QLabel(message)
        message_label.setObjectName("messageText")
        message_label.setTextFormat(Qt.TextFormat.PlainText)
        message_label.setWordWrap(True)
        message_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(message_label)

        button_layout = QHBoxLayout()
        button_layout.setSpacing(10)
        button_layout.addStretch()

        if cancel_text:
            cancel_button = QPushButton(cancel_text)
            cancel_button.setObjectName("messageCancelButton")
            cancel_button.setDefault(True)
            cancel_button.clicked.connect(self.reject)
            button_layout.addWidget(cancel_button)

        confirm_button = QPushButton(confirm_text)
        confirm_button.setObjectName("messageConfirmButton")
        confirm_button.setProperty("kind", kind)
        confirm_button.setDefault(not bool(cancel_text))
        confirm_button.clicked.connect(self.accept)
        button_layout.addWidget(confirm_button)
        layout.addLayout(button_layout)

        self.setStyleSheet("""
            QFrame#messageSurface {
                background: #FFFFFF;
                border: 1px solid #DDE2E8;
                border-radius: 14px;
                font-family: "Microsoft YaHei UI", "Segoe UI";
            }

            QLabel#messageIcon {
                color: #FFFFFF;
                border-radius: 14px;
                font-size: 17px;
                font-weight: 700;
            }

            QLabel#messageIcon[kind="warning"] {
                background: #B54134;
            }

            QLabel#messageIcon[kind="error"] {
                background: #B42318;
            }

            QLabel#messageIcon[kind="success"] {
                background: #287A4B;
            }

            QLabel#messageIcon[kind="info"] {
                background: #3B6F8F;
            }

            QLabel#messageTitle {
                color: #182230;
                font-size: 17px;
                font-weight: 600;
            }

            QLabel#messageText {
                color: #475467;
                font-size: 13px;
            }

            QPushButton#messageCancelButton,
            QPushButton#messageConfirmButton {
                min-width: 96px;
                min-height: 36px;
                padding: 0 14px;
                border-radius: 6px;
                font-size: 13px;
                font-weight: 600;
            }

            QPushButton#messageCancelButton {
                color: #344054;
                background: #FFFFFF;
                border: 1px solid #D0D5DD;
            }

            QPushButton#messageCancelButton:hover {
                background: #F9FAFB;
                border-color: #98A2B3;
            }

            QPushButton#messageConfirmButton {
                color: #FFFFFF;
                background: #B54134;
                border: 1px solid #B54134;
            }

            QPushButton#messageConfirmButton:hover {
                background: #9E352A;
                border-color: #9E352A;
            }

            QPushButton#messageConfirmButton:pressed {
                background: #852C24;
                border-color: #852C24;
            }
        """)
        self.adjustSize()


def show_message(parent, title, message, *, kind="info", button_text="确定"):
    dialog = AppMessageDialog(
        title,
        message,
        parent,
        kind=kind,
        confirm_text=button_text,
    )
    return dialog.exec()


def ask_confirmation(
    parent,
    title,
    message,
    *,
    confirm_text="确认",
    cancel_text="取消",
    kind="warning",
):
    dialog = AppMessageDialog(
        title,
        message,
        parent,
        kind=kind,
        confirm_text=confirm_text,
        cancel_text=cancel_text,
    )
    return dialog.exec() == QDialog.DialogCode.Accepted
