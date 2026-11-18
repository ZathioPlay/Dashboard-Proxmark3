"""Tests de la Api con el cliente falso de pm3 y una base de datos temporal."""

from __future__ import annotations

import json
import threading
from datetime import date
from pathlib import Path

import pytest

from pm3_dashboard.api import Api
from pm3_dashboard.config import ConfigPm3
from pm3_dashboard.pm3 import ClientePm3, Proxmark3
from pm3_dashboard.storage import BaseDatos, actividad, tarjetas
from pm3_dashboard.storage.actividad import TipoActividad
from pm3_dashboard.storage.tarjetas import NuevaTarjeta
from tests.pm3.falsos import LanzadorFalso, cargar_muestra


class DialogosFalsos:
    """Diálogos de archivo falsos: devuelven la ruta preparada (None = el usuario cancela)."""

    def __init__(self) -> None:
        self.ruta_guardar: Path | None = None
        self.ruta_abrir: Path | None = None
        self.nombre_sugerido = ""

    def elegir_guardar(self, nombre_sugerido: str) -> Path | None:
        self.nombre_sugerido = nombre_sugerido
        return self.ruta_guardar

    def elegir_abrir(self) -> Path | None:
        return self.ruta_abrir


class Entorno:
    """Proxmark falsa (con o sin dispositivo) + BD temporal + Api."""

    def __init__(self, tmp_path: Path) -> None:
        ejecutable = tmp_path / "cliente" / "proxmark3.exe"
        ejecutable.parent.mkdir()
        ejecutable.touch()
        config = ConfigPm3(ruta_cliente=str(ejecutable), puerto="auto")
        self.conectada = True
        self.lanzador = LanzadorFalso()
        self.lanzador.responder("hw version", stdout=cargar_muestra("hw_version"))
        self.lanzador.responder("hw tune", stdout=cargar_muestra("hw_tune_ok"))
        cliente = ClientePm3(
            cargar=lambda: config,
            lanzador=self.lanzador,
            detectar=lambda _: "COM5" if self.conectada else None,
            presencia=lambda _: "COM5" if self.conectada else None,
            carpeta_trabajo=tmp_path / "dumps",
        )
        self.bd = BaseDatos(tmp_path / "pm3.db")
        self.proxmark = Proxmark3(cliente=cliente, hoy=lambda: "2026-11-18", espera_emulacion=0)
        self.dialogos = DialogosFalsos()
        self.api = Api(proxmark=self.proxmark, bd=self.bd, dialogos=self.dialogos, hoy=lambda: date(2026, 11, 18))

    def descripciones(self) -> list[str]:
        return [e.descripcion for e in actividad.ultimas(self.bd, 50)]


@pytest.fixture
def entorno(tmp_path: Path) -> Entorno:
    return Entorno(tmp_path)


# ---------------------------------------------------------------- resumen


def test_resumen_con_bd_vacia(entorno: Entorno) -> None:
    resumen = entorno.api.obtener_resumen()

    assert resumen == {
        "ok": True,
        "tarjetas": {"total": 0, "hf": 0, "lf": 0},
        "antenas": None,
        "actividad": [],
    }


def test_resumen_no_usa_la_proxmark(entorno: Entorno) -> None:
    entorno.api.obtener_resumen()

    assert entorno.lanzador.llamadas == []


def test_resumen_con_error_de_bd_no_lanza_excepciones(tmp_path: Path) -> None:
    carpeta = tmp_path / "carpeta.db"
    carpeta.mkdir()
    api = Api(proxmark=Proxmark3(cliente=ClientePm3(lanzador=LanzadorFalso())), bd=BaseDatos(carpeta))

    resumen = api.obtener_resumen()

    assert resumen["ok"] is False
    assert "No se pudo abrir la base de datos" in resumen["error"]


# ---------------------------------------------------------------- estado


