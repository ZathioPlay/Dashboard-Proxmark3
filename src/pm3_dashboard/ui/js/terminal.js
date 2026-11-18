/* PM3 Dashboard — sección Terminal: enviar comandos al cliente de Iceman.
 * Solo lectura/diagnóstico corre directo; cualquier otro comando lo confirma la Api.
 */
'use strict';

const historialTerminal = [];
let posicionHistorial = 0;   // apunta "después del último"

function anadirBloqueTerminal(comando, salida, tipo) {
    const salidaEl = $('terminal-salida');
    const bloque = document.createElement('div');
    const color = tipo === 'error' ? 'text-rose-300' : 'text-slate-300';
    bloque.innerHTML = `
        <div class="text-cyan-400">pm3 &gt; ${escaparHtml(comando)}</div>
        ${salida ? `<pre class="salida-cliente ${color} mt-0.5">${escaparHtml(salida)}</pre>` : ''}`;
    salidaEl.appendChild(bloque);
    salidaEl.scrollTop = salidaEl.scrollHeight;
}

async function correrComandoTerminal(comando, confirmado) {
    $('btn-terminal').disabled = true;
    try {
        const r = await api().ejecutar_terminal(comando, confirmado);
        if (r.requiere_confirmacion) {
            pedirConfirmacionTerminal(comando);
            return;
        }
        if (r.es_emulacion) {
            anadirBloqueTerminal(comando, `${r.error} (menú «Clonado y emulación»)`, 'error');
            return;
        }
        anadirBloqueTerminal(comando, r.ok ? (r.salida || '(sin salida)') : r.error, r.ok ? 'ok' : 'error');
    } catch (error) {
        anadirBloqueTerminal(comando, `Error: ${textoError(error)}`, 'error');
    } finally {
        $('btn-terminal').disabled = false;
        $('terminal-entrada').focus();
    }
}

// Confirmación en línea (encima de la entrada) para comandos que no son de lectura.
function pedirConfirmacionTerminal(comando) {
    const caja = $('terminal-confirmacion');
    caja.innerHTML = `
        <div class="rounded-xl p-3 text-xs ${CLASES_MENSAJE.aviso} space-y-2">
            <p><code class="text-white">${escaparHtml(comando)}</code> no es un comando de lectura/diagnóstico. Puede <strong class="text-white">escribir o borrar</strong> datos de la tarjeta.</p>
            <p>Ejecútalo solo con tarjetas propias o con autorización.</p>
            <div class="flex justify-end gap-2">
                <button data-term="cancelar" class="px-3 py-1.5 bg-cyber-800 hover:bg-slate-700 border border-slate-700 text-slate-200 font-semibold rounded-lg">Cancelar</button>
                <button data-term="confirmar" class="px-3 py-1.5 bg-rose-600 hover:bg-rose-500 text-white font-semibold rounded-lg">Ejecutar de todos modos</button>
            </div>
        </div>`;
    caja.querySelector('[data-term="cancelar"]').addEventListener('click', () => {
        caja.innerHTML = '';
        anadirBloqueTerminal(comando, 'Cancelado.', 'error');
    });
    caja.querySelector('[data-term="confirmar"]').addEventListener('click', () => {
        caja.innerHTML = '';
        correrComandoTerminal(comando, true);
    });
}

function enviarTerminal(evento) {
    evento.preventDefault();
    const entrada = $('terminal-entrada');
    const comando = entrada.value.trim();
    if (!comando) {
        return;
    }
    $('terminal-confirmacion').innerHTML = '';
    historialTerminal.push(comando);
    posicionHistorial = historialTerminal.length;
    entrada.value = '';
    correrComandoTerminal(comando, false);
}

// Historial con flechas ↑ / ↓.
function navegarHistorial(evento) {
    if (evento.key !== 'ArrowUp' && evento.key !== 'ArrowDown') {
        return;
    }
    if (!historialTerminal.length) {
        return;
    }
    evento.preventDefault();
    if (evento.key === 'ArrowUp') {
        posicionHistorial = Math.max(0, posicionHistorial - 1);
    } else {
        posicionHistorial = Math.min(historialTerminal.length, posicionHistorial + 1);
    }
    const entrada = $('terminal-entrada');
    entrada.value = posicionHistorial < historialTerminal.length ? historialTerminal[posicionHistorial] : '';
    // Cursor al final.
    requestAnimationFrame(() => entrada.setSelectionRange(entrada.value.length, entrada.value.length));
}

function iniciarSeccionTerminal() {
    $('terminal-form').addEventListener('submit', enviarTerminal);
    $('terminal-entrada').addEventListener('keydown', navegarHistorial);
}
