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
      placeholder="Preguntá algo… por ejemplo: ¿qué le pasó al lavador de humos?" aria-label="Preguntale a la app">
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

/** Hace la pregunta y muestra la respuesta a medida que llega. */
async function asisPreguntar(texto) {
  const pregunta = String(texto || '').trim();
  if (!pregunta) return $('#asis-pregunta').focus();
  _asisPedido?.abort();
  const pedido = _asisPedido = new AbortController();
  const panel = $('#asis-panel');
  panel.classList.remove('oculto');
  document.documentElement.style.setProperty('--asis-alto', $('.barra').getBoundingClientRect().bottom + 'px');
  panel.innerHTML = `<div class="asis-cabeza"><b class="asis-titulo">${esc(pregunta)}</b>
      <button class="link" type="button" onclick="asisCerrar()" title="Cerrar (Esc)">✕</button></div>
    <p class="asis-estado sutil">Buscando…</p><div class="asis-texto"></div><div class="asis-enlaces"></div>`;
  const inicio = Date.now();
  const reloj = setInterval(() => {
    const e = $('.asis-estado', panel);
    if (e && e.dataset.esperando) e.textContent = `${e.dataset.esperando} ${Math.round((Date.now() - inicio) / 1000)} s`;
  }, 500);
  let escrito = '';
  try {
    const r = await fetch('/api/asistente/preguntar', {
      method: 'POST', signal: pedido.signal,
      headers: { 'Content-Type': 'application/json', Authorization: 'Bearer ' + S.token },
      body: JSON.stringify({ pregunta }),
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
      for (const l of lineas) if (l.trim()) escrito = _asisEvento(JSON.parse(l), panel, escrito);
    }
  } catch (e) {
    if (e.name === 'AbortError') return;
    $('.asis-estado', panel).outerHTML = `<p class="error">${esc(e.message)}</p>`;
  } finally {
    clearInterval(reloj);
  }
}

function _asisEvento(e, panel, escrito) {
  const estado = $('.asis-estado', panel);
  if (e.tipo === 'inicio') {
    if (e.titulo) $('.asis-titulo', panel).insertAdjacentHTML('afterend', `<span class="chip">${esc(e.titulo)}</span>`);
    const textos = { ia: 'La IA está leyendo los datos y escribiendo…', directa: '', resumen: '', nada: '' };
    estado.dataset.esperando = textos[e.modo] || '';
    estado.textContent = estado.dataset.esperando;
    if (e.aviso) estado.insertAdjacentHTML('afterend', `<p class="asis-aviso">${esc(e.aviso)}</p>`);
    $('.asis-enlaces', panel).innerHTML = (e.enlaces || []).map(x =>
      `<button type="button" class="chico" onclick="asisIr('${esc(x.ir)}')">${esc(x.texto)}</button>`).join('');
    panel.dataset.modo = e.modo;
  } else if (e.tipo === 'texto') {
    escrito += e.texto;
    $('.asis-texto', panel).innerHTML = _asisFormato(escrito);
    if (estado.dataset.esperando) { delete estado.dataset.esperando; estado.textContent = ''; }
  } else if (e.tipo === 'aviso') {
    $('.asis-texto', panel).insertAdjacentHTML('afterend', `<p class="asis-aviso">${esc(e.aviso)}</p>`);
  } else if (e.tipo === 'fin') {
    delete estado.dataset.esperando;
    const como = { ia: 'Redactado por la IA local con los datos de la app: verificá lo importante en la ficha.',
      directa: 'Respondido por la app, con sus propios cálculos.', resumen: 'Resumen de la app (sin IA).', nada: '' }[panel.dataset.modo] || '';
    estado.textContent = como ? `${como} · ${e.segundos} s` : '';
    if (_asisTactil && !_asisMicro) estado.textContent += ' · Para dictar, usá el micrófono del teclado.';
  }
  return escrito;
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
    campo.placeholder = 'Preguntá algo… por ejemplo: ¿qué le pasó al lavador de humos?';
    if (final.trim()) asisPreguntar(final);
  };
  rec.start();
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
        Lo demás lo redacta la IA local con los datos de la app, sin salir a internet. Sin IA, la barra muestra un resumen.</p>
      <p class="sutil">Micrófono: ${_asisMicro ? 'disponible en este navegador (botón 🎤).'
        : 'este navegador no lo permite en esta dirección; en el celular se dicta con el micrófono del teclado.'}</p>
      ${admin ? `<form id="f-asistente" class="campos">
        <label>Dirección de la IA (Ollama) <input name="url" value="${esc(e.url)}" placeholder="http://127.0.0.1:11434"></label>
        <label>Modelo ${e.modelos.length ? `<select name="modelo">${opcionesSelect(e.modelos.map(m => [m, m]), e.modelo, null)}</select>`
          : `<input name="modelo" value="${esc(e.modelo)}">`}</label>
        <div class="botones"><button class="primario" type="submit">Guardar</button></div><p class="error"></p></form>` : ''}</div>`;
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
  texto: 'Escribí (o dictá) una pregunta sobre una máquina: qué le pasó, qué se le cambió, qué falta, cómo se hace un servicio. '
    + 'Lo que se calcula lo contesta la app; lo demás lo redacta una IA que corre en esta PC, con los datos cargados.' });

Nucleo.alEntrar.push(async () => { _asisArmar(); });
_asisArmar();
