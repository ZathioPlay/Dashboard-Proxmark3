/* PM3 Dashboard — lógica de la interfaz.
 * La interfaz nunca ejecuta comandos: todo pasa por window.pywebview.api.
 */
'use strict';

// ==================== SECCIONES DEL MENÚ ====================

const SECCIONES = [
    { id: 'inicio',   titulo: 'Inicio',               descripcion: '' },
    { id: 'antenas',  titulo: 'Antenas',              descripcion: 'Medición de las antenas LF y HF con hw tune.' },
    { id: 'lectura',  titulo: 'Lectura',              descripcion: 'Lectura de tarjetas RFID / NFC (hf search, lf search).' },
    { id: 'clonado',  titulo: 'Clonado y emulación',  descripcion: 'Clonar tarjetas propias o emularlas desde la Proxmark3.' },
    { id: 'base',     titulo: 'Base de datos',        descripcion: 'Gestión de las tarjetas guardadas: búsqueda, edición, exportar e importar.' },
    { id: 'terminal', titulo: 'Terminal',             descripcion: 'Consola para enviar comandos al cliente de Iceman.' },
];

const CLASE_NAV_ACTIVO = 'flex items-center gap-3 px-3.5 py-2.5 rounded-xl text-sm font-medium transition bg-cyan-600/15 text-cyan-300 border border-cyan-500/30';
const CLASE_NAV_INACTIVO = 'flex items-center gap-3 px-3.5 py-2.5 rounded-xl text-sm font-medium transition text-slate-400 hover:text-white hover:bg-slate-800/60 border border-transparent';
const CLASE_NUM_ACTIVO = 'w-6 h-6 rounded-lg bg-cyan-500/20 flex items-center justify-center font-mono text-xs font-bold';
const CLASE_NUM_INACTIVO = 'w-6 h-6 rounded-lg bg-slate-800 flex items-center justify-center font-mono text-xs font-bold';

function crearMenu() {
    const menu = document.getElementById('menu');
    SECCIONES.forEach((seccion, indice) => {
        const boton = document.createElement('button');
        boton.id = `nav-${seccion.id}`;
        boton.innerHTML = `<span class="${CLASE_NUM_INACTIVO}">${indice}</span><span>${seccion.titulo}</span>`;
        boton.addEventListener('click', () => mostrarSeccion(seccion.id));
        menu.appendChild(boton);
    });
}

function mostrarSeccion(id) {
    const seccion = SECCIONES.find((s) => s.id === id);

    SECCIONES.forEach((s) => {
        const boton = document.getElementById(`nav-${s.id}`);
        const activo = s.id === id;
        boton.className = activo ? CLASE_NAV_ACTIVO : CLASE_NAV_INACTIVO;
        boton.firstElementChild.className = activo ? CLASE_NUM_ACTIVO : CLASE_NUM_INACTIVO;
    });

    document.querySelectorAll('[data-seccion]').forEach((el) => el.classList.add('hidden'));

    if (id === 'inicio') {
        document.getElementById('seccion-inicio').classList.remove('hidden');
    } else {
        document.getElementById('proximamente-titulo').textContent = seccion.titulo;
        document.getElementById('proximamente-descripcion').textContent = seccion.descripcion;
        document.getElementById('seccion-proximamente').classList.remove('hidden');
    }
}

// ==================== UTILIDADES ====================

function escaparHtml(texto) {
    const div = document.createElement('div');
    div.textContent = String(texto ?? '');
    return div.innerHTML;
}

function ponerTexto(id, texto) {
    document.getElementById(id).textContent = texto;
}

// ==================== PINTAR EL RESUMEN ====================

function pintarInsignia(dispositivo) {
    const punto = document.getElementById('insignia-punto');
    const insignia = document.getElementById('insignia-estado');
    const texto = document.getElementById('insignia-texto');

    if (dispositivo.conectado) {
        insignia.className = 'flex items-center gap-2 px-3 py-1 rounded-full bg-emerald-950/50 border border-emerald-500/30 text-xs font-mono';
        punto.className = 'w-2 h-2 rounded-full bg-emerald-400 animate-pulse';
        texto.className = 'text-emerald-300 font-semibold';
        texto.textContent = 'CONECTADO';
        ponerTexto('insignia-puerto', `(${dispositivo.puerto})`);
    } else {
        insignia.className = 'flex items-center gap-2 px-3 py-1 rounded-full bg-rose-950/50 border border-rose-500/30 text-xs font-mono';
        punto.className = 'w-2 h-2 rounded-full bg-rose-400';
        texto.className = 'text-rose-300 font-semibold';
        texto.textContent = 'DESCONECTADO';
        ponerTexto('insignia-puerto', '');
    }
}

function pintarKpis(resumen) {
    const { dispositivo, tarjetas } = resumen;
    const kpi = document.getElementById('kpi-dispositivo');
    kpi.textContent = dispositivo.conectado ? `Conectado · ${dispositivo.puerto}` : 'Desconectado';
    kpi.className = `text-xl font-bold mt-2 ${dispositivo.conectado ? 'text-emerald-400' : 'text-rose-400'}`;
    ponerTexto('kpi-firmware', dispositivo.firmware || '—');
    ponerTexto('kpi-total', tarjetas.total);
    ponerTexto('kpi-hf', tarjetas.hf);
    ponerTexto('kpi-lf', tarjetas.lf);
}

