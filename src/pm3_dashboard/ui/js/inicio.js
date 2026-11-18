/* PM3 Dashboard — sección Inicio: estado de la Proxmark3, resumen, antenas y actividad. */
'use strict';

// ==================== ESTADO DEL DISPOSITIVO ====================

const CLASES_INSIGNIA = {
    conectado:    { caja: 'bg-emerald-950/50 border-emerald-500/30', punto: 'bg-emerald-400 animate-pulse', texto: 'text-emerald-300' },
    desconectado: { caja: 'bg-rose-950/50 border-rose-500/30',       punto: 'bg-rose-400',                 texto: 'text-rose-300' },
    comprobando:  { caja: 'bg-slate-800/60 border-slate-700',        punto: 'bg-slate-500 animate-pulse',  texto: 'text-slate-300' },
};

function pintarInsignia(tipo, texto, puerto) {
    const clases = CLASES_INSIGNIA[tipo];
    $('insignia-estado').className = `flex items-center gap-2 px-3 py-1 rounded-full border text-xs font-mono ${clases.caja}`;
    $('insignia-punto').className = `w-2 h-2 rounded-full ${clases.punto}`;
    const etiqueta = $('insignia-texto');
    etiqueta.className = `font-semibold ${clases.texto}`;
    etiqueta.textContent = texto;
    ponerTexto('insignia-puerto', puerto ? `(${puerto})` : '');
}

function pintarComprobando() {
    pintarInsignia('comprobando', 'COMPROBANDO…', '');
    const kpi = $('kpi-dispositivo');
    kpi.textContent = 'Comprobando…';
    kpi.className = 'text-xl font-bold mt-2 text-slate-300';
}

function pintarEstado(estado) {
    const kpi = $('kpi-dispositivo');
    if (estado.conectado) {
        pintarInsignia('conectado', estado.ocupado ? 'OCUPADA' : 'CONECTADO', estado.puerto);
        kpi.textContent = `Conectado · ${estado.puerto || '?'}`;
        kpi.className = 'text-xl font-bold mt-2 text-emerald-400';
        const detalle = [estado.dispositivo, estado.version_firmware].filter(Boolean).join(' · ');
        ponerTexto('kpi-firmware', detalle || estado.firmware || '—');
    } else {
        pintarInsignia('desconectado', 'DESCONECTADO', '');
        kpi.textContent = 'Desconectado';
        kpi.className = 'text-xl font-bold mt-2 text-rose-400';
        ponerTexto('kpi-firmware', '—');
    }
    ponerTexto('aviso-dispositivo-texto', estado.mensaje || '');
    mostrar('aviso-dispositivo', !estado.conectado);
    ponerTexto('aviso-version-texto', estado.aviso_version || '');
    mostrar('aviso-version', Boolean(estado.conectado && estado.aviso_version));
}

// ==================== RESUMEN (BASE DE DATOS) ====================

function pintarTarjetas(tarjetas) {
    ponerTexto('kpi-total', tarjetas.total);
    ponerTexto('kpi-hf', tarjetas.hf);
    ponerTexto('kpi-lf', tarjetas.lf);
}

const ESTILO_ANTENA = {
    'OK':           'bg-emerald-500/15 text-emerald-300',
    'MARGINAL':     'bg-amber-500/15 text-amber-300',
    'BAJA':         'bg-amber-500/15 text-amber-300',
    'INUTILIZABLE': 'bg-rose-500/15 text-rose-300',
    'SIN DATOS':    'bg-slate-700 text-slate-300',
};

function htmlAntena(nombre, frecuencia, medida, color) {
    const hayVoltios = typeof medida.voltios === 'number';
    // Escala de la barra: el doble del mínimo llena la barra.
    const porcentaje = hayVoltios ? Math.min(100, (medida.voltios / (medida.minimo * 2)) * 100) : 0;
    const estilo = ESTILO_ANTENA[medida.estado] || ESTILO_ANTENA['SIN DATOS'];

    return `
        <div class="space-y-2">
            <div class="flex items-center justify-between">
                <span class="text-xs font-mono ${color.texto} uppercase">${nombre} · ${frecuencia}</span>
                <span class="px-2 py-0.5 text-xs font-mono rounded-lg ${estilo}">${escaparHtml(medida.estado)}</span>
            </div>
            <div class="flex items-baseline gap-2">
                <span class="text-2xl font-mono font-bold text-white">${hayVoltios ? medida.voltios.toFixed(2) : '--.--'}</span>
                <span class="text-xs font-mono text-slate-400">V (mínimo ${medida.minimo.toFixed(2)} V)</span>
            </div>
            <div class="w-full bg-cyber-950 h-2.5 rounded-full overflow-hidden border border-slate-800">
                <div class="${color.barra} h-full transition-all duration-700" style="width: ${porcentaje}%"></div>
            </div>
        </div>`;
}

function pintarAntenas(antenas) {
    mostrar('antenas-vacio', !antenas);
    if (!antenas) {
        ponerTexto('antenas-fecha', 'Nunca se han medido');
        $('antena-lf').innerHTML = '';
        $('antena-hf').innerHTML = '';
        return;
    }
    ponerTexto('antenas-fecha', `Medido el ${antenas.fecha}`);
    $('antena-lf').innerHTML = htmlAntena('LF', '125 kHz', antenas.lf, { texto: 'text-amber-400', barra: 'bg-amber-500' });
    $('antena-hf').innerHTML = htmlAntena('HF', '13.56 MHz', antenas.hf, { texto: 'text-cyan-400', barra: 'bg-cyan-500' });
}

