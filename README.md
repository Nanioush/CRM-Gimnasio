# Fight Gym CRM

CRM de escritorio para un gimnasio de deportes de contacto.

## Requisitos cubiertos

- Alumnos
- Profesores
- Actividades
- Pagos
- Asistencias
- Facturación
- Estadísticas
- Login
- Dashboard

## Tecnologías

- Python 3
- PySide6
- SQLite
- Pandas
- Matplotlib
- Git
- GitHub

## Arquitectura

- `app/ui` - interfaz gráfica
- `app/data` - base de datos SQLite
- `app/services` - lógica de negocio
- `app/reports` - informes y preparación de datos con Pandas
- `app/config` - configuración
- `app/ui/login.py` - login

## Cuotas

- Infantil: 28 €
- Adulto: 49 €
- Adulto con 2 actividades: 64 €

La cuota de 2 actividades obliga a seleccionar dos actividades diferentes.

## Automatismos

- Al crear un alumno se genera automáticamente la cuota de su mes como `Pendiente`.
- Al comenzar un nuevo mes se crean las cuotas pendientes que falten para los alumnos activos.
- Al marcar una cuota como `Pagado`, el Dashboard actualiza los ingresos.
- Las actividades del alumno se utilizan también en Asistencias y Estadísticas.
- Un profesor puede quedar vinculado a una o varias actividades.

## Ejecución en Windows

Por el tamaño de las rutas internas de PySide6, conviene usar una ruta corta, por ejemplo:

`C:\CRM`

Después ejecuta:

`INICIAR.bat`

Credenciales iniciales:

- Usuario: `admin`
- Contraseña: `admin123`

## Git

Después de modificar el proyecto:

```bash
git add .
git commit -m "Actualización CRM gimnasio"
git push
```
