// ── MAPA DE PLANTA ──
// Planos dibujados en la app (rectángulos, líneas y textos, en metros) con las máquinas como puntos. El color del punto es
// el peor estado de lo que tiene pendiente (lo mismo que Inicio). Editar es solo de administradores y se guarda todo junto.

const M = { datos: null, planoId: null, edit: null };
const ESTADOS_MAPA = { vencido: ['rojo', 'Vencido'], pendiente: ['ambar', 'Pendiente / próximo'], sin_dato: ['azul', 'Sin dato'],
  al_dia: ['verde', 'Al día'] };
const COLORES_PLANO = { gris: 'Gris', azul: 'Azul', verde: 'Verde', ambar: 'Ámbar', rojo: 'Rojo' };
const HERRAMIENTAS = { mover: 'Seleccionar / mover', rect: 'Rectángulo', linea: 'Línea / pared', texto: 'Texto' };

VISTAS.mapa = async id => {
  M.datos = await api('/api/planos');
  const ids = M.datos.planos.map(p => p.id);
  M.planoId = ids.includes(Number(id)) ? Number(id) : ids.includes(M.planoId) ? M.planoId : ids[0] ?? null;
  M.edit = null;
  pintarMapa();
};

const planoActual = () => M.datos.planos.find(p => p.id === M.planoId);
const equipoMapa = id => M.datos.equipos.find(e => e.id === id);

function pintarMapa() {
  const plano = planoActual();
  const pestanas = M.datos.planos.map(p => `<button class="${p.id === M.planoId ? 'primario' : ''}" ${M.edit ? 'disabled' : ''}
    onclick="irA('mapa/${p.id}')">${esc(p.nombre)}</button>`).join('');
  const leyenda = Object.values(ESTADOS_MAPA).map(([c, t]) => `<span class="chip ${c}">● ${t}</span>`).join(' ');
  $('#vista').innerHTML = `
    <div class="encabezado"><h2>Mapa de planta</h2><div class="botones">${M.edit ? '' : soloAdmin(`
      <button onclick="modalNuevoPlano()">Nuevo plano</button>
      ${plano ? `<button class="primario" onclick="editarPlano()">Editar este plano</button>
        <button class="peligro" onclick="eliminarPlano()">Eliminar plano</button>` : ''}`)}</div></div>
    ${plano ? `<div class="botones mapa-pestanas">${pestanas}</div>
      ${M.edit ? '' : `<p class="mapa-leyenda">${leyenda} <span class="sutil">Tocar una máquina muestra lo que tiene pendiente.</span></p>`}
      <div class="mapa-cuerpo">
        <div class="tarjeta mapa-lienzo"><svg id="mapa-svg" class="${M.edit ? 'editando herr-' + M.edit.herramienta : ''}"></svg></div>
        <aside class="tarjeta mapa-lado" id="mapa-lado"></aside>
      </div>`
    : `<div class="tarjeta"><p>Todavía no hay planos.</p>${S.usuario.es_admin
      ? '<p class="sutil">Un plano por nave o sector: se dibujan las paredes y los sectores, y después se ubican las máquinas.</p>'
      : '<p class="sutil">Los arma un administrador.</p>'}</div>`}`;
  if (!plano) return;
  pintarSvg();
  pintarLado();
  const svg = $('#mapa-svg');
  if (M.edit) {
    svg.addEventListener('pointerdown', mapaAbajo);
    svg.addEventListener('pointermove', mapaMover);
    svg.addEventListener('pointerup', mapaArriba);
  } else {
    svg.addEventListener('click', ev => {
      const g = ev.target.closest('[data-equipo]');
      if (g) fichaEquipoMapa(Number(g.dataset.equipo));
    });
  }
}

/** Lo que se dibuja: el plano en edición (con sus cambios sin guardar) o el guardado. */
function vistaPlano() {
  if (M.edit) return { plano: M.edit.plano, puntos: M.edit.puntos };
  const plano = planoActual();
  const puntos = new Map(M.datos.equipos.filter(e => e.plano_id === plano.id).map(e => [e.id, { x: e.plano_x, y: e.plano_y }]));
  return { plano, puntos };
}

