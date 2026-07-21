import os
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
    QPushButton, QComboBox, QFileDialog, QFrame, QMessageBox, 
    QProgressBar, QSizePolicy, QAbstractButton, QGraphicsDropShadowEffect
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QIcon, QPainter, QPen

from src.data_migration import MigrationWorker
from src.utils import get_versions, find_max_version, get_resource_path, get_dependence_path, setup_logging
from src.constants import APP_VERSION, MIGRATION_RULE_FILE_NAME


class WindowControlButton(QAbstractButton):
    """Small, fully painted window control used by the custom title bar."""

    def __init__(self, control_type, parent=None):
        super().__init__(parent)
        self.control_type = control_type
        self.setFixedSize(42, 34)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setCursor(Qt.CursorShape.ArrowCursor)
        if control_type == "close":
            self.setToolTip("关闭")
            self.setAccessibleName("关闭窗口")
        else:
            self.setToolTip("最小化")
            self.setAccessibleName("最小化窗口")

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        hovered = self.underMouse()
        pressed = self.isDown()
        if self.control_type == "close" and hovered:
            background = QColor("#C42B1C" if not pressed else "#A82015")
            foreground = QColor("#FFFFFF")
        else:
            if pressed:
                background = QColor("#D9E1E6")
            elif hovered:
                background = QColor("#E3EAEE")
            else:
                background = QColor(Qt.GlobalColor.transparent)
            foreground = QColor("#182230")

        painter.fillRect(self.rect(), background)
        pen = QPen(foreground)
        pen.setWidthF(1.5)
        pen.setCapStyle(Qt.PenCapStyle.SquareCap)
        painter.setPen(pen)

        center_x = self.width() / 2
        center_y = self.height() / 2
        if self.control_type == "close":
            painter.drawLine(
                int(center_x - 5), int(center_y - 5),
                int(center_x + 5), int(center_y + 5),
            )
            painter.drawLine(
                int(center_x + 5), int(center_y - 5),
                int(center_x - 5), int(center_y + 5),
            )
        else:
            painter.drawLine(
                int(center_x - 5), int(center_y + 3),
                int(center_x + 5), int(center_y + 3),
            )


class DraggableHeader(QWidget):
    """Content header that doubles as the frameless window drag area."""

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


class ElidedPathLabel(QLabel):
    """Single-line path display that preserves the useful path ending."""

    def __init__(self, placeholder="尚未选择..."):
        super().__init__()
        self._full_text = ""
        self._placeholder = placeholder
        self.setObjectName("pathDisplay")
        self.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setMinimumWidth(0)
        self.setFixedHeight(38)
        self._refresh_text()

    def setText(self, text):
        self._full_text = text or ""
        self.setToolTip(self._full_text)
        self._refresh_text()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._refresh_text()

    def _refresh_text(self):
        display_text = self._full_text or self._placeholder
        available_width = max(40, self.width() - 24)
        elided = self.fontMetrics().elidedText(
            display_text,
            Qt.TextElideMode.ElideMiddle,
            available_width,
        )
        QLabel.setText(self, elided)


