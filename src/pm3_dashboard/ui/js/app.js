/* PM3 Dashboard — menú lateral y arranque. Se carga después de las secciones. */
'use strict';

// ==================== SECCIONES DEL MENÚ ====================

const SECCIONES = [
    { id: 'inicio',   titulo: 'Inicio',               descripcion: '' },
    { id: 'antenas',  titulo: 'Antenas',              descripcion: 'Medición de las antenas LF y HF con hw tune.' },
    { id: 'lectura',  titulo: 'Lectura',              descripcion: '' },
    { id: 'clonado',  titulo: 'Clonado y emulación',  descripcion: 'Para clonar una tarjeta HF, ábrela en Base de datos, lee sus bloques y pulsa «Clonar». La emulación llegará en una próxima versión.' },
    { id: 'base',     titulo: 'Base de datos',        descripcion: '' },
    { id: 'terminal', titulo: 'Terminal',             descripcion: 'Consola para enviar comandos al cliente de Iceman.' },
];

// Qué hacer al entrar en cada sección (refrescar sus datos).
const AL_ENTRAR = {
    inicio: () => cargarResumen(),
    base: () => cargarTarjetas(),
};

const CLASE_NAV_ACTIVO = 'flex items-center gap-3 px-3.5 py-2.5 rounded-xl text-sm font-medium transition bg-cyan-600/15 text-cyan-300 border border-cyan-500/30';
const CLASE_NAV_INACTIVO = 'flex items-center gap-3 px-3.5 py-2.5 rounded-xl text-sm font-medium transition text-slate-400 hover:text-white hover:bg-slate-800/60 border border-transparent';
const CLASE_NUM_ACTIVO = 'w-6 h-6 rounded-lg bg-cyan-500/20 flex items-center justify-center font-mono text-xs font-bold';
const CLASE_NUM_INACTIVO = 'w-6 h-6 rounded-lg bg-slate-800 flex items-center justify-center font-mono text-xs font-bold';

function crearMenu() {
    const menu = $('menu');
    SECCIONES.forEach((seccion, indice) => {
        const boton = document.createElement('button');
        boton.id = `nav-${seccion.id}`;
        boton.innerHTML = `<span class="${CLASE_NUM_INACTIVO}">${indice}</span><span>${escaparHtml(seccion.titulo)}</span>`;
        boton.addEventListener('click', () => mostrarSeccion(seccion.id));
        menu.appendChild(boton);
    });
}

function mostrarSeccion(id) {
    const seccion = SECCIONES.find((s) => s.id === id);

    SECCIONES.forEach((s) => {
        const boton = $(`nav-${s.id}`);
        const activo = s.id === id;
        boton.className = activo ? CLASE_NAV_ACTIVO : CLASE_NAV_INACTIVO;
        boton.firstElementChild.className = activo ? CLASE_NUM_ACTIVO : CLASE_NUM_INACTIVO;
    });

    document.querySelectorAll('[data-seccion]').forEach((el) => el.classList.add('hidden'));

    const propia = $(`seccion-${id}`);
    if (propia) {
        propia.classList.remove('hidden');
        if (apiLista && AL_ENTRAR[id]) {
            AL_ENTRAR[id]();
        }
    } else {
        ponerTexto('proximamente-titulo', seccion.titulo);
        ponerTexto('proximamente-descripcion', seccion.descripcion);
        mostrar('seccion-proximamente', true);
    }
}

// ==================== ARRANQUE ====================

let apiLista = false;

function apiDisponible() {
    return Boolean(window.pywebview && window.pywebview.api && window.pywebview.api.obtener_resumen);
}

// Carga inicial: se llama desde DOMContentLoaded y desde 'pywebviewready'
// (no se sabe cuál llega antes), pero solo debe cargar una vez.
function alEstarListaLaApi() {
    if (apiLista || !apiDisponible()) {
        return;
    }
    apiLista = true;
    cargarTodo();
    setInterval(comprobarConexion, INTERVALO_CONEXION_MS);
}

document.addEventListener('DOMContentLoaded', () => {
    crearMenu();
    iniciarSeccionInicio();
    iniciarSeccionLectura();
    iniciarSeccionBaseDatos();
    mostrarSeccion('inicio');
    alEstarListaLaApi();

    // Si tras unos segundos no aparece pywebview, se ha abierto fuera de la app.
    setTimeout(() => {
        if (!apiLista) {
            mostrarError('Sin conexión con Python: abre la interfaz con "python -m pm3_dashboard", no directamente en el navegador.');
            pintarEstado({ conectado: false, mensaje: 'La interfaz no está conectada con Python.' });
        }
    }, 3000);
});

// pywebview lanza este evento cuando window.pywebview.api está lista.
window.addEventListener('pywebviewready', alEstarListaLaApi);