function pintarSvg() {
  const { plano, puntos } = vistaPlano();
  const { ancho, alto } = plano;
  const u = Math.max(ancho, alto) / 100;   // unidad de dibujo: los grosores y textos acompañan el tamaño del plano
  const m = u * 3;
  const svg = $('#mapa-svg');
  svg.setAttribute('viewBox', `${-m} ${-m} ${ancho + 2 * m} ${alto + 2 * m}`);
  const sel = M.edit?.sel;
  const paso = pasoGrilla(plano);
  const grilla = M.edit ? `<defs><pattern id="mapa-grilla" width="${paso}" height="${paso}" patternUnits="userSpaceOnUse">
      <path d="M ${paso} 0 L 0 0 0 ${paso}" class="pl-grilla" stroke-width="${u * 0.12}"/></pattern></defs>
    <rect width="${ancho}" height="${alto}" fill="url(#mapa-grilla)"/>` : '';
  const elementos = plano.elementos.map((el, i) => {
    const s = sel?.tipo === 'el' && sel.i === i ? ' sel' : '';
    if (el.tipo === 'rect') {
      const fs = Math.min(u * 1.8, el.h * 0.5, el.w / Math.max(4, el.etiqueta.length) * 1.6);
      return `<g data-el="${i}" class="pl-${el.color}${s}"><rect x="${el.x}" y="${el.y}" width="${el.w}" height="${el.h}" class="pl-rect" stroke-width="${u * 0.15}"/>
        ${el.etiqueta ? `<text x="${el.x + el.w / 2}" y="${el.y + el.h / 2}" font-size="${fs}" class="pl-etiqueta">${esc(el.etiqueta)}</text>` : ''}</g>`;
    }
    if (el.tipo === 'linea') return `<g data-el="${i}" class="pl-${el.color}${s}"><line x1="${el.x1}" y1="${el.y1}" x2="${el.x2}" y2="${el.y2}"
      class="pl-linea" stroke-width="${u * 0.5}"/><line x1="${el.x1}" y1="${el.y1}" x2="${el.x2}" y2="${el.y2}" class="pl-tocar" stroke-width="${u * 2}"/></g>`;
    return `<g data-el="${i}" class="pl-${el.color}${s}"><text x="${el.x}" y="${el.y}" font-size="${u * 1.4 * el.tamanio}" class="pl-texto">${esc(el.texto)}</text></g>`;
  }).join('');
  const maquinas = [...puntos].map(([id, p]) => {
    const e = equipoMapa(id);
    if (!e) return '';
    const [color, texto] = ESTADOS_MAPA[e.estado] || ESTADOS_MAPA.al_dia;
    const s = sel?.tipo === 'equipo' && sel.id === id ? ' sel' : '';
    return `<g data-equipo="${id}" class="mapa-punto punto-${color}${s}" transform="translate(${p.x} ${p.y})">
      <title>${esc(e.codigo)} · ${esc(e.nombre)} — ${texto}</title>
      <circle r="${u * 1.2}" stroke-width="${u * 0.3}"/><text y="${-u * 1.9}" font-size="${u * 1.4}" stroke-width="${u * 0.35}">${esc(e.codigo)}</text></g>`;
  }).join('');
  svg.innerHTML = `<rect width="${ancho}" height="${alto}" class="pl-borde" stroke-width="${u * 0.2}"/>${grilla}
    ${elementos}<g id="mapa-previa"></g>${maquinas}`;
}

const pasoGrilla = plano => { const l = Math.max(plano.ancho, plano.alto); return l <= 60 ? 1 : l <= 300 ? 5 : 10; };
const pasoImanes = plano => pasoGrilla(plano) / (Math.max(plano.ancho, plano.alto) <= 60 ? 2 : 5);

