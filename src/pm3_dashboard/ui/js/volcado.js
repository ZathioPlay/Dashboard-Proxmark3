/* PM3 Dashboard — volcado de memoria HF: tabla hex+ASCII, claves, accesos, NDEF,
 * leer/recuperar/clonar y, en modo laboratorio, edición de bloques.
 * Volcar, clonar y escribir solo en tarjetas propias o con autorización (uso legítimo).
 */
'use strict';

let modoLaboratorio = false;

const AVISO_USO = 'Vuelca memoria, clona y escribe solo en tarjetas propias o con autorización expresa de su titular.';

// ==================== TABLA HEX + ASCII ====================

function htmlFilaBloque(bloque, tecnologia) {
    const editable = modoLaboratorio && bloque.leido;
    if (!bloque.leido) {
        return `
            <tr>
                <td class="px-2 py-1 text-right font-mono text-[11px] text-slate-500">${Number(bloque.indice)}</td>
                <td class="px-2 py-1 font-mono text-[11px] text-rose-300/70 italic" colspan="3">— sin leer (falta clave) —</td>
            </tr>`;
    }
    return `
        <tr class="${bloque.es_trailer ? 'bg-cyber-800/40' : ''}">
            <td class="px-2 py-1 text-right font-mono text-[11px] text-slate-500">${Number(bloque.indice)}</td>
            <td class="px-2 py-1 font-mono text-[11px] break-all text-slate-200">${escaparHtml(bloque.datos)}</td>
            <td class="px-2 py-1 font-mono text-[11px] text-slate-400 whitespace-pre">${escaparHtml(bloque.ascii)}</td>
            <td class="px-1 py-1 text-right">${editable
                ? `<button data-editar="${Number(bloque.indice)}" class="px-1.5 py-0.5 rounded bg-cyber-800 hover:bg-slate-700 text-[10px] text-cyan-300">Editar</button>`
                : ''}</td>
        </tr>`;
}

function htmlClavesYAccesos(sector) {
    if (sector.clave_a === null && sector.clave_b === null) {
        return '';
    }
    let html = `
        <div class="px-2 py-1 text-[10px] font-mono text-slate-400 border-t border-slate-800 flex gap-4">
            <span>Clave A: <span class="text-emerald-300">${escaparHtml(sector.clave_a || '—')}</span></span>
            <span>Clave B: <span class="text-emerald-300">${escaparHtml(sector.clave_b || '—')}</span></span>
        </div>`;
    if (sector.accesos) {
        html += '<ul class="px-2 py-1 text-[10px] text-slate-400 border-t border-slate-800 space-y-0.5">' +
            sector.accesos.map((a, i) => `<li><span class="text-slate-500">Bloque ${i}${i === 3 ? ' (trailer)' : ''}:</span> ${escaparHtml(a)}</li>`).join('') +
            '</ul>';
    } else {
        html += '<div class="px-2 py-1 text-[10px] text-amber-300/80 border-t border-slate-800">Bits de acceso: no se pueden interpretar.</div>';
    }
    return html;
}

function htmlSector(sector, tecnologia) {
    const classic = tecnologia === 'mifare_classic';
    const cabecera = classic
        ? `<div class="flex items-center justify-between px-2 py-1 bg-cyber-950 border-b border-slate-800">
               <span class="text-[11px] font-mono text-slate-400">Sector ${Number(sector.indice)}</span>
               ${sector.completo
                   ? '<span class="text-[10px] font-mono text-emerald-300">leído</span>'
                   : '<span class="text-[10px] font-mono text-amber-300">falta clave</span>'}
           </div>`
        : '';
    const filas = sector.bloques.map((b) => htmlFilaBloque(b, tecnologia)).join('');
    return `
        <div class="border border-slate-800 rounded-lg overflow-hidden ${classic && !sector.completo ? 'ring-1 ring-amber-500/30' : ''}">
            ${cabecera}
            <table class="w-full"><tbody>${filas}</tbody></table>
            ${classic ? htmlClavesYAccesos(sector) : ''}
        </div>`;
}

