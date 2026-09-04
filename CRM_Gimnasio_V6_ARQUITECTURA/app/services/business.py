from datetime import date
from app.config.settings import FEES


def plan_price(plan):
    return FEES.get(plan, 0.0)


class GymService:
    """Lógica de negocio del gimnasio."""

    def __init__(self, db):
        self.db = db

    def ensure_monthly_dues(self, target_date=None):
        target_date = target_date or date.today()
        month = target_date.strftime("%Y-%m")
        charge_date = target_date.replace(day=1).isoformat()

        students = self.db.fetchall(
            "SELECT id, plan FROM students WHERE active=1 ORDER BY id"
        )

        for student in students:
            exists = self.db.fetchone(
                "SELECT id FROM payments WHERE student_id=? AND billing_month=?",
                (student["id"], month),
            )
            if exists:
                continue

            self.db.execute(
                """INSERT INTO payments(
                       student_id, amount, concept, date, status, billing_month
                   ) VALUES(?,?,?,?,?,?)""",
                (
                    student["id"],
                    plan_price(student["plan"]),
                    f"Cuota mensual {month}",
                    charge_date,
                    "Pendiente",
                    month,
                ),
            )

    def create_due_for_student(self, student_id, plan, join_date):
        month = join_date[:7]

        exists = self.db.fetchone(
            "SELECT id FROM payments WHERE student_id=? AND billing_month=?",
            (student_id, month),
        )
        if exists:
            return

        self.db.execute(
            """INSERT INTO payments(
                   student_id, amount, concept, date, status, billing_month
               ) VALUES(?,?,?,?,?,?)""",
            (
                student_id,
                plan_price(plan),
                f"Cuota mensual {month}",
                join_date,
                "Pendiente",
                month,
            ),
        )

    def mark_payment_paid(self, payment_id):
        self.db.execute(
            "UPDATE payments SET status='Pagado', date=? WHERE id=?",
            (date.today().isoformat(), payment_id),
        )

    def dashboard_data(self, target_date=None):
        target_date = target_date or date.today()
        month = target_date.strftime("%Y-%m")

        self.ensure_monthly_dues(target_date)

        students = self.db.fetchone(
            "SELECT COUNT(*) total FROM students WHERE active=1"
        )["total"]

        pending = self.db.fetchone(
            "SELECT COUNT(*) total FROM payments WHERE status='Pendiente'"
        )["total"]

        income = self.db.fetchone(
            """SELECT COALESCE(SUM(amount),0) total
               FROM payments
               WHERE status='Pagado' AND substr(date,1,7)=?""",
            (month,),
        )["total"]

        new_students = self.db.fetchone(
            "SELECT COUNT(*) total FROM students WHERE substr(join_date,1,7)=?",
            (month,),
        )["total"]

        activities = self.db.fetchall(
            """SELECT COALESCE(activity,'Sin asignar') activity, COUNT(*) total
               FROM students
               WHERE active=1
               GROUP BY activity
               ORDER BY total DESC"""
        )

        return {
            "students": students,
            "pending": pending,
            "income": income,
            "new_students": new_students,
            "activities": activities,
        }
