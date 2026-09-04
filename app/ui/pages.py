from datetime import date
import csv

from PySide6.QtCore import QDate
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QFrame,
    QPushButton, QLineEdit, QComboBox, QTableWidget, QTableWidgetItem,
    QMessageBox, QDialog, QFormLayout, QDateEdit, QDoubleSpinBox,
    QSpinBox, QFileDialog, QListWidget, QAbstractItemView
)
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure

from app.services.business import GymService, plan_price, required_activity_count
from app.reports.reports import Reports
from app.config.settings import FEES


def page_header(title, subtitle=""):
    box = QVBoxLayout()
    title_label = QLabel(title)
    title_label.setObjectName("title")
    box.addWidget(title_label)
    if subtitle:
        subtitle_label = QLabel(subtitle)
        subtitle_label.setStyleSheet("color:#8d98a6;")
        box.addWidget(subtitle_label)
    return box


def selected_id(table):
    row = table.currentRow()
    if row < 0:
        return None
    item = table.item(row, 0)
    return int(item.text()) if item else None


def make_table(headers):
    table = QTableWidget(0, len(headers))
    table.setHorizontalHeaderLabels(headers)
    table.setAlternatingRowColors(True)
    table.setSelectionBehavior(QTableWidget.SelectRows)
    table.setEditTriggers(QTableWidget.NoEditTriggers)
    table.horizontalHeader().setStretchLastSection(True)
    return table


class MetricCard(QFrame):
    def __init__(self, title, value="0"):
        super().__init__()
        self.setObjectName("card")
        layout = QVBoxLayout(self)
        label = QLabel(title)
        label.setStyleSheet("color:#8d98a6;")
        self.value = QLabel(str(value))
        self.value.setObjectName("metric")
        layout.addWidget(label)
        layout.addWidget(self.value)


class DashboardPage(QWidget):
    def __init__(self, db):
        super().__init__()
        self.db = db

        root = QVBoxLayout(self)
        root.setContentsMargins(28, 26, 28, 26)
        root.setSpacing(18)
        root.addLayout(page_header("Dashboard", "Resumen general del gimnasio"))

        grid = QGridLayout()
        self.c_students = MetricCard("Alumnos activos")
        self.c_pending = MetricCard("Pagos pendientes")
        self.c_income = MetricCard("Ingresos mensuales")
        self.c_new = MetricCard("Nuevos alumnos")

        for index, card in enumerate(
            [self.c_students, self.c_pending, self.c_income, self.c_new]
        ):
            grid.addWidget(card, 0, index)

        root.addLayout(grid)
        root.addWidget(QLabel("Actividades más utilizadas"))

        self.activity_table = make_table(["Actividad", "Alumnos"])
        root.addWidget(self.activity_table, 1)
        self.refresh()

    def refresh(self):
        data = GymService(self.db).dashboard_data()

        self.c_students.value.setText(str(data["students"]))
        self.c_pending.value.setText(str(data["pending"]))
        self.c_income.value.setText(f'{data["income"]:.2f} €')
        self.c_new.value.setText(str(data["new_students"]))

        rows = data["activities"][:8]
        self.activity_table.setRowCount(len(rows))
        for row_index, row in enumerate(rows):
            self.activity_table.setItem(
                row_index, 0, QTableWidgetItem(str(row["activity"]))
            )
            self.activity_table.setItem(
                row_index, 1, QTableWidgetItem(str(row["total"]))
            )


