/* PM3 Dashboard — menú lateral y arranque. Se carga después de las secciones. */
'use strict';

// ==================== SECCIONES DEL MENÚ ====================

// Cada sección lleva su icono (el 'd' de un SVG lineal de 24x24).
const SECCIONES = [
    { id: 'inicio',   titulo: 'Inicio',              icono: 'M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6' },
    { id: 'antenas',  titulo: 'Antenas',             icono: 'M8.111 16.404a5.5 5.5 0 017.778 0M12 20h.01m-7.08-7.071c3.904-3.905 10.236-3.905 14.141 0M1.394 9.393c5.857-5.857 15.355-5.857 21.213 0' },
    { id: 'lectura',  titulo: 'Lectura',             icono: 'M3 10h18M7 15h1m4 0h1m-7 4h12a3 3 0 003-3V8a3 3 0 00-3-3H6a3 3 0 00-3 3v8a3 3 0 003 3z' },
    { id: 'clonado',  titulo: 'Clonado y emulación', icono: 'M8 7v8a2 2 0 002 2h6M8 7V5a2 2 0 012-2h4.586a1 1 0 01.707.293l4.414 4.414a1 1 0 01.293.707V15a2 2 0 01-2 2h-2M8 7H6a2 2 0 00-2 2v10a2 2 0 002 2h8a2 2 0 002-2v-2' },
    { id: 'base',     titulo: 'Base de datos',       icono: 'M4 7v10c0 2.21 3.582 4 8 4s8-1.79 8-4V7M4 7c0 2.21 3.582 4 8 4s8-1.79 8-4M4 7c0-2.21 3.582-4 8-4s8 1.79 8 4m0 5c0 2.21-3.582 4-8 4s-8-1.79-8-4' },
    { id: 'terminal', titulo: 'Terminal',            icono: 'M8 9l3 3-3 3m5 0h3M5 20h14a2 2 0 002-2V6a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z' },
    { id: 'guia',     titulo: 'Guía de comandos',    icono: 'M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253' },
];

// Qué hacer al entrar en cada sección (refrescar sus datos).
const AL_ENTRAR = {
    inicio: () => cargarResumen(),
    antenas: () => cargarAntenas(),
    base: () => cargarTarjetas(),
    clonado: () => cargarSeccionClonado(),
    terminal: () => cargarEstadoConsola(),
};

const CLASE_NAV_ACTIVO = 'flex items-center gap-3 px-3.5 py-2.5 rounded-xl text-sm font-medium transition bg-cyan-600/15 text-cyan-300 border border-cyan-500/30';
const CLASE_NAV_INACTIVO = 'flex items-center gap-3 px-3.5 py-2.5 rounded-xl text-sm font-medium transition text-slate-400 hover:text-white hover:bg-slate-800/60 border border-transparent';

// El icono usa stroke="currentColor", así que su color sigue al del botón (activo/inactivo).
function iconoMenu(d) {
    return `<svg class="w-5 h-5 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="${d}"></path></svg>`;
}

function crearMenu() {
    const menu = $('menu');
    SECCIONES.forEach((seccion) => {
        const boton = document.createElement('button');
        boton.id = `nav-${seccion.id}`;
        boton.innerHTML = `${iconoMenu(seccion.icono)}<span>${escaparHtml(seccion.titulo)}</span>`;
        boton.addEventListener('click', () => mostrarSeccion(seccion.id));
        menu.appendChild(boton);
    });
}

function mostrarSeccion(id) {
    SECCIONES.forEach((s) => {
        const boton = $(`nav-${s.id}`);
        boton.className = s.id === id ? CLASE_NAV_ACTIVO : CLASE_NAV_INACTIVO;
    });

    document.querySelectorAll('[data-seccion]').forEach((el) => el.classList.add('hidden'));
    $(`seccion-${id}`).classList.remove('hidden');
    if (apiLista && AL_ENTRAR[id]) {
        AL_ENTRAR[id]();
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
    iniciarSeccionAntenas();
    iniciarSeccionLectura();
    iniciarSeccionBaseDatos();
    iniciarSeccionClonado();
    iniciarSeccionTerminal();
    iniciarSeccionGuia();
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
