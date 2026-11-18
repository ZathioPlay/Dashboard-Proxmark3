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
    $('guardar-nombre').focus();
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
}
