# Registro de decisiones

Anotar aquí cada decisión importante: fecha, qué se decidió y por qué.
Sirve directamente para el apartado de justificación de la memoria.

| Fecha | Decisión | Motivo |
|---|---|---|
| 2026-11-18 | Pasar de web local a aplicación de escritorio tipo dashboard | Cada usuario usa su propia Proxmark en su PC; no hace falta servidor |
| 2026-11-18 | pywebview en lugar de servidor HTTP | Se reutiliza el HTML existente y se eliminan puertos y problemas de procesos duplicados |
| 2026-11-18 | Sin login en la v1 | App local de un solo usuario |
| 2026-11-18 | Servidor (torre vieja) como fase opcional | El TFG no depende de él; posible sincronización o copias de seguridad al final |
| 2026-11-18 | Tailwind y fuentes por CDN solo en la fase 1 | Avanzar rápido con la interfaz; en la fase 5 se compila Tailwind en local y se incluyen las fuentes para que funcione sin internet |
| 2026-11-18 | Cliente de Iceman en `pm3-client\` junto al `.exe`, instalado por Inno Setup, y no dentro del `.exe` de PyInstaller | Arranque más rápido (PyInstaller no tiene que descomprimir el cliente y sus DLL en cada ejecución); se puede actualizar el cliente sin recompilar la app; el cliente (GPLv3) queda como programa separado, con su licencia, en lugar de mezclado dentro de nuestro ejecutable |
| 2026-11-18 | Las dependencias de la `Api` (Proxmark3, base de datos) se guardan en atributos privados (`self._proxmark`, `self._bd`) | pywebview expone a JavaScript todos los atributos públicos de la `Api`, incluidos los objetos anidados: con `self.proxmark` la interfaz podría llamar a `pywebview.api.proxmark.ejecutar(...)` y saltarse la `Api`. Los nombres que empiezan por `_` no se exponen |
| 2026-11-18 | SQLite con una conexión por operación, `journal_mode=WAL` y `busy_timeout` de 5 s | pywebview ejecuta cada llamada de JavaScript en un hilo distinto; así varias escrituras simultáneas esperan su turno en lugar de fallar con "database is locked" |
| 2026-11-18 | Detección automática del cliente de Iceman: config.json → incluido con la app → `~/proxmark3` → ProxSpace → PATH | Si el usuario ya tiene Iceman instalado, la app lo usa sin configurar nada. config.json tiene prioridad absoluta y, si apunta a una ruta que no existe, se da error en vez de usar otro cliente sin avisar (podría no coincidir con el firmware). La interfaz muestra siempre la ruta completa del binario y su origen |
| 2026-11-18 | El PATH se recorre a mano en vez de usar `shutil.which` | En Windows, `shutil.which` busca primero en el directorio actual: un `proxmark3.exe` en la carpeta de trabajo se ejecutaría en lugar del bueno. Se ignoran las entradas vacías o relativas |
| 2026-11-18 | Un cliente detectado en ProxSpace añade al PATH las DLL de su MSYS2 | Sin ellas no arranca (en el prototipo había que configurarlas a mano en `extra_path`) |
| 2026-11-18 | La base de datos no guarda comandos de clonado/emulación ni datos derivados (tarjeta destino, seguridad) | Se regeneran siempre con `pm3/recetas.py` a partir del UID/ID y el tipo; así nunca se ejecuta un comando guardado o importado |