def test_estado_conectado(entorno: Entorno) -> None:
    estado = entorno.api.obtener_estado_dispositivo()

    assert estado["ok"] and estado["conectado"]
    assert estado["puerto"] == "COM5"
    assert estado["dispositivo"] == "RDV4"
    assert estado["version_firmware"] == "v4.18994-48-gd2e0a3b4d"
    assert estado["aviso_version"] == ""
    assert entorno.descripciones() == ["Proxmark3 conectada en COM5 (firmware v4.18994-48-gd2e0a3b4d)"]


def test_sin_proxmark_mensaje_claro_y_datos_de_la_bd(entorno: Entorno) -> None:
    entorno.conectada = False
    actividad.registrar(entorno.bd, TipoActividad.LECTURA, "lectura anterior")

    estado = entorno.api.obtener_estado_dispositivo()
    resumen = entorno.api.obtener_resumen()

    assert estado["ok"] and not estado["conectado"]
    assert "No se detecta ninguna Proxmark3" in estado["mensaje"]
    assert resumen["ok"]
    assert [e["descripcion"] for e in resumen["actividad"]] == ["lectura anterior"]
    assert entorno.lanzador.llamadas == []


def test_aviso_si_las_versiones_no_coinciden(entorno: Entorno) -> None:
    entorno.lanzador.responder("hw version", stdout=cargar_muestra("hw_version_distinta"))

    estado = entorno.api.obtener_estado_dispositivo()

    assert estado["versiones_coinciden"] is False
    assert "cliente (v4.19552) no coincide con la del firmware (v4.17140)" in estado["aviso_version"]


def test_ocupada_mantiene_el_ultimo_estado(entorno: Entorno) -> None:
    entorno.api.obtener_estado_dispositivo()
    assert entorno.proxmark.iniciar_emulacion("lf em 410x sim --id 0F0368568B").ok

    # Mientras emula, 'hw version' no puede usar el puerto.
    estado = entorno.api.obtener_estado_dispositivo()

    entorno.proxmark.detener_emulacion()
    assert estado["conectado"] and estado["ocupado"]
    assert estado["dispositivo"] == "RDV4"
    assert "Proxmark3 desconectada" not in entorno.descripciones()


def test_el_evento_de_conexion_solo_se_registra_al_cambiar(entorno: Entorno) -> None:
    entorno.api.obtener_estado_dispositivo()
    entorno.api.obtener_estado_dispositivo()
    entorno.conectada = False
    entorno.api.obtener_estado_dispositivo()
    entorno.api.obtener_estado_dispositivo()

    assert entorno.descripciones() == [
        "Proxmark3 desconectada",
        "Proxmark3 conectada en COM5 (firmware v4.18994-48-gd2e0a3b4d)",
    ]


def test_arrancar_sin_proxmark_no_registra_nada(entorno: Entorno) -> None:
    entorno.conectada = False
    entorno.api.obtener_estado_dispositivo()

    assert entorno.descripciones() == []


# ---------------------------------------------------------------- comprobación periódica


def test_comprobacion_periodica_detecta_cambios(entorno: Entorno) -> None:
    primera = entorno.api.comprobar_conexion()
    assert primera["presente"] and primera["cambio"] is None  # primera vez: solo línea base

    assert entorno.api.comprobar_conexion()["cambio"] is None

    entorno.conectada = False
    desaparece = entorno.api.comprobar_conexion()
    assert desaparece["cambio"] == "desaparece"
    assert desaparece["estado"]["conectado"] is False
    assert "Se ha desconectado" in desaparece["estado"]["mensaje"]

    entorno.conectada = True
    assert entorno.api.comprobar_conexion()["cambio"] == "aparece"
    assert entorno.lanzador.llamadas == []  # nunca lanza comandos


def test_la_linea_base_se_fija_al_pedir_el_estado(entorno: Entorno) -> None:
    entorno.conectada = False
    entorno.api.obtener_estado_dispositivo()
    entorno.conectada = True

    # La Proxmark se conectó después de cargar: la primera comprobación ya lo detecta.
    assert entorno.api.comprobar_conexion()["cambio"] == "aparece"