class StudentsPage(QWidget):
    def __init__(self, db):
        super().__init__()
        self.db = db

        root = QVBoxLayout(self)
        root.setContentsMargins(28, 26, 28, 26)
        root.addLayout(page_header("Alumnos", "Altas, bajas y consulta de alumnos"))

        top = QHBoxLayout()
        self.search = QLineEdit()
        self.search.setPlaceholderText("Buscar por nombre, apellido o teléfono...")
        self.search.textChanged.connect(self.refresh)

        add = QPushButton("Nuevo alumno")
        add.setObjectName("primary")
        add.clicked.connect(self.add_student)

        edit = QPushButton("Editar")
        edit.clicked.connect(self.edit_student)

        deactivate = QPushButton("Dar de baja")
        deactivate.setObjectName("danger")
        deactivate.clicked.connect(self.deactivate_student)

        reactivate = QPushButton("Reactivar")
        reactivate.clicked.connect(self.reactivate_student)

        top.addWidget(self.search, 1)
        top.addWidget(add)
        top.addWidget(edit)
        top.addWidget(deactivate)
        top.addWidget(reactivate)
        root.addLayout(top)

        self.table = make_table(
            ["ID", "Nombre", "Apellidos", "Teléfono", "Plan",
             "Actividades", "Alta", "Estado"]
        )
        root.addWidget(self.table, 1)
        self.refresh()

    def refresh(self):
        query = self.search.text().strip() if hasattr(self, "search") else ""
        like = f"%{query}%"

        rows = self.db.fetchall(
            """SELECT s.*,
                      COALESCE((
                          SELECT GROUP_CONCAT(name, ' / ')
                          FROM (
                              SELECT a.name name
                              FROM student_activities sa
                              JOIN activities a ON a.id=sa.activity_id
                              WHERE sa.student_id=s.id
                              ORDER BY a.name
                          )
                      ), '') activities
               FROM students s
               WHERE s.name LIKE ? OR s.surname LIKE ? OR s.phone LIKE ?
               ORDER BY s.id DESC""",
            (like, like, like)
        )

        self.table.setRowCount(len(rows))
        for row_index, row in enumerate(rows):
            values = [
                row["id"], row["name"], row["surname"], row["phone"] or "",
                row["plan"], row["activities"], row["join_date"],
                "Activo" if row["active"] else "Baja"
            ]
            for column, value in enumerate(values):
                self.table.setItem(
                    row_index, column, QTableWidgetItem(str(value))
                )

    def add_student(self):
        dialog = StudentDialog(self.db, parent=self)
        if dialog.exec():
            self.refresh()

    def edit_student(self):
        student_id = selected_id(self.table)
        if student_id is None:
            QMessageBox.information(self, "Alumno", "Selecciona un alumno.")
            return
        dialog = StudentDialog(self.db, student_id=student_id, parent=self)
        if dialog.exec():
            self.refresh()

    def deactivate_student(self):
        student_id = selected_id(self.table)
        if student_id is None:
            QMessageBox.information(self, "Alumno", "Selecciona un alumno.")
            return
        self.db.execute("UPDATE students SET active=0 WHERE id=?", (student_id,))
        self.refresh()

    def reactivate_student(self):
        student_id = selected_id(self.table)
        if student_id is None:
            QMessageBox.information(self, "Alumno", "Selecciona un alumno.")
            return
        self.db.execute("UPDATE students SET active=1 WHERE id=?", (student_id,))
        GymService(self.db).ensure_monthly_dues()
        self.refresh()


