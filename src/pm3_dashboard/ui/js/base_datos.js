/* PM3 Dashboard — sección Base de datos: buscar, ver, editar, borrar, exportar e importar. */
'use strict';

const ESPERA_BUSQUEDA_MS = 250;
let temporizadorBusqueda = null;

// ==================== LISTA ====================

async function cargarTarjetas() {
    const texto = $('base-buscar').value;
    const banda = $('base-banda').value;
    try {
        const resultado = await api().listar_tarjetas(texto, banda);
        if (!resultado.ok) {
            mostrarMensaje('base-mensaje', resultado.error, 'error');
            return;
        }
        pintarTabla(resultado.tarjetas, Boolean(texto.trim() || banda));
    } catch (error) {
        mostrarMensaje('base-mensaje', `No se pudo cargar la lista: ${textoError(error)}`, 'error');
    }
}

function botonAccion(accion, texto, clase) {
    return `<button type="button" data-accion="${accion}" class="px-2.5 py-1 rounded-lg text-xs font-medium transition ${clase}">${texto}</button>`;
}

function pintarTabla(tarjetas, hayFiltros) {
    $('base-filas').innerHTML = tarjetas.map((t) => `
        <tr data-id="${Number(t.id)}" data-nombre="${escaparHtml(t.nombre)}" class="hover:bg-cyber-800/40">
            <td class="px-4 py-3">
                <div class="font-medium text-slate-100">${escaparHtml(t.nombre)}</div>
                ${t.notas ? `<div class="text-xs text-slate-500 truncate max-w-xs">${escaparHtml(t.notas)}</div>` : ''}
            </td>
            <td class="px-4 py-3">
                <span class="px-1.5 py-0.5 rounded text-[10px] font-mono mr-1 ${t.banda === 'lf' ? 'bg-amber-500/15 text-amber-300' : 'bg-cyan-500/15 text-cyan-300'}">${t.banda === 'lf' ? 'LF' : 'HF'}</span>
                <span class="text-slate-300">${escaparHtml(t.tipo)}</span>
            </td>
            <td class="px-4 py-3 font-mono text-xs text-slate-300">${escaparHtml(t.uid)}</td>
            <td class="px-4 py-3 font-mono text-xs text-slate-500">${escaparHtml(t.fecha)}</td>
            <td class="px-4 py-3 text-right whitespace-nowrap space-x-1">
                ${botonAccion('ver', 'Ver', 'bg-cyber-800 hover:bg-slate-700 text-cyan-300')}
                ${botonAccion('editar', 'Editar', 'bg-cyber-800 hover:bg-slate-700 text-slate-200')}
                ${botonAccion('borrar', 'Borrar', 'bg-rose-950/40 hover:bg-rose-600 text-rose-300 hover:text-white')}
            </td>
        </tr>`).join('');

    ponerTexto('base-vacio', hayFiltros
        ? 'No hay tarjetas que coincidan con la búsqueda.'
        : 'Todavía no hay tarjetas guardadas. Lee una en la sección Lectura o importa un archivo JSON.');
    mostrar('base-vacio', tarjetas.length === 0);
}

function alEscribirBusqueda() {
    clearTimeout(temporizadorBusqueda);
    temporizadorBusqueda = setTimeout(cargarTarjetas, ESPERA_BUSQUEDA_MS);
}

/** Desde Inicio: abre la Base de datos, opcionalmente filtrada por banda. */
function irABaseDeDatos(banda) {
    $('base-buscar').value = '';
    $('base-banda').value = banda;
    mostrarSeccion('base');
}

// ==================== ACCIONES POR TARJETA ====================

async function alPulsarEnTabla(evento) {
    const boton = evento.target.closest('button[data-accion]');
    if (!boton) {
        return;
    }
    const fila = boton.closest('tr');
    const id = Number(fila.dataset.id);
    const nombre = fila.dataset.nombre;
    mostrarMensaje('base-mensaje', '');
    if (boton.dataset.accion === 'ver') {
        await verTarjeta(id);
    } else if (boton.dataset.accion === 'editar') {
        await editarTarjeta(id);
    } else if (boton.dataset.accion === 'borrar') {
        await borrarTarjeta(id, nombre);
    }
}