# ---------------------------------------------------------------- antenas


def test_medir_antenas_guarda_y_registra(entorno: Entorno) -> None:
    resultado = entorno.api.medir_antenas()

    assert resultado["ok"]
    assert resultado["medicion"]["lf"] == {"voltios": 44.28, "estado": "OK", "minimo": 20.0}
    resumen = entorno.api.obtener_resumen()
    assert resumen["antenas"]["hf"]["voltios"] == 31.40
    assert resumen["actividad"][0]["tipo"] == "antenas"
    assert resumen["actividad"][0]["descripcion"] == (
        "Medición de antenas: LF 44.28 V (OK), HF 31.40 V (OK)"
    )


def test_medir_antenas_con_error_no_guarda_nada(entorno: Entorno) -> None:
    entorno.conectada = False

    resultado = entorno.api.medir_antenas()

    assert not resultado["ok"]
    assert "No se detecta ninguna Proxmark3" in resultado["error"]
    resumen = entorno.api.obtener_resumen()
    assert resumen["antenas"] is None
    assert resumen["actividad"] == []


# ---------------------------------------------------------------- generales


def test_todo_se_puede_pasar_a_json(entorno: Entorno) -> None:
    respuestas = [
        entorno.api.obtener_estado_dispositivo(),
        entorno.api.medir_antenas(),
        entorno.api.comprobar_conexion(),
        entorno.api.obtener_resumen(),
    ]

    json.dumps(respuestas)


def test_solo_se_exponen_los_metodos_previstos(entorno: Entorno) -> None:
    """pywebview expone a JavaScript todo lo público: no debe haber nada más."""
    publicos = {nombre for nombre in dir(entorno.api) if not nombre.startswith("_")}

    assert publicos == {
        "obtener_resumen",
        "obtener_estado_dispositivo",
        "comprobar_conexion",
        "medir_antenas",
        "escanear",
        "guardar_tarjeta",
        "listar_tarjetas",
        "obtener_tarjeta",
        "editar_tarjeta",
        "borrar_tarjeta",
        "exportar_tarjetas",
        "importar_tarjetas",
    }


# ================================================================ lectura


def _escanear_1k(entorno: Entorno) -> dict:
    entorno.lanzador.responder("hf search", stdout=cargar_muestra("hf_search_1k"))
    return entorno.api.escanear("auto")


def test_escanear_devuelve_la_tarjeta_con_derivados(entorno: Entorno) -> None:
    resultado = _escanear_1k(entorno)

    assert resultado["ok"]
    tarjeta = resultado["tarjeta"]
    assert tarjeta["tipo"] == "MIFARE Classic 1K"
    assert tarjeta["uid"] == "5A 3E 7C 1B"
    assert tarjeta["derivados"]["comando_emulacion"] == "hf mf sim --1k -u 5A3E7C1B"
    assert tarjeta["id_lectura"] == 1
    assert tarjeta["guardadas_con_mismo_uid"] == []
    assert entorno.descripciones() == ["Leída MIFARE Classic 1K (UID 5A 3E 7C 1B)"]


def test_escanear_lf_usa_el_tipo_canonico(entorno: Entorno) -> None:
    entorno.lanzador.responder("hf search", stdout=cargar_muestra("hf_search_vacio"))
    entorno.lanzador.responder("lf search", stdout=cargar_muestra("lf_search_em410x"))

    resultado = entorno.api.escanear("auto")

    assert resultado["tarjeta"]["tipo"] == "EM410x"
    assert entorno.descripciones() == ["Leída EM410x (ID 0F 03 68 56 8B)"]


