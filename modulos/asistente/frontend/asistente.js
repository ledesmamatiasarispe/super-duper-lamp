'use strict';
// ── ASISTENTE: la barra "Preguntá algo" arriba de todo ──
// Va en la barra de arriba (una fila propia, siempre visible). La respuesta se muestra en un panel debajo, a medida que
// llega (ver servicios.preguntar: directa / con IA / resumen sin IA).
// Micrófono: si el navegador trae reconocimiento de voz y la página es segura (http://localhost en la PC, o https), hay
// un botón 🎤. En un celular entrando por la red (http://192.168...) el navegador no lo permite: se dicta con el
// micrófono del teclado (el de Google en Android), que funciona en cualquier campo de texto.

const _asisRec = window.SpeechRecognition || window.webkitSpeechRecognition;
const _asisMicro = !!_asisRec && window.isSecureContext;
const _asisTactil = window.matchMedia?.('(pointer: coarse)').matches;
let _asisPedido = null;      // AbortController de la pregunta en curso
let _asisEscucha = null;     // reconocimiento de voz en curso
let _asisEnlaces = [];       // los botones de la respuesta que se está mostrando
let _asisSiNoFigura = null;  // lo que se ofrece si la IA contesta "No figura en la app"
let _asisAyudaCache = null;
// La conversación: las últimas preguntas con su respuesta y de qué hablaron (tema), para que "¿y el aceite?" siga con la
// misma máquina y la IA entienda a qué se refiere. Vive en esta pestaña; "Nueva" la borra, y se olvida sola tras 30 min
// sin preguntar. El servidor recorta lo que manda a la IA (servicios._historial).
let _asisCharla = [];
let _asisUltima = 0;
let _asisActual = '';        // la pregunta que se está contestando
const _ASIS_TURNOS = 6, _ASIS_OLVIDO_MS = 30 * 60 * 1000;
const _ASIS_PISTA = 'Preguntá algo… por ejemplo: ¿qué le pasó al lavador de humos?';
const _ASIS_PISTA_SEGUIR = 'Seguí preguntando… (por ejemplo: ¿y cuándo fue el último servicio?)';
// Las acciones que un módulo ofrece en las respuestas (por ejemplo, abrir un formulario ya completado):
//   window.asisAcciones.<nombre> = datos => {...}     (el módulo puede registrarla antes o después de este archivo)
window.asisAcciones = window.asisAcciones || {};

function _asisArmar() {
  const barra = $('.barra');
  if (!barra || $('#asis-form')) return;
  const form = document.createElement('form');
  form.id = 'asis-form';
  form.className = 'asis-form';
  form.setAttribute('role', 'search');
  form.innerHTML = `
    <span class="asis-lupa" aria-hidden="true">🔎</span>
    <input id="asis-pregunta" name="pregunta" type="search" enterkeyhint="search" autocomplete="off" maxlength="300"
      placeholder="${_ASIS_PISTA}" aria-label="Preguntale a la app">
    ${_asisMicro ? '<button id="asis-micro" class="asis-micro" type="button" title="Preguntar hablando">🎤</button>' : ''}
    <button class="asis-enviar" type="submit">Preguntar</button>`;
  barra.appendChild(form);
  const panel = document.createElement('div');
  panel.id = 'asis-panel';
  panel.className = 'asis-panel oculto';
  panel.setAttribute('aria-live', 'polite');
  barra.after(panel);
  const medir = () => document.documentElement.style.setProperty('--asis-alto', barra.getBoundingClientRect().bottom + 'px');
  window.addEventListener('resize', medir);
  window.addEventListener('scroll', medir, { passive: true });
  new ResizeObserver(medir).observe(barra);

  form.addEventListener('submit', ev => { ev.preventDefault(); asisPreguntar($('#asis-pregunta').value); });
  $('#asis-micro')?.addEventListener('click', _asisDictar);
  document.addEventListener('keydown', ev => { if (ev.key === 'Escape' && !$('#asis-panel').classList.contains('oculto')) asisCerrar(); });
  document.addEventListener('pointerdown', ev => {
    if (!ev.target.closest?.('#asis-panel, #asis-form, #modal')) asisCerrar();
  });
}