async function pedirTarjeta(id) {
    const resultado = await api().obtener_tarjeta(id);
    if (!resultado.ok) {
        mostrarMensaje('base-mensaje', resultado.error, 'error');
        cargarTarjetas();
        return null;
    }
    return resultado.tarjeta;
}

async function verTarjeta(id) {
    const tarjeta = await pedirTarjeta(id);
    if (!tarjeta) {
        return;
    }
    const notas = tarjeta.notas
        ? `<p class="text-sm text-slate-300 whitespace-pre-wrap bg-cyber-950 border border-slate-800 rounded-lg p-3">${escaparHtml(tarjeta.notas)}</p>`
        : '';
    const esHF = tarjeta.banda === 'hf';
    // El último volcado guardado (si lo hay) se muestra al abrir, sin leer la Proxmark.
    let volcado = null;
    if (esHF) {
        const r = await api().obtener_volcado(id);
        volcado = r.ok ? r.volcado : null;
    }
    const memoria = esHF ? htmlPanelMemoria(tarjeta, volcado) : '';

    await abrirModal({
        titulo: tarjeta.nombre,
        html: notas + htmlFichaTarjeta(tarjeta) + memoria,
        botones: [{ texto: 'Cerrar', valor: 'cerrar' }],
        ancho: esHF ? 'max-w-4xl' : 'max-w-2xl',
        alAbrir: esHF ? (cuerpo) => engancharMemoria(cuerpo, tarjeta) : undefined,
    });
}

// ==================== VOLCADO Y CLONADO (dentro de la ficha) ====================

function engancharMemoria(cuerpo, tarjeta) {
    cuerpo.querySelector('[data-mem="leer"]')?.addEventListener('click', () => accionMemoria(cuerpo, tarjeta, 'leer'));
    cuerpo.querySelector('[data-mem="recuperar"]')?.addEventListener('click', () => accionMemoria(cuerpo, tarjeta, 'recuperar'));
    cuerpo.querySelector('[data-mem="clonar"]')?.addEventListener('click', () => clonar(cuerpo, tarjeta));
}

function estadoMemoria(cuerpo, texto, tipo) {
    const caja = cuerpo.querySelector('[data-mem="estado"]');
    caja.className = `rounded-lg p-2 text-xs ${CLASES_MENSAJE[tipo]}`;
    caja.textContent = texto;
    caja.classList.toggle('hidden', !texto);
}

function repintarMemoria(cuerpo, tarjeta, volcado) {
    // Se sustituye el panel entero (botones, resumen y tabla) y se vuelve a enganchar.
    const panel = cuerpo.querySelector('[data-mem="estado"]').parentElement;
    panel.outerHTML = htmlPanelMemoria(tarjeta, volcado);
    engancharMemoria(cuerpo, tarjeta);
}

async function accionMemoria(cuerpo, tarjeta, accion) {
    const esRecuperar = accion === 'recuperar';
    const botones = cuerpo.querySelectorAll('[data-mem="leer"], [data-mem="recuperar"], [data-mem="clonar"]');
    botones.forEach((b) => (b.disabled = true));
    estadoMemoria(cuerpo, esRecuperar
        ? 'Recuperando claves… Puede tardar varios minutos. No cierres la aplicación.'
        : 'Leyendo la memoria de la tarjeta…', 'aviso');
    try {
        const r = esRecuperar ? await api().recuperar_claves(tarjeta.id) : await api().leer_bloques(tarjeta.id);
        if (!r.ok) {
            estadoMemoria(cuerpo, r.error, 'error');
            botones.forEach((b) => (b.disabled = false));
            return;
        }
        repintarMemoria(cuerpo, tarjeta, r.volcado);
        if (r.aviso) {
            estadoMemoria(cuerpo, r.aviso, 'aviso');
        }
        cargarResumen(); // la lectura aparece en la actividad reciente
    } catch (error) {
        estadoMemoria(cuerpo, `Error: ${textoError(error)}`, 'error');
        botones.forEach((b) => (b.disabled = false));
    }
}

function deshabilitarBotonesMemoria(cuerpo, deshabilitar) {
    cuerpo.querySelectorAll('[data-mem="leer"], [data-mem="recuperar"], [data-mem="clonar"]')
        .forEach((b) => (b.disabled = deshabilitar));
}

