from datetime import date
import csv
import pandas as pd

from PySide6.QtCore import Qt, QDate
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QFrame,
    QPushButton, QLineEdit, QComboBox, QTableWidget, QTableWidgetItem,
    QMessageBox, QDialog, QFormLayout, QDateEdit, QDoubleSpinBox, QSpinBox, QFileDialog
)
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
from app.services.business import GymService, plan_price
from app.reports.reports import Reports
from app.config.settings import FEES

def page_header(title, subtitle=""):
    box = QVBoxLayout()
    t = QLabel(title)
    t.setObjectName("title")
    box.addWidget(t)
    if subtitle:
        s = QLabel(subtitle)
        s.setStyleSheet("color:#8d98a6;")
        box.addWidget(s)
    return box

def selected_id(table):
    row=table.currentRow()
    if row<0: return None
    item=table.item(row,0)
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
        lay = QVBoxLayout(self)
        t = QLabel(title)
        t.setStyleSheet("color:#8d98a6;")
        self.value = QLabel(str(value))
        self.value.setObjectName("metric")
        lay.addWidget(t)
        lay.addWidget(self.value)

class DashboardPage(QWidget):
    def __init__(self, db):
        super().__init__()
        self.db = db
        root = QVBoxLayout(self)
        root.setContentsMargins(28,26,28,26)
        root.setSpacing(18)
        root.addLayout(page_header("Dashboard", "Resumen general del gimnasio"))

        grid = QGridLayout()
        self.c_students = MetricCard("Alumnos activos")
        self.c_pending = MetricCard("Pagos pendientes")
        self.c_income = MetricCard("Ingresos mensuales")
        self.c_new = MetricCard("Nuevos alumnos")
        for i, c in enumerate([self.c_students,self.c_pending,self.c_income,self.c_new]):
            grid.addWidget(c, 0, i)
        root.addLayout(grid)

        self.activity_table = make_table(["Actividad", "Alumnos"])
        root.addWidget(QLabel("Actividades más utilizadas"))
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
        for r, row in enumerate(rows):
            self.activity_table.setItem(r,0,QTableWidgetItem(str(row["activity"])))
            self.activity_table.setItem(r,1,QTableWidgetItem(str(row["total"])))

class StudentsPage(QWidget):
    def __init__(self, db):
        super().__init__()
        self.db=db
        root=QVBoxLayout(self)
        root.setContentsMargins(28,26,28,26)
        root.addLayout(page_header("Alumnos","Altas, bajas y consulta de alumnos"))

        top=QHBoxLayout()
        self.search=QLineEdit()
        self.search.setPlaceholderText("Buscar por nombre, apellido o teléfono...")
        self.search.textChanged.connect(self.refresh)
        add=QPushButton("Nuevo alumno"); add.setObjectName("primary"); add.clicked.connect(self.add_student)
        edit=QPushButton("Editar"); edit.clicked.connect(self.edit_student)
        delete=QPushButton("Dar de baja"); delete.setObjectName("danger"); delete.clicked.connect(self.deactivate_student)
        reactivate=QPushButton("Reactivar"); reactivate.clicked.connect(self.reactivate_student)
        top.addWidget(self.search,1); top.addWidget(add); top.addWidget(edit); top.addWidget(delete); top.addWidget(reactivate)
        root.addLayout(top)

        self.table=make_table(["ID","Nombre","Apellidos","Teléfono","Plan","Actividad","Alta","Estado"])
        root.addWidget(self.table,1)
        self.refresh()

    def refresh(self):
        q=self.search.text().strip() if hasattr(self,"search") else ""
        like=f"%{q}%"
        rows=self.db.fetchall("""
            SELECT * FROM students
            WHERE name LIKE ? OR surname LIKE ? OR phone LIKE ?
            ORDER BY id DESC
        """,(like,like,like))
        self.table.setRowCount(len(rows))
        for r,row in enumerate(rows):
            vals=[row["id"],row["name"],row["surname"],row["phone"] or "",row["plan"],
                  row["activity"] or "",row["join_date"],"Activo" if row["active"] else "Baja"]
            for c,v in enumerate(vals):
                self.table.setItem(r,c,QTableWidgetItem(str(v)))

    def add_student(self):
        dlg=StudentDialog(self.db,parent=self)
        if dlg.exec(): self.refresh()

    def edit_student(self):
        sid=selected_id(self.table)
        if sid is None:
            QMessageBox.information(self,"Alumno","Selecciona un alumno."); return
        dlg=StudentDialog(self.db,student_id=sid,parent=self)
        if dlg.exec(): self.refresh()

    def reactivate_student(self):
        sid=selected_id(self.table)
        if sid is None:
            QMessageBox.information(self,"Alumno","Selecciona un alumno."); return
        self.db.execute("UPDATE students SET active=1 WHERE id=?",(sid,)); self.refresh()

    def deactivate_student(self):
        row=self.table.currentRow()
        if row<0:
            QMessageBox.information(self,"Alumno","Selecciona un alumno.")
            return
        sid=int(self.table.item(row,0).text())
        self.db.execute("UPDATE students SET active=0 WHERE id=?",(sid,))
        self.refresh()