def test_escanear_sin_tarjeta(entorno: Entorno) -> None:
    entorno.lanzador.responder("hf search", stdout=cargar_muestra("hf_search_vacio"))
    entorno.lanzador.responder("lf search", stdout=cargar_muestra("lf_search_vacio"))

    resultado = entorno.api.escanear("auto")

    assert not resultado["ok"]
    assert "No se detectó ninguna tarjeta" in resultado["error"]
    assert entorno.descripciones() == []


def test_escanear_con_banda_no_texto(entorno: Entorno) -> None:
    resultado = entorno.api.escanear(123)  # type: ignore[arg-type]

    assert not resultado["ok"]
    assert entorno.lanzador.llamadas == []


def test_guardar_la_lectura(entorno: Entorno) -> None:
    lectura = _escanear_1k(entorno)["tarjeta"]

    resultado = entorno.api.guardar_tarjeta(lectura["id_lectura"], "  Tarjeta oficina ", "notas")

    assert resultado["ok"]
    guardada = entorno.api.obtener_tarjeta(resultado["id"])["tarjeta"]
    assert guardada["nombre"] == "Tarjeta oficina"
    assert guardada["tipo"] == "MIFARE Classic 1K"
    assert guardada["salida"].startswith("[usb] pm3 --> hf search")
    assert guardada["fecha"] == "2026-11-18"
    assert entorno.descripciones()[0] == "Guardada «Tarjeta oficina» (MIFARE Classic 1K, UID 5A 3E 7C 1B)"


def test_guardar_dos_veces_la_misma_lectura_no_duplica(entorno: Entorno) -> None:
    lectura = _escanear_1k(entorno)["tarjeta"]
    assert entorno.api.guardar_tarjeta(lectura["id_lectura"], "Una", "")["ok"]

    segunda = entorno.api.guardar_tarjeta(lectura["id_lectura"], "Otra", "")

    assert not segunda["ok"]
    assert "ya no está disponible" in segunda["error"]
    assert entorno.api.obtener_resumen()["tarjetas"]["total"] == 1


def test_guardar_una_lectura_antigua(entorno: Entorno) -> None:
    primera = _escanear_1k(entorno)["tarjeta"]
    _escanear_1k(entorno)

    resultado = entorno.api.guardar_tarjeta(primera["id_lectura"], "Vieja", "")

    assert not resultado["ok"]
    assert "ya no está disponible" in resultado["error"]


def test_guardar_sin_haber_escaneado(entorno: Entorno) -> None:
    assert not entorno.api.guardar_tarjeta(1, "x", "")["ok"]


def test_guardar_con_nombre_no_valido_no_pierde_la_lectura(entorno: Entorno) -> None:
    lectura = _escanear_1k(entorno)["tarjeta"]

    fallo = entorno.api.guardar_tarjeta(lectura["id_lectura"], "   ", "")
    correcto = entorno.api.guardar_tarjeta(lectura["id_lectura"], "Ahora sí", "")

    assert not fallo["ok"] and "nombre no puede estar vacío" in fallo["error"]
    assert correcto["ok"]


@pytest.mark.parametrize("id_lectura", ["1", 1.0, True, None])
def test_guardar_con_id_de_tipo_incorrecto(entorno: Entorno, id_lectura: object) -> None:
    _escanear_1k(entorno)

    resultado = entorno.api.guardar_tarjeta(id_lectura, "x", "")  # type: ignore[arg-type]

    assert not resultado["ok"]
    assert "número entero" in resultado["error"]


def test_escaneos_simultaneos_no_se_pisan(entorno: Entorno) -> None:
    """Con muchos escaneos a la vez, cada id_lectura es único y solo el último se puede guardar."""
    entorno.lanzador.responder("hf search", stdout=cargar_muestra("hf_search_1k"))
    resultados: list[dict] = []
    hilos = [threading.Thread(target=lambda: resultados.append(entorno.api.escanear("hf"))) for _ in range(10)]
    for hilo in hilos:
        hilo.start()
    for hilo in hilos:
        hilo.join(10)

    ids = sorted(r["tarjeta"]["id_lectura"] for r in resultados if r["ok"])
    assert ids == list(range(1, len(ids) + 1))  # sin repetidos
    guardados = [entorno.api.guardar_tarjeta(i, f"t{i}", "")["ok"] for i in ids]
    assert guardados.count(True) == 1
    assert guardados[-1] is True