function pintarLado() {
  const lado = $('#mapa-lado');
  const plano = planoActual();
  if (!M.edit) {
    const aca = M.datos.equipos.filter(e => e.plano_id === plano.id);
    const sinUbicar = M.datos.equipos.filter(e => !e.plano_id);
    lado.innerHTML = `<h3>Máquinas en este plano (${aca.length})</h3>
      ${aca.length ? `<ul class="mapa-lista">${aca.map(e => `<li><a onclick="fichaEquipoMapa(${e.id})">${esc(e.codigo)} · ${esc(e.nombre)}</a>
        <span class="chip ${ESTADOS_MAPA[e.estado][0]}">${ESTADOS_MAPA[e.estado][1]}</span></li>`).join('')}</ul>`
        : `<p class="sutil">Ninguna todavía.${S.usuario.es_admin ? ' Se ubican con <b>Editar este plano</b>.' : ''}</p>`}
      ${sinUbicar.length ? `<p class="sutil">${sinUbicar.length} máquina(s) sin ubicar en ningún plano.</p>` : ''}`;
    return;
  }
  const E = M.edit;
  const otroPlano = id => M.datos.planos.find(p => p.id === id)?.nombre;
  const fuera = M.datos.equipos.filter(e => !E.puntos.has(e.id));
  lado.innerHTML = `
    <form id="f-plano" class="campos-plano">
      <label>Nombre <input name="nombre" value="${esc(E.plano.nombre)}" maxlength="60"></label>
      <div class="fila-2"><label>Ancho (m) <input name="ancho" type="number" min="1" step="0.5" value="${E.plano.ancho}"></label>
        <label>Alto (m) <input name="alto" type="number" min="1" step="0.5" value="${E.plano.alto}"></label></div></form>
    <h3>Dibujar</h3>
    <div class="mapa-herramientas">${Object.entries(HERRAMIENTAS).map(([k, t]) =>
      `<button class="${E.herramienta === k ? 'primario' : ''}" onclick="herramientaMapa('${k}')">${t}</button>`).join('')}</div>
    <label>Color de lo nuevo <select id="mapa-color">${opcionesSelect(Object.entries(COLORES_PLANO), E.color, null)}</select></label>
    <p class="sutil mapa-ayuda">${E.colocar ? `Tocá el plano donde está <b>${esc(equipoMapa(E.colocar).codigo)}</b>.`
      : { mover: 'Tocá algo para elegirlo y arrastralo para moverlo. Supr lo borra.', rect: 'Arrastrá para dibujar un sector, nave o sala.',
        linea: 'Arrastrá de punta a punta para dibujar una pared.', texto: 'Tocá donde va el texto.' }[E.herramienta]}
      La grilla es de ${pasoGrilla(E.plano)} m.</p>
    <div id="mapa-propiedades">${propiedadesMapa()}</div>
    <h3>Máquinas sin ubicar acá (${fuera.length})</h3>
    <ul class="mapa-lista">${fuera.map(e => `<li><span>${esc(e.codigo)} · ${esc(e.nombre)}
      ${e.plano_id && otroPlano(e.plano_id) ? `<span class="sutil">(en ${esc(otroPlano(e.plano_id))})</span>` : ''}</span>
      <button class="chico ${E.colocar === e.id ? 'primario' : ''}" onclick="colocarEquipo(${e.id})">Ubicar</button></li>`).join('')
      || '<li class="sutil">Todas las máquinas están en este plano.</li>'}</ul>
    <p class="error" id="mapa-error"></p>
    <div class="botones"><button class="primario" onclick="guardarPlano(this)">Guardar plano</button>
      <button onclick="cancelarEdicionPlano()">Cancelar</button></div>`;
  $('#mapa-color').addEventListener('change', ev => { E.color = ev.target.value; });
  $('#f-plano').addEventListener('input', ev => {
    const { name, value } = ev.target;
    if (name === 'nombre') E.plano.nombre = value;
    else if (Number(value) > 0) { E.plano[name] = Number(value); pintarSvg(); }
  });
  activarPropiedades();
}