const ESTILO_ACTIVIDAD = {
    lectura:     { etiqueta: 'LECTURA',     clase: 'bg-cyan-500/15 text-cyan-300' },
    antenas:     { etiqueta: 'ANTENAS',     clase: 'bg-amber-500/15 text-amber-300' },
    guardado:    { etiqueta: 'GUARDADO',    clase: 'bg-emerald-500/15 text-emerald-300' },
    borrado:     { etiqueta: 'BORRADO',     clase: 'bg-rose-500/15 text-rose-300' },
    importacion: { etiqueta: 'IMPORTACIÓN', clase: 'bg-teal-500/15 text-teal-300' },
    exportacion: { etiqueta: 'EXPORTACIÓN', clase: 'bg-teal-500/15 text-teal-300' },
    emulacion:   { etiqueta: 'EMULACIÓN',   clase: 'bg-violet-500/15 text-violet-300' },
    clonado:     { etiqueta: 'CLONADO',     clase: 'bg-rose-500/15 text-rose-300' },
    conexion:    { etiqueta: 'CONEXIÓN',    clase: 'bg-slate-700 text-slate-300' },
};

function pintarActividad(actividad) {
    const lista = $('lista-actividad');
    if (!actividad.length) {
        lista.innerHTML = '<li class="py-3 text-sm text-slate-500">Sin actividad todavía.</li>';
        return;
    }
    lista.innerHTML = actividad.map((evento) => {
        const estilo = ESTILO_ACTIVIDAD[evento.tipo] || { etiqueta: String(evento.tipo).toUpperCase(), clase: 'bg-slate-700 text-slate-300' };
        return `
            <li class="py-3 flex items-center gap-3">
                <span class="w-24 shrink-0 text-center px-2 py-0.5 rounded-md text-[10px] font-mono ${estilo.clase}">${escaparHtml(estilo.etiqueta)}</span>
                <span class="flex-1 text-sm text-slate-200">${escaparHtml(evento.descripcion)}</span>
                <span class="text-xs font-mono text-slate-500 shrink-0">${escaparHtml(evento.fecha)}</span>
            </li>`;
    }).join('');
}

function pintarResumen(resumen) {
    mostrar('error-api', false);
    pintarTarjetas(resumen.tarjetas);
    pintarAntenas(resumen.antenas);
    pintarActividad(resumen.actividad);
}

function mostrarError(mensaje) {
    ponerTexto('error-api', mensaje);
    mostrar('error-api', true);
}

// ==================== LLAMADAS A PYTHON ====================

async function cargarResumen() {
    try {
        const resumen = await api().obtener_resumen();
        if (resumen.ok) {
            pintarResumen(resumen);
        } else {
            mostrarError(`No se pudo leer la base de datos: ${resumen.error}`);
        }
    } catch (error) {
        mostrarError(`No se pudo obtener el resumen: ${textoError(error)}`);
    }
}

async function cargarEstado() {
    pintarComprobando();
    try {
        const estado = await api().obtener_estado_dispositivo();
        pintarEstado(estado.ok ? estado : { conectado: false, mensaje: estado.error });
    } catch (error) {
        pintarEstado({ conectado: false, mensaje: `Error al comprobar la Proxmark3: ${textoError(error)}` });
    }
}

function cargarTodo() {
    // En paralelo: los datos de la BD aparecen enseguida aunque 'hw version' tarde.
    cargarResumen();
    // Al terminar se recarga el resumen por si se ha registrado un evento de conexión.
    cargarEstado().then(cargarResumen);
}

async function medirAntenas() {
    mostrar('antenas-error', false);
    await conBotonOcupado('btn-medir', 'btn-medir-texto', 'Midiendo… (hasta 45 s)', async () => {
        try {
            const resultado = await api().medir_antenas();
            if (!resultado.ok) {
                ponerTexto('antenas-error', resultado.error);
                mostrar('antenas-error', true);
            }
            await cargarResumen();
        } catch (error) {
            ponerTexto('antenas-error', `Error al medir: ${textoError(error)}`);
            mostrar('antenas-error', true);
        }
    });
}

// ==================== COMPROBACIÓN PERIÓDICA DE CONEXIÓN ====================
// Solo mira si el puerto existe (no lanza comandos). Si la Proxmark aparece,
// se pide el estado completo una vez; si desaparece, se marca desconectada.

const INTERVALO_CONEXION_MS = 5000;
let comprobandoConexion = false;

async function comprobarConexion() {
    if (comprobandoConexion) {
        return;
    }
    comprobandoConexion = true;
    try {
        const resultado = await api().comprobar_conexion();
        if (resultado.cambio === 'aparece') {
            await cargarEstado();
            cargarResumen();
        } else if (resultado.cambio === 'desaparece') {
            pintarEstado(resultado.estado);
            cargarResumen();
        }
    } catch (error) {
        // Fallo puntual: se reintenta en la siguiente vuelta.
    } finally {
        comprobandoConexion = false;
    }
}

function iniciarSeccionInicio() {
    $('btn-actualizar').addEventListener('click', cargarTodo);
    $('btn-medir').addEventListener('click', medirAntenas);
    // Las tarjetas de recuento llevan a la Base de datos (filtrada por banda si procede).
    document.querySelectorAll('[data-ir-a="base"]').forEach((tarjeta) => {
        tarjeta.addEventListener('click', () => irABaseDeDatos(tarjeta.dataset.banda || ''));
    });
}
