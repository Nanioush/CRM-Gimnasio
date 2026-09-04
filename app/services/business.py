from datetime import date
from app.config.settings import FEES


def plan_price(plan):
    return FEES.get(plan, 0.0)


def required_activity_count(plan):
    return 2 if plan == "Adulto 2 actividades - 64 €" else 1


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

    def student_activity_ids(self, student_id):
        rows = self.db.fetchall(
            """SELECT activity_id
               FROM student_activities
               WHERE student_id=?
               ORDER BY activity_id""",
            (student_id,)
        )
        return [row["activity_id"] for row in rows]

    def student_activities(self, student_id):
        return self.db.fetchall(
            """SELECT a.id, a.name
               FROM student_activities sa
               JOIN activities a ON a.id=sa.activity_id
               WHERE sa.student_id=?
               ORDER BY a.name""",
            (student_id,)
        )

    def set_student_activities(self, student_id, activity_ids):
        unique_ids = list(dict.fromkeys(activity_ids))
        self.db.execute(
            "DELETE FROM student_activities WHERE student_id=?",
            (student_id,)
        )
        if unique_ids:
            self.db.execute_many(
                """INSERT INTO student_activities(student_id, activity_id)
                   VALUES(?,?)""",
                [(student_id, activity_id) for activity_id in unique_ids]
            )

        # Mantiene el campo antiguo sincronizado con la actividad principal.
        primary_name = ""
        if unique_ids:
            row = self.db.fetchone(
                "SELECT name FROM activities WHERE id=?",
                (unique_ids[0],)
            )
            primary_name = row["name"] if row else ""
        self.db.execute(
            "UPDATE students SET activity=? WHERE id=?",
            (primary_name, student_id)
        )

    def update_pending_due_for_plan(self, student_id, plan, target_date=None):
        target_date = target_date or date.today()
        month = target_date.strftime("%Y-%m")
        pending = self.db.fetchone(
            """SELECT id FROM payments
               WHERE student_id=? AND billing_month=? AND status='Pendiente'""",
            (student_id, month)
        )
        if pending:
            self.db.execute(
                "UPDATE payments SET amount=? WHERE id=?",
                (plan_price(plan), pending["id"])
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
            """SELECT a.name activity, COUNT(DISTINCT sa.student_id) total
               FROM student_activities sa
               JOIN activities a ON a.id=sa.activity_id
               JOIN students s ON s.id=sa.student_id
               WHERE s.active=1
               GROUP BY a.id, a.name
               ORDER BY total DESC, a.name"""
        )

        return {
            "students": students,
            "pending": pending,
            "income": income,
            "new_students": new_students,
            "activities": activities,
        }