/** Hace la pregunta y muestra la respuesta a medida que llega, debajo de lo que ya se venía preguntando.
 *  `sinTema`: contestar sin pegarle el tema de la pregunta anterior ("Preguntar en general"). */
async function asisPreguntar(texto, { sinTema = false } = {}) {
  const pregunta = String(texto || '').trim();
  const campo = $('#asis-pregunta');
  if (!pregunta) return campo.focus();
  _asisPedido?.abort();
  const pedido = _asisPedido = new AbortController();
  if (Date.now() - _asisUltima > _ASIS_OLVIDO_MS) _asisCharla = [];
  _asisUltima = Date.now();
  _asisActual = pregunta;
  campo.value = '';                           // la barra queda lista para la próxima
  campo.placeholder = _ASIS_PISTA_SEGUIR;
  const panel = $('#asis-panel');
  panel.classList.remove('oculto');
  document.documentElement.style.setProperty('--asis-alto', $('.barra').getBoundingClientRect().bottom + 'px');
  const anteriores = _asisCharla.map(t => `<details class="asis-turno"><summary><span class="asis-p">${esc(t.pregunta)}</span>
      ${t.titulo ? `<span class="chip">${esc(t.titulo)}</span>` : ''}</summary><div class="asis-texto">${_asisFormato(t.respuesta)}</div></details>`).join('');
  panel.innerHTML = `<div class="asis-cabeza">${_asisCharla.length ? `<span class="sutil">Conversación · ${_asisCharla.length + 1} preguntas</span>` : ''}
      <span class="asis-acciones">${_asisCharla.length ? '<button class="chico" type="button" onclick="asisNueva()" title="Olvidar lo que se venía preguntando">Nueva</button>' : ''}
      <button class="link" type="button" onclick="asisCerrar()" title="Cerrar (Esc)">✕</button></span></div>
    ${anteriores ? `<div class="asis-anteriores">${anteriores}</div>` : ''}
    <div class="asis-actual"><div class="asis-cabeza"><b class="asis-titulo">${esc(pregunta)}</b></div>
    <p class="asis-estado sutil">Buscando…</p><div class="asis-texto"></div><div class="asis-enlaces"></div></div>`;
  panel.scrollTop = panel.scrollHeight;
  const actual = $('.asis-actual', panel);     // lo de esta pregunta (las anteriores tienen las mismas clases)
  const historial = _asisCharla.map(({ pregunta, respuesta, tema }) => ({ pregunta, respuesta, tema }));
  const inicio = Date.now();
  const reloj = setInterval(() => {
    const e = $('.asis-estado', actual);
    if (e && e.dataset.esperando) e.textContent = `${e.dataset.esperando} ${Math.round((Date.now() - inicio) / 1000)} s`;
  }, 500);
  let escrito = '';
  try {
    const r = await fetch('/api/asistente/preguntar', {
      method: 'POST', signal: pedido.signal,
      headers: { 'Content-Type': 'application/json', Authorization: 'Bearer ' + S.token },
      body: JSON.stringify({ pregunta, ayuda: _asisAyuda(), historial, sin_tema: sinTema }),
    });
    if (r.status === 401) return salir();
    if (!r.ok) throw new Error((await r.json().catch(() => ({}))).detail || 'No se pudo preguntar.');
    const lector = r.body.getReader(), deco = new TextDecoder();
    let resto = '';
    for (;;) {
      const { value, done } = await lector.read();
      if (done) break;
      resto += deco.decode(value, { stream: true });
      const lineas = resto.split('\n');
      resto = lineas.pop();
      for (const l of lineas) if (l.trim()) escrito = _asisEvento(JSON.parse(l), actual, escrito);
    }
    if (pedido === _asisPedido) {            // terminó (no la cortó otra pregunta): pasa a ser parte de la conversación
      _asisCharla = [..._asisCharla, { pregunta, respuesta: escrito.trim(), tema: actual.dataset.tema || '',
        titulo: actual.dataset.titulo || '' }].slice(-_ASIS_TURNOS);
    }
  } catch (e) {
    if (e.name === 'AbortError') return;
    $('.asis-estado', actual).outerHTML = `<p class="error">${esc(e.message)}</p>`;
  } finally {
    clearInterval(reloj);
  }
}

