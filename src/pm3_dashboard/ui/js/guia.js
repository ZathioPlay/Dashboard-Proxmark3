/* PM3 Dashboard — sección Guía de comandos: referencia de los comandos más usados
 * del cliente de Iceman, con descripción y un ejemplo de salida.
 * Las salidas son EJEMPLOS con el formato real de Iceman; los valores concretos
 * (UID, voltajes…) son ilustrativos y variarán en tu Proxmark.
 */
'use strict';

const GUIA = [
    {
        categoria: 'Hardware',
        comandos: [
            {
                cmd: 'hw version',
                desc: 'Muestra la versión del cliente y del firmware de la Proxmark3.',
                salida: `[usb] pm3 --> hw version
 [ CLIENT ]
  client: RRG/Iceman/master/v4.18994-48-gd2e0a3b4d 2024-07-21
 [ PROXMARK3 ]
  device.................... RDV4
 [ ARM ]
       os: RRG/Iceman/master/v4.18994-48-gd2e0a3b4d 2024-07-21`,
            },
            {
                cmd: 'hw status',
                desc: 'Estado del dispositivo: memoria, FPGA, reloj y temperatura.',
                salida: `[usb] pm3 --> hw status
[=] Memory
[=]   BigBuf_size............. 40States
[=] Flash memory
[=]   Baudrate................ 115200 bps
[=] USART
[=]   Ready................... OK`,
            },
            {
                cmd: 'hw tune',
                desc: 'Mide el voltaje y la sintonía de las antenas LF y HF. Solo informativo.',
                salida: `[usb] pm3 --> hw tune
[=] -------- LF Antenna ----------
[+] LF antenna: 44.28 V - 125.00 kHz
[+] LF antenna ( ok )
[=] -------- HF Antenna ----------
[+] HF antenna: 31.40 V - 13.56 MHz
[+] HF antenna ( ok )`,
            },
        ],
    },
    {
        categoria: 'Baja frecuencia (125 kHz)',
        comandos: [
            {
                cmd: 'lf search',
                desc: 'Detecta e identifica una tarjeta de baja frecuencia sobre la antena.',
                salida: `[usb] pm3 --> lf search
[=] Checking for known tags...
[+] EM 410x ID 0F0368568B
[+] EM410x ( RF/64 )
[+] Valid EM410x ID found!
[+] Chipset detection: T55xx`,
            },
            {
                cmd: 'lf em 410x reader',
                desc: 'Lee el identificador de una tarjeta EM410x (EM4100).',
                salida: `[usb] pm3 --> lf em 410x reader
[+] EM 410x ID 0F0368568B
[+] EM410x ( RF/64 )`,
            },
            {
                cmd: 'lf em 410x clone --id <id>',
                desc: 'Graba un identificador EM410x en una tarjeta regrabable T5577.',
                escritura: true,
                salida: `[usb] pm3 --> lf em 410x clone --id 0F0368568B
[+] Preparing to clone EM4100 to T55x7 with ID 0F0368568B
[+] Done!
[?] Hint: try \`lf em 410x reader\` to verify`,
            },
        ],
    },
    {
        categoria: 'Alta frecuencia — MIFARE Classic (13.56 MHz)',
        comandos: [
            {
                cmd: 'hf search',
                desc: 'Detecta e identifica una tarjeta de alta frecuencia (NFC).',
                salida: `[usb] pm3 --> hf search
[+]  UID: 5A 3E 7C 1B
[+] ATQA: 00 04
[+]  SAK: 08 [2]
[+] Possible types:
[+]    MIFARE Classic 1K
[+] Valid ISO 14443-A tag found`,
            },
            {
                cmd: 'hf mf autopwn',
                desc: 'Prueba las claves por defecto y, si hacen falta, las recupera; luego vuelca la tarjeta. Puede tardar varios minutos.',
                salida: `[usb] pm3 --> hf mf autopwn
[+] Found 16 sectors
[=] Loading default keys dictionary...
[+] target sector 5 key type A -- found valid key [A0B1C2D3E4F5]
[+] Transfering keys to simulator memory...
[+] Saved to \`hf-mf-5A3E7C1B-dump.bin\``,
            },
            {
                cmd: 'hf mf dump',
                desc: 'Vuelca la memoria de una MIFARE Classic usando un fichero de claves ya conocido.',
                salida: `[usb] pm3 --> hf mf dump
[+] Successfully downloaded data
[=]   0  | 5A 3E 7C 1B 88 08 04 00 62 63 64 65 66 67 68 69
[=]   1  | 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00
[+] Saved 1024 bytes to binary file \`hf-mf-5A3E7C1B-dump.bin\``,
            },
            {
                cmd: 'hf mf rdbl --blk <n> -k <clave>',
                desc: 'Lee un bloque concreto con la clave indicada (clave A por defecto).',
                salida: `[usb] pm3 --> hf mf rdbl --blk 4 -k FFFFFFFFFFFF
[=]   # | sector 01 / 0x01   | data
[=]   4 | 11 22 33 44 55 66 77 88 99 AA BB CC DD EE FF 00`,
            },
            {
                cmd: 'hf mf wrbl --blk <n> -k <clave> -d <datos>',
                desc: 'Escribe 16 bytes en un bloque. No escribas en el bloque trailer salvo que sepas lo que haces.',
                escritura: true,
                salida: `[usb] pm3 --> hf mf wrbl --blk 4 -k FFFFFFFFFFFF -d 00112233445566778899AABBCCDDEEFF
[=] Writing block no 4, key A - FFFFFFFFFFFF
[+] Write ( ok )`,
            },
        ],
    },
    {
        categoria: 'Ultralight / NTAG',
        comandos: [
            {
                cmd: 'hf mfu info',
                desc: 'Muestra la información de una tarjeta Ultralight / NTAG (tipo, firma, contadores).',
                salida: `[usb] pm3 --> hf mfu info
[=] --- Tag Information
[+]       TYPE: NTAG 215 504bytes (NT2H1511G0DU)
[+]        UID: 04 68 95 71 FA 5C 64
[+]     Signature validation: successful`,
            },
            {
                cmd: 'hf mfu dump',
                desc: 'Vuelca la memoria (páginas de 4 bytes) de una Ultralight / NTAG.',
                salida: `[usb] pm3 --> hf mfu dump
[=] Blk | Data        | Ascii
[=] 00  | 04 68 95 71  | ....
[=] 03  | E1 10 12 00  | ....
[=] 04  | 03 10 D1 01  | ....
[+] Saved to \`hf-mfu-04689571-dump.bin\``,
            },
        ],
    },
    {
        categoria: 'Datos y otros',
        comandos: [
            {
                cmd: 'data plot',
                desc: 'Abre la ventana con la gráfica de la última señal capturada.',
                salida: `[usb] pm3 --> data plot
[=] Use scroll to zoom, clic to move trace, press h for help`,
            },
            {
                cmd: 'hw dbg',
                desc: 'Consulta o cambia el nivel de mensajes de depuración del dispositivo.',
                salida: `[usb] pm3 --> hw dbg
[=] Debug log level... 1 ( error )`,
            },
        ],
    },
];