class StudentDialog(QDialog):
    def __init__(self, db, student_id=None, parent=None):
        super().__init__(parent)
        self.db = db
        self.service = GymService(db)
        self.student_id = student_id

        self.setWindowTitle("Editar alumno" if student_id else "Nuevo alumno")
        self.resize(450, 570)

        self.form = QFormLayout(self)

        self.name = QLineEdit()
        self.surname = QLineEdit()
        self.phone = QLineEdit()
        self.email = QLineEdit()

        self.birth = QDateEdit(QDate.currentDate())
        self.birth.setCalendarPopup(True)

        self.plan = QComboBox()
        self.plan.addItems(FEES.keys())
        self.plan.currentTextChanged.connect(self.update_activity_mode)

        self.activity1 = QComboBox()
        self.activity2 = QComboBox()
        self.fill_activity_combo(self.activity1)
        self.fill_activity_combo(self.activity2)

        self.join = QDateEdit(QDate.currentDate())
        self.join.setCalendarPopup(True)

        for label, widget in [
            ("Nombre", self.name),
            ("Apellidos", self.surname),
            ("Teléfono", self.phone),
            ("Email", self.email),
            ("Fecha nacimiento", self.birth),
            ("Cuota", self.plan),
            ("Actividad 1", self.activity1),
            ("Actividad 2", self.activity2),
            ("Fecha alta", self.join),
        ]:
            self.form.addRow(label, widget)

        save_button = QPushButton("Guardar alumno")
        save_button.setObjectName("primary")
        save_button.clicked.connect(self.save)
        self.form.addRow(save_button)

        if student_id:
            self.load_student()
        else:
            self.update_activity_mode()

    def fill_activity_combo(self, combo):
        combo.clear()
        combo.addItem("Selecciona una actividad", None)
        for row in self.db.fetchall("SELECT id,name FROM activities ORDER BY name"):
            combo.addItem(row["name"], row["id"])

    def update_activity_mode(self):
        two_activities = required_activity_count(self.plan.currentText()) == 2
        self.activity2.setVisible(two_activities)
        label = self.form.labelForField(self.activity2)
        if label:
            label.setVisible(two_activities)
        if not two_activities:
            self.activity2.setCurrentIndex(0)

    def load_student(self):
        row = self.db.fetchone(
            "SELECT * FROM students WHERE id=?",
            (self.student_id,)
        )
        if not row:
            return

        self.name.setText(row["name"] or "")
        self.surname.setText(row["surname"] or "")
        self.phone.setText(row["phone"] or "")
        self.email.setText(row["email"] or "")

        if row["birth_date"]:
            self.birth.setDate(QDate.fromString(row["birth_date"], "yyyy-MM-dd"))

        plan_index = self.plan.findText(row["plan"])
        self.plan.setCurrentIndex(plan_index if plan_index >= 0 else 0)

        if row["join_date"]:
            self.join.setDate(QDate.fromString(row["join_date"], "yyyy-MM-dd"))

        activity_ids = self.service.student_activity_ids(self.student_id)
        if activity_ids:
            index = self.activity1.findData(activity_ids[0])
            if index >= 0:
                self.activity1.setCurrentIndex(index)

        if len(activity_ids) > 1:
            index = self.activity2.findData(activity_ids[1])
            if index >= 0:
                self.activity2.setCurrentIndex(index)

        self.update_activity_mode()

    def save(self):
        if not self.name.text().strip() or not self.surname.text().strip():
            QMessageBox.warning(
                self, "Faltan datos", "Nombre y apellidos son obligatorios."
            )
            return

        expected = required_activity_count(self.plan.currentText())
        activity_ids = [self.activity1.currentData()]
        if expected == 2:
            activity_ids.append(self.activity2.currentData())

        if any(activity_id is None for activity_id in activity_ids):
            QMessageBox.warning(
                self,
                "Actividades",
                f"Esta cuota necesita {expected} actividad"
                + ("es." if expected == 2 else ".")
            )
            return

        if len(set(activity_ids)) != len(activity_ids):
            QMessageBox.warning(
                self,
                "Actividades",
                "Las dos actividades deben ser diferentes."
            )
            return

        primary_name = self.activity1.currentText()
        values = (
            self.name.text().strip(),
            self.surname.text().strip(),
            self.phone.text().strip(),
            self.email.text().strip(),
            self.birth.date().toString("yyyy-MM-dd"),
            self.plan.currentText(),
            primary_name,
            self.join.date().toString("yyyy-MM-dd"),
        )

        if self.student_id:
            self.db.execute(
                """UPDATE students
                   SET name=?,surname=?,phone=?,email=?,birth_date=?,
                       plan=?,activity=?,join_date=?
                   WHERE id=?""",
                values + (self.student_id,)
            )
            student_id = self.student_id
            self.service.update_pending_due_for_plan(
                student_id, self.plan.currentText()
            )
        else:
            student_id = self.db.execute(
                """INSERT INTO students(
                       name,surname,phone,email,birth_date,plan,activity,join_date
                   ) VALUES(?,?,?,?,?,?,?,?)""",
                values
            )
            self.service.create_due_for_student(
                student_id,
                self.plan.currentText(),
                self.join.date().toString("yyyy-MM-dd")
            )

        self.service.set_student_activities(student_id, activity_ids)
        self.accept()


class TeachersPage(QWidget):
    def __init__(self, db):
        super().__init__()
        self.db = db

        root = QVBoxLayout(self)
        root.setContentsMargins(28, 26, 28, 26)
        root.addLayout(page_header("Profesores", "Gestión del equipo docente"))

        top = QHBoxLayout()
        add = QPushButton("Nuevo profesor")
        add.setObjectName("primary")
        add.clicked.connect(self.add_teacher)

        edit = QPushButton("Editar")
        edit.clicked.connect(self.edit_teacher)

        delete = QPushButton("Eliminar")
        delete.setObjectName("danger")
        delete.clicked.connect(self.delete_teacher)

        top.addStretch()
        top.addWidget(add)
        top.addWidget(edit)
        top.addWidget(delete)
        root.addLayout(top)

        self.table = make_table(
            ["ID", "Nombre", "Apellidos", "Teléfono", "Email",
             "Especialidad", "Actividades"]
        )
        root.addWidget(self.table, 1)
        self.refresh()

    def refresh(self):
        rows = self.db.fetchall(
            """SELECT t.*,
                      COALESCE((
                          SELECT GROUP_CONCAT(name, ' / ')
                          FROM (
                              SELECT a.name name
                              FROM activities a
                              WHERE a.teacher_id=t.id
                              ORDER BY a.name
                          )
                      ), '') activities
               FROM teachers t
               ORDER BY t.id DESC"""
        )

        self.table.setRowCount(len(rows))
        for row_index, row in enumerate(rows):
            values = [
                row["id"], row["name"], row["surname"], row["phone"] or "",
                row["email"] or "", row["specialty"] or "", row["activities"]
            ]
            for column, value in enumerate(values):
                self.table.setItem(
                    row_index, column, QTableWidgetItem(str(value))
                )

    def add_teacher(self):
        dialog = TeacherDialog(self.db, parent=self)
        if dialog.exec():
            self.refresh()

    def edit_teacher(self):
        teacher_id = selected_id(self.table)
        if teacher_id is None:
            QMessageBox.information(self, "Profesor", "Selecciona un profesor.")
            return

        dialog = TeacherDialog(
            self.db, teacher_id=teacher_id, parent=self
        )
        if dialog.exec():
            self.refresh()

    def delete_teacher(self):
        teacher_id = selected_id(self.table)
        if teacher_id is None:
            QMessageBox.information(self, "Profesor", "Selecciona un profesor.")
            return

        self.db.execute(
            "UPDATE activities SET teacher_id=NULL WHERE teacher_id=?",
            (teacher_id,)
        )
        self.db.execute("DELETE FROM teachers WHERE id=?", (teacher_id,))
        self.refresh()


