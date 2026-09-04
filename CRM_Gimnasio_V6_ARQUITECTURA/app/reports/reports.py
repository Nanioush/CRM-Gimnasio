import pandas as pd


class Reports:
    """Preparación de datos para informes y estadísticas."""

    def __init__(self, db):
        self.db = db

    def students_by_activity(self):
        rows = self.db.fetchall(
            """SELECT COALESCE(activity,'Sin asignar') activity, COUNT(*) total
               FROM students
               WHERE active=1
               GROUP BY activity
               ORDER BY total DESC"""
        )
        return pd.DataFrame([dict(row) for row in rows])

    def payments_summary(self):
        rows = self.db.fetchall(
            """SELECT p.date,
                      s.name || ' ' || s.surname alumno,
                      p.amount,
                      p.status
               FROM payments p
               JOIN students s ON s.id=p.student_id
               ORDER BY p.date DESC"""
        )
        return pd.DataFrame([dict(row) for row in rows])
