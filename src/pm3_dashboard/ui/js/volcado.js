/* PM3 Dashboard — volcado de memoria HF: tabla hex, leer bloques, recuperar claves y clonar.
 * Volcar memoria y clonar solo de tarjetas propias o con autorización (uso legítimo).
 */
'use strict';

// ==================== TABLA HEX ====================

function htmlFilaBloque(bloque, esTrailer) {
    const datos = bloque.leido
        ? `<span class="text-slate-200">${escaparHtml(bloque.datos)}</span>`
        : '<span class="text-rose-300/70 italic">— sin leer (falta clave) —</span>';
    return `
        <tr class="${esTrailer ? 'bg-cyber-800/40' : ''}">
            <td class="px-2 py-1 text-right font-mono text-[11px] text-slate-500">${Number(bloque.indice)}</td>
            <td class="px-2 py-1 font-mono text-[11px] break-all">${datos}${esTrailer ? ' <span class="text-[9px] text-slate-500">(claves)</span>' : ''}</td>
        </tr>`;
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
    const filas = sector.bloques.map((b, i) => htmlFilaBloque(b, classic && i === sector.bloques.length - 1)).join('');
    return `
        <div class="border border-slate-800 rounded-lg overflow-hidden ${classic && !sector.completo ? 'ring-1 ring-amber-500/30' : ''}">
            ${cabecera}
            <table class="w-full"><tbody>${filas}</tbody></table>
        </div>`;
}

function htmlTablaVolcado(volcado) {
    const columnas = volcado.tecnologia === 'mifare_classic' ? 'md:grid-cols-2' : 'md:grid-cols-4';
    return `
        <div class="grid grid-cols-1 ${columnas} gap-2">
            ${volcado.sectores.map((s) => htmlSector(s, volcado.tecnologia)).join('')}
        </div>`;
}

// ==================== PANEL DE MEMORIA (dentro de la ficha) ====================

const AVISO_USO = 'Vuelca memoria y clona solo tarjetas propias o con autorización expresa de su titular.';

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
            <div data-mem="estado" class="hidden rounded-lg p-2 text-xs"></div>
            <div data-mem="resumen">${resumen}</div>
            <div data-mem="tabla">${volcado ? htmlTablaVolcado(volcado) : ''}</div>
        </div>`;
}