class StudentDialog(QDialog):
    def __init__(self,db,student_id=None,parent=None):
        super().__init__(parent)
        self.db=db
        self.student_id=student_id
        self.setWindowTitle("Editar alumno" if student_id else "Nuevo alumno")
        self.resize(430,520)
        form=QFormLayout(self)

        self.name=QLineEdit(); self.surname=QLineEdit()
        self.phone=QLineEdit(); self.email=QLineEdit()
        self.birth=QDateEdit(QDate.currentDate()); self.birth.setCalendarPopup(True)
        self.plan=QComboBox(); self.plan.addItems(FEES.keys())
        self.activity=QComboBox()
        acts=db.fetchall("SELECT name FROM activities ORDER BY name")
        self.activity.addItems([r["name"] for r in acts])
        self.join=QDateEdit(QDate.currentDate()); self.join.setCalendarPopup(True)

        for label,w in [
            ("Nombre",self.name),("Apellidos",self.surname),("Teléfono",self.phone),
            ("Email",self.email),("Fecha nacimiento",self.birth),("Cuota",self.plan),
            ("Actividad",self.activity),("Fecha alta",self.join)
        ]:
            form.addRow(label,w)

        btn=QPushButton("Guardar alumno"); btn.setObjectName("primary"); btn.clicked.connect(self.save)
        form.addRow(btn)
        if student_id: self.load_student()

    def load_student(self):
        row=self.db.fetchone("SELECT * FROM students WHERE id=?",(self.student_id,))
        if not row: return
        self.name.setText(row["name"] or ""); self.surname.setText(row["surname"] or "")
        self.phone.setText(row["phone"] or ""); self.email.setText(row["email"] or "")
        if row["birth_date"]: self.birth.setDate(QDate.fromString(row["birth_date"],"yyyy-MM-dd"))
        ix=self.plan.findText(row["plan"]); self.plan.setCurrentIndex(ix if ix>=0 else 0)
        ix=self.activity.findText(row["activity"] or ""); self.activity.setCurrentIndex(ix if ix>=0 else 0)
        if row["join_date"]: self.join.setDate(QDate.fromString(row["join_date"],"yyyy-MM-dd"))

    def save(self):
        if not self.name.text().strip() or not self.surname.text().strip():
            QMessageBox.warning(self,"Faltan datos","Nombre y apellidos son obligatorios.")
            return
        vals=(self.name.text().strip(),self.surname.text().strip(),self.phone.text().strip(),self.email.text().strip(),self.birth.date().toString("yyyy-MM-dd"),self.plan.currentText(),self.activity.currentText(),self.join.date().toString("yyyy-MM-dd"))
        if self.student_id:
            self.db.execute(
                "UPDATE students SET name=?,surname=?,phone=?,email=?,birth_date=?,plan=?,activity=?,join_date=? WHERE id=?",
                vals+(self.student_id,)
            )
            # Si cambia de plan, una cuota pendiente del mes actual adopta el importe nuevo.
            month = date.today().strftime("%Y-%m")
            pending = self.db.fetchone(
                """SELECT id FROM payments
                   WHERE student_id=? AND billing_month=? AND status='Pendiente'""",
                (self.student_id, month)
            )
            if pending:
                self.db.execute(
                    "UPDATE payments SET amount=? WHERE id=?",
                    (plan_price(self.plan.currentText()), pending["id"])
                )
        else:
            student_id = self.db.execute(
                "INSERT INTO students(name,surname,phone,email,birth_date,plan,activity,join_date) VALUES(?,?,?,?,?,?,?,?)",
                vals
            )
            GymService(self.db).create_due_for_student(
                student_id,
                self.plan.currentText(),
                self.join.date().toString("yyyy-MM-dd")
            )
        self.accept()