class TeacherDialog(QDialog):
    def __init__(self, db, teacher_id=None, parent=None):
        super().__init__(parent)
        self.db = db
        self.teacher_id = teacher_id

        self.setWindowTitle(
            "Editar profesor" if teacher_id else "Nuevo profesor"
        )
        self.resize(440, 520)

        form = QFormLayout(self)

        self.name = QLineEdit()
        self.surname = QLineEdit()
        self.phone = QLineEdit()
        self.email = QLineEdit()
        self.specialty = QLineEdit()

        self.activities = QListWidget()
        self.activities.setSelectionMode(QAbstractItemView.MultiSelection)
        self.activities.setMinimumHeight(150)

        for row in self.db.fetchall("SELECT id,name FROM activities ORDER BY name"):
            self.activities.addItem(row["name"])
            item = self.activities.item(self.activities.count() - 1)
            item.setData(256, row["id"])

        for label, widget in [
            ("Nombre", self.name),
            ("Apellidos", self.surname),
            ("Teléfono", self.phone),
            ("Email", self.email),
            ("Especialidad", self.specialty),
            ("Actividades", self.activities),
        ]:
            form.addRow(label, widget)

        save = QPushButton("Guardar")
        save.setObjectName("primary")
        save.clicked.connect(self.save)
        form.addRow(save)

        if teacher_id:
            self.load_teacher()

    def load_teacher(self):
        row = self.db.fetchone(
            "SELECT * FROM teachers WHERE id=?",
            (self.teacher_id,)
        )
        if not row:
            return

        self.name.setText(row["name"] or "")
        self.surname.setText(row["surname"] or "")
        self.phone.setText(row["phone"] or "")
        self.email.setText(row["email"] or "")
        self.specialty.setText(row["specialty"] or "")

        assigned = {
            r["id"] for r in self.db.fetchall(
                "SELECT id FROM activities WHERE teacher_id=?",
                (self.teacher_id,)
            )
        }

        for index in range(self.activities.count()):
            item = self.activities.item(index)
            item.setSelected(item.data(256) in assigned)

    def save(self):
        if not self.name.text().strip() or not self.surname.text().strip():
            QMessageBox.warning(
                self, "Faltan datos", "Nombre y apellidos son obligatorios."
            )
            return

        values = (
            self.name.text().strip(),
            self.surname.text().strip(),
            self.phone.text().strip(),
            self.email.text().strip(),
            self.specialty.text().strip(),
        )

        if self.teacher_id:
            teacher_id = self.teacher_id
            self.db.execute(
                """UPDATE teachers
                   SET name=?,surname=?,phone=?,email=?,specialty=?
                   WHERE id=?""",
                values + (teacher_id,)
            )
        else:
            teacher_id = self.db.execute(
                """INSERT INTO teachers(
                       name,surname,phone,email,specialty
                   ) VALUES(?,?,?,?,?)""",
                values
            )

        selected_activity_ids = [
            item.data(256) for item in self.activities.selectedItems()
        ]

        self.db.execute(
            "UPDATE activities SET teacher_id=NULL WHERE teacher_id=?",
            (teacher_id,)
        )
        for activity_id in selected_activity_ids:
            self.db.execute(
                "UPDATE activities SET teacher_id=? WHERE id=?",
                (teacher_id, activity_id)
            )

        self.accept()


