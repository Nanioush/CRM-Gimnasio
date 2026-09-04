from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, QFrame,
    QPushButton, QLabel, QStackedWidget
)
from app.ui.theme import APP_STYLE
from app.ui.pages import (
    DashboardPage, StudentsPage, TeachersPage, ActivitiesPage,
    AttendancePage, PaymentsPage, InvoicesPage, StatisticsPage
)

class MainWindow(QMainWindow):
    def __init__(self, db):
        super().__init__()
        self.db = db
        self.setWindowTitle("Fight Gym CRM")
        self.resize(1280, 760)
        self.setMinimumSize(1050, 650)
        self.setStyleSheet(APP_STYLE)
        self.build_ui()

    def build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        layout = QHBoxLayout(central)
        layout.setContentsMargins(0,0,0,0)
        layout.setSpacing(0)

        sidebar = QFrame()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(220)
        side = QVBoxLayout(sidebar)
        side.setContentsMargins(18, 22, 18, 22)
        side.setSpacing(9)

        brand = QLabel("FIGHT\nGYM CRM")
        brand.setStyleSheet("font-size:22px; font-weight:900;")
        side.addWidget(brand)
        side.addSpacing(18)

        self.stack = QStackedWidget()

        self.pages = [
            ("Dashboard", DashboardPage(self.db)),
            ("Alumnos", StudentsPage(self.db)),
            ("Profesores", TeachersPage(self.db)),
            ("Actividades", ActivitiesPage(self.db)),
            ("Asistencias", AttendancePage(self.db)),
            ("Pagos", PaymentsPage(self.db)),
            ("Facturación", InvoicesPage(self.db)),
            ("Estadísticas", StatisticsPage(self.db)),
        ]

        for i, (name, page) in enumerate(self.pages):
            btn = QPushButton(name)
            btn.clicked.connect(lambda checked=False, ix=i: self.set_page(ix))
            side.addWidget(btn)
            self.stack.addWidget(page)

        side.addStretch()
        version = QLabel("Proyecto prácticas")
        version.setStyleSheet("color:#6f7985;")
        side.addWidget(version)

        layout.addWidget(sidebar)
        layout.addWidget(self.stack, 1)

    def set_page(self, index):
        self.stack.setCurrentIndex(index)
        page = self.stack.currentWidget()
        if hasattr(page, "refresh"):
            page.refresh()