class TeachersPage(QWidget):
    def __init__(self,db):
        super().__init__(); self.db=db
        root=QVBoxLayout(self); root.setContentsMargins(28,26,28,26)
        root.addLayout(page_header("Profesores","Gestión del equipo docente"))
        top=QHBoxLayout()
        add=QPushButton("Nuevo profesor"); add.setObjectName("primary"); add.clicked.connect(self.add_teacher)
        edit=QPushButton("Editar"); edit.clicked.connect(self.edit_teacher)
        delete=QPushButton("Eliminar"); delete.setObjectName("danger"); delete.clicked.connect(self.delete_teacher)
        top.addStretch(); top.addWidget(add); top.addWidget(edit); top.addWidget(delete); root.addLayout(top)
        self.table=make_table(["ID","Nombre","Apellidos","Teléfono","Email","Especialidad"])
        root.addWidget(self.table,1); self.refresh()

    def refresh(self):
        rows=self.db.fetchall("SELECT * FROM teachers ORDER BY id DESC")
        self.table.setRowCount(len(rows))
        for r,row in enumerate(rows):
            vals=[row["id"],row["name"],row["surname"],row["phone"] or "",row["email"] or "",row["specialty"] or ""]
            for c,v in enumerate(vals): self.table.setItem(r,c,QTableWidgetItem(str(v)))

    def add_teacher(self):
        dlg=TeacherDialog(self.db,parent=self)
        if dlg.exec(): self.refresh()

    def edit_teacher(self):
        tid=selected_id(self.table)
        if tid is None:
            QMessageBox.information(self,"Profesor","Selecciona un profesor."); return
        dlg=TeacherDialog(self.db,teacher_id=tid,parent=self)
        if dlg.exec(): self.refresh()

    def delete_teacher(self):
        tid=selected_id(self.table)
        if tid is None:
            QMessageBox.information(self,"Profesor","Selecciona un profesor."); return
        self.db.execute("UPDATE activities SET teacher_id=NULL WHERE teacher_id=?",(tid,)); self.db.execute("DELETE FROM teachers WHERE id=?",(tid,)); self.refresh()