class ActivitiesPage(QWidget):
    def __init__(self, db):
        super().__init__()
        self.db = db

        root = QVBoxLayout(self)
        root.setContentsMargins(28, 26, 28, 26)
        root.addLayout(
            page_header(
                "Actividades",
                "Gestión de disciplinas, profesor, horario y aforo"
            )
        )

        top = QHBoxLayout()
        add = QPushButton("Nueva actividad")
        add.setObjectName("primary")
        add.clicked.connect(self.add_activity)

        edit = QPushButton("Editar")
        edit.clicked.connect(self.edit_activity)

        top.addStretch()
        top.addWidget(add)
        top.addWidget(edit)
        root.addLayout(top)

        self.table = make_table(
            ["ID", "Actividad", "Profesor", "Horario", "Aforo"]
        )
        root.addWidget(self.table, 1)
        self.refresh()

    def refresh(self):
        rows = self.db.fetchall(
            """SELECT a.id,a.name,
                      COALESCE(t.name || ' ' || t.surname,'Sin asignar') teacher,
                      COALESCE(a.schedule,'') schedule,
                      a.capacity
               FROM activities a
               LEFT JOIN teachers t ON t.id=a.teacher_id
               ORDER BY a.name"""
        )

        self.table.setRowCount(len(rows))
        for row_index, row in enumerate(rows):
            values = [
                row["id"], row["name"], row["teacher"],
                row["schedule"], row["capacity"]
            ]
            for column, value in enumerate(values):
                self.table.setItem(
                    row_index, column, QTableWidgetItem(str(value))
                )

    def add_activity(self):
        dialog = ActivityDialog(self.db, parent=self)
        if dialog.exec():
            self.refresh()

    def edit_activity(self):
        activity_id = selected_id(self.table)
        if activity_id is None:
            QMessageBox.information(
                self, "Actividad", "Selecciona una actividad."
            )
            return

        dialog = ActivityDialog(
            self.db, activity_id=activity_id, parent=self
        )
        if dialog.exec():
            self.refresh()


class ActivityDialog(QDialog):
    def __init__(self, db, activity_id=None, parent=None):
        super().__init__(parent)
        self.db = db
        self.activity_id = activity_id

        self.setWindowTitle(
            "Editar actividad" if activity_id else "Nueva actividad"
        )

        form = QFormLayout(self)

        self.name = QLineEdit()
        self.teacher = QComboBox()
        self.teacher.addItem("Sin asignar", None)

        for row in db.fetchall(
            "SELECT id,name,surname FROM teachers ORDER BY name,surname"
        ):
            self.teacher.addItem(
                f"{row['name']} {row['surname']}", row["id"]
            )

        self.schedule = QLineEdit()
        self.schedule.setPlaceholderText("Ej: L-X-V 18:00")

        self.capacity = QSpinBox()
        self.capacity.setRange(1, 500)
        self.capacity.setValue(20)

        for label, widget in [
            ("Nombre", self.name),
            ("Profesor", self.teacher),
            ("Horario", self.schedule),
            ("Aforo", self.capacity),
        ]:
            form.addRow(label, widget)

        save = QPushButton("Guardar")
        save.setObjectName("primary")
        save.clicked.connect(self.save)
        form.addRow(save)

        if activity_id:
            self.load_activity()

    def load_activity(self):
        row = self.db.fetchone(
            "SELECT * FROM activities WHERE id=?",
            (self.activity_id,)
        )
        if not row:
            return

        self.name.setText(row["name"] or "")
        self.schedule.setText(row["schedule"] or "")
        self.capacity.setValue(row["capacity"] or 20)

        index = self.teacher.findData(row["teacher_id"])
        self.teacher.setCurrentIndex(index if index >= 0 else 0)

    def save(self):
        if not self.name.text().strip():
            QMessageBox.warning(
                self, "Falta nombre", "La actividad necesita un nombre."
            )
            return

        values = (
            self.name.text().strip(),
            self.teacher.currentData(),
            self.schedule.text().strip(),
            self.capacity.value(),
        )

        try:
            if self.activity_id:
                self.db.execute(
                    """UPDATE activities
                       SET name=?,teacher_id=?,schedule=?,capacity=?
                       WHERE id=?""",
                    values + (self.activity_id,)
                )
            else:
                self.db.execute(
                    """INSERT INTO activities(
                           name,teacher_id,schedule,capacity
                       ) VALUES(?,?,?,?)""",
                    values
                )
        except Exception as exc:
            QMessageBox.warning(self, "No se pudo guardar", str(exc))
            return

        self.accept()


