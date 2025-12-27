import os
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
    QPushButton, QComboBox, QFileDialog, QFrame, QMessageBox, 
    QProgressBar, QSpacerItem, QSizePolicy, QGroupBox, QLineEdit, QTextEdit
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont, QIcon, QPixmap, QTextOption

from src.data_migration import MigrationWorker
from src.utils import get_versions, find_max_version, get_resource_path, get_dependence_path, setup_logging
from src.constants import APP_VERSION, MIGRATION_RULE_FILE_NAME

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"DC整合包数据迁移工具 {APP_VERSION}")

        icon_path = get_resource_path('assets', 'icon.ico')
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))

        self.setWindowFlag(Qt.WindowType.WindowMaximizeButtonHint, False)
        
        # Main Widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        self.main_layout = QVBoxLayout(central_widget)
        self.main_layout.setContentsMargins(12, 12, 12, 12)

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

        # Prevent long status text from stretching layout
        self._status_elide_width = (
            self.from_group.width() + self.arrow_label.width() + self.to_group.width()
        )

        # Disable resizing
        self.adjustSize()
        self.setFixedSize(self.size())

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
        header_layout = QVBoxLayout()
        header_layout.setSpacing(2)
        
        desc = QLabel("帮你快速迁移旧版DC整合包数据（存档/设置/地图等）到新版中。")
        tutorial = QLabel("<b>使用方法：</b>1. 先安装新版DC整合包 &nbsp; 2. 使用本工具迁移旧版数据到新版 &nbsp; 3. 自行添加可选MOD")
        
        header_layout.addWidget(desc)
        header_layout.addWidget(tutorial)
        
        self.main_layout.addLayout(header_layout)
        
        # Separator
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setFrameShadow(QFrame.Shadow.Sunken)
        self.main_layout.addWidget(line)

    def setup_footer(self):
        footer_layout = QHBoxLayout()
        footer_layout.setContentsMargins(0, 10, 0, 0)

        info_text = (
            "项目开源地址："
            "<a href='https://github.com/DreamCity-DC/DC-Modpack-Data-Migration' "
            "style='color:blue;text-decoration:none;'>"
            "https://github.com/DreamCity-DC/DC-Modpack-Data-Migration"
            "</a>"
        )
        info = QLabel(info_text)
        info.setOpenExternalLinks(True)
        info.setStyleSheet("color: gray;")

        footer_layout.addWidget(info)
        footer_layout.addStretch()
        self.main_layout.addLayout(footer_layout)

    def setup_selection_area(self):
        selection_layout = QHBoxLayout()
        selection_layout.setAlignment(Qt.AlignmentFlag.AlignCenter) # Center everything
        
        # --- Left Group (Source) ---
        self.lbl_from_path = QTextEdit()
        self.combo_from_ver = QComboBox()
        
        self.from_group = self.create_part_group(
            "旧版本 (Source)", 
            self.lbl_from_path, 
            self.select_from_directory, 
            self.combo_from_ver
        )
        
        # --- Right Group (Target) ---
        self.lbl_to_path = QTextEdit()
        self.combo_to_ver = QComboBox()
        
        self.to_group = self.create_part_group(
            "新版本 (Target)", 
            self.lbl_to_path, 
            self.select_to_directory, 
            self.combo_to_ver
        )

        # Arrow (in layout, avoids manual repositioning)
        self.arrow_label = QLabel("➜")
        font = self.arrow_label.font()
        font.setPointSize(20)
        font.setBold(True)
        self.arrow_label.setFont(font)
        self.arrow_label.setStyleSheet("color: #666; background: transparent;")
        self.arrow_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.arrow_label.setFixedWidth(25)

        selection_layout.addWidget(self.from_group)
        selection_layout.addWidget(self.arrow_label)
        selection_layout.addWidget(self.to_group)
        
        self.main_layout.addLayout(selection_layout)

    def create_part_group(self, title, path_widget, browse_func, combo_box):
        group = QGroupBox(title)
        group.setFixedWidth(320) 
        
        layout = QVBoxLayout(group)
        
        # Row 1: Header + Browse Button
        header_layout = QHBoxLayout()
        lbl_title = QLabel("整合包文件夹:")
        lbl_title.setStyleSheet("font-weight: bold; color: #444;")
        
        btn_browse = QPushButton("选择...")
        btn_browse.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_browse.setFixedWidth(60)
        btn_browse.setFixedHeight(24)
        btn_browse.clicked.connect(browse_func)
        
        header_layout.addWidget(lbl_title)
        header_layout.addStretch()
        header_layout.addWidget(btn_browse)
        
        # Row 2: Path Display (QTextEdit)
        path_widget.setPlaceholderText("未选择路径")
        path_widget.setReadOnly(True)
        path_widget.setFrameStyle(QFrame.Shape.NoFrame) # No border
        path_widget.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        path_widget.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        # Wrap anywhere to prevent ugly breaks at slashes
        path_widget.setWordWrapMode(QTextOption.WrapMode.WrapAnywhere)
        
        path_widget.setStyleSheet("""
            QTextEdit {
                background: transparent;
                color: #333;
                font-family: "Segoe UI", "Microsoft YaHei";
                font-size: 12px;
            }
            QTextEdit:disabled {
                color: #666;
            }
        """)
        path_widget.setFixedHeight(45) 
        # Keep path display disabled until a valid directory is selected.
        path_widget.setEnabled(False)
        
        # Row 3: Version Header
        lbl_ver = QLabel("游戏版本:")
        lbl_ver.setStyleSheet("font-weight: bold; color: #444;")
        
        # Row 4: ComboBox
        combo_box.setPlaceholderText("请先选择路径...")
        combo_box.setEnabled(False)
        combo_box.setFixedHeight(28)
        
        layout.addLayout(header_layout)
        layout.addWidget(path_widget)
        layout.addWidget(lbl_ver)
        layout.addWidget(combo_box)
        layout.addStretch() 
        
        return group

    def setup_action_area(self):
        action_layout = QVBoxLayout()
        action_layout.setSpacing(5)
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setFixedHeight(15) # Slim progress bar
        self.progress_bar.hide()
        
        self.lbl_status = QLabel("")
        self.lbl_status.setAlignment(Qt.AlignmentFlag.AlignLeft)
        self.lbl_status.setTextFormat(Qt.TextFormat.PlainText)
        self.lbl_status.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.lbl_status.setMinimumWidth(0)
        font = self.lbl_status.font()
        font.setPointSize(8)
        self.lbl_status.setFont(font)
        self.lbl_status.hide()
        
        self.btn_migrate = QPushButton("开始迁移数据")
        self.btn_migrate.setMinimumHeight(30)
        self.btn_migrate.setEnabled(False)
        self.btn_migrate.clicked.connect(self.start_migration)
        
        action_layout.addWidget(self.progress_bar)
        action_layout.addWidget(self.lbl_status)
        action_layout.addWidget(self.btn_migrate)
        
        self.main_layout.addLayout(action_layout)

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
            "选择旧版本整合包目录",
            self.set_from_path,
            self.combo_from_ver,
            auto_select_max=False
        )

    def select_to_directory(self):
        self.handle_directory_selection(
            "选择新版本整合包目录",
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
                QMessageBox.warning(self, "错误", "你必须选择一个有效的整合包路径")
            set_path_func(None) # Reset
            combo_box.clear()
            combo_box.setEnabled(False)
            combo_box.setPlaceholderText("请先选择路径...")

    def check_ready(self):
        is_ready = (
            hasattr(self, 'from_root_path') and self.from_root_path and
            hasattr(self, 'to_root_path') and self.to_root_path and
            self.combo_from_ver.currentText() and
            self.combo_to_ver.currentText()
        )
        self.btn_migrate.setEnabled(bool(is_ready))

    def start_migration(self):
        from_ver = self.combo_from_ver.currentText()
        to_ver = self.combo_to_ver.currentText()
        
        from_full_path = os.path.join(self.from_root_path, '.minecraft', 'versions', from_ver)
        to_full_path = os.path.join(self.to_root_path, '.minecraft', 'versions', to_ver)

        from_full_path = self._normalize_path_for_fs(from_full_path)
        to_full_path = self._normalize_path_for_fs(to_full_path)

        if os.path.normpath(from_full_path) == os.path.normpath(to_full_path):
            QMessageBox.warning(self, "错误", "源目录和目标目录相同，请重新选择")
            return

        confirm = QMessageBox(self)
        confirm.setIcon(QMessageBox.Icon.Question)
        confirm.setWindowTitle("确认")
        confirm.setText("确认进行数据迁移工作？")
        confirm.setInformativeText(
            f"从：{self._format_path_for_ui(from_full_path)}\n\n"
            f"到：{self._format_path_for_ui(to_full_path)}"
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
        self.lbl_status.setText("")
        self.lbl_status.show()
        self.btn_migrate.setEnabled(False)
        self.worker.start()

    def update_progress(self, value, msg):
        self.progress_bar.setValue(value)
        msg = msg or ""
        self.lbl_status.setToolTip(msg)
        self.lbl_status.setText(
            self.lbl_status.fontMetrics().elidedText(
                msg,
                Qt.TextElideMode.ElideMiddle,
                self._status_elide_width,
            )
        )
        if not self.lbl_status.isVisible():
            self.lbl_status.show()

    def migration_finished(self, success, msg):
        self.btn_migrate.setEnabled(True)
        self.progress_bar.hide()
        self.lbl_status.setText("")
        self.lbl_status.hide()
        
        if success:
            QMessageBox.information(self, "成功", f"{msg}\n\n请打开【可选Mod】文件夹选用自己想要的可选MOD")
            # Open Explorer
            try:
                os.startfile(self.to_root_path)
            except Exception:
                pass
        else:
            QMessageBox.critical(self, "错误", msg)