class TeacherDialog(QDialog):
    def __init__(self,db,teacher_id=None,parent=None):
        super().__init__(parent); self.db=db; self.teacher_id=teacher_id; self.setWindowTitle("Editar profesor" if teacher_id else "Nuevo profesor")
        form=QFormLayout(self)
        self.name=QLineEdit(); self.surname=QLineEdit(); self.phone=QLineEdit(); self.email=QLineEdit(); self.specialty=QLineEdit()
        self.activity=QComboBox()
        self.activity.addItem("Sin asignar", None)
        for row in self.db.fetchall("SELECT id,name FROM activities ORDER BY name"):
            self.activity.addItem(row["name"], row["id"])
        for l,w in [
            ("Nombre",self.name),("Apellidos",self.surname),("Teléfono",self.phone),
            ("Email",self.email),("Especialidad",self.specialty),("Actividad",self.activity)
        ]:
            form.addRow(l,w)
        b=QPushButton("Guardar"); b.setObjectName("primary"); b.clicked.connect(self.save); form.addRow(b)
        if teacher_id: self.load_teacher()

    def load_teacher(self):
        row=self.db.fetchone("SELECT * FROM teachers WHERE id=?",(self.teacher_id,))
        if not row: return
        self.name.setText(row["name"] or ""); self.surname.setText(row["surname"] or ""); self.phone.setText(row["phone"] or ""); self.email.setText(row["email"] or ""); self.specialty.setText(row["specialty"] or "")
        assigned = self.db.fetchone(
            "SELECT id FROM activities WHERE teacher_id=? ORDER BY id LIMIT 1",
            (self.teacher_id,)
        )
        if assigned:
            ix = self.activity.findData(assigned["id"])
            if ix >= 0:
                self.activity.setCurrentIndex(ix)

    def save(self):
        if not self.name.text().strip() or not self.surname.text().strip():
            return
        vals=(self.name.text(),self.surname.text(),self.phone.text(),self.email.text(),self.specialty.text())
        if self.teacher_id:
            teacher_id = self.teacher_id
            self.db.execute(
                "UPDATE teachers SET name=?,surname=?,phone=?,email=?,specialty=? WHERE id=?",
                vals+(teacher_id,)
            )
        else:
            teacher_id = self.db.execute(
                "INSERT INTO teachers(name,surname,phone,email,specialty) VALUES(?,?,?,?,?)",
                vals
            )

        # Sincroniza automáticamente profesor <-> actividad.
        self.db.execute("UPDATE activities SET teacher_id=NULL WHERE teacher_id=?", (teacher_id,))
        activity_id = self.activity.currentData()
        if activity_id is not None:
            self.db.execute(
                "UPDATE activities SET teacher_id=? WHERE id=?",
                (teacher_id, activity_id)
            )
        self.accept()

class ActivitiesPage(QWidget):
    def __init__(self,db):
        super().__init__(); self.db=db
        root=QVBoxLayout(self); root.setContentsMargins(28,26,28,26)
        root.addLayout(page_header("Actividades","Gestión de disciplinas, profesor, horario y aforo"))
        top=QHBoxLayout(); add=QPushButton("Nueva actividad"); add.setObjectName("primary"); add.clicked.connect(self.add_activity); edit=QPushButton("Editar"); edit.clicked.connect(self.edit_activity); top.addStretch(); top.addWidget(add); top.addWidget(edit); root.addLayout(top)
        self.table=make_table(["ID","Actividad","Profesor","Horario","Aforo"])
        root.addWidget(self.table,1); self.refresh()

    def refresh(self):
        rows=self.db.fetchall("""
            SELECT a.id,a.name,
            COALESCE(t.name || ' ' || t.surname,'Sin asignar') teacher,
            COALESCE(a.schedule,'') schedule,a.capacity
            FROM activities a LEFT JOIN teachers t ON t.id=a.teacher_id
            ORDER BY a.name
        """)
        self.table.setRowCount(len(rows))
        for r,row in enumerate(rows):
            for c,v in enumerate([row["id"],row["name"],row["teacher"],row["schedule"],row["capacity"]]): self.table.setItem(r,c,QTableWidgetItem(str(v)))

    def add_activity(self):
        dlg=ActivityDialog(self.db,parent=self)
        if dlg.exec(): self.refresh()
    def edit_activity(self):
        aid=selected_id(self.table)
        if aid is None: QMessageBox.information(self,"Actividad","Selecciona una actividad."); return
        dlg=ActivityDialog(self.db,activity_id=aid,parent=self)
        if dlg.exec(): self.refresh()