function _asisEvento(e, panel, escrito) {
  const estado = $('.asis-estado', panel);
  if (e.tipo === 'inicio') {
    if (e.titulo) $('.asis-titulo', panel).insertAdjacentHTML('afterend', `<span class="chip">${esc(e.titulo)}</span>`);
    panel.dataset.tema = e.tema || '';
    panel.dataset.titulo = e.titulo || '';
    // se contestó sobre lo que se venía hablando: se dice, y se puede preguntar sin eso
    if (e.sigue) estado.insertAdjacentHTML('beforebegin', `<p class="asis-sigue sutil">Sobre <b>${esc(e.titulo || e.sigue)}</b>,
      por lo que venías preguntando. <button type="button" class="link" onclick="asisSinTema()">Preguntar en general</button></p>`);
    const textos = { ia: 'La IA está eligiendo en los datos lo que contesta la pregunta…', directa: '', resumen: '', nada: '' };
    estado.dataset.esperando = textos[e.modo] || '';
    estado.textContent = estado.dataset.esperando;
    if (e.aviso) estado.insertAdjacentHTML('afterend', `<p class="asis-aviso">${esc(e.aviso)}</p>`);
    _asisEnlaces = [...(e.enlaces || [])];
    $('.asis-enlaces', panel).innerHTML = _asisEnlaces.map((x, i) =>
      `<button type="button" class="chico${x.accion && x.accion !== 'preguntar' ? ' primario' : ''}" onclick="asisEnlace(${i})">${esc(x.texto)}</button>`).join('');
    panel.dataset.modo = e.modo;
    _asisSiNoFigura = e.si_no_figura || null;
  } else if (e.tipo === 'texto') {
    escrito += e.texto;
    $('.asis-texto', panel).innerHTML = _asisFormato(escrito);
    if (estado.dataset.esperando) { delete estado.dataset.esperando; estado.textContent = ''; }
  } else if (e.tipo === 'aviso') {
    $('.asis-texto', panel).insertAdjacentHTML('afterend', `<p class="asis-aviso">${esc(e.aviso)}</p>`);
  } else if (e.tipo === 'fin') {
    delete estado.dataset.esperando;
    const como = { ia: 'Elegido por la IA local: lo de abajo es copia fiel de la app; la primera línea la escribió la IA.',
      directa: 'Respondido por la app, con sus propios cálculos.', resumen: 'Resumen de la app (sin IA).', nada: '' }[panel.dataset.modo] || '';
    estado.textContent = como ? `${como} · ${e.segundos} s` : '';
    if (_asisTactil && !_asisMicro) estado.textContent += ' · Para dictar, usá el micrófono del teclado.';
    // la IA no lo encontró en los datos: se ofrece cargarlo (por ejemplo, como especificación de la máquina)
    const s = _asisSiNoFigura;
    if (s && /no figura/i.test(escrito) && s.enlace) {
      _asisEnlaces.push(s.enlace);
      $('.asis-texto', panel).insertAdjacentHTML('afterend', `<p class="asis-sugerencia">${esc(s.texto)}
        <button type="button" class="chico primario" onclick="asisEnlace(${_asisEnlaces.length - 1})">${esc(s.enlace.texto)}</button></p>`);
    }
  }
  return escrito;
}

/** Un botón de la respuesta: ir a una pantalla, volver a preguntar, o una acción de un módulo (window.asisAcciones). */
function asisEnlace(i) {
  const x = _asisEnlaces[i];
  if (!x) return;
  if (x.ir) return asisIr(x.ir);
  if (x.accion === 'preguntar') return asisPreguntar(x.datos?.pregunta);
  const accion = window.asisAcciones?.[x.accion];
  if (!accion) return avisar('Esta acción no está disponible en esta app.', true);
  asisCerrar();
  accion(x.datos || {});
}