function htmlNdef(volcado) {
    if (volcado.tecnologia !== 'mifare_ultralight' || !volcado.ndef || !volcado.ndef.length) {
        return '';
    }
    const iconos = { uri: '🔗', texto: '📝', otro: '…' };
    return `
        <div class="bg-cyber-950 border border-slate-800 rounded-lg p-3 mb-2 space-y-1">
            <div class="text-[11px] font-mono text-cyan-300">Registros NDEF</div>
            ${volcado.ndef.map((r) => `
                <div class="text-xs text-slate-200 break-all">${iconos[r.tipo] || ''}
                    <span class="text-slate-500">${escaparHtml(r.tipo)}:</span> ${escaparHtml(r.contenido)}</div>`).join('')}
        </div>`;
}

function htmlTablaVolcado(volcado) {
    const columnas = volcado.tecnologia === 'mifare_classic' ? 'md:grid-cols-2' : 'md:grid-cols-4';
    return `
        ${htmlNdef(volcado)}
        <div class="grid grid-cols-1 ${columnas} gap-2">
            ${volcado.sectores.map((s) => htmlSector(s, volcado.tecnologia)).join('')}
        </div>`;
}

// ==================== PANEL DE MEMORIA (dentro de la ficha) ====================

function htmlPanelMemoria(tarjeta, volcado) {
    const puedeClonar = volcado && volcado.completo && volcado.tecnologia === 'mifare_classic';
    let resumen = '<p class="text-sm text-slate-400">Aún no se ha leído la memoria de esta tarjeta.</p>';
    if (volcado) {
        const estado = volcado.faltan_claves
            ? `<span class="text-amber-300">faltan claves en algunos sectores</span>`
            : `<span class="text-emerald-300">completo</span>`;
        resumen = `<p class="text-sm text-slate-300">Volcado del ${escaparHtml(volcado.fecha)}:
            ${Number(volcado.bloques_leidos)}/${Number(volcado.total_bloques)} bloques — ${estado}.</p>`;
    }

    return `
        <div class="pt-4 mt-4 border-t border-slate-800 space-y-3">
            <div class="flex items-center justify-between gap-2">
                <h4 class="text-sm font-bold text-white">Memoria de la tarjeta</h4>
                <div class="flex items-center gap-2">
                    <button data-mem="leer" class="px-3 py-1.5 bg-cyan-600 hover:bg-cyan-500 disabled:bg-slate-700 disabled:text-slate-400 text-white text-xs font-semibold rounded-lg transition">Leer bloques</button>
                    ${volcado && volcado.faltan_claves
                        ? '<button data-mem="recuperar" class="px-3 py-1.5 bg-amber-600 hover:bg-amber-500 disabled:bg-slate-700 disabled:text-slate-400 text-white text-xs font-semibold rounded-lg transition">Recuperar claves</button>'
                        : ''}
                    <button data-mem="clonar" class="px-3 py-1.5 bg-rose-600 hover:bg-rose-500 disabled:bg-slate-700 disabled:text-slate-400 text-white text-xs font-semibold rounded-lg transition" ${puedeClonar ? '' : 'disabled title="Hace falta un volcado completo"'}>Clonar a tarjeta mágica</button>
                </div>
            </div>
            <p class="text-[11px] text-amber-300/80">${escaparHtml(AVISO_USO)}</p>
            ${volcado ? `
                <label class="flex items-center gap-2 text-xs text-slate-300">
                    <input type="checkbox" data-mem="laboratorio" ${modoLaboratorio ? 'checked' : ''} class="accent-rose-500">
                    Modo laboratorio (editar bloques — escritura en la tarjeta)
                </label>` : ''}
            <div data-mem="estado" class="hidden rounded-lg p-2 text-xs"></div>
            <div data-mem="resumen">${resumen}</div>
            <div data-mem="tabla">${volcado ? htmlTablaVolcado(volcado) : ''}</div>
        </div>`;
}
