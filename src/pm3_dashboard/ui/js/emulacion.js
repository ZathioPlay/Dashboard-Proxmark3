/* PM3 Dashboard — sección Clonado y emulación (sobre una tarjeta guardada).
 * Emular usa el comando de recetas.py (vía la Api); clonar reutiliza la ficha de la tarjeta.
 */
'use strict';

const INTERVALO_EMULACION_MS = 1500;
let tarjetaSeleccionada = null;   // {id, nombre, banda, tipo, derivados}
let sondeoEmulacion = null;

async function cargarSeccionClonado() {
    detenerSondeoEmulacion();
    try {
        const r = await api().listar_tarjetas('', '');
        const tarjetas = r.ok ? r.tarjetas : [];
        const select = $('clonado-tarjeta');
        const elegida = select.value;
        select.innerHTML = '<option value="">— elige una tarjeta guardada —</option>' +
            tarjetas.map((t) => `<option value="${Number(t.id)}">${escaparHtml(t.nombre)} · ${escaparHtml(t.tipo)}</option>`).join('');
        mostrar('clonado-vacio', tarjetas.length === 0);
        // Mantiene la selección si la tarjeta sigue existiendo.
        if (elegida && tarjetas.some((t) => String(t.id) === elegida)) {
            select.value = elegida;
        } else {
            mostrar('clonado-detalle', false);
            tarjetaSeleccionada = null;
        }
    } catch (error) {
        mostrar('clonado-vacio', true);
        ponerTexto('clonado-vacio', `No se pudo cargar: ${textoError(error)}`);
    }
}

async function alElegirTarjeta() {
    const id = Number($('clonado-tarjeta').value);
    detenerSondeoEmulacion();
    $('emu-confirmacion').innerHTML = '';
    mostrar('emu-salida', false);
    if (!id) {
        mostrar('clonado-detalle', false);
        tarjetaSeleccionada = null;
        return;
    }
    const r = await api().obtener_tarjeta(id);
    if (!r.ok) {
        mostrar('clonado-detalle', false);
        return;
    }
    tarjetaSeleccionada = r.tarjeta;
    pintarDetalleClonado(r.tarjeta);
    mostrar('clonado-detalle', true);
    actualizarEstadoEmulacion();
}

function pintarDetalleClonado(tarjeta) {
    const d = tarjeta.derivados;
    $('emu-comando').innerHTML = d
        ? htmlComando('Comando de emulación (generado por la app)', d.comando_emulacion)
        : '<p class="text-xs text-amber-200">El tipo o el UID no permiten generar la emulación.</p>';
    $('btn-emular').disabled = !d;

    const esHF = tarjeta.banda === 'hf';
    ponerTexto('clonado-ayuda', esHF
        ? 'El clonado se hace desde la ficha de la tarjeta: leer los bloques y escribirlos en una tarjeta mágica.'
        : 'El clonado directo solo está disponible para tarjetas HF (MIFARE Classic).');
    $('btn-ir-clonar').disabled = !esHF;
}

// ---------------------------------------------------------------- emulación

function pintarEstadoEmulacion(estado) {
    const activa = estado && estado.activa;
    $('emu-estado').classList.toggle('hidden', !activa);
    $('emu-estado').classList.toggle('flex', activa);
    mostrar('btn-detener-emu', activa);
    $('btn-emular').disabled = activa || !(tarjetaSeleccionada && tarjetaSeleccionada.derivados);
    if (estado && estado.salida) {
        mostrar('emu-salida', true);
        ponerTexto('emu-salida', estado.salida);
    }
}

async function actualizarEstadoEmulacion() {
    try {
        const r = await api().estado_emulacion();
        if (r.ok) {
            pintarEstadoEmulacion(r.estado);
            if (!r.estado.activa) {
                detenerSondeoEmulacion();
            }
        }
    } catch (error) {
        detenerSondeoEmulacion();
    }
}

function iniciarSondeoEmulacion() {
    if (!sondeoEmulacion) {
        sondeoEmulacion = setInterval(actualizarEstadoEmulacion, INTERVALO_EMULACION_MS);
    }
}

function detenerSondeoEmulacion() {
    if (sondeoEmulacion) {
        clearInterval(sondeoEmulacion);
        sondeoEmulacion = null;
    }
}

function pedirEmular() {
    if (!tarjetaSeleccionada) {
        return;
    }
    // Confirmación en línea (emular emite señal de RF): aviso de uso legítimo.
    $('emu-confirmacion').innerHTML = `
        <div class="rounded-lg p-3 text-xs ${CLASES_MENSAJE.aviso} space-y-2">
            <p>Se va a <strong class="text-white">emular</strong> «${escaparHtml(tarjetaSeleccionada.nombre)}». Hazlo solo con tarjetas propias o con autorización.</p>
            <div class="flex justify-end gap-2">
                <button data-emu="cancelar" class="px-3 py-1.5 bg-cyber-800 hover:bg-slate-700 border border-slate-700 text-slate-200 text-xs font-semibold rounded-lg">Cancelar</button>
                <button data-emu="confirmar" class="px-3 py-1.5 bg-violet-600 hover:bg-violet-500 text-white text-xs font-semibold rounded-lg">Sí, emular</button>
            </div>
        </div>`;
    $('emu-confirmacion').querySelector('[data-emu="cancelar"]').addEventListener('click', () => ($('emu-confirmacion').innerHTML = ''));
    $('emu-confirmacion').querySelector('[data-emu="confirmar"]').addEventListener('click', emular);
}

async function emular() {
    $('emu-confirmacion').innerHTML = '';
    $('btn-emular').disabled = true;
    try {
        const r = await api().emular_tarjeta(tarjetaSeleccionada.id);
        if (!r.ok) {
            $('emu-confirmacion').innerHTML = `<p class="text-xs text-rose-300">${escaparHtml(r.error)}</p>`;
            $('btn-emular').disabled = false;
            return;
        }
        pintarEstadoEmulacion(r.estado);
        iniciarSondeoEmulacion();
        cargarResumen();
    } catch (error) {
        $('emu-confirmacion').innerHTML = `<p class="text-xs text-rose-300">Error: ${escaparHtml(textoError(error))}</p>`;
        $('btn-emular').disabled = false;
    }
}

async function detenerEmulacion() {
    $('btn-detener-emu').disabled = true;
    try {
        const r = await api().detener_emulacion();
        pintarEstadoEmulacion(r.estado);
    } catch (error) {
        /* se reintenta en el siguiente sondeo */
    } finally {
        detenerSondeoEmulacion();
        $('btn-detener-emu').disabled = false;
    }
}

function irAClonar() {
    if (tarjetaSeleccionada) {
        verTarjeta(tarjetaSeleccionada.id); // reutiliza la ficha con Leer bloques / Clonar (4c)
    }
}

function iniciarSeccionClonado() {
    $('clonado-tarjeta').addEventListener('change', alElegirTarjeta);
    $('btn-emular').addEventListener('click', pedirEmular);
    $('btn-detener-emu').addEventListener('click', detenerEmulacion);
    $('btn-ir-clonar').addEventListener('click', irAClonar);
}