class ActivityDialog(QDialog):
    def __init__(self,db,activity_id=None,parent=None):
        super().__init__(parent); self.db=db; self.activity_id=activity_id; self.setWindowTitle("Editar actividad" if activity_id else "Nueva actividad")
        form=QFormLayout(self); self.name=QLineEdit(); self.teacher=QComboBox(); self.teacher.addItem("Sin asignar",None)
        for r in db.fetchall("SELECT id,name,surname FROM teachers ORDER BY name"): self.teacher.addItem(f"{r['name']} {r['surname']}",r["id"])
        self.schedule=QLineEdit(); self.schedule.setPlaceholderText("Ej: L-X-V 18:00"); self.capacity=QSpinBox(); self.capacity.setRange(1,500); self.capacity.setValue(20)
        for l,w in [("Nombre",self.name),("Profesor",self.teacher),("Horario",self.schedule),("Aforo",self.capacity)]: form.addRow(l,w)
        b=QPushButton("Guardar"); b.setObjectName("primary"); b.clicked.connect(self.save); form.addRow(b)
        if activity_id: self.load_activity()
    def load_activity(self):
        row=self.db.fetchone("SELECT * FROM activities WHERE id=?",(self.activity_id,))
        if not row: return
        self.name.setText(row["name"] or ""); self.schedule.setText(row["schedule"] or ""); self.capacity.setValue(row["capacity"] or 20); ix=self.teacher.findData(row["teacher_id"]); self.teacher.setCurrentIndex(ix if ix>=0 else 0)
    def save(self):
        if not self.name.text().strip(): QMessageBox.warning(self,"Falta nombre","La actividad necesita un nombre."); return
        vals=(self.name.text().strip(),self.teacher.currentData(),self.schedule.text().strip(),self.capacity.value())
        try:
            if self.activity_id: self.db.execute("UPDATE activities SET name=?,teacher_id=?,schedule=?,capacity=? WHERE id=?",vals+(self.activity_id,))
            else: self.db.execute("INSERT INTO activities(name,teacher_id,schedule,capacity) VALUES(?,?,?,?)",vals)
        except Exception as exc: QMessageBox.warning(self,"No se pudo guardar",str(exc)); return
        self.accept()

class AttendancePage(QWidget):
    def __init__(self,db):
        super().__init__(); self.db=db
        root=QVBoxLayout(self); root.setContentsMargins(28,26,28,26)
        root.addLayout(page_header("Asistencias","Registro diario de presencia"))
        top=QHBoxLayout()
        self.student=QComboBox(); self.activity=QComboBox()
        self.load_combos()
        mark=QPushButton("Registrar asistencia"); mark.setObjectName("primary"); mark.clicked.connect(self.mark)
        top.addWidget(self.student); top.addWidget(self.activity); top.addWidget(mark)
        root.addLayout(top)
        self.table=make_table(["Fecha","Alumno","Actividad","Estado"])
        root.addWidget(self.table,1); self.refresh()

    def load_combos(self):
        self.student.clear()
        for r in self.db.fetchall("SELECT id,name,surname FROM students WHERE active=1 ORDER BY name"):
            self.student.addItem(f"{r['name']} {r['surname']}",r["id"])
        self.activity.clear()
        for r in self.db.fetchall("SELECT name FROM activities ORDER BY name"):
            self.activity.addItem(r["name"])

    def refresh(self):
        self.load_combos()
        rows=self.db.fetchall("""
            SELECT a.date,s.name || ' ' || s.surname student,a.activity,a.present
            FROM attendance a JOIN students s ON s.id=a.student_id
            ORDER BY a.id DESC LIMIT 100
        """)
        self.table.setRowCount(len(rows))
        for r,row in enumerate(rows):
            vals=[row["date"],row["student"],row["activity"],"Presente" if row["present"] else "Ausente"]
            for c,v in enumerate(vals): self.table.setItem(r,c,QTableWidgetItem(str(v)))

    def mark(self):
        sid=self.student.currentData()
        if sid is None: return
        self.db.execute("INSERT INTO attendance(student_id,activity,date,present) VALUES(?,?,?,1)",
                        (sid,self.activity.currentText(),date.today().isoformat()))
        self.refresh()