const AVISO_GUIA = 'Usa estos comandos solo con tarjetas propias o con autorización expresa de su titular.';

function htmlComandoGuia(c) {
    const insignia = c.escritura
        ? '<span class="px-1.5 py-0.5 rounded text-[10px] font-mono bg-rose-500/15 text-rose-300">ESCRITURA</span>'
        : '';
    return `
        <div class="bg-cyber-900 border ${c.escritura ? 'border-rose-500/30' : 'border-slate-800'} rounded-xl p-4 space-y-2" data-cmd="${escaparHtml(c.cmd)}">
            <div class="flex items-center justify-between gap-2 flex-wrap">
                <code class="font-mono text-sm text-cyan-300 break-all cursor-pointer" data-guia="copiar" title="Clic para copiar">${escaparHtml(c.cmd)}</code>
                <div class="flex items-center gap-1.5 shrink-0">
                    ${insignia}
                    <button data-guia="copiar" class="px-2 py-1 rounded-lg bg-cyber-800 hover:bg-slate-700 text-[11px] text-slate-200">Copiar</button>
                    <button data-guia="terminal" class="px-2 py-1 rounded-lg bg-cyber-800 hover:bg-slate-700 text-[11px] text-cyan-300">Enviar a Terminal</button>
                </div>
            </div>
            <p class="text-sm text-slate-300">${escaparHtml(c.desc)}</p>
            ${c.escritura ? '<p class="text-[11px] text-rose-300/90">Modifica la tarjeta. Hazlo solo en tarjetas propias.</p>' : ''}
            <details>
                <summary class="cursor-pointer text-xs text-slate-400 hover:text-slate-200">Ejemplo de salida</summary>
                <pre class="salida-cliente mt-2 bg-cyber-950 border border-slate-800 rounded-lg p-3 text-[11px] font-mono text-slate-300 overflow-x-auto">${escaparHtml(c.salida)}</pre>
            </details>
        </div>`;
}

function htmlCategoriaGuia(cat) {
    return `
        <div class="space-y-3">
            <h3 class="text-sm font-mono uppercase tracking-wider text-cyan-400">${escaparHtml(cat.categoria)}</h3>
            <div class="grid grid-cols-1 lg:grid-cols-2 gap-3">
                ${cat.comandos.map(htmlComandoGuia).join('')}
            </div>
        </div>`;
}

async function copiarComandoGuia(boton) {
    const cmd = boton.closest('[data-cmd]').dataset.cmd;
    const ok = await copiarTexto(cmd);
    const original = boton.tagName === 'BUTTON' ? boton.textContent : null;
    if (original !== null) {
        boton.textContent = ok ? 'Copiado ✓' : 'No se pudo';
        setTimeout(() => (boton.textContent = original), 1200);
    }
}

function alPulsarGuia(ev) {
    const boton = ev.target.closest('[data-guia]');
    if (!boton) {
        return;
    }
    const cmd = boton.closest('[data-cmd]').dataset.cmd;
    if (boton.dataset.guia === 'copiar') {
        copiarComandoGuia(boton);
    } else if (boton.dataset.guia === 'terminal') {
        mostrarSeccion('terminal');
        ponerEnTerminal(cmd);
    }
}

function iniciarSeccionGuia() {
    const cont = $('guia-lista');
    cont.innerHTML = GUIA.map(htmlCategoriaGuia).join('');
    cont.addEventListener('click', alPulsarGuia);
    ponerTexto('guia-aviso', AVISO_GUIA);
}