// La confirmación es EN LÍNEA (no un modal aparte): la ficha usa el único
// <dialog>, así que abrir otro modal encima la cerraría.
function clonar(cuerpo, tarjeta) {
    deshabilitarBotonesMemoria(cuerpo, true);
    const caja = cuerpo.querySelector('[data-mem="estado"]');
    caja.className = `rounded-lg p-3 text-xs ${CLASES_MENSAJE.aviso} space-y-2`;
    caja.classList.remove('hidden');
    caja.innerHTML = `
        <p>Se va a <strong class="text-white">escribir</strong> el volcado de «${escaparHtml(tarjeta.nombre)}» en la tarjeta mágica que haya sobre la antena. No se puede deshacer.</p>
        <p>${escaparHtml(AVISO_USO)}</p>
        <div class="flex justify-end gap-2 pt-1">
            <button data-mem="cancelar-clon" class="px-3 py-1.5 bg-cyber-800 hover:bg-slate-700 border border-slate-700 text-slate-200 text-xs font-semibold rounded-lg">Cancelar</button>
            <button data-mem="confirmar-clon" class="px-3 py-1.5 bg-rose-600 hover:bg-rose-500 text-white text-xs font-semibold rounded-lg">Sí, clonar</button>
        </div>`;
    caja.querySelector('[data-mem="cancelar-clon"]').addEventListener('click', () => {
        estadoMemoria(cuerpo, '', 'aviso');
        deshabilitarBotonesMemoria(cuerpo, false);
    });
    caja.querySelector('[data-mem="confirmar-clon"]').addEventListener('click', () => ejecutarClonado(cuerpo, tarjeta));
}

async function ejecutarClonado(cuerpo, tarjeta) {
    estadoMemoria(cuerpo, 'Escribiendo en la tarjeta mágica…', 'aviso');
    try {
        const r = await api().clonar_tarjeta(tarjeta.id);
        estadoMemoria(cuerpo, r.ok ? 'Tarjeta clonada correctamente.' : r.error, r.ok ? 'ok' : 'error');
        if (r.ok) {
            cargarResumen();
        }
    } catch (error) {
        estadoMemoria(cuerpo, `Error al clonar: ${textoError(error)}`, 'error');
    } finally {
        deshabilitarBotonesMemoria(cuerpo, false);
    }
}

function htmlFormularioEdicion(nombre, notas, error) {
    return `
        <label class="block space-y-1">
            <span class="text-xs font-mono text-slate-400">Nombre *</span>
            <input id="editar-nombre" type="text" maxlength="100" value="${escaparHtml(nombre)}"
                class="w-full bg-cyber-950 border border-slate-700 rounded-xl px-3 py-2 text-sm text-slate-200 focus:outline-none focus:border-cyan-500">
        </label>
        <label class="block space-y-1">
            <span class="text-xs font-mono text-slate-400">Notas</span>
            <textarea id="editar-notas" rows="5" maxlength="2000"
                class="w-full bg-cyber-950 border border-slate-700 rounded-xl px-3 py-2 text-sm text-slate-200 focus:outline-none focus:border-cyan-500">${escaparHtml(notas)}</textarea>
        </label>
        ${error ? `<p class="text-xs text-rose-200 bg-rose-950/30 border border-rose-500/40 rounded-lg p-2">${escaparHtml(error)}</p>` : ''}`;
}

async function editarTarjeta(id) {
    const tarjeta = await pedirTarjeta(id);
    if (!tarjeta) {
        return;
    }
    let nombre = tarjeta.nombre;
    let notas = tarjeta.notas;
    let error = '';
    // Si Python rechaza los datos, se vuelve a abrir con lo escrito y el motivo.
    for (;;) {
        const valor = await abrirModal({
            titulo: `Editar «${tarjeta.nombre}»`,
            html: htmlFormularioEdicion(nombre, notas, error),
            botones: [
                { texto: 'Cancelar', valor: 'cancelar' },
                { texto: 'Guardar cambios', valor: 'guardar', estilo: 'primario' },
            ],
        });
        if (valor !== 'guardar') {
            return;
        }
        nombre = $('editar-nombre').value;
        notas = $('editar-notas').value;
        const resultado = await api().editar_tarjeta(id, nombre, notas);
        if (resultado.ok) {
            mostrarMensaje('base-mensaje', 'Cambios guardados.', 'ok');
            cargarTarjetas();
            return;
        }
        error = resultado.error;
    }
}

