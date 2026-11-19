/* PM3 Dashboard — utilidades comunes a todas las secciones.
 * La interfaz nunca ejecuta comandos: todo pasa por window.pywebview.api.
 * pywebview ejecuta cada llamada en un hilo de Python, así que la ventana no se congela.
 */
'use strict';

// ==================== DOM ====================

function $(id) {
    return document.getElementById(id);
}

/** Escapa texto para meterlo en HTML, también dentro de atributos (comillas incluidas). */
function escaparHtml(texto) {
    return String(texto ?? '')
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;');
}

function ponerTexto(id, texto) {
    $(id).textContent = texto;
}

function mostrar(id, visible) {
    $(id).classList.toggle('hidden', !visible);
}

/** Muestra un mensaje en una caja (tipo: 'ok' | 'error' | 'aviso'); texto vacío = ocultar. */
const CLASES_MENSAJE = {
    ok: 'bg-emerald-950/30 border border-emerald-500/40 text-emerald-200',
    error: 'bg-rose-950/30 border border-rose-500/40 text-rose-200',
    aviso: 'bg-amber-950/30 border border-amber-500/40 text-amber-200',
};

function mostrarMensaje(id, texto, tipo = 'ok') {
    const caja = $(id);
    const base = caja.dataset.claseBase ?? (caja.dataset.claseBase = caja.className.replace(/\bhidden\b/, '').trim());
    caja.className = `${base} ${CLASES_MENSAJE[tipo]}`;
    caja.textContent = texto;
    mostrar(id, Boolean(texto));
}

// ==================== API ====================

function api() {
    return window.pywebview.api;
}

/** Copia texto al portapapeles. Usa la API moderna y, si no está (WebView2 sin
 *  permiso de clipboard), recurre a un textarea temporal. Devuelve true si copió. */
async function copiarTexto(texto) {
    try {
        if (navigator.clipboard && navigator.clipboard.writeText) {
            await navigator.clipboard.writeText(texto);
            return true;
        }
    } catch (error) {
        /* cae al método de reserva */
    }
    try {
        const area = document.createElement('textarea');
        area.value = texto;
        area.style.position = 'fixed';
        area.style.opacity = '0';
        document.body.appendChild(area);
        area.select();
        const ok = document.execCommand('copy');
        document.body.removeChild(area);
        return ok;
    } catch (error) {
        return false;
    }
}

/** (1, 'importada') -> '1 tarjeta importada'; (3, 'importada') -> '3 tarjetas importadas'. */
function cantidadTarjetas(n, participio) {
    const plural = n === 1 ? '' : 's';
    return `${n} tarjeta${plural} ${participio}${plural}`;
}

function textoError(error) {
    return (error && error.message) || String(error);
}

/** Texto de un fallo de la Api: el mensaje y, si existe, la salida del cliente de Iceman.
 *  Para contextos que ya escapan (p. ej. dentro de un <pre> con escaparHtml). */
function mensajeFallo(r) {
    let texto = r.error || 'El comando falló.';
    if (r.salida && r.salida.trim()) {
        texto += `\n\n${r.salida}`;
    }
    return texto;
}

/** HTML de un fallo: mensaje + salida completa del cliente en un <pre>, todo escapado. */
function htmlFalloConSalida(r) {
    let html = `<div>${escaparHtml(r.error || 'El comando falló.')}</div>`;
    if (r.salida && r.salida.trim()) {
        html += `<pre class="salida-cliente mt-2 bg-cyber-950 border border-slate-800 rounded-lg p-2 text-[11px] text-slate-300 max-h-48 overflow-y-auto">${escaparHtml(r.salida)}</pre>`;
    }
    return html;
}

/** Pone un botón en modo "trabajando" y lo restaura al terminar la promesa. */
async function conBotonOcupado(idBoton, idTexto, textoOcupado, tarea) {
    const boton = $(idBoton);
    const textoOriginal = $(idTexto).textContent;
    boton.disabled = true;
    boton.querySelector('svg')?.classList.add('animate-pulse');
    ponerTexto(idTexto, textoOcupado);
    try {
        return await tarea();
    } finally {
        boton.disabled = false;
        boton.querySelector('svg')?.classList.remove('animate-pulse');
        ponerTexto(idTexto, textoOriginal);
    }
}

// ==================== VENTANA EMERGENTE ====================

const ESTILOS_BOTON = {
    primario: 'bg-cyan-600 hover:bg-cyan-500 text-white',
    peligro: 'bg-rose-600 hover:bg-rose-500 text-white',
    secundario: 'bg-cyber-800 hover:bg-slate-700 border border-slate-700 text-slate-200',
};

/**
 * Abre la ventana emergente y devuelve una promesa con el 'valor' del botón
 * pulsado (o null si se cierra con Esc).
 *   abrirModal({ titulo, html, botones: [{ texto, valor, estilo }], ancho, alAbrir })
 * 'html' debe venir ya escapado. 'ancho' es una clase Tailwind (p. ej. 'max-w-4xl').
 * 'alAbrir(cuerpo)' se llama tras abrir, para enganchar contenido interactivo.
 */