class AttendancePage(QWidget):
    def __init__(self, db):
        super().__init__()
        self.db = db
        self.service = GymService(db)

        root = QVBoxLayout(self)
        root.setContentsMargins(28, 26, 28, 26)
        root.addLayout(
            page_header("Asistencias", "Registro diario de presencia")
        )

        top = QHBoxLayout()
        self.student = QComboBox()
        self.activity = QComboBox()
        self.student.currentIndexChanged.connect(self.load_student_activities)

        mark = QPushButton("Registrar asistencia")
        mark.setObjectName("primary")
        mark.clicked.connect(self.mark)

        top.addWidget(self.student)
        top.addWidget(self.activity)
        top.addWidget(mark)
        root.addLayout(top)

        self.table = make_table(["Fecha", "Alumno", "Actividad", "Estado"])
        root.addWidget(self.table, 1)
        self.refresh()

    def load_students(self):
        current_id = self.student.currentData()
        self.student.blockSignals(True)
        self.student.clear()

        for row in self.db.fetchall(
            """SELECT id,name,surname
               FROM students
               WHERE active=1
               ORDER BY name,surname"""
        ):
            self.student.addItem(
                f"{row['name']} {row['surname']}", row["id"]
            )

        if current_id is not None:
            index = self.student.findData(current_id)
            if index >= 0:
                self.student.setCurrentIndex(index)

        self.student.blockSignals(False)
        self.load_student_activities()

    def load_student_activities(self):
        self.activity.clear()
        student_id = self.student.currentData()
        if student_id is None:
            return

        for row in self.service.student_activities(student_id):
            self.activity.addItem(row["name"], row["id"])

    def refresh(self):
        self.load_students()

        rows = self.db.fetchall(
            """SELECT a.date,
                      s.name || ' ' || s.surname student,
                      a.activity,
                      a.present
               FROM attendance a
               JOIN students s ON s.id=a.student_id
               ORDER BY a.id DESC
               LIMIT 100"""
        )

        self.table.setRowCount(len(rows))
        for row_index, row in enumerate(rows):
            values = [
                row["date"], row["student"], row["activity"],
                "Presente" if row["present"] else "Ausente"
            ]
            for column, value in enumerate(values):
                self.table.setItem(
                    row_index, column, QTableWidgetItem(str(value))
                )

    def mark(self):
        student_id = self.student.currentData()
        if student_id is None:
            QMessageBox.information(
                self, "Asistencia", "No hay alumnos activos."
            )
            return

        if self.activity.currentData() is None:
            QMessageBox.information(
                self,
                "Asistencia",
                "El alumno no tiene actividades asignadas."
            )
            return

        try:
            self.db.execute(
                """INSERT INTO attendance(student_id,activity,date,present)
                   VALUES(?,?,?,1)""",
                (
                    student_id,
                    self.activity.currentText(),
                    date.today().isoformat()
                )
            )
        except Exception:
            QMessageBox.information(
                self,
                "Asistencia",
                "La asistencia de este alumno a esa actividad ya está registrada hoy."
            )
            return

        self.refresh()


class PaymentsPage(QWidget):
    def __init__(self, db):
        super().__init__()
        self.db = db

        root = QVBoxLayout(self)
        root.setContentsMargins(28, 26, 28, 26)
        root.addLayout(
            page_header("Pagos", "Cuotas, pendientes e ingresos")
        )

        top = QHBoxLayout()

        add = QPushButton("Nuevo pago")
        add.setObjectName("primary")
        add.clicked.connect(self.add_payment)

        paid = QPushButton("Marcar pagado")
        paid.clicked.connect(self.mark_paid)

        top.addStretch()
        top.addWidget(add)
        top.addWidget(paid)
        root.addLayout(top)

        self.table = make_table(
            ["ID", "Fecha", "Alumno", "Importe", "Concepto", "Estado"]
        )
        root.addWidget(self.table, 1)
        self.refresh()

    def refresh(self):
        GymService(self.db).ensure_monthly_dues()

        rows = self.db.fetchall(
            """SELECT p.id,p.date,
                      s.name || ' ' || s.surname student,
                      p.amount,p.concept,p.status
               FROM payments p
               JOIN students s ON s.id=p.student_id
               ORDER BY p.id DESC"""
        )

        self.table.setRowCount(len(rows))
        for row_index, row in enumerate(rows):
            values = [
                row["id"], row["date"], row["student"],
                f"{row['amount']:.2f} €", row["concept"] or "", row["status"]
            ]
            for column, value in enumerate(values):
                self.table.setItem(
                    row_index, column, QTableWidgetItem(str(value))
                )

    def add_payment(self):
        dialog = PaymentDialog(self.db, self)
        if dialog.exec():
            self.refresh()

    def mark_paid(self):
        payment_id = selected_id(self.table)
        if payment_id is None:
            QMessageBox.information(self, "Pago", "Selecciona un pago.")
            return

        row = self.db.fetchone(
            "SELECT status FROM payments WHERE id=?",
            (payment_id,)
        )
        if row and row["status"] == "Pagado":
            QMessageBox.information(
                self, "Pago", "Este pago ya está marcado como pagado."
            )
            return

        GymService(self.db).mark_payment_paid(payment_id)
        self.refresh()