class PaymentsPage(QWidget):
    def __init__(self,db):
        super().__init__(); self.db=db
        root=QVBoxLayout(self); root.setContentsMargins(28,26,28,26)
        root.addLayout(page_header("Pagos","Cuotas, pendientes e ingresos"))
        top=QHBoxLayout()
        add=QPushButton("Nuevo pago"); add.setObjectName("primary"); add.clicked.connect(self.add_payment); paid=QPushButton("Marcar pagado"); paid.clicked.connect(self.mark_paid)
        top.addStretch(); top.addWidget(add); top.addWidget(paid); root.addLayout(top)
        self.table=make_table(["ID","Fecha","Alumno","Importe","Concepto","Estado"])
        root.addWidget(self.table,1); self.refresh()

    def refresh(self):
        GymService(self.db).ensure_monthly_dues()
        rows=self.db.fetchall("""
            SELECT p.id,p.date,s.name || ' ' || s.surname student,p.amount,p.concept,p.status
            FROM payments p JOIN students s ON s.id=p.student_id
            ORDER BY p.id DESC
        """)
        self.table.setRowCount(len(rows))
        for r,row in enumerate(rows):
            vals=[row["id"],row["date"],row["student"],f"{row['amount']:.2f} €",row["concept"] or "",row["status"]]
            for c,v in enumerate(vals): self.table.setItem(r,c,QTableWidgetItem(str(v)))

    def add_payment(self):
        dlg=PaymentDialog(self.db,self)
        if dlg.exec(): self.refresh()
    def mark_paid(self):
        pid=selected_id(self.table)
        if pid is None: QMessageBox.information(self,"Pago","Selecciona un pago."); return
        GymService(self.db).mark_payment_paid(pid)
        self.refresh()

class PaymentDialog(QDialog):
    def __init__(self,db,parent=None):
        super().__init__(parent); self.db=db; self.setWindowTitle("Nuevo pago")
        form=QFormLayout(self)
        self.student=QComboBox()
        for r in db.fetchall("SELECT id,name,surname,plan FROM students WHERE active=1 ORDER BY name"):
            self.student.addItem(f"{r['name']} {r['surname']}",(r["id"],r["plan"]))
        self.student.currentIndexChanged.connect(self.apply_plan_price)
        self.amount=QDoubleSpinBox(); self.amount.setMaximum(10000); self.amount.setValue(49); self.amount.setSuffix(" €")
        self.concept=QLineEdit("Cuota mensual")
        self.status=QComboBox(); self.status.addItems(["Pendiente","Pagado"])
        self.date=QDateEdit(QDate.currentDate()); self.date.setCalendarPopup(True)
        for l,w in [("Alumno",self.student),("Importe",self.amount),("Concepto",self.concept),("Estado",self.status),("Fecha",self.date)]:
            form.addRow(l,w)
        b=QPushButton("Guardar pago"); b.setObjectName("primary"); b.clicked.connect(self.save); form.addRow(b); self.apply_plan_price()
    def apply_plan_price(self):
        data=self.student.currentData()
        if not data: return
        _,plan=data; self.amount.setValue(plan_price(plan))
    def save(self):
        data=self.student.currentData()
        if not data: return
        sid,_=data
        self.db.execute(
            "INSERT INTO payments(student_id,amount,concept,date,status,billing_month) VALUES(?,?,?,?,?,NULL)",
            (sid,self.amount.value(),self.concept.text(),self.date.date().toString("yyyy-MM-dd"),self.status.currentText())
        )
        self.accept()

class InvoicesPage(QWidget):
    def __init__(self,db):
        super().__init__(); self.db=db; root=QVBoxLayout(self); root.setContentsMargins(28,26,28,26); root.addLayout(page_header("Facturación","Emisión y control de facturas"))
        top=QHBoxLayout(); new=QPushButton("Nueva factura"); new.setObjectName("primary"); new.clicked.connect(self.new_invoice); export=QPushButton("Exportar CSV"); export.clicked.connect(self.export_csv); top.addStretch(); top.addWidget(new); top.addWidget(export); root.addLayout(top)
        self.table=make_table(["ID","Nº factura","Fecha","Alumno","Importe","Concepto","Estado"]); root.addWidget(self.table,1); self.refresh()
    def refresh(self):
        rows=self.db.fetchall("SELECT i.id,i.invoice_number,i.issue_date,s.name || ' ' || s.surname student,i.amount,i.concept,i.status FROM invoices i JOIN students s ON s.id=i.student_id ORDER BY i.id DESC"); self.table.setRowCount(len(rows))
        for r,row in enumerate(rows):
            for c,v in enumerate([row["id"],row["invoice_number"],row["issue_date"],row["student"],f"{row['amount']:.2f} €",row["concept"],row["status"]]): self.table.setItem(r,c,QTableWidgetItem(str(v)))
    def new_invoice(self):
        dlg=InvoiceDialog(self.db,self)
        if dlg.exec(): self.refresh()
    def export_csv(self):
        rows=self.db.fetchall("SELECT i.invoice_number,i.issue_date,s.name || ' ' || s.surname student,i.amount,i.concept,i.status FROM invoices i JOIN students s ON s.id=i.student_id ORDER BY i.id DESC")
        if not rows: QMessageBox.information(self,"Facturación","No hay facturas para exportar."); return
        path,_=QFileDialog.getSaveFileName(self,"Guardar facturas","facturas.csv","CSV (*.csv)")
        if not path: return
        with open(path,"w",newline="",encoding="utf-8-sig") as f:
            w=csv.writer(f,delimiter=";"); w.writerow(["Numero","Fecha","Alumno","Importe","Concepto","Estado"]); [w.writerow([r["invoice_number"],r["issue_date"],r["student"],r["amount"],r["concept"],r["status"]]) for r in rows]
        QMessageBox.information(self,"Exportación","CSV exportado correctamente.")

