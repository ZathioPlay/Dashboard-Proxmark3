# PM3 Dashboard — contexto para Claude Code

## Qué es este proyecto

Aplicación de escritorio para Windows (Trabajo de Fin de Grado de ASIR, autores
Daniel Pérez y Pedro Smith) que permite usar una **Proxmark3** con firmware
Iceman/RRG desde una interfaz gráfica tipo *dashboard*, sin tener que escribir
comandos en consola. Cada usuario la instala en su propio PC; **no hay servidor**.

Es la evolución del proyecto anterior `../TFG-proxmark3/rfid-clone`, que era una
web local (servidor HTTP en Python + HTML con Tailwind). De allí se reutiliza:

- `rfid-clone/backend/pm3_controller.py`: lanzar el cliente de Iceman, detectar
  el puerto COM, parsear `hf search`, `lf search`, `hw tune`, emulación.
- `rfid-clone/frontend/menu.html` y `login.html`: diseño visual (paleta "cyber",
  fuentes Inter y JetBrains Mono) y secciones (antenas, lectura, clonado/emulación,
  base de datos, terminal).
- `rfid-clone/database/schema.sql`: tabla de tarjetas.

Ese proyecto es **solo de consulta**: no se modifica desde aquí.

## Decisiones técnicas (no cambiarlas sin preguntar)

