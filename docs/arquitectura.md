# Arquitectura

```
┌──────────────────── Ventana de la aplicación (pywebview) ───────────────────┐
│  Interfaz: HTML + JS + Tailwind (src/pm3_dashboard/ui)                      │
│        │  window.pywebview.api.metodo()                                     │
│        ▼                                                                    │
│  api/  ── puente: valida y reparte las peticiones                           │
│     ├──► pm3/      ── lanza el cliente de Iceman ──► USB ──► Proxmark3      │
│     └──► storage/  ── SQLite en %APPDATA%\PM3-Dashboard\pm3.db              │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Por qué así

- **Sin servidor ni puertos**: la interfaz habla con Python directamente a
  través de pywebview. Desaparecen los problemas de "puerto 8000 en uso".
- **Instalable**: PyInstaller genera un `.exe` e Inno Setup el instalador.
- **Funciona sin internet**: Tailwind compilado y fuentes incluidas.
- **Datos del usuario fuera de la carpeta del programa** (`%APPDATA%`), para
  que actualizar o desinstalar no borre sus tarjetas.

## Diferencias con el prototipo web (TFG-proxmark3/rfid-clone)

| Prototipo web | PM3 Dashboard |
|---|---|
| Servidor HTTP local en el puerto 8000 | Ventana propia, sin servidor |
| Se abre en el navegador | Programa instalado con acceso directo |
| Login con usuarios | App local de un solo usuario |
| Tailwind desde CDN (requiere internet) | Tailwind compilado localmente |
