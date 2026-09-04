import sys
from PySide6.QtWidgets import QApplication
from app.data.database import Database
from app.ui.login import LoginWindow
from app.services.business import GymService
from app.config.settings import APP_NAME

def main():
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    db = Database()
    db.initialize()
    GymService(db).ensure_monthly_dues()

    login = LoginWindow(db)
    login.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
