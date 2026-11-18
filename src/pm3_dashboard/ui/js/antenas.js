/* PM3 Dashboard — sección Antenas: medir y ver el histórico.
 * Reutiliza htmlAntena / ESTILO_ANTENA de inicio.js.
 */
'use strict';

function pintarAntenaSeccion(id, nombre, frecuencia, medida, color) {
    $(id).innerHTML = htmlAntena(nombre, frecuencia, medida, color);
}

function pintarAntenasSeccion(antenas) {
    const lf = antenas ? antenas.lf : { voltios: null, minimo: 20, estado: 'SIN DATOS' };
    const hf = antenas ? antenas.hf : { voltios: null, minimo: 18, estado: 'SIN DATOS' };
    pintarAntenaSeccion('antenas-sec-lf', 'LF', '125 kHz', lf, { texto: 'text-amber-400', barra: 'bg-amber-500' });
    pintarAntenaSeccion('antenas-sec-hf', 'HF', '13.56 MHz', hf, { texto: 'text-cyan-400', barra: 'bg-cyan-500' });
}

function textoAntena(medida) {
    if (typeof medida.voltios !== 'number') {
        return '— ';
    }
    return `${medida.voltios.toFixed(2)} V · ${medida.estado}`;
}

function pintarHistorialAntenas(mediciones) {
    $('antenas-historial').innerHTML = mediciones.map((m) => `
        <tr>
            <td class="py-2 font-mono text-xs text-slate-400">${escaparHtml(m.fecha)}</td>
            <td class="py-2 text-right font-mono text-xs text-amber-300">${escaparHtml(textoAntena(m.lf))}</td>
            <td class="py-2 text-right font-mono text-xs text-cyan-300">${escaparHtml(textoAntena(m.hf))}</td>
        </tr>`).join('');
    mostrar('antenas-historial-vacio', mediciones.length === 0);
}

async function cargarAntenas() {
    try {
        const [resumen, historial] = await Promise.all([api().obtener_resumen(), api().listar_mediciones(10)]);
        pintarAntenasSeccion(resumen.ok ? resumen.antenas : null);
        pintarHistorialAntenas(historial.ok ? historial.mediciones : []);
    } catch (error) {
        mostrar('antenas-error-seccion', true);
        ponerTexto('antenas-error-seccion', `No se pudo cargar: ${textoError(error)}`);
    }
}

async function medirAntenasSeccion() {
    mostrar('antenas-error-seccion', false);
    await conBotonOcupado('btn-medir-antenas', 'btn-medir-antenas-texto', 'Midiendo… (hasta 45 s)', async () => {
        try {
            const r = await api().medir_antenas();
            if (!r.ok) {
                mostrar('antenas-error-seccion', true);
                ponerTexto('antenas-error-seccion', r.error);
            }
            await cargarAntenas();
            cargarResumen(); // actualiza también el panel de inicio
        } catch (error) {
            mostrar('antenas-error-seccion', true);
            ponerTexto('antenas-error-seccion', `Error al medir: ${textoError(error)}`);
        }
    });
}

function iniciarSeccionAntenas() {
    $('btn-medir-antenas').addEventListener('click', medirAntenasSeccion);
}