| Tema | Decisión |
|---|---|
| Lenguaje | Python 3.11+ |
| Ventana | `pywebview`: la interfaz HTML se abre en una ventana propia, sin navegador |
| Comunicación interfaz ↔ Python | API de pywebview (`window.pywebview.api.metodo()`), **sin servidor HTTP ni puertos** |
| Interfaz | HTML + JavaScript sin frameworks; CSS con Tailwind **compilado localmente** (nada de CDN: debe funcionar sin internet) |
| Base de datos | SQLite (`sqlite3` de la librería estándar), en `%APPDATA%\PM3-Dashboard\pm3.db` |
| Configuración | `%APPDATA%\PM3-Dashboard\config.json` (ruta del cliente, puerto "auto" o COMx) |
| Proxmark3 | Se controla lanzando el cliente de Iceman con `subprocess`; un único acceso al puerto a la vez |
| Cliente de Iceman | Se localiza con `pm3/localizador.py` en este orden: `ruta_cliente` de config.json (prioridad absoluta: si no existe, error), incluido con la app (`vendor/pm3-client` o `pm3-client\` junto al `.exe`), `~/proxmark3`, ProxSpace y PATH (solo entradas absolutas, nunca el directorio actual) |
| Tests | `pytest`; la lógica de la Proxmark se prueba con un cliente falso, nunca con hardware real |
| Empaquetado | PyInstaller (un `.exe`) + Inno Setup (instalador) |
| Usuarios | Sin login en la v1: es una app local de un solo usuario |

## Estructura de carpetas

```
pm3-dashboard/
├── src/pm3_dashboard/      Código Python
│   ├── __main__.py         Punto de entrada (python -m pm3_dashboard)
│   ├── config.py           Carga y guarda la configuración
│   ├── paths.py            Rutas de %APPDATA%, recursos empaquetados, etc.
│   ├── api/                Clase expuesta a JavaScript (puente con la interfaz)
│   ├── pm3/                Control de la Proxmark3 (cliente, puerto, parsers, emulación)
│   ├── storage/            Base de datos SQLite (esquema, migraciones, consultas)
│   └── ui/                 Interfaz: index.html, css/, js/, assets/
├── tests/                  Tests con pytest (pm3/ con cliente falso, storage/)
├── docs/                   Arquitectura, decisiones y material para la memoria
├── scripts/                Utilidades: compilar Tailwind, generar el .exe
├── installer/              Script de Inno Setup
└── vendor/pm3-client/      Cliente de Iceman para empaquetar (no se sube a git)
```

## Funcionalidades (por fases)

1. **Base**: ventana pywebview que carga `ui/index.html`, navegación lateral,
   pantalla de inicio *dashboard* con datos de ejemplo.
2. **Proxmark3**: portar `pm3_controller.py` a `pm3/` separado en módulos
   (cliente, detección de puerto, parsers, emulación) con tests.
3. **Dashboard real**: estado del dispositivo (conectado, puerto, firmware),
   última medición de antenas, nº de tarjetas por banda, actividad reciente.
4. **Secciones**: antenas (`hw tune`), lectura, base de datos de tarjetas
   (CRUD, búsqueda, exportar/importar JSON), clonado y emulación, terminal.
   Hecho: las seis secciones del menú funcionan — inicio, antenas (`hw tune`
   con histórico), lectura, base de datos (CRUD, búsqueda, exportar/importar),
   clonado y emulación (volcado HF `hf mf dump` / `hf mfu dump`, recuperación de
   claves `hf mf autopwn`, clonado real de MIFARE Classic y emulación `sim`) y
   terminal (lista blanca de comandos de lectura; el resto pide confirmación).
   Lectura enriquecida del volcado: ASCII, claves A/B por sector, bits de acceso
   en palabras y registros NDEF (NTAG/Ultralight). Escritura de bloques en
   **modo laboratorio** (`hf mf wrbl` / `hf mfu wrbl`) para tarjetas propias: ver
   abajo las protecciones del trailer.
   Pendiente para esta fase:
   - Lectura de **HID Prox** en LF (`lf hid clone/sim -r <raw>`); en la fase 2
     solo se reconoce EM410x, igual que el prototipo.
   - Clonado de **Ultralight / NTAG** y de volcados **incompletos** (ahora solo
     se clona MIFARE Classic con el volcado completo).
   - Progreso en vivo y botón de **cancelar** en `autopwn` (ahora es una
     llamada bloqueante con *timeout* amplio).
5. **Distribución**: Tailwind local, PyInstaller, instalador con Inno Setup.

## Normas de trabajo

- Código, comentarios, textos de la interfaz y mensajes de commit **en español**.
- Funciones pequeñas, con nombres claros y *type hints*.
- Cada módulo nuevo de `pm3/` o `storage/` lleva sus tests.
- La interfaz nunca ejecuta comandos directamente: siempre pasa por `api/`.
- Toda acción que **escribe** en una tarjeta (clonar, escribir un bloque) pide
  confirmación, comprobada en la `Api` (no solo en la interfaz).
- Los comandos de clonado, emulación y escritura se generan siempre con
  `pm3/recetas.py` a partir del UID/ID, el índice y los datos (validados como
  hexadecimal y de longitud exacta); nunca se ejecuta una cadena guardada en la
  base de datos ni importada de un archivo.
- La **escritura de bloques** es para **tarjetas propias en laboratorio**. El
  trailer de sector (claves y bits de acceso) se rechaza por defecto; solo se
  permite en modo experto, y aun así se rechaza si los bits de acceso son
  incoherentes (grabarlos puede bloquear el sector para siempre).
- No hacer commits ni push sin que el usuario lo pida.
- Uso legítimo: la herramienta es para auditar tarjetas propias o con
  autorización; mantener ese aviso visible en la app y en la documentación.

## Comandos

```powershell
py -m venv .venv
.venv\Scripts\activate
pip install -r requirements-dev.txt   # dependencias + "pip install -e ." del proyecto
python -m pm3_dashboard               # ejecutar la app (o simplemente: pm3-dashboard)
pytest                                # tests
```

El proyecto se instala en modo editable (`pip install -e .`, incluido en
`requirements-dev.txt`), así que no hace falta poner `PYTHONPATH`: los cambios
en `src/` se ven sin reinstalar. Solo hay que repetir la instalación si cambia
`pyproject.toml` (dependencias, `[project.scripts]`...).
