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
