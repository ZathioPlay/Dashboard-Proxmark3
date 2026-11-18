# PM3 Dashboard

Aplicación de escritorio para usar una **Proxmark3** (firmware Iceman/RRG) desde
una interfaz gráfica, sin escribir comandos. Se instala en el PC de cada usuario
y funciona sin internet y sin servidor.

Trabajo de Fin de Grado de ASIR — Daniel Pérez y Pedro Smith.

> Herramienta de auditoría para tarjetas RFID/NFC **propias o con autorización**.

## Estado

En desarrollo. Evolución del prototipo web `TFG-proxmark3/rfid-clone`.

## Funcionalidades previstas

- Panel de inicio con el estado de la Proxmark3 y resumen de tarjetas
- Diagnóstico de antenas LF/HF
- Lectura de tarjetas de alta (13,56 MHz) y baja frecuencia (125 kHz)
- Base de datos local de tarjetas, con búsqueda y exportación
- Clonado y emulación
- Terminal para comandos avanzados

## Desarrollo

```powershell
py -m venv .venv
.venv\Scripts\activate
pip install -r requirements-dev.txt
python -m pm3_dashboard
pytest
```

Estructura y decisiones técnicas: ver [CLAUDE.md](CLAUDE.md) y [docs/](docs/).

## Licencia

El cliente de Iceman (proxmark3) es software libre bajo GPLv3. Si se distribuye
junto a esta aplicación, se incluye su licencia y la referencia a su código fuente:
https://github.com/RfidResearchGroup/proxmark3