def test_aviso_si_el_uid_ya_esta_guardado(entorno: Entorno) -> None:
    lectura = _escanear_1k(entorno)["tarjeta"]
    entorno.api.guardar_tarjeta(lectura["id_lectura"], "Tarjeta oficina", "")

    otra = _escanear_1k(entorno)["tarjeta"]

    assert otra["guardadas_con_mismo_uid"] == ["Tarjeta oficina"]


# ================================================================ base de datos


def _guardar(entorno: Entorno, nombre: str, banda: str = "lf", tipo: str = "EM410x", uid: str = "0F0368568B") -> int:
    return tarjetas.insertar_tarjeta(entorno.bd, NuevaTarjeta(nombre=nombre, banda=banda, tipo=tipo, uid=uid))


def test_listar_con_derivados_generados(entorno: Entorno) -> None:
    _guardar(entorno, "Llavero")
    _guardar(entorno, "Oficina", "hf", "MIFARE Classic 4K", "9E2B44C0")

    resultado = entorno.api.listar_tarjetas("", "")

    assert resultado["ok"]
    por_nombre = {t["nombre"]: t for t in resultado["tarjetas"]}
    assert por_nombre["Llavero"]["derivados"]["comando_clonado"] == "lf em 410x clone --id 0F0368568B"
    assert por_nombre["Oficina"]["derivados"]["comando_emulacion"] == "hf mf sim --4k -u 9E2B44C0"
    assert [t["nombre"] for t in entorno.api.listar_tarjetas("llav", "lf")["tarjetas"]] == ["Llavero"]


def test_listar_con_banda_no_valida(entorno: Entorno) -> None:
    resultado = entorno.api.listar_tarjetas("", "todas")

    assert not resultado["ok"]
    assert "banda desconocida" in resultado["error"]


def test_los_derivados_nunca_se_leen_de_la_bd(entorno: Entorno) -> None:
    id_tarjeta = _guardar(entorno, "Llavero")
    # Alguien edita la BD a mano: tipo antiguo (fase 2) y UID con un comando.
    with entorno.bd.conexion() as con:
        con.execute("UPDATE tarjetas SET tipo = 'ISO14443-A (HF)' WHERE id = ?", (id_tarjeta,))
    assert entorno.api.obtener_tarjeta(id_tarjeta)["tarjeta"]["derivados"] is None

    with entorno.bd.conexion() as con:
        con.execute("UPDATE tarjetas SET tipo = 'EM410x', uid = '0F0368568B; lf t55xx wipe' WHERE id = ?", (id_tarjeta,))
    tarjeta = entorno.api.obtener_tarjeta(id_tarjeta)["tarjeta"]
    assert tarjeta["derivados"] is None  # sin comandos antes que un comando manipulado


def test_editar_tarjeta(entorno: Entorno) -> None:
    id_tarjeta = _guardar(entorno, "Llavero")

    assert entorno.api.editar_tarjeta(id_tarjeta, "Portal", "notas nuevas")["ok"]
    tarjeta = entorno.api.obtener_tarjeta(id_tarjeta)["tarjeta"]
    assert (tarjeta["nombre"], tarjeta["notas"]) == ("Portal", "notas nuevas")

    fallo = entorno.api.editar_tarjeta(id_tarjeta, "", "")
    assert not fallo["ok"] and "nombre no puede estar vacío" in fallo["error"]
    assert not entorno.api.editar_tarjeta(9999, "x", "")["ok"]