/** El panel de lo elegido: sus datos editables y cómo sacarlo. */
function propiedadesMapa() {
  const E = M.edit, sel = E.sel;
  if (!sel) return '';
  if (sel.tipo === 'equipo') {
    const e = equipoMapa(sel.id);
    return `<div class="mapa-prop"><b>${esc(e.codigo)} · ${esc(e.nombre)}</b>
      <div class="botones"><button class="chico peligro" onclick="borrarSeleccion()">Sacar del plano</button></div></div>`;
  }
  const el = E.plano.elementos[sel.i];
  const color = `<label>Color <select data-prop="color">${opcionesSelect(Object.entries(COLORES_PLANO), el.color, null)}</select></label>`;
  const campos = el.tipo === 'rect' ? `<label>Nombre del sector <input data-prop="etiqueta" maxlength="60" value="${esc(el.etiqueta)}"></label>${color}`
    : el.tipo === 'texto' ? `<label>Texto <input data-prop="texto" maxlength="80" value="${esc(el.texto)}"></label>
      <label>Tamaño <select data-prop="tamanio">${opcionesSelect([1, 2, 3, 4, 5].map(n => [n, n]), el.tamanio, null)}</select></label>${color}`
    : color;
  return `<div class="mapa-prop"><b>${{ rect: 'Rectángulo', linea: 'Línea', texto: 'Texto' }[el.tipo]}</b>${campos}
    <div class="botones"><button class="chico peligro" onclick="borrarSeleccion()">Borrar</button></div></div>`;
}

function activarPropiedades() {
  $('#mapa-propiedades').querySelectorAll('[data-prop]').forEach(inp => inp.addEventListener('input', () => {
    const el = M.edit.plano.elementos[M.edit.sel.i];
    el[inp.dataset.prop] = inp.dataset.prop === 'tamanio' ? Number(inp.value) : inp.value;
    pintarSvg();
  }));
}

function repintarPropiedades() { $('#mapa-propiedades').innerHTML = propiedadesMapa(); activarPropiedades(); }

function editarPlano() {
  const p = planoActual();
  M.edit = { plano: JSON.parse(JSON.stringify(p)), herramienta: 'mover', color: 'gris', sel: null, colocar: null, arrastre: null,
    puntos: new Map(M.datos.equipos.filter(e => e.plano_id === p.id).map(e => [e.id, { x: e.plano_x, y: e.plano_y }])) };
  document.addEventListener('keydown', teclaMapa);
  pintarMapa();
}

function cancelarEdicionPlano() {
  if (!confirm('¿Descartar los cambios del plano?')) return;
  terminarEdicion(); pintarMapa();
}

function terminarEdicion() { M.edit = null; document.removeEventListener('keydown', teclaMapa); }

function teclaMapa(ev) {
  if (!M.edit || !document.getElementById('mapa-svg')) return terminarEdicion();
  if ((ev.key === 'Delete' || ev.key === 'Backspace') && M.edit.sel && !ev.target.closest('input, select, textarea')) {
    ev.preventDefault(); borrarSeleccion();
  }
  if (ev.key === 'Escape') { M.edit.colocar = null; M.edit.sel = null; pintarSvg(); pintarLado(); }
}

function herramientaMapa(h) {
  Object.assign(M.edit, { herramienta: h, colocar: null, sel: null });
  $('#mapa-svg').setAttribute('class', 'editando herr-' + h);
  pintarSvg(); pintarLado();
}

function colocarEquipo(id) {
  Object.assign(M.edit, { colocar: id, sel: null });
  pintarLado();
}

function borrarSeleccion() {
  const E = M.edit, sel = E.sel;
  if (!sel) return;
  if (sel.tipo === 'equipo') E.puntos.delete(sel.id); else E.plano.elementos.splice(sel.i, 1);
  E.sel = null;
  pintarSvg(); pintarLado();
}

/** Del clic en pantalla a metros del plano, pegado a la grilla y dentro del plano. */
function puntoMapa(ev, iman = true) {
  const svg = $('#mapa-svg'), pt = svg.createSVGPoint();
  pt.x = ev.clientX; pt.y = ev.clientY;
  const p = pt.matrixTransform(svg.getScreenCTM().inverse());
  const { ancho, alto } = M.edit.plano, paso = pasoImanes(M.edit.plano);
  const ajustar = (v, max) => Math.min(max, Math.max(0, iman ? Math.round(v / paso) * paso : v));
  return { x: +ajustar(p.x, ancho).toFixed(2), y: +ajustar(p.y, alto).toFixed(2) };
}

