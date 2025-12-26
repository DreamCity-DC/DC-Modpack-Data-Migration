import sys
import os
from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QIcon
from src.ui import MainWindow
from src.utils import get_resource_path, setup_null_logging

def main():
    # Do not emit logs before the user starts migration.
    setup_null_logging()

    app = QApplication(sys.argv)

    icon_path = get_resource_path('assets', 'icon.ico')
    if os.path.exists(icon_path):
        app.setWindowIcon(QIcon(icon_path))
    
    window = MainWindow()
    window.show()
    
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
