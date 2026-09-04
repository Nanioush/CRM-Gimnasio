from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QLineEdit, QPushButton,
    QMessageBox, QFrame
)
from app.ui.main_window import MainWindow
from app.ui.theme import APP_STYLE

class LoginWindow(QWidget):
    def __init__(self, db):
        super().__init__()
        self.db = db
        self.main_window = None
        self.setWindowTitle("Fight Gym CRM - Login")
        self.resize(430, 520)
        self.setStyleSheet(APP_STYLE)
        self.build_ui()

    def build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(45, 55, 45, 55)
        root.setSpacing(18)

        title = QLabel("FIGHT GYM CRM")
        title.setObjectName("title")
        title.setAlignment(Qt.AlignCenter)

        sub = QLabel("Gestión integral del gimnasio")
        sub.setAlignment(Qt.AlignCenter)
        sub.setStyleSheet("color:#9aa4b2; font-size:14px;")

        card = QFrame()
        card.setObjectName("card")
        form = QVBoxLayout(card)
        form.setContentsMargins(28, 28, 28, 28)
        form.setSpacing(12)

        self.user = QLineEdit()
        self.user.setPlaceholderText("Usuario")
        self.password = QLineEdit()
        self.password.setPlaceholderText("Contraseña")
        self.password.setEchoMode(QLineEdit.Password)

        btn = QPushButton("Entrar")
        btn.setObjectName("primary")
        btn.clicked.connect(self.login)
        self.user.returnPressed.connect(self.login)
        self.password.returnPressed.connect(self.login)

        hint = QLabel("Demo inicial: admin / admin123")
        hint.setStyleSheet("color:#7f8996;")
        hint.setAlignment(Qt.AlignCenter)

        form.addWidget(QLabel("Usuario"))
        form.addWidget(self.user)
        form.addWidget(QLabel("Contraseña"))
        form.addWidget(self.password)
        form.addSpacing(6)
        form.addWidget(btn)
        form.addWidget(hint)

        root.addStretch()
        root.addWidget(title)
        root.addWidget(sub)
        root.addSpacing(12)
        root.addWidget(card)
        root.addStretch()

    def login(self):
        username = self.user.text().strip()
        password = self.password.text().strip()

        try:
            user = self.db.authenticate(username, password)
        except Exception as exc:
            QMessageBox.critical(
                self,
                "Error de base de datos",
                f"No se pudo comprobar el usuario.\n\n{type(exc).__name__}: {exc}"
            )
            return

        if not user:
            QMessageBox.warning(
                self,
                "Acceso denegado",
                "Usuario o contraseña incorrectos.\n\nPrueba: admin / admin123"
            )
            return

        try:
            self.main_window = MainWindow(self.db)
            self.main_window.show()
            self.hide()
        except Exception as exc:
            import traceback
            details = traceback.format_exc()
            try:
                from pathlib import Path
                (Path.cwd() / "error_dashboard.txt").write_text(details, encoding="utf-8")
            except Exception:
                pass
            QMessageBox.critical(
                self,
                "Error al abrir el CRM",
                f"El usuario es correcto, pero falló la apertura del dashboard.\n\n"
                f"{type(exc).__name__}: {exc}\n\n"
                "Se ha creado error_dashboard.txt."
            )