function mapaAbajo(ev) {
  const E = M.edit, p = puntoMapa(ev);
  if (E.colocar) {
    E.puntos.set(E.colocar, p);
    Object.assign(E, { sel: { tipo: 'equipo', id: E.colocar }, colocar: null });
    pintarSvg(); pintarLado();
    return;
  }
  if (E.herramienta === 'texto') {
    const texto = prompt('Texto:');
    if (!texto?.trim()) return;
    E.plano.elementos.push({ tipo: 'texto', x: p.x, y: p.y, texto: texto.trim().slice(0, 80), tamanio: 1, color: E.color });
    E.sel = { tipo: 'el', i: E.plano.elementos.length - 1 };
    pintarSvg(); pintarLado();
    return;
  }
  try { ev.currentTarget.setPointerCapture(ev.pointerId); } catch { /* sin captura igual se puede dibujar */ }
  if (E.herramienta === 'rect' || E.herramienta === 'linea') {
    E.arrastre = { dibujo: E.herramienta, desde: p, hasta: p };
    return;
  }
  // mover: lo que está más arriba gana (las máquinas se dibujan encima de todo)
  const g = ev.target.closest('[data-equipo], [data-el]');
  if (!g) { E.sel = null; pintarSvg(); repintarPropiedades(); return; }
  E.sel = g.dataset.equipo ? { tipo: 'equipo', id: Number(g.dataset.equipo) } : { tipo: 'el', i: Number(g.dataset.el) };
  const original = E.sel.tipo === 'equipo' ? { ...E.puntos.get(E.sel.id) } : { ...E.plano.elementos[E.sel.i] };
  E.arrastre = { mover: true, desde: p, original };
  pintarSvg(); repintarPropiedades();
}

function mapaMover(ev) {
  const E = M.edit, a = E?.arrastre;
  if (!a) return;
  const p = puntoMapa(ev);
  if (a.dibujo) {
    a.hasta = p;
    const previa = $('#mapa-previa'), u = Math.max(E.plano.ancho, E.plano.alto) / 100;
    previa.innerHTML = a.dibujo === 'rect'
      ? `<rect x="${Math.min(a.desde.x, p.x)}" y="${Math.min(a.desde.y, p.y)}" width="${Math.abs(p.x - a.desde.x)}"
          height="${Math.abs(p.y - a.desde.y)}" class="pl-previa" stroke-width="${u * 0.2}"/>`
      : `<line x1="${a.desde.x}" y1="${a.desde.y}" x2="${p.x}" y2="${p.y}" class="pl-previa" stroke-width="${u * 0.5}"/>`;
    return;
  }
  const dx = p.x - a.desde.x, dy = p.y - a.desde.y;
  const { ancho, alto } = E.plano;
  const dentro = (v, max) => +Math.min(max, Math.max(0, v)).toFixed(2);
  if (E.sel.tipo === 'equipo') {
    E.puntos.set(E.sel.id, { x: dentro(a.original.x + dx, ancho), y: dentro(a.original.y + dy, alto) });
  } else {
    const o = a.original, el = E.plano.elementos[E.sel.i];
    if (el.tipo === 'linea') {
      // la línea entera se corre sin salirse del plano
      const mx = Math.min(Math.max(dx, -Math.min(o.x1, o.x2)), ancho - Math.max(o.x1, o.x2));
      const my = Math.min(Math.max(dy, -Math.min(o.y1, o.y2)), alto - Math.max(o.y1, o.y2));
      Object.assign(el, { x1: +(o.x1 + mx).toFixed(2), x2: +(o.x2 + mx).toFixed(2), y1: +(o.y1 + my).toFixed(2), y2: +(o.y2 + my).toFixed(2) });
    } else if (el.tipo === 'rect') {
      Object.assign(el, { x: dentro(o.x + dx, ancho - o.w), y: dentro(o.y + dy, alto - o.h) });
    } else {
      Object.assign(el, { x: dentro(o.x + dx, ancho), y: dentro(o.y + dy, alto) });
    }
  }
  pintarSvg();
}