function htmlAntena(nombre, frecuencia, medida, color) {
    // Escala de la barra: el doble del óptimo llena la barra.
    const porcentaje = Math.min(100, (medida.voltios / (medida.optimo * 2)) * 100);
    const estado = medida.ok
        ? '<span class="px-2 py-0.5 text-xs font-mono rounded-lg bg-emerald-500/15 text-emerald-300">OK</span>'
        : '<span class="px-2 py-0.5 text-xs font-mono rounded-lg bg-rose-500/15 text-rose-300">BAJO</span>';

    return `
        <div class="space-y-2">
            <div class="flex items-center justify-between">
                <span class="text-xs font-mono ${color.texto} uppercase">${nombre} · ${frecuencia}</span>
                ${estado}
            </div>
            <div class="flex items-baseline gap-2">
                <span class="text-2xl font-mono font-bold text-white">${medida.voltios.toFixed(2)}</span>
                <span class="text-xs font-mono text-slate-400">V (óptimo &gt; ${medida.optimo.toFixed(2)} V)</span>
            </div>
            <div class="w-full bg-cyber-950 h-2.5 rounded-full overflow-hidden border border-slate-800">
                <div class="${color.barra} h-full transition-all duration-700" style="width: ${porcentaje}%"></div>
            </div>
        </div>`;
}

function pintarAntenas(antenas) {
    ponerTexto('antenas-fecha', `Medido el ${antenas.fecha}`);
    document.getElementById('antena-lf').innerHTML =
        htmlAntena('LF', '125 kHz', antenas.lf, { texto: 'text-amber-400', barra: 'bg-amber-500' });
    document.getElementById('antena-hf').innerHTML =
        htmlAntena('HF', '13.56 MHz', antenas.hf, { texto: 'text-cyan-400', barra: 'bg-cyan-500' });
}

const ESTILO_ACTIVIDAD = {
    lectura:   { etiqueta: 'LECTURA',   clase: 'bg-cyan-500/15 text-cyan-300' },
    antenas:   { etiqueta: 'ANTENAS',   clase: 'bg-amber-500/15 text-amber-300' },
    guardado:  { etiqueta: 'GUARDADO',  clase: 'bg-emerald-500/15 text-emerald-300' },
    emulacion: { etiqueta: 'EMULACIÓN', clase: 'bg-violet-500/15 text-violet-300' },
    conexion:  { etiqueta: 'CONEXIÓN',  clase: 'bg-slate-700 text-slate-300' },
};

function pintarActividad(actividad) {
    const lista = document.getElementById('lista-actividad');
    if (!actividad.length) {
        lista.innerHTML = '<li class="py-3 text-sm text-slate-500">Sin actividad todavía.</li>';
        return;
    }
    lista.innerHTML = actividad.map((evento) => {
        const estilo = ESTILO_ACTIVIDAD[evento.tipo] || { etiqueta: evento.tipo.toUpperCase(), clase: 'bg-slate-700 text-slate-300' };
        return `
            <li class="py-3 flex items-center gap-3">
                <span class="w-24 shrink-0 text-center px-2 py-0.5 rounded-md text-[10px] font-mono ${estilo.clase}">${escaparHtml(estilo.etiqueta)}</span>
                <span class="flex-1 text-sm text-slate-200">${escaparHtml(evento.descripcion)}</span>
                <span class="text-xs font-mono text-slate-500 shrink-0">${escaparHtml(evento.fecha)}</span>
            </li>`;
    }).join('');
}

function pintarResumen(resumen) {
    document.getElementById('error-api').classList.add('hidden');
    document.getElementById('aviso-ejemplo').classList.toggle('hidden', !resumen.es_ejemplo);
    pintarInsignia(resumen.dispositivo);
    pintarKpis(resumen);
    pintarAntenas(resumen.antenas);
    pintarActividad(resumen.actividad);
}

function mostrarError(mensaje) {
    const caja = document.getElementById('error-api');
    caja.textContent = mensaje;
    caja.classList.remove('hidden');
    ponerTexto('insignia-texto', 'SIN API');
}

// ==================== COMUNICACIÓN CON PYTHON ====================

async function cargarResumen() {
    try {
        const resumen = await window.pywebview.api.obtener_resumen();
        pintarResumen(resumen);
    } catch (error) {
        mostrarError(`No se pudo obtener el resumen: ${error}`);
    }
}

// ==================== ARRANQUE ====================

document.addEventListener('DOMContentLoaded', () => {
    crearMenu();
    mostrarSeccion('inicio');
    document.getElementById('btn-actualizar').addEventListener('click', cargarResumen);

    if (window.pywebview && window.pywebview.api && window.pywebview.api.obtener_resumen) {
        cargarResumen();
    } else {
        // Si tras unos segundos no aparece pywebview, se ha abierto fuera de la app.
        setTimeout(() => {
            if (!window.pywebview) {
                mostrarError('Sin conexión con Python: abre la interfaz con "python -m pm3_dashboard", no directamente en el navegador.');
            }
        }, 3000);
    }
});

// pywebview lanza este evento cuando window.pywebview.api está lista.
window.addEventListener('pywebviewready', cargarResumen);