class InvoiceDialog(QDialog):
    def __init__(self,db,parent=None):
        super().__init__(parent); self.db=db; self.setWindowTitle("Nueva factura"); form=QFormLayout(self); self.student=QComboBox()
        for r in db.fetchall("SELECT id,name,surname,plan FROM students WHERE active=1 ORDER BY name"): self.student.addItem(f"{r['name']} {r['surname']}",(r["id"],r["plan"]))
        self.student.currentIndexChanged.connect(self.apply_plan_price); self.amount=QDoubleSpinBox(); self.amount.setMaximum(10000); self.amount.setSuffix(" €"); self.concept=QLineEdit("Cuota mensual"); self.date=QDateEdit(QDate.currentDate()); self.date.setCalendarPopup(True); self.status=QComboBox(); self.status.addItems(["Emitida","Pagada","Anulada"])
        for l,w in [("Alumno",self.student),("Importe",self.amount),("Concepto",self.concept),("Fecha",self.date),("Estado",self.status)]: form.addRow(l,w)
        b=QPushButton("Emitir factura"); b.setObjectName("primary"); b.clicked.connect(self.save); form.addRow(b); self.apply_plan_price()
    def apply_plan_price(self):
        data=self.student.currentData()
        if not data: return
        _,plan=data; self.amount.setValue(plan_price(plan))
    def save(self):
        data=self.student.currentData()
        if not data: QMessageBox.information(self,"Factura","No hay alumnos activos."); return
        sid,_=data; n=self.db.fetchone("SELECT COALESCE(MAX(id),0)+1 n FROM invoices")["n"]; inv=f"F-{date.today().year}-{n:05d}"
        self.db.execute("INSERT INTO invoices(invoice_number,student_id,amount,concept,issue_date,status) VALUES(?,?,?,?,?,?)",(inv,sid,self.amount.value(),self.concept.text().strip(),self.date.date().toString("yyyy-MM-dd"),self.status.currentText())); self.accept()

class StatisticsPage(QWidget):
    def __init__(self,db):
        super().__init__(); self.db=db
        root=QVBoxLayout(self); root.setContentsMargins(28,26,28,26)
        root.addLayout(page_header("Estadísticas","Visualización con Pandas + Matplotlib"))
        self.figure=Figure(figsize=(8,5))
        self.canvas=FigureCanvas(self.figure)
        root.addWidget(self.canvas,1)
        btn=QPushButton("Actualizar gráficas"); btn.setObjectName("primary"); btn.clicked.connect(self.refresh)
        root.addWidget(btn)
        self.refresh()

    def refresh(self):
        self.figure.clear()
        ax=self.figure.add_subplot(111)
        df = Reports(self.db).students_by_activity()
        if df.empty:
            ax.text(0.5,0.5,"Todavía no hay datos de alumnos",ha="center",va="center",transform=ax.transAxes)
            ax.set_xticks([]); ax.set_yticks([])
        else:
            ax.bar(df["activity"],df["total"])
            ax.set_title("Alumnos activos por actividad")
            ax.set_ylabel("Alumnos")
            ax.tick_params(axis="x",rotation=25)
        self.figure.tight_layout()
        self.canvas.draw()
