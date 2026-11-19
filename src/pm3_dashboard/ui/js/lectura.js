/* PM3 Dashboard — sección Lectura: escanear una tarjeta y guardarla.
 * La lectura la guarda Python; aquí solo se envían el nombre y las notas.
 */
'use strict';

let lecturaActual = null;

async function escanear() {
    mostrar('lectura-error', false);
    await conBotonOcupado('btn-escanear', 'btn-escanear-texto', 'Buscando tarjeta…', async () => {
        try {
            const resultado = await api().escanear($('lectura-banda').value);
            if (resultado.ok) {
                pintarLectura(resultado.tarjeta);
            } else {
                lecturaActual = null;
                mostrar('lectura-resultado', false);
                ponerTexto('lectura-error', resultado.error);
                mostrar('lectura-error', true);
            }
        } catch (error) {
            ponerTexto('lectura-error', `Error al escanear: ${textoError(error)}`);
            mostrar('lectura-error', true);
        }
    });
    cargarResumen(); // la lectura aparece en la actividad reciente
}

function pintarLectura(tarjeta) {
    lecturaActual = tarjeta;
    $('lectura-ficha').innerHTML = htmlFichaTarjeta(tarjeta);

    const guardadas = tarjeta.guardadas_con_mismo_uid || [];
    ponerTexto('lectura-ya-guardada', guardadas.length
        ? `Ya tienes ${guardadas.length === 1 ? 'una tarjeta guardada' : `${guardadas.length} tarjetas guardadas`} con este UID: ${guardadas.join(', ')}.`
        : '');
    mostrar('lectura-ya-guardada', guardadas.length > 0);

    $('guardar-nombre').value = '';
    $('guardar-notas').value = '';
    $('btn-guardar').disabled = false;
    mostrarMensaje('guardar-mensaje', '');
    mostrar('lectura-resultado', true);

    // Leer bloques solo tiene sentido en HF; se parte de cero en cada escaneo.
    $('lectura-bloques-tabla').innerHTML = '';
    mostrar('lectura-bloques-estado', false);
    $('btn-leer-lectura').disabled = false;
    mostrar('lectura-bloques', tarjeta.banda === 'hf');

    $('guardar-nombre').focus();
}

async function leerBloquesLectura() {
    if (!lecturaActual) {
        return;
    }
    const boton = $('btn-leer-lectura');
    boton.disabled = true;
    const estado = (texto, tipo) => {
        const caja = $('lectura-bloques-estado');
        caja.className = `rounded-lg p-2 text-xs ${CLASES_MENSAJE[tipo]}`;
        caja.innerHTML = texto;
        caja.classList.remove('hidden');
    };
    const esClassic = String(lecturaActual.tipo).startsWith('MIFARE Classic');
    estado(esClassic
        ? 'Leyendo la tarjeta… Si no tiene claves de fábrica, puede tardar varios minutos. No cierres la aplicación.'
        : 'Leyendo la memoria de la tarjeta…', 'aviso');
    try {
        const r = await api().leer_bloques_lectura(lecturaActual.id_lectura);
        if (!r.ok) {
            estado(htmlFalloConSalida(r), 'error');  // incluye la salida del cliente
            boton.disabled = false;
            return;
        }
        mostrar('lectura-bloques-estado', false);
        // Misma vista de bloques que la ficha (hex, ASCII, claves y accesos), de solo lectura.
        $('lectura-bloques-tabla').innerHTML = htmlTablaVolcado(r.volcado, false);
        cargarResumen();
    } catch (error) {
        estado(`Error: ${escaparHtml(textoError(error))}`, 'error');
        boton.disabled = false;
    }
}

async function guardarLectura(evento) {
    evento.preventDefault();
    if (!lecturaActual) {
        return;
    }
    const boton = $('btn-guardar');
    boton.disabled = true;
    let guardada = false;
    try {
        const resultado = await api().guardar_tarjeta(
            lecturaActual.id_lectura, $('guardar-nombre').value, $('guardar-notas').value,
        );
        if (resultado.ok) {
            guardada = true;
            lecturaActual = null;
            mostrarMensaje('guardar-mensaje', 'Tarjeta guardada. Puedes verla en la sección Base de datos.', 'ok');
            cargarResumen();
        } else {
            mostrarMensaje('guardar-mensaje', resultado.error, 'error');
        }
    } catch (error) {
        mostrarMensaje('guardar-mensaje', `Error al guardar: ${textoError(error)}`, 'error');
    } finally {
        boton.disabled = guardada; // una lectura solo se guarda una vez
    }
}

function iniciarSeccionLectura() {
    $('btn-escanear').addEventListener('click', escanear);
    $('form-guardar').addEventListener('submit', guardarLectura);
    $('btn-leer-lectura').addEventListener('click', leerBloquesLectura);
}