const ANCHO_MODAL_BASE = 'bg-cyber-900 text-slate-200 border border-slate-700 rounded-2xl p-0 w-full shadow-2xl';

function abrirModal({ titulo, html, botones, ancho = 'max-w-2xl', alAbrir }) {
    const modal = $('modal');
    modal.className = `${ANCHO_MODAL_BASE} ${ancho}`;
    ponerTexto('modal-titulo', titulo);
    $('modal-cuerpo').innerHTML = html;

    const contenedor = $('modal-botones');
    contenedor.innerHTML = '';
    for (const { texto, valor, estilo = 'secundario' } of botones) {
        const boton = document.createElement('button');
        boton.type = 'button';
        boton.textContent = texto;
        boton.className = `px-4 py-2 rounded-xl text-sm font-semibold transition ${ESTILOS_BOTON[estilo]}`;
        boton.addEventListener('click', () => modal.close(valor));
        contenedor.appendChild(boton);
    }

    return new Promise((resolver) => {
        modal.returnValue = '';
        modal.addEventListener('close', () => resolver(modal.returnValue || null), { once: true });
        modal.showModal();
        modal.querySelector('input, textarea')?.focus();
        alAbrir?.($('modal-cuerpo'));
    });
}

async function confirmar(titulo, mensajeHtml, textoAceptar = 'Aceptar') {
    const valor = await abrirModal({
        titulo,
        html: mensajeHtml,
        botones: [
            { texto: 'Cancelar', valor: 'cancelar' },
            { texto: textoAceptar, valor: 'aceptar', estilo: 'peligro' },
        ],
    });
    return valor === 'aceptar';
}

// ==================== FICHA DE TARJETA ====================

function htmlDato(etiqueta, valor, mono = true) {
    return `
        <div class="flex justify-between gap-4 py-1.5 border-b border-slate-800/80">
            <span class="text-xs text-slate-400">${escaparHtml(etiqueta)}</span>
            <span class="text-sm text-right ${mono ? 'font-mono' : ''} text-slate-100 break-all">${escaparHtml(valor || '—')}</span>
        </div>`;
}

function htmlComando(etiqueta, comando) {
    return `
        <div class="space-y-1">
            <div class="text-xs text-slate-400">${escaparHtml(etiqueta)}</div>
            <code class="block bg-cyber-950 border border-slate-800 rounded-lg px-3 py-2 text-xs font-mono text-cyan-300 break-all">${escaparHtml(comando)}</code>
        </div>`;
}

/**
 * Ficha con los datos de una tarjeta (leída o guardada). Los derivados
 * (destino, seguridad, comandos) vienen generados por pm3/recetas.py.
 */
function htmlFichaTarjeta(t) {
    const lf = t.banda === 'lf';
    const d = t.derivados;
    let html = `
        <div class="flex items-center gap-2 mb-2">
            <span class="px-2 py-0.5 rounded-md text-[11px] font-mono ${lf ? 'bg-amber-500/15 text-amber-300' : 'bg-cyan-500/15 text-cyan-300'}">${lf ? 'LF' : 'HF'}</span>
            <span class="text-lg font-bold text-white">${escaparHtml(t.tipo)}</span>
        </div>
        ${htmlDato(lf ? 'ID' : 'UID', t.uid)}
        ${lf ? '' : htmlDato('ATQA', t.atqa) + htmlDato('SAK', t.sak)}
        ${htmlDato('Fecha de lectura', t.fecha)}`;

    if (d) {
        html += `
            ${htmlDato('Frecuencia', d.frecuencia)}
            ${htmlDato('Tarjeta destino para clonar', d.tarjeta_destino, false)}
            ${htmlDato('Seguridad', d.seguridad, false)}
            <div class="pt-3 space-y-2">
                ${htmlComando('Comando de clonado', d.comando_clonado)}
                ${htmlComando('Comando de emulación', d.comando_emulacion)}
                <p class="text-[11px] text-slate-500">Generados a partir del tipo y el UID. Para emular, usa la sección «Clonado y emulación».</p>
            </div>`;
    } else {
        html += `<p class="mt-3 text-xs text-amber-200 bg-amber-950/30 border border-amber-500/30 rounded-lg p-2">
            El tipo o el UID guardados no son válidos: no se pueden generar los datos de clonado y emulación.</p>`;
    }

    if (t.salida) {
        html += `
            <details class="pt-3">
                <summary class="cursor-pointer text-xs text-slate-400 hover:text-slate-200">Salida completa del cliente</summary>
                <pre class="salida-cliente mt-2 bg-cyber-950 border border-slate-800 rounded-lg p-3 text-[11px] font-mono text-slate-300 max-h-80 overflow-y-auto">${escaparHtml(t.salida)}</pre>
            </details>`;
    }
    return html;
}