def test_borrar_tarjeta(entorno: Entorno) -> None:
    id_tarjeta = _guardar(entorno, "Llavero")

    assert entorno.api.borrar_tarjeta(id_tarjeta)["ok"]
    assert not entorno.api.obtener_tarjeta(id_tarjeta)["ok"]
    assert not entorno.api.borrar_tarjeta(id_tarjeta)["ok"]
    assert entorno.descripciones() == ["Borrada «Llavero» (EM410x, 0F 03 68 56 8B)"]


# ================================================================ exportar / importar


def test_exportar(entorno: Entorno, tmp_path: Path) -> None:
    _guardar(entorno, "Llavero")
    entorno.dialogos.ruta_guardar = tmp_path / "copia.json"

    resultado = entorno.api.exportar_tarjetas()

    assert resultado == {"ok": True, "cantidad": 1, "ruta": str(tmp_path / "copia.json")}
    assert entorno.dialogos.nombre_sugerido == "tarjetas_2026-11-18.json"
    assert json.loads((tmp_path / "copia.json").read_text(encoding="utf-8"))["tarjetas"][0]["nombre"] == "Llavero"
    assert entorno.descripciones() == ["1 tarjeta exportada a copia.json"]


def test_exportar_cancelado(entorno: Entorno) -> None:
    assert entorno.api.exportar_tarjetas() == {"ok": False, "cancelado": True}
    assert entorno.descripciones() == []


def test_exportar_a_una_ruta_no_valida(entorno: Entorno, tmp_path: Path) -> None:
    entorno.dialogos.ruta_guardar = tmp_path / "no_existe" / "copia.json"

    resultado = entorno.api.exportar_tarjetas()

    assert not resultado["ok"] and "No se pudo escribir" in resultado["error"]


def test_importar_con_resumen(entorno: Entorno, tmp_path: Path) -> None:
    archivo = tmp_path / "entrada.json"
    archivo.write_text(
        json.dumps({
            "formato": "pm3-dashboard/tarjetas",
            "version": 1,
            "tarjetas": [
                {"nombre": "Buena", "banda": "lf", "tipo": "EM410x", "uid": "0F0368568B", "clone_cmd": "lf t55xx wipe"},
                {"nombre": "Mala", "banda": "lf", "tipo": "EM410x", "uid": "0F0368568B; hw tune"},
            ],
        }),
        encoding="utf-8-sig",  # con BOM, como guardan algunos editores de Windows
    )
    entorno.dialogos.ruta_abrir = archivo

    resultado = entorno.api.importar_tarjetas()

    assert resultado["ok"]
    assert resultado["archivo"] == "entrada.json"
    assert resultado["importadas"] == 1
    assert resultado["rechazadas"][0]["nombre"] == "Mala"
    assert "hexadecimal" in resultado["rechazadas"][0]["motivo"]
    assert resultado["campos_ignorados"] == ["clone_cmd"]
    assert entorno.descripciones() == ["1 tarjeta importada desde entrada.json (1 rechazada)"]
    json.dumps(resultado)


def test_importar_archivo_no_valido(entorno: Entorno, tmp_path: Path) -> None:
    archivo = tmp_path / "malo.json"
    archivo.write_text("no es json", encoding="utf-8")
    entorno.dialogos.ruta_abrir = archivo

    resultado = entorno.api.importar_tarjetas()

    assert not resultado["ok"] and "no es un JSON válido" in resultado["error"]
    assert entorno.descripciones() == []


def test_importar_archivo_binario(entorno: Entorno, tmp_path: Path) -> None:
    archivo = tmp_path / "binario.json"
    archivo.write_bytes(b"\xff\xfe\x00\x81\x82")
    entorno.dialogos.ruta_abrir = archivo

    resultado = entorno.api.importar_tarjetas()

    assert not resultado["ok"] and "UTF-8" in resultado["error"]


def test_importar_cancelado(entorno: Entorno) -> None:
    assert entorno.api.importar_tarjetas() == {"ok": False, "cancelado": True}