/** Los textos de la Ayuda de todas las pantallas (Ayuda.pasos y el Tour), para contestar "¿cómo cargo…?". Se arma una
 *  vez: los pasos no dependen de estar en esa pantalla (sus `el` son funciones que no se llaman acá). */
function _asisAyuda() {
  if (_asisAyudaCache) return _asisAyudaCache;
  const limpio = t => String(t || '').replace(/<[^>]+>/g, '').replace(/\s+/g, ' ').trim();
  const pasos = [];
  for (const [pantalla, fn] of Object.entries(typeof Ayuda !== 'undefined' ? Ayuda.pasos : {})) {
    try { for (const p of fn() || []) if (p?.texto) pasos.push({ pantalla, titulo: limpio(p.titulo), texto: limpio(p.texto) }); }
    catch { /* una ayuda que necesita su pantalla abierta: se saltea */ }
  }
  for (const p of (typeof Ayuda !== 'undefined' ? Ayuda.tour : [])) {
    if (p?.texto) pasos.push({ pantalla: p.ir || '', titulo: limpio(p.titulo), texto: limpio(p.texto) });
  }
  const vistos = new Set();
  return (_asisAyudaCache = pasos.filter(p => { const k = p.titulo + p.texto; return !vistos.has(k) && vistos.add(k); }).slice(0, 400));
}

/** Texto plano a HTML seguro: renglones, listas con "-", "*" o "1." y **negrita**. */
function _asisFormato(t) {
  const html = esc(t.trim()).replace(/\*\*(.+?)\*\*/g, '<b>$1</b>');
  let enLista = false;
  return html.split('\n').map(l => {
    const m = l.match(/^\s*(?:[-*•]|\d+[.)])\s+(.*)$/);
    const antes = m && !enLista ? '<ul>' : !m && enLista ? '</ul>' : '';
    enLista = !!m;
    return antes + (m ? `<li>${m[1]}</li>` : l.trim() ? `<p>${l}</p>` : '');
  }).join('') + (enLista ? '</ul>' : '');
}

function asisIr(destino) { asisCerrar(); irA(destino); }

/** "Preguntar en general": la misma pregunta, sin pegarle la máquina (o lo que sea) de la anterior. */
function asisSinTema() {
  const q = _asisActual;
  if (_asisCharla.at(-1)?.pregunta === q) _asisCharla = _asisCharla.slice(0, -1);   // reemplaza la respuesta, no se suma
  asisPreguntar(q, { sinTema: true });
}

/** "Nueva": olvida la conversación y deja la barra lista para empezar de cero. */
function asisNueva() {
  _asisCharla = [];
  asisCerrar();
  const campo = $('#asis-pregunta');
  campo.placeholder = _ASIS_PISTA;
  campo.focus();
}

function asisCerrar() {
  _asisPedido?.abort();
  _asisPedido = null;
  $('#asis-panel')?.classList.add('oculto');
}

function _asisDictar() {
  const boton = $('#asis-micro');
  if (_asisEscucha) { _asisEscucha.stop(); return; }
  const rec = _asisEscucha = new _asisRec();
  rec.lang = 'es-AR';
  rec.interimResults = true;
  rec.maxAlternatives = 1;
  const campo = $('#asis-pregunta');
  let final = '';
  boton.classList.add('escuchando');
  campo.placeholder = 'Te escucho… hablá y al terminar se pregunta solo';
  rec.onresult = ev => {
    let parcial = '';
    for (let i = ev.resultIndex; i < ev.results.length; i++) {
      if (ev.results[i].isFinal) final += ev.results[i][0].transcript; else parcial += ev.results[i][0].transcript;
    }
    campo.value = (final + parcial).trim();
  };
  rec.onerror = ev => {
    const motivos = { 'not-allowed': 'El navegador no dio permiso para usar el micrófono.',
      'no-speech': 'No se escuchó nada.', network: 'El dictado del navegador necesita internet.',
      'audio-capture': 'No se encontró un micrófono.' };
    avisar(motivos[ev.error] || 'No se pudo usar el micrófono (' + ev.error + ').', ev.error !== 'no-speech');
  };
  rec.onend = () => {
    _asisEscucha = null;
    boton.classList.remove('escuchando');
    campo.placeholder = _asisCharla.length ? _ASIS_PISTA_SEGUIR : _ASIS_PISTA;
    if (final.trim()) asisPreguntar(final);
  };
  rec.start();
}