class ChevronComboBox(QComboBox):
    """Combo box with a lightweight chevron that matches the custom UI."""

    def paintEvent(self, event):
        super().paintEvent(event)

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        color = QColor("#667085" if self.isEnabled() else "#98A2B3")
        pen = QPen(color)
        pen.setWidthF(1.5)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        painter.setPen(pen)

        center_x = self.width() - 18
        center_y = self.height() // 2
        painter.drawLine(center_x - 4, center_y - 2, center_x, center_y + 2)
        painter.drawLine(center_x, center_y + 2, center_x + 4, center_y - 2)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"DreamCity 整合包数据迁移工具 {APP_VERSION}")
        self.setWindowFlag(Qt.WindowType.FramelessWindowHint, True)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)

        icon_path = get_resource_path('assets', 'icon.ico')
        window_icon = QIcon()
        if os.path.exists(icon_path):
            window_icon = QIcon(icon_path)
            self.setWindowIcon(window_icon)

        # Main Widget
        central_widget = QWidget()
        central_widget.setObjectName("centralWidget")
        self.setCentralWidget(central_widget)

        window_layout = QVBoxLayout(central_widget)
        # Keep a transparent gutter around the surface so its soft shadow is
        # fully visible against light desktop backgrounds.
        window_layout.setContentsMargins(14, 14, 14, 18)
        window_layout.setSpacing(0)

        self.window_surface = QFrame()
        self.window_surface.setObjectName("windowSurface")
        window_shadow = QGraphicsDropShadowEffect(self.window_surface)
        window_shadow.setBlurRadius(16)
        window_shadow.setOffset(0, 3)
        window_shadow.setColor(QColor(16, 24, 40, 42))
        self.window_surface.setGraphicsEffect(window_shadow)
        window_layout.addWidget(self.window_surface, 1)

        self.main_layout = QVBoxLayout(self.window_surface)
        self.main_layout.setContentsMargins(24, 18, 24, 8)
        self.main_layout.setSpacing(18)

        self.setup_style()

        # 1. Header Section
        self.setup_header()
        
        # 2. Selection Section (Split View)
        self.setup_selection_area()

        # Keep action button state in sync with selections
        self.combo_from_ver.currentTextChanged.connect(self.check_ready)
        self.combo_to_ver.currentTextChanged.connect(self.check_ready)

        # 3. Action Section
        self.setup_action_area()

        # 4. Footer (Open Source Link)
        self.setup_footer()

        # Initialize State
        self.worker = None
        self.init_defaults()

        # Use a stable initial size, while still adapting to DPI and longer text.
        # Preserve the 780 × 410 content surface while allowing room for the
        # translucent shadow around it.
        self.setFixedSize(808, 442)

    def setup_style(self):
        self.setStyleSheet("""
            QMainWindow, QWidget#centralWidget {
                background: transparent;
            }

            QFrame#windowSurface {
                background: #F5F7FA;
                color: #182230;
                font-family: "Microsoft YaHei UI", "Segoe UI";
                font-size: 13px;
                border: 1px solid #D9E0E6;
                border-radius: 14px;
            }

            QLabel#appTitle {
                color: #101828;
                font-size: 20px;
                font-weight: 600;
            }

            QLabel#versionBadge {
                color: #8F352A;
                background: #FBEAE7;
                border-radius: 9px;
                padding: 2px 8px;
                font-size: 11px;
                font-weight: 600;
            }

            QLabel#description {
                color: #475467;
                font-size: 13px;
            }

            QLabel#fieldLabel, QLabel#statusLabel {
                color: #667085;
                font-size: 12px;
            }

            QLabel#statusLabel[state="ready"] {
                color: #287A4B;
            }

            QLabel#statusLabel[state="error"] {
                color: #B42318;
            }

            QFrame#migrationCard {
                background: #FFFFFF;
                border: 1px solid #DDE2E8;
                border-radius: 10px;
            }

            QLabel#cardTitle {
                color: #182230;
                font-size: 15px;
                font-weight: 600;
                border: none;
                background: transparent;
            }

            QLabel#pathDisplay {
                color: #344054;
                background: #F9FAFB;
                border: 1px solid #D0D5DD;
                border-radius: 6px;
                padding: 0 11px;
            }

            QLabel#pathDisplay:disabled {
                color: #98A2B3;
                background: #F2F4F7;
                border-color: #E4E7EC;
            }

            QPushButton#browseButton {
                min-height: 36px;
                padding: 0 14px;
                color: #344054;
                background: #FFFFFF;
                border: 1px solid #D0D5DD;
                border-radius: 6px;
                font-weight: 500;
            }

            QPushButton#browseButton:hover {
                background: #F9FAFB;
                border-color: #98A2B3;
            }

            QPushButton#browseButton:pressed {
                background: #F2F4F7;
            }

            QComboBox {
                min-height: 36px;
                padding: 0 10px;
                color: #182230;
                background: #FFFFFF;
                border: 1px solid #D0D5DD;
                border-radius: 6px;
            }

            QComboBox:hover, QComboBox:focus {
                border-color: #A84235;
            }

            QComboBox:disabled {
                color: #98A2B3;
                background: #F2F4F7;
                border-color: #E4E7EC;
            }

            QComboBox::drop-down {
                width: 34px;
                border: none;
                background: transparent;
            }

            QComboBox::down-arrow {
                image: none;
                width: 0;
                height: 0;
            }

            QPushButton#primaryButton {
                min-width: 150px;
                min-height: 40px;
                padding: 0 20px;
                color: #FFFFFF;
                background: #B54134;
                border: 1px solid #B54134;
                border-radius: 7px;
                font-size: 13px;
                font-weight: 600;
            }

            QPushButton#primaryButton:hover {
                background: #9E352A;
                border-color: #9E352A;
            }

            QPushButton#primaryButton:pressed {
                background: #852C24;
                border-color: #852C24;
            }

            QPushButton#primaryButton:disabled {
                color: #98A2B3;
                background: #E4E7EC;
                border-color: #E4E7EC;
            }

            QProgressBar {
                min-height: 7px;
                max-height: 7px;
                background: #E4E7EC;
                border: none;
                border-radius: 3px;
            }

            QProgressBar::chunk {
                background: #B54134;
                border-radius: 3px;
            }

            QLabel#footerLink {
                color: #667085;
                font-size: 12px;
            }
        """)

    @staticmethod
    def _normalize_path_for_fs(path: str) -> str:
        if not path:
            return path
        # Keep internal paths in platform-native form.
        return os.path.normpath(path)

    @staticmethod
    def _format_path_for_ui(path: str) -> str:
        if not path:
            return path
        # Qt/Python on Windows can operate with both separators, but for UI readability
        # we consistently display forward slashes.
        return path.replace('\\', '/')

    def setup_header(self):
        header = DraggableHeader(self)
        header.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        header_layout = QVBoxLayout(header)
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(2)

        title_layout = QHBoxLayout()
        title_layout.setSpacing(8)

        title = QLabel("DreamCity 整合包数据迁移工具")
        title.setObjectName("appTitle")
        title.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        version = QLabel(APP_VERSION)
        version.setObjectName("versionBadge")
        version.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)

        self.minimize_button = WindowControlButton("minimize")
        self.close_button = WindowControlButton("close")
        self.minimize_button.clicked.connect(self.showMinimized)
        self.close_button.clicked.connect(self.close)

        title_layout.addWidget(title)
        title_layout.addWidget(version)
        title_layout.addStretch()
        title_layout.addWidget(self.minimize_button)
        title_layout.addWidget(self.close_button)

        desc = QLabel("快速迁移旧版存档、设置和地图等到新版整合包")
        desc.setObjectName("description")
        desc.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)

        header_layout.addLayout(title_layout)
        header_layout.addWidget(desc)
        self.main_layout.addWidget(header)

    def setup_footer(self):
        footer = QWidget()
        footer.setFixedHeight(22)
        footer_layout = QHBoxLayout(footer)
        footer_layout.setContentsMargins(0, 0, 0, 0)

        info_text = (
            "<a href='https://github.com/DreamCity-DC/DC-Modpack-Data-Migration' "
            "style='color:#8F352A;text-decoration:none;'>"
            "GitHub 开源地址"
            "</a>"
        )
        info = QLabel(info_text)
        info.setObjectName("footerLink")
        info.setOpenExternalLinks(True)

        footer_layout.addWidget(info)
        footer_layout.addStretch()
        self.main_layout.addWidget(footer)

    def setup_selection_area(self):
        selection_layout = QHBoxLayout()
        selection_layout.setSpacing(14)
        
        # --- Left Group (Source) ---
        self.lbl_from_path = ElidedPathLabel()
        self.combo_from_ver = ChevronComboBox()
        
        self.from_group = self.create_part_group(
            "旧版整合包",
            self.lbl_from_path, 
            self.select_from_directory, 
            self.combo_from_ver
        )
        
        # --- Right Group (Target) ---
        self.lbl_to_path = ElidedPathLabel()
        self.combo_to_ver = ChevronComboBox()
        
        self.to_group = self.create_part_group(
            "新版整合包",
            self.lbl_to_path, 
            self.select_to_directory, 
            self.combo_to_ver
        )

        # Arrow (in layout, avoids manual repositioning)
        self.arrow_label = QLabel("→")
        font = self.arrow_label.font()
        font.setPointSize(18)
        self.arrow_label.setFont(font)
        self.arrow_label.setStyleSheet("color: #98A2B3; background: transparent;")
        self.arrow_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.arrow_label.setFixedWidth(28)

        selection_layout.addWidget(self.from_group, 1)
        selection_layout.addWidget(self.arrow_label)
        selection_layout.addWidget(self.to_group, 1)
        
        self.main_layout.addLayout(selection_layout)

    def create_part_group(self, title, path_widget, browse_func, combo_box):
        group = QFrame()
        group.setObjectName("migrationCard")
        group.setMinimumWidth(280)

        layout = QVBoxLayout(group)
        layout.setContentsMargins(18, 16, 18, 18)
        layout.setSpacing(9)

        card_title = QLabel(title)
        card_title.setObjectName("cardTitle")
        layout.addWidget(card_title)
        layout.addSpacing(3)

        lbl_title = QLabel("整合包文件夹")
        lbl_title.setObjectName("fieldLabel")
        layout.addWidget(lbl_title)

        path_layout = QHBoxLayout()
        path_layout.setSpacing(8)

        btn_browse = QPushButton("选择文件夹")
        btn_browse.setObjectName("browseButton")
        btn_browse.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_browse.clicked.connect(browse_func)

        path_layout.addWidget(path_widget, 1)
        path_layout.addWidget(btn_browse)
        layout.addLayout(path_layout)

        path_widget.setEnabled(False)

        lbl_ver = QLabel("游戏版本")
        lbl_ver.setObjectName("fieldLabel")

        combo_box.setPlaceholderText("请先选择整合包...")
        combo_box.setEnabled(False)
        combo_box.setFixedHeight(38)

        layout.addSpacing(5)
        layout.addWidget(lbl_ver)
        layout.addWidget(combo_box)

        return group

    def setup_action_area(self):
        action_layout = QHBoxLayout()
        action_layout.setSpacing(18)

        status_panel = QWidget()
        status_panel.setFixedHeight(48)
        status_layout = QVBoxLayout(status_panel)
        status_layout.setContentsMargins(0, 1, 0, 1)
        status_layout.setSpacing(6)

        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.hide()

        self.lbl_status = QLabel("请选择旧版整合包和游戏版本")
        self.lbl_status.setObjectName("statusLabel")
        self.lbl_status.setAlignment(Qt.AlignmentFlag.AlignLeft)
        self.lbl_status.setTextFormat(Qt.TextFormat.PlainText)
        self.lbl_status.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.lbl_status.setMinimumWidth(0)

        status_layout.addWidget(self.lbl_status)
        status_layout.addWidget(self.progress_bar)
        status_layout.addStretch()

        self.btn_migrate = QPushButton("开始迁移数据")
        self.btn_migrate.setObjectName("primaryButton")
        self.btn_migrate.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_migrate.setEnabled(False)
        self.btn_migrate.clicked.connect(self.start_migration)

        action_layout.addWidget(status_panel, 1)
        action_layout.addWidget(self.btn_migrate)

        self.main_layout.addLayout(action_layout)

    def _set_status(self, text, state="normal"):
        self.lbl_status.setText(text)
        self.lbl_status.setProperty("state", state)
        self.lbl_status.style().unpolish(self.lbl_status)
        self.lbl_status.style().polish(self.lbl_status)

    def init_defaults(self):
        # Default TO path: Current Directory
        current_dir = os.getcwd()

        # Validate current dir using the same logic as the browse flow.
        # On startup, avoid modal warnings; just keep UI disabled if invalid.
        self.process_directory_path(
            current_dir,
            self.set_to_path,
            self.combo_to_ver,
            auto_select_max=True,
            show_warning=False,
        )
        
        self.check_ready()

    def set_to_path(self, path):
        if path:
            normalized = self._normalize_path_for_fs(path)
            display = self._format_path_for_ui(normalized)
            self.to_root_path = normalized
            self.lbl_to_path.setText(display)
            self.lbl_to_path.setToolTip(display)
            self.lbl_to_path.setEnabled(True)
        else:
            self.to_root_path = None
            # Use placeholder text for the empty state to keep visuals consistent.
            self.lbl_to_path.setText("")
            self.lbl_to_path.setToolTip("")
            self.lbl_to_path.setEnabled(False)

    def set_from_path(self, path):
        if path:
            normalized = self._normalize_path_for_fs(path)
            display = self._format_path_for_ui(normalized)
            self.from_root_path = normalized
            self.lbl_from_path.setText(display)
            self.lbl_from_path.setToolTip(display)
            self.lbl_from_path.setEnabled(True)
        else:
            self.from_root_path = None
            # Use placeholder text for the empty state to keep visuals consistent.
            self.lbl_from_path.setText("")
            self.lbl_from_path.setToolTip("")
            self.lbl_from_path.setEnabled(False)

    def select_from_directory(self):
        self.handle_directory_selection(
            "选择旧版本整合包文件夹",
            self.set_from_path,
            self.combo_from_ver,
            auto_select_max=False
        )

    def select_to_directory(self):
        self.handle_directory_selection(
            "选择新版本整合包文件夹",
            self.set_to_path,
            self.combo_to_ver,
            auto_select_max=True
        )

    def handle_directory_selection(self, title, set_path_func, combo_box, auto_select_max=False):
        dir_path = QFileDialog.getExistingDirectory(self, title)
        if not dir_path:
            return

        self.process_directory_path(
            dir_path,
            set_path_func,
            combo_box,
            auto_select_max=auto_select_max,
            show_warning=True,
        )

        self.check_ready()

    def process_directory_path(self, dir_path, set_path_func, combo_box, auto_select_max=False, show_warning=True):
        detected_root = None
        valid_versions = []
        target_version = None

        # Logic to detect if user selected root or versions folder
        # Case 1: Selected .minecraft/versions/X.X.X
        if os.path.basename(os.path.dirname(dir_path)) == 'versions' and \
           os.path.basename(os.path.dirname(os.path.dirname(dir_path))) == '.minecraft':
            # User selected a specific version folder
            target_version = os.path.basename(dir_path)
            detected_root = os.path.dirname(os.path.dirname(os.path.dirname(dir_path))) # Go up 3 levels
            valid_versions = get_versions(detected_root)

        # Case 2: Selected root (contains .minecraft)
        elif os.path.exists(os.path.join(dir_path, '.minecraft')):
            detected_root = dir_path
            valid_versions = get_versions(dir_path)

        # Fallback: Try to find versions anyway, maybe they selected .minecraft
        elif os.path.basename(dir_path) == '.minecraft':
            detected_root = os.path.dirname(dir_path)
            valid_versions = get_versions(detected_root)

        if detected_root and valid_versions:
            set_path_func(detected_root)
            combo_box.clear()
            combo_box.addItems(valid_versions)
            combo_box.setEnabled(True)
            combo_box.setPlaceholderText("选择游戏版本...")

            if target_version:
                combo_box.setCurrentText(target_version)
            elif auto_select_max:
                max_ver = find_max_version(valid_versions)
                if max_ver:
                    combo_box.setCurrentText(max_ver)
            else:
                combo_box.setCurrentIndex(-1)
        else:
            if show_warning:
                QMessageBox.warning(self, "错误", "你必须选择一个有效的整合包文件夹")
            set_path_func(None) # Reset
            combo_box.clear()
            combo_box.setEnabled(False)
            combo_box.setPlaceholderText("请先选择整合包...")

    def check_ready(self):
        is_ready = (
            hasattr(self, 'from_root_path') and self.from_root_path and
            hasattr(self, 'to_root_path') and self.to_root_path and
            self.combo_from_ver.currentText() and
            self.combo_to_ver.currentText()
        )
        self.btn_migrate.setEnabled(bool(is_ready))

        worker = getattr(self, "worker", None)
        if worker is not None and worker.isRunning():
            return

        if is_ready:
            self._set_status("已准备就绪，请确认版本后开始迁移", "ready")
        elif not getattr(self, "from_root_path", None):
            self._set_status("请选择旧版整合包和游戏版本")
        elif not self.combo_from_ver.currentText():
            self._set_status("请选择旧版整合包的游戏版本")
        elif not getattr(self, "to_root_path", None):
            self._set_status("请选择新版整合包和游戏版本")
        else:
            self._set_status("请选择新版整合包的游戏版本")

    def start_migration(self):
        from_ver = self.combo_from_ver.currentText()
        to_ver = self.combo_to_ver.currentText()
        
        from_full_path = os.path.join(self.from_root_path, '.minecraft', 'versions', from_ver)
        to_full_path = os.path.join(self.to_root_path, '.minecraft', 'versions', to_ver)

        from_full_path = self._normalize_path_for_fs(from_full_path)
        to_full_path = self._normalize_path_for_fs(to_full_path)

        if os.path.normpath(from_full_path) == os.path.normpath(to_full_path):
            QMessageBox.warning(self, "错误", "源文件夹和目标文件夹相同，请重新选择")
            return

        confirm = QMessageBox(self)
        confirm.setIcon(QMessageBox.Icon.Question)
        confirm.setWindowTitle("确认")
        confirm.setText("确认进行数据迁移工作？")
        confirm.setInformativeText(
            f"从：{self._format_path_for_ui(from_full_path)}\n\n"
            f"到：{self._format_path_for_ui(to_full_path)}\n\n"
            "新版整合包的数据将会被覆盖，请确认无误"
        )
        confirm.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel)
        confirm.setDefaultButton(QMessageBox.StandardButton.Cancel)

        # Override button text to avoid accidental clicks
        confirm.button(QMessageBox.StandardButton.Yes).setText("确认")
        confirm.button(QMessageBox.StandardButton.Cancel).setText("取消")

        if confirm.exec() != QMessageBox.StandardButton.Yes:
            return

        # Initialize logging only when migration is about to start.
        # Logs are written into: .minecraft\versions\<目标版本>\logs
        try:
            setup_logging(to_full_path)
        except Exception:
            # If logging setup fails, still allow migration to proceed.
            pass
        
        migration_rule_file = get_dependence_path(MIGRATION_RULE_FILE_NAME)

        self.worker = MigrationWorker(from_full_path, to_full_path, migration_rule_file)
        self.worker.progress_update.connect(self.update_progress)
        self.worker.finished.connect(self.migration_finished)

        self.progress_bar.setValue(0)
        self.progress_bar.show()
        self._set_status("正在准备迁移...")
        self.btn_migrate.setEnabled(False)
        self.from_group.setEnabled(False)
        self.to_group.setEnabled(False)
        self.worker.start()

    def update_progress(self, value, msg):
        self.progress_bar.setValue(value)
        msg = msg or ""
        self.lbl_status.setToolTip(msg)
        self._set_status(
            self.lbl_status.fontMetrics().elidedText(
                f"{value}%  ·  {msg}",
                Qt.TextElideMode.ElideMiddle,
                max(80, self.lbl_status.width()),
            )
        )

    def migration_finished(self, success, msg):
        self.from_group.setEnabled(True)
        self.to_group.setEnabled(True)
        self.btn_migrate.setEnabled(True)
        self.progress_bar.hide()

        if success:
            self._set_status("迁移完成", "ready")
            QMessageBox.information(self, "成功", f"{msg}\n\n请打开【可选Mod】文件夹选用自己想要的可选MOD")
            # Open Explorer
            try:
                os.startfile(self.to_root_path)
            except Exception:
                pass
        else:
            self._set_status("迁移失败，请查看错误信息", "error")
            QMessageBox.critical(self, "错误", msg)