class PaymentDialog(QDialog):
    def __init__(self, db, parent=None):
        super().__init__(parent)
        self.db = db
        self.setWindowTitle("Nuevo pago")

        form = QFormLayout(self)

        self.student = QComboBox()
        for row in db.fetchall(
            """SELECT id,name,surname,plan
               FROM students
               WHERE active=1
               ORDER BY name,surname"""
        ):
            self.student.addItem(
                f"{row['name']} {row['surname']}",
                (row["id"], row["plan"])
            )

        self.student.currentIndexChanged.connect(self.apply_plan_price)

        self.amount = QDoubleSpinBox()
        self.amount.setMaximum(10000)
        self.amount.setSuffix(" €")

        self.concept = QLineEdit("Pago adicional")
        self.status = QComboBox()
        self.status.addItems(["Pendiente", "Pagado"])

        self.date = QDateEdit(QDate.currentDate())
        self.date.setCalendarPopup(True)

        for label, widget in [
            ("Alumno", self.student),
            ("Importe", self.amount),
            ("Concepto", self.concept),
            ("Estado", self.status),
            ("Fecha", self.date),
        ]:
            form.addRow(label, widget)

        save = QPushButton("Guardar pago")
        save.setObjectName("primary")
        save.clicked.connect(self.save)
        form.addRow(save)

        self.apply_plan_price()

    def apply_plan_price(self):
        data = self.student.currentData()
        if not data:
            return
        _, plan = data
        self.amount.setValue(plan_price(plan))

    def save(self):
        data = self.student.currentData()
        if not data:
            QMessageBox.information(self, "Pago", "No hay alumnos activos.")
            return

        student_id, _ = data
        self.db.execute(
            """INSERT INTO payments(
                   student_id,amount,concept,date,status,billing_month
               ) VALUES(?,?,?,?,?,NULL)""",
            (
                student_id,
                self.amount.value(),
                self.concept.text().strip() or "Pago adicional",
                self.date.date().toString("yyyy-MM-dd"),
                self.status.currentText()
            )
        )
        self.accept()


class InvoicesPage(QWidget):
    def __init__(self, db):
        super().__init__()
        self.db = db

        root = QVBoxLayout(self)
        root.setContentsMargins(28, 26, 28, 26)
        root.addLayout(
            page_header("Facturación", "Emisión y control de facturas")
        )

        top = QHBoxLayout()

        new = QPushButton("Nueva factura")
        new.setObjectName("primary")
        new.clicked.connect(self.new_invoice)

        export = QPushButton("Exportar CSV")
        export.clicked.connect(self.export_csv)

        top.addStretch()
        top.addWidget(new)
        top.addWidget(export)
        root.addLayout(top)

        self.table = make_table(
            ["ID", "Nº factura", "Fecha", "Alumno",
             "Importe", "Concepto", "Estado"]
        )
        root.addWidget(self.table, 1)
        self.refresh()

    def refresh(self):
        rows = self.db.fetchall(
            """SELECT i.id,i.invoice_number,i.issue_date,
                      s.name || ' ' || s.surname student,
                      i.amount,i.concept,i.status
               FROM invoices i
               JOIN students s ON s.id=i.student_id
               ORDER BY i.id DESC"""
        )

        self.table.setRowCount(len(rows))
        for row_index, row in enumerate(rows):
            values = [
                row["id"], row["invoice_number"], row["issue_date"],
                row["student"], f"{row['amount']:.2f} €",
                row["concept"], row["status"]
            ]
            for column, value in enumerate(values):
                self.table.setItem(
                    row_index, column, QTableWidgetItem(str(value))
                )

    def new_invoice(self):
        dialog = InvoiceDialog(self.db, self)
        if dialog.exec():
            self.refresh()

    def export_csv(self):
        rows = self.db.fetchall(
            """SELECT i.invoice_number,i.issue_date,
                      s.name || ' ' || s.surname student,
                      i.amount,i.concept,i.status
               FROM invoices i
               JOIN students s ON s.id=i.student_id
               ORDER BY i.id DESC"""
        )

        if not rows:
            QMessageBox.information(
                self, "Facturación", "No hay facturas para exportar."
            )
            return

        path, _ = QFileDialog.getSaveFileName(
            self, "Guardar facturas", "facturas.csv", "CSV (*.csv)"
        )
        if not path:
            return

        with open(path, "w", newline="", encoding="utf-8-sig") as file:
            writer = csv.writer(file, delimiter=";")
            writer.writerow(
                ["Numero", "Fecha", "Alumno", "Importe", "Concepto", "Estado"]
            )
            for row in rows:
                writer.writerow(
                    [
                        row["invoice_number"], row["issue_date"],
                        row["student"], row["amount"],
                        row["concept"], row["status"]
                    ]
                )

        QMessageBox.information(
            self, "Exportación", "CSV exportado correctamente."
        )