function mapaArriba() {
  const E = M.edit, a = E?.arrastre;
  if (!a) return;
  E.arrastre = null;
  if (!a.dibujo) return;
  const { desde: d, hasta: h } = a;
  if (a.dibujo === 'rect') {
    const w = Math.abs(h.x - d.x), alto = Math.abs(h.y - d.y);
    if (!w || !alto) return pintarSvg();
    E.plano.elementos.push({ tipo: 'rect', x: Math.min(d.x, h.x), y: Math.min(d.y, h.y), w: +w.toFixed(2), h: +alto.toFixed(2),
      etiqueta: '', color: E.color });
  } else {
    if (d.x === h.x && d.y === h.y) return pintarSvg();
    E.plano.elementos.push({ tipo: 'linea', x1: d.x, y1: d.y, x2: h.x, y2: h.y, color: E.color });
  }
  E.sel = { tipo: 'el', i: E.plano.elementos.length - 1 };
  pintarSvg(); pintarLado();
  if (a.dibujo === 'rect') $('#mapa-propiedades [data-prop=etiqueta]')?.focus();
}

async function guardarPlano(boton) {
  const E = M.edit;
  $('#mapa-error').textContent = '';
  boton.disabled = true;
  try {
    await api('/api/planos/' + E.plano.id, { metodo: 'PUT', datos: { nombre: E.plano.nombre, ancho: E.plano.ancho, alto: E.plano.alto,
      elementos: E.plano.elementos, equipos: [...E.puntos].map(([equipo_id, p]) => ({ equipo_id, ...p })) } });
    terminarEdicion();
    avisar('Plano guardado.');
    await VISTAS.mapa(E.plano.id);
  } catch (e) { $('#mapa-error').textContent = e.message; boton.disabled = false; }
}

function modalNuevoPlano() {
  abrirModal(`<h2>Nuevo plano</h2>
    <form id="f-nuevo-plano"><p class="sutil">Uno por nave o sector. Las medidas son del área a dibujar, en metros: se pueden cambiar después.</p>
      <div class="campos"><label>Nombre <input name="nombre" maxlength="60" required placeholder="Nave de fundición"></label>
        <label>Ancho (m) <input name="ancho" type="number" min="1" step="0.5" value="50" required></label>
        <label>Alto (m) <input name="alto" type="number" min="1" step="0.5" value="30" required></label></div>
      <p class="error"></p>
      <div class="botones"><button class="primario">Crear y dibujar</button><button type="button" onclick="cerrarModal()">Cancelar</button></div></form>`);
  const f = $('#f-nuevo-plano');
  f.addEventListener('submit', ev => {
    ev.preventDefault();
    enviar(f, async d => {
      const p = await api('/api/planos', { metodo: 'POST', datos: d });
      cerrarModal();
      history.replaceState(null, '', '#mapa/' + p.id);
      await VISTAS.mapa(p.id);
      editarPlano();
    });
  });
}

async function eliminarPlano() {
  const p = planoActual();
  if (!confirm(`¿Eliminar el plano "${p.nombre}"?\nSus máquinas quedan sin ubicar; no se borra nada de su historial.`)) return;
  try { await api('/api/planos/' + p.id, { metodo: 'DELETE' }); M.planoId = null; avisar('Plano eliminado.'); irA('mapa'); }
  catch (e) { avisar(e.message, true); }
}

/** Al tocar una máquina: lo que tiene pendiente, con el botón para registrarlo ahí mismo. */
function fichaEquipoMapa(id) {
  const e = equipoMapa(id);
  const [color, texto] = ESTADOS_MAPA[e.estado];
  abrirModal(`<h2>${esc(e.codigo)} · ${esc(e.nombre)}</h2>
    <p>${e.sector ? esc(e.sector) + ' · ' : ''}<span class="chip ${color}">${texto}</span></p>
    ${e.pendientes.length ? `<div class="tabla-wrap"><table><thead><tr><th>Tarea</th><th>Mantenimiento</th><th>Estado</th><th></th></tr></thead><tbody>
      ${e.pendientes.map(t => `<tr><td><b>${esc(t.codigo)}</b></td><td>${esc(t.seccion)}</td>
        <td><span class="chip ${ESTADOS_MAPA[t.estado][0]}">${esc(t.detalle)}</span></td>
        <td class="botones"><button class="chico primario" onclick="modalRegistro(${t.tarea_id})">Registrar</button></td></tr>`).join('')}
    </tbody></table></div>` : '<p class="sutil">No tiene nada pendiente.</p>'}
    <div class="botones"><button onclick="cerrarModal()">Cerrar</button></div>`);
}
