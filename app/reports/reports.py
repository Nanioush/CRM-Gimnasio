import pandas as pd


class Reports:
    """Preparación de datos para informes y estadísticas."""

    def __init__(self, db):
        self.db = db

    def students_by_activity(self):
        rows = self.db.fetchall(
            """SELECT a.name activity, COUNT(DISTINCT sa.student_id) total
               FROM student_activities sa
               JOIN activities a ON a.id=sa.activity_id
               JOIN students s ON s.id=sa.student_id
               WHERE s.active=1
               GROUP BY a.id, a.name
               ORDER BY total DESC, a.name"""
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