class InvoiceDialog(QDialog):
    def __init__(self, db, parent=None):
        super().__init__(parent)
        self.db = db
        self.setWindowTitle("Nueva factura")

        form = QFormLayout(self)

        self.student = QComboBox()
        for row in db.fetchall(
            """SELECT id,name,surname,plan
               FROM students
               WHERE active=1
               ORDER BY name,surname"""
        ):
            self.student.addItem(
                f"{row['name']} {row['surname']}",
                (row["id"], row["plan"])
            )

        self.student.currentIndexChanged.connect(self.apply_plan_price)

        self.amount = QDoubleSpinBox()
        self.amount.setMaximum(10000)
        self.amount.setSuffix(" €")

        self.concept = QLineEdit("Cuota mensual")

        self.date = QDateEdit(QDate.currentDate())
        self.date.setCalendarPopup(True)

        self.status = QComboBox()
        self.status.addItems(["Emitida", "Pagada", "Anulada"])

        for label, widget in [
            ("Alumno", self.student),
            ("Importe", self.amount),
            ("Concepto", self.concept),
            ("Fecha", self.date),
            ("Estado", self.status),
        ]:
            form.addRow(label, widget)

        save = QPushButton("Emitir factura")
        save.setObjectName("primary")
        save.clicked.connect(self.save)
        form.addRow(save)

        self.apply_plan_price()

    def apply_plan_price(self):
        data = self.student.currentData()
        if not data:
            return
        _, plan = data
        self.amount.setValue(plan_price(plan))

    def save(self):
        data = self.student.currentData()
        if not data:
            QMessageBox.information(
                self, "Factura", "No hay alumnos activos."
            )
            return

        student_id, _ = data
        next_number = self.db.fetchone(
            "SELECT COALESCE(MAX(id),0)+1 n FROM invoices"
        )["n"]
        invoice_number = f"F-{date.today().year}-{next_number:05d}"

        self.db.execute(
            """INSERT INTO invoices(
                   invoice_number,student_id,amount,concept,issue_date,status
               ) VALUES(?,?,?,?,?,?)""",
            (
                invoice_number,
                student_id,
                self.amount.value(),
                self.concept.text().strip() or "Cuota mensual",
                self.date.date().toString("yyyy-MM-dd"),
                self.status.currentText()
            )
        )
        self.accept()


class StatisticsPage(QWidget):
    def __init__(self, db):
        super().__init__()
        self.db = db

        root = QVBoxLayout(self)
        root.setContentsMargins(28, 26, 28, 26)
        root.addLayout(
            page_header(
                "Estadísticas",
                "Visualización con Pandas + Matplotlib"
            )
        )

        self.figure = Figure(figsize=(8, 5))
        self.canvas = FigureCanvas(self.figure)
        root.addWidget(self.canvas, 1)

        refresh = QPushButton("Actualizar gráficas")
        refresh.setObjectName("primary")
        refresh.clicked.connect(self.refresh)
        root.addWidget(refresh)

        self.refresh()

    def refresh(self):
        self.figure.clear()
        axis = self.figure.add_subplot(111)
        dataframe = Reports(self.db).students_by_activity()

        if dataframe.empty:
            axis.text(
                0.5, 0.5,
                "Todavía no hay datos de alumnos",
                ha="center", va="center",
                transform=axis.transAxes
            )
            axis.set_xticks([])
            axis.set_yticks([])
        else:
            axis.bar(dataframe["activity"], dataframe["total"])
            axis.set_title("Alumnos activos por actividad")
            axis.set_ylabel("Alumnos")
            axis.tick_params(axis="x", rotation=25)

        self.figure.tight_layout()
        self.canvas.draw()