async function borrarTarjeta(id, nombre) {
    const aceptado = await confirmar(
        'Borrar tarjeta',
        `<p>¿Borrar «<strong class="text-white">${escaparHtml(nombre)}</strong>» de la base de datos?</p>
         <p class="text-xs text-slate-400">No se puede deshacer. Si la necesitas más adelante, expórtala antes.</p>`,
        'Borrar',
    );
    if (!aceptado) {
        return;
    }
    const resultado = await api().borrar_tarjeta(id);
    mostrarMensaje('base-mensaje', resultado.ok ? `Se ha borrado «${nombre}».` : resultado.error, resultado.ok ? 'ok' : 'error');
    cargarTarjetas();
    cargarResumen();
}

// ==================== EXPORTAR E IMPORTAR ====================

async function exportarTarjetas() {
    mostrarMensaje('base-mensaje', '');
    try {
        const resultado = await api().exportar_tarjetas();
        if (resultado.cancelado) {
            return;
        }
        mostrarMensaje(
            'base-mensaje',
            resultado.ok ? `${cantidadTarjetas(resultado.cantidad, 'exportada')} a ${resultado.ruta}` : resultado.error,
            resultado.ok ? 'ok' : 'error',
        );
        cargarResumen();
    } catch (error) {
        mostrarMensaje('base-mensaje', `Error al exportar: ${textoError(error)}`, 'error');
    }
}

function htmlResumenImportacion(r) {
    let html = `<p>Archivo: <span class="font-mono text-slate-100">${escaparHtml(r.archivo)}</span></p>
        <p class="text-base"><strong class="text-emerald-300">${escaparHtml(cantidadTarjetas(r.importadas, 'importada'))}</strong>,
        <strong class="${r.rechazadas.length ? 'text-rose-300' : 'text-slate-300'}">${r.rechazadas.length}</strong> rechazada${r.rechazadas.length === 1 ? '' : 's'}.</p>`;

    if (r.rechazadas.length) {
        html += `<div class="border border-slate-800 rounded-lg divide-y divide-slate-800">
            ${r.rechazadas.map((x) => `
                <div class="p-2 text-xs">
                    <span class="font-mono text-slate-500">#${Number(x.posicion)}</span>
                    <span class="text-slate-200">${escaparHtml(x.nombre || '(sin nombre)')}</span>
                    <div class="text-rose-300 mt-0.5">${escaparHtml(x.motivo)}</div>
                </div>`).join('')}
        </div>`;
    }
    if (r.campos_ignorados.length) {
        html += `<p class="text-xs text-amber-200 bg-amber-950/30 border border-amber-500/30 rounded-lg p-2">
            Se han ignorado estos campos del archivo (los comandos nunca se importan; se generan siempre a partir del tipo y el UID):
            <span class="font-mono">${r.campos_ignorados.map(escaparHtml).join(', ')}</span></p>`;
    }
    return html;
}

async function importarTarjetas() {
    mostrarMensaje('base-mensaje', '');
    try {
        const resultado = await api().importar_tarjetas();
        if (resultado.cancelado) {
            return;
        }
        if (!resultado.ok) {
            mostrarMensaje('base-mensaje', resultado.error, 'error');
            return;
        }
        cargarTarjetas();
        cargarResumen();
        await abrirModal({
            titulo: 'Resultado de la importación',
            html: htmlResumenImportacion(resultado),
            botones: [{ texto: 'Cerrar', valor: 'cerrar', estilo: 'primario' }],
        });
    } catch (error) {
        mostrarMensaje('base-mensaje', `Error al importar: ${textoError(error)}`, 'error');
    }
}

function iniciarSeccionBaseDatos() {
    $('base-buscar').addEventListener('input', alEscribirBusqueda);
    $('base-banda').addEventListener('change', cargarTarjetas);
    $('base-filas').addEventListener('click', alPulsarEnTabla);
    $('btn-exportar').addEventListener('click', exportarTarjetas);
    $('btn-importar').addEventListener('click', importarTarjetas);
}