/** Opciones → "Reiniciar la IA": cierra Ollama y lo vuelve a abrir (solo un administrador, solo si corre en esta PC). */
async function asisReiniciar(boton) {
  boton.disabled = true;
  const texto = boton.textContent;
  boton.textContent = 'Reiniciando… (hasta un minuto)';
  try {
    const e = await api('/api/asistente/reiniciar', { metodo: 'POST' });
    avisar(e.disponible ? 'La IA se reinició y está lista.' : 'La IA se reinició, pero: ' + e.motivo, !e.disponible);
    irA('opciones');
  } catch (e) {
    avisar(e.message, true);
    boton.disabled = false;
    boton.textContent = texto;
  }
}

/** Opciones → "Ver lo que lee la IA": la guía de uso, los sinónimos y las fichas que se arman solas con los datos. */
async function asisVerTextos() {
  const t = await api('/api/asistente/textos');
  const tipos = Object.entries(t.por_tipo).map(([k, n]) => `${esc(k)}: ${n}`).join(' · ');
  const bloque = (titulo, cuerpo) => `<details class="asis-textos"><summary><b>${titulo}</b></summary>${cuerpo}</details>`;
  abrirModal(`<h2>Lo que lee la IA</h2>
    <p class="sutil">Para contestar, la IA no lee toda la base: recibe solo lo que viene al caso de estos textos.
      La guía y los sinónimos vienen con la app; las fichas se arman solas con lo cargado y se rehacen cuando algo cambia.</p>
    ${bloque(`Guía de uso (${t.guia.length} secciones)`, t.guia.map(s => `<h4>${esc(s.titulo)}${s.ir ? ` <span class="chip">${esc(s.ir)}</span>` : ''}</h4>
      <p class="asis-pre">${esc(s.texto)}</p>`).join(''))}
    ${bloque(`Sinónimos (${t.sinonimos.length} grupos)`, `<ul>${t.sinonimos.map(g => `<li>${esc(g.join(', '))}</li>`).join('')}</ul>
      <p class="sutil">Se comparan por la raíz, sin acentos: por eso algunas palabras se ven recortadas.</p>`)}
    ${bloque(`Fichas (${t.fichas.length}${tipos ? ': ' + tipos : ''})`, `<ul class="asis-fichas">${t.fichas.slice(0, 1500).map(f =>
      `<li><b>[${esc(f.tipo)}] ${esc(f.titulo)}</b>: ${esc(f.texto)}</li>`).join('')}</ul>`)}
    <div class="botones"><button type="button" onclick="cerrarModal()">Cerrar</button></div>`, true);
}

