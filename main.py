import sys
import os
from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QIcon
from src.ui import MainWindow
from src.utils import setup_logging, get_resource_path

def main():
    setup_logging()
    
    app = QApplication(sys.argv)

    icon_path = get_resource_path('assets', 'icon.ico')
    if os.path.exists(icon_path):
        app.setWindowIcon(QIcon(icon_path))
    
    window = MainWindow()
    window.show()
    
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
