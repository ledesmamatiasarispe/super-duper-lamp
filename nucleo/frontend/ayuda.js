'use strict';
// ── NÚCLEO: Ayuda guiada ──
// Recorrido paso a paso por la pantalla que se está viendo (botón "Ayuda") y por toda la app ("Tour completo"): un
// overlay transparente que bloquea los clics de fondo, un "agujero" que oscurece todo menos el control que se explica, y
// un globo con "Paso X de N", título, texto y Saltar / Atrás / Siguiente. Teclado: ← → para moverse, Esc para cerrar.
//
// LOS PASOS LOS TRAE CADA MÓDULO (sus scripts se cargan después de este):
//   Ayuda.pasos.<vista> = () => [ { el, titulo, texto }, ... ]      la ayuda de una pantalla (VISTAS.<vista>)
//   Ayuda.pasos.<id del form> = () => [...]                        la de un formulario del modal (<form id="...">)
//   Ayuda.tour.push({ ir: '<vista>', el, titulo, texto }, ...)     pasos del Tour completo (entre los del núcleo)
//   Ayuda.detectores.push(() => 'clave' | null)                   para una pantalla que no se reconoce por el hash
// `el` es una función que busca el elemento en el momento (o una lista, que se resaltan juntos); si no encuentra nada
// visible el paso se saltea solo. Sin `el`, el paso es una explicación general, centrada. `si: () => bool` lo filtra.
// Para buscar elementos: Ayuda.h.enVista(sel), .boton(texto), .tarjeta(titulo h3), .campo(name), .botonModal(texto), .menu(vista).
(function () {
  // ── buscar elementos ──
  const visible = el => !!el && el.getClientRects().length > 0 && getComputedStyle(el).visibility !== 'hidden';
  const todos = (sel, raiz = document) => [...raiz.querySelectorAll(sel)].filter(visible);
  const uno = (sel, raiz = document) => todos(sel, raiz)[0] || null;
  /** El primer elemento visible de `sel` cuyo texto contiene `t`. */
  const conTexto = (sel, t, raiz = document) => todos(sel, raiz).find(e => e.textContent.includes(t)) || null;
  const vista = () => document.getElementById('vista');
  const modal = () => document.getElementById('modal');
  const enVista = sel => uno(sel, vista());
  const boton = t => conTexto('button', t, vista());
  const tarjeta = t => conTexto('.tarjeta h3', t, vista())?.closest('.tarjeta') || null;
  /** En el modal: el <label> del campo `name` (así se resalta junto con su título). */
  const campo = name => { const el = modal().querySelector(`[name="${name}"]`); return visible(el) ? el.closest('label') || el : null; };
  const botonModal = t => conTexto('button', t, modal());

  // ── el motor ──
  let pasos = [], paso = 0, gen = 0, dentroDelModal = false;
  let completo = false;   // tour completo: los pasos llevan `ir` (la pantalla donde se muestran) y no se filtran de antemano
  let overlay, spot, tip;

  function armar() {
    if (overlay) return;
    overlay = document.createElement('div');
    overlay.id = 'ayuda-overlay';
    overlay.innerHTML = '<div id="ayuda-spot"></div><div id="ayuda-tip" role="dialog" aria-live="polite"></div>';
    spot = overlay.firstChild; tip = overlay.lastChild;
    tip.addEventListener('click', ev => {
      const a = ev.target.closest('[data-ayuda-accion]')?.dataset.ayudaAccion;
      if (a === 'cerrar') cerrar(); else if (a === 'siguiente') siguiente(); else if (a === 'anterior') anterior();
    });
  }

  const abierto = () => !!overlay && overlay.classList.contains('abierto');

  function iniciar(lista, opciones = {}) {
    armar();
    completo = !!opciones.completo;
    // un paso que hoy no tiene a qué apuntar no cuenta: así "Paso X de N" dice la verdad y "Atrás" no rebota.
    // En el tour completo no se puede saber de antemano (el elemento está en otra pantalla): se decide al mostrarlo.
    pasos = completo ? lista.filter(p => !p.si || p.si()) : lista.filter(p => !p.el || elementos(p).length);
    if (!pasos.length) return;
    paso = 0;
    // un <dialog> abierto vive en la capa superior: el overlay tiene que ir adentro suyo para quedar por encima
    dentroDelModal = !!modal()?.open;
    (dentroDelModal ? modal() : document.body).appendChild(overlay);
    overlay.classList.add('abierto');
    window.addEventListener('resize', reposicionar);
    window.addEventListener('scroll', reposicionar, true);
    document.addEventListener('keydown', teclado, true);
    mostrar();
  }

  function cerrar() {
    if (!abierto()) return;
    overlay.classList.remove('abierto');
    window.removeEventListener('resize', reposicionar);
    window.removeEventListener('scroll', reposicionar, true);
    document.removeEventListener('keydown', teclado, true);
    gen++;
  }

  function teclado(e) {
    const accion = { Escape: cerrar, ArrowRight: siguiente, ArrowLeft: anterior }[e.key];
    if (!accion) return;
    e.preventDefault(); e.stopPropagation();   // Esc no cierra el modal de abajo, ni las flechas mueven el cursor del campo
    accion();
  }

  function siguiente() { if (paso >= pasos.length - 1) return cerrar(); paso++; mostrar(); }
  function anterior() { if (paso <= 0) return; paso--; mostrar(); }

  function elementos(p) {
    if (!p.el) return [];
    let r;
    try { r = p.el(); } catch { r = null; }
    return (Array.isArray(r) ? r : [r]).filter(visible);
  }

  function mostrar() {
    const p = pasos[paso], g = ++gen;
    const destino = typeof p.ir === 'function' ? p.ir() : p.ir;
    if (destino === null) {   // la pantalla no se puede mostrar (por ejemplo, no hay ningún instructivo): se saltea
      pasos.splice(paso, 1);
      if (paso >= pasos.length) return cerrar();
      return mostrar();
    }
    if (destino && (location.hash.slice(1) || 'inicio') !== destino) {   // el paso es de otra pantalla: se abre y se espera
      tip.innerHTML = '<div class="ayuda-texto">Abriendo la pantalla…</div>';
      ubicar([]);
      window.scrollTo(0, 0);
      irA(destino);   // de app.js; usa replaceState, así que no dispara el hashchange que cierra el recorrido
      return esperarPantalla(g, mostrar);
    }
    const els = elementos(p);
    // si el elemento no está, se saltea; salvo en el tour completo, donde el paso explica igual (centrado)
    if (p.el && !els.length && !completo) {   // desapareció mientras tanto: se sigue de largo en la dirección en que se venía
      pasos.splice(paso, 1);
      if (paso >= pasos.length) return cerrar();
      return mostrar();
    }
    const ultimo = paso === pasos.length - 1;
    tip.innerHTML = `
      <div class="ayuda-paso">Paso ${paso + 1} de ${pasos.length}</div>
      <div class="ayuda-titulo">${p.titulo}</div>
      <div class="ayuda-texto">${p.texto}</div>
      <div class="ayuda-botones">
        <button type="button" data-ayuda-accion="cerrar">Saltar</button>
        <span>${paso > 0 ? '<button type="button" data-ayuda-accion="anterior">&#8249; Atrás</button>' : ''}
          <button type="button" class="primario" data-ayuda-accion="siguiente">${ultimo ? 'Listo' : 'Siguiente &#8250;'}</button></span>
      </div>`;
    tip.querySelector('.primario').focus({ preventScroll: true });
    if (els.length) els[0].scrollIntoView({ behavior: 'smooth', block: 'center', inline: 'nearest' });
    ubicar(els);   // ya mismo, sin esperar al primer cuadro: si no, se ve un instante el agujero del paso anterior
    seguir(els, g);
  }

  // Mientras dura el scroll suave se sigue al elemento cuadro a cuadro (en vez de adivinar cuánto tarda), hasta que
  // queda quieto unos cuadros seguidos. `g` cancela el seguimiento de un paso viejo si se avanzó rápido.
  function seguir(els, g) {
    let quietos = 0, cuadros = 0, antes = '';
    const tick = () => {
      if (g !== gen || !abierto()) return;
      const r = ubicar(els), ahora = r ? r.top + ',' + r.left : '';
      quietos = ahora === antes ? quietos + 1 : 0; antes = ahora;
      if (quietos < 6 && ++cuadros < 180) requestAnimationFrame(tick);
    };
    requestAnimationFrame(tick);
  }

  /** Espera a que la pantalla termine de cargar (deja de decir "Cargando…") y sigue; `g` lo cancela si se avanzó o cerró. */
  function esperarPantalla(g, seguirCon, intentos = 0) {
    if (g !== gen || !abierto()) return;
    const v = vista(), cargando = v?.children.length === 1 && v.textContent.trim() === 'Cargando…';
    if (cargando && intentos < 60) return setTimeout(() => esperarPantalla(g, seguirCon, intentos + 1), 100);
    seguirCon();
  }

  function reposicionar() { if (abierto()) ubicar(elementos(pasos[paso])); }

  /** Pone el agujero sobre la unión de los elementos y el globo debajo (o arriba, si abajo no entra). */
  function ubicar(els) {
    const W = window.innerWidth, H = window.innerHeight, m = 10;
    const tw = tip.offsetWidth, th = tip.offsetHeight;
    if (!els.length) {   // explicación general: sin agujero, el globo en el centro
      Object.assign(spot.style, { top: H / 2 + 'px', left: W / 2 + 'px', width: '0px', height: '0px' });
      spot.classList.add('sin-elemento');
      tip.style.top = Math.max(m, (H - th) / 2) + 'px';
      tip.style.left = Math.max(m, (W - tw) / 2) + 'px';
      return null;
    }
    spot.classList.remove('sin-elemento');
    const rs = els.map(e => e.getBoundingClientRect());
    const pad = 6;
    const r = { top: Math.min(...rs.map(x => x.top)) - pad, left: Math.min(...rs.map(x => x.left)) - pad,
      bottom: Math.max(...rs.map(x => x.bottom)) + pad, right: Math.max(...rs.map(x => x.right)) + pad };
    // lo que se va de la pantalla no hace falta dibujarlo (una tabla larga, por ejemplo)
    const v = { top: Math.max(r.top, 2), left: Math.max(r.left, 2), bottom: Math.min(r.bottom, H - 2), right: Math.min(r.right, W - 2) };
    Object.assign(spot.style, { top: v.top + 'px', left: v.left + 'px',
      width: Math.max(0, v.right - v.left) + 'px', height: Math.max(0, v.bottom - v.top) + 'px' });
    let top = v.bottom + 12;
    if (top + th > H - m) top = v.top - th - 12;              // abajo no entra: arriba
    if (top < m) top = H - th - m;                            // tampoco: abajo de todo, encima del elemento
    let left = W < 640 ? (W - tw) / 2 : v.left;               // en el celular, centrado
    left = Math.min(Math.max(m, left), W - tw - m);
    tip.style.top = Math.max(m, top) + 'px';
    tip.style.left = Math.max(m, left) + 'px';
    return v;
  }

  // Si se cambia de pantalla o se cierra el modal en el medio, el recorrido ya no tiene sentido.
  window.addEventListener('hashchange', cerrar);

  // ── los pasos: los del núcleo; los módulos agregan los suyos ──
  const menu = v => uno(`#menu a[data-vista="${v}"]`);
  const COMO_VER_OCULTOS = 'Marcá <b>Ver ocultos</b> (el número dice cuántos hay) y aparecen tachados, con el botón para reactivarlos. Se recuerda mientras navegás.';
  const PASOS = {
    inicio: () => [
      { titulo: 'Inicio', texto: 'La pantalla de entrada. Las demás están en las pestañas de arriba; <b>Ayuda</b> explica la que estés viendo y <b>Tour completo</b> recorre toda la app.' },
    ],
    opciones: () => [
      { titulo: 'Opciones', texto: 'Ajustes de la app. Se entra desde <b>Opciones</b>, arriba a la derecha.' },
      { el: () => document.getElementById('op-version'), titulo: 'Versión y actualizaciones', texto: 'Qué versión está instalada y si hay una más nueva. Cada vez que arranca, la app la busca sola, y al entrar un administrador le pregunta si quiere instalarla '
        + '(si responde <b>Ahora no</b>, no vuelve a preguntar por una semana). Antes de instalar se copia la base; si algo falla, vuelve la versión anterior.' },
      { el: () => boton('Buscar ahora'), titulo: 'Buscar ahora', texto: 'Vuelve a consultar si salió una versión nueva, sin esperar al próximo arranque.' },
      { el: () => document.getElementById('op-password'), titulo: 'Contraseña', texto: 'Para elegir una contraseña propia: pide la actual y la nueva dos veces. Las otras sesiones abiertas se cierran. '
        + 'Mientras sigas con una contraseña provisoria se puede usar todo, pero arriba queda un aviso amarillo hasta que la cambies.' },
      { el: () => document.getElementById('op-puerto'), titulo: 'Puerto (solo administradores)', texto: 'El número que va después de localhost: en la dirección de la app. '
        + 'Se cambia si choca con otro programa de la PC; vale desde la próxima vez que se abre. Si al abrirla el elegido está ocupado, la app arranca igual en el siguiente libre y lo avisa acá.' },
      { el: () => document.getElementById('op-marca'), titulo: 'Nombre y logo (solo administradores)', texto: 'Cambia el nombre y el logo que se ven en la barra, en la pantalla de ingreso y en la pestaña del navegador, para todos. '
        + 'Con el nombre vacío vuelve al de fábrica; <b>Volver al logo original</b> recupera el de siempre. Se guardan con los datos: las actualizaciones no los pisan.' },
    ],
    usuarios: () => [
      { titulo: 'Usuarios', texto: 'Quiénes entran al sistema y con qué rol. Solo la ve un administrador.' },
      { el: () => boton('Nuevo usuario'), titulo: 'Nuevo usuario', texto: 'Usuario para entrar, nombre, una contraseña provisoria y si es administrador. Al entrar le queda un aviso hasta que elija una propia.' },
      { el: () => enVista('.ver-ocultos'), titulo: 'Ver ocultos', texto: 'Los usuarios dados de baja no se borran (lo que registraron sigue diciendo quién fue). ' + COMO_VER_OCULTOS },
      { el: () => boton('Restablecer contraseña'), titulo: 'Restablecer contraseña', texto: 'Para quien se olvidó la suya: le ponés una provisoria. Se le cierran las sesiones abiertas.' },
      { el: () => boton('Dar de baja'), titulo: 'Dar de baja', texto: 'Ya no puede entrar. Siempre tiene que quedar al menos un administrador activo, y nadie se da de baja a sí mismo.' },
    ],
    'f-password': () => [
      { el: () => campo('actual'), titulo: 'La actual', texto: 'La que usaste para entrar (la provisoria, si es la primera vez).' },
      { el: () => [campo('nueva'), campo('repetida')], titulo: 'La nueva, dos veces', texto: 'Mínimo 6 caracteres y distinta de la actual. Se repite para no equivocarse.' },
    ],
    'f-usuario': () => [
      { el: () => campo('usuario'), titulo: 'Usuario', texto: 'Con lo que entra (un nombre o un número de legajo). No se repite y no se cambia después.' },
      { el: () => campo('es_admin'), titulo: 'Administrador', texto: 'Configura el sistema y maneja los usuarios.' },
    ],
  };

  // Tour completo: los del núcleo al principio y al final; los módulos agregan los suyos con Ayuda.tour.push(...).
  const TOUR_INICIO = [
    { ir: 'inicio', titulo: 'Tour completo', texto: 'Este recorrido muestra <b>toda la app</b>. Podés salir cuando quieras con <b>Saltar</b> o Esc, y moverte con las flechas ← →.' },
    { ir: 'inicio', el: () => document.getElementById('menu'), titulo: 'Las pestañas', texto: 'Arriba están todas las pantallas.' },
  ];
  const TOUR_FIN = [
    { ir: 'opciones', el: () => document.getElementById('op-version'), titulo: 'Opciones', texto: 'La versión, las actualizaciones, la contraseña y, para un administrador, el puerto y el nombre y logo.' },
    { ir: 'inicio', el: () => document.getElementById('ayuda-boton'), titulo: '¿Y cada pantalla en detalle?', texto: 'El botón <b>Ayuda</b> explica, control por control, la pantalla en la que estés (y los formularios tienen el suyo).' },
  ];
  const tour = [];
  const TOUR = () => [...TOUR_INICIO, ...tour, ...TOUR_FIN];
  const detectores = [];

  /** Qué pantalla se está viendo: lo que diga el detector de un módulo, o el hash. */
  function pantallaActual() {
    for (const d of detectores) { const c = d(); if (c && PASOS[c]) return c; }
    const v = (location.hash.slice(1) || 'inicio').split('/')[0];
    return PASOS[v] ? v : 'inicio';
  }

  function ayudaPantalla() {
    if (abierto()) return;
    // si se toca mientras la pantalla todavía dice "Cargando…", se espera un poco a que termine
    let intentos = 0;
    const probar = () => {
      const cargando = vista()?.children.length === 1 && vista().textContent.trim() === 'Cargando…';
      if (cargando && ++intentos < 40) return setTimeout(probar, 100);
      iniciar(PASOS[pantallaActual()]());
    };
    probar();
  }

  function ayudaModal() {
    const form = modal().querySelector('form[id]');
    if (form && PASOS[form.id]) iniciar(PASOS[form.id]());
  }

  // ── los botones ──
  document.addEventListener('click', ev => {
    if (ev.target.closest('#ayuda-boton')) ayudaPantalla();
    else if (ev.target.closest('#tour-boton')) { if (!abierto()) iniciar(TOUR(), { completo: true }); }
    else if (ev.target.closest('.ayuda-boton-modal')) ayudaModal();
  });

  // Los formularios del modal que tienen recorrido reciben su botón "Ayuda" junto al título, apenas se abren.
  const cuerpo = document.getElementById('modal-cuerpo');
  if (cuerpo) new MutationObserver(() => {
    const form = cuerpo.querySelector('form[id]'), h2 = cuerpo.querySelector('h2');
    if (!form || !PASOS[form.id] || !h2 || h2.querySelector('.ayuda-boton-modal')) return;
    h2.insertAdjacentHTML('beforeend', ' <button type="button" class="ayuda-boton ayuda-boton-modal" title="Cómo se usa este formulario"><span class="ayuda-icono">?</span> Ayuda</button>');
  }).observe(cuerpo, { childList: true });

  // Esc con el recorrido abierto cierra el recorrido, no el modal; y si el modal se cierra, el recorrido también.
  const dlg = modal();
  if (dlg) {
    dlg.addEventListener('cancel', ev => { if (abierto() && dentroDelModal) { ev.preventDefault(); cerrar(); } }, true);
    dlg.addEventListener('close', () => { if (dentroDelModal) cerrar(); });
  }

  window.Ayuda = { pasos: PASOS, tour, detectores, pantalla: ayudaPantalla, tourCompleto: () => iniciar(TOUR(), { completo: true }),
    iniciar, cerrar, h: { uno, todos, conTexto, enVista, boton, tarjeta, campo, botonModal, menu, visible } };
})();