// ── Opciones: la IA local ──
Nucleo.tarjetasOpciones.push({
  orden: 40,
  html: async () => {
    const e = await api('/api/asistente/estado');
    const admin = S.usuario?.es_admin;
    return `<div class="tarjeta" id="op-asistente"><h3>Asistente (barra de preguntas)</h3>
      <p>${e.disponible ? `<span class="chip verde">IA local lista</span> Modelo <b>${esc(e.modelo)}</b>.`
        : `<span class="chip ambar">Sin IA</span> ${esc(e.motivo)}`}</p>
      <p class="sutil">Lo que se puede contestar con cuentas (vencidos, pendientes, horas que faltan) lo contesta la app sola.
        Lo demás lo busca la IA local: elige de los datos de la app lo que contesta y se muestra tal cual, sin salir a internet.
        Sin IA, la barra muestra un resumen.</p>
      <div class="botones"><button type="button" onclick="asisVerTextos()">Ver lo que lee la IA</button></div>
      <p class="sutil">Micrófono: ${_asisMicro ? 'disponible en este navegador (botón 🎤).'
        : 'este navegador no lo permite en esta dirección; en el celular se dicta con el micrófono del teclado.'}</p>
      ${admin ? `<form id="f-asistente" class="campos">
        <label>Dirección de la IA (Ollama) <input name="url" value="${esc(e.url)}" placeholder="http://127.0.0.1:11434"></label>
        <label>Modelo ${e.modelos.length ? `<select name="modelo">${opcionesSelect(e.modelos.map(m => [m, m]), e.modelo, null)}</select>`
          : `<input name="modelo" value="${esc(e.modelo)}">`}</label>
        <div class="botones"><button class="primario" type="submit">Guardar</button></div><p class="error"></p></form>
      <div class="botones"><button id="asis-reiniciar" type="button" onclick="asisReiniciar(this)">Reiniciar la IA</button></div>
      <p class="sutil">Si la IA no contesta, se colgó o se cerró: la cierra y la vuelve a abrir (tarda hasta un minuto).
        Solo cierra Ollama, ningún otro programa.</p>` : ''}</div>`;
  },
  activar: () => {
    const f = $('#f-asistente');
    if (f) alEnviar(f, async d => {
      const e = await api('/api/asistente/ajustes', { metodo: 'PUT', datos: d });
      avisar(e.disponible ? 'Guardado: la IA local está lista.' : 'Guardado, pero: ' + e.motivo, !e.disponible);
      irA('opciones');
    });
  },
});

Ayuda.tour.push({ ir: 'inicio', el: '#asis-form', titulo: 'Preguntale a la app',
  texto: 'Escribí (o dictá) una pregunta: qué le pasó a una máquina, qué falta hacer, qué aceite lleva, o cómo se usa una pantalla («¿cómo cargo…?», «¿qué hago si…?»). '
    + 'Lo que se calcula lo contesta la app; lo demás lo busca una IA que corre en esta PC y muestra lo cargado tal cual. '
    + 'Recuerda las últimas preguntas: «¿y cuántas horas tiene?» sigue con la misma máquina; <b>Nueva</b> empieza de cero.' });

// La Ayuda de Opciones suma la tarjeta del asistente (la del núcleo y la de otros módulos quedan como están).
const _asisOpcionesAntes = Ayuda.pasos.opciones;
Ayuda.pasos.opciones = () => [...(_asisOpcionesAntes ? _asisOpcionesAntes() : []),
  { el: () => document.getElementById('op-asistente'), titulo: 'Asistente (barra de preguntas)', texto: 'Dice si la IA local está lista y con qué modelo. '
    + 'Sin IA la barra funciona igual: contesta lo que se calcula y, para lo demás, muestra un resumen de lo encontrado.' },
  { el: () => Ayuda.h.boton('Ver lo que lee la IA'), titulo: 'Ver lo que lee la IA', texto: 'La guía de uso, los sinónimos y las <b>fichas</b> que se arman solas con lo cargado. '
    + 'La IA no lee toda la base: recibe solo lo que viene al caso de estos textos. Sirve para ver por qué contestó lo que contestó.' },
  { el: () => document.getElementById('f-asistente'), titulo: 'Dirección y modelo (solo administradores)', texto: 'Dónde corre la IA (Ollama, en esta PC o en otra de la red) y qué modelo usa.' },
  { el: () => document.getElementById('asis-reiniciar'), titulo: 'Reiniciar la IA', texto: 'Si la IA no contesta o tarda demasiado: cierra Ollama y lo vuelve a abrir (hasta un minuto). No toca ningún otro programa. '
    + 'Si tarda siempre, suele ser poca memoria libre en la PC: cerrar programas ayuda.' },
];

Nucleo.alEntrar.push(async () => { _asisArmar(); });
_asisArmar();
