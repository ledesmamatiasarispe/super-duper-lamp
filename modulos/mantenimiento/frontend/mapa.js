// ── MAPA DE PLANTA ──
// Planos dibujados en la app con las máquinas como puntos. El color del punto es el peor estado de lo que tiene
// pendiente (lo mismo que Inicio). Editar es solo de administradores y se guarda todo junto.
// El dibujo es un CROQUIS como el de SolidWorks u Onshape (el motor está en croquis.js): líneas encadenadas,
// rectángulos, círculos, arcos y polígonos con imanes e inferencias; restricciones (horizontal, paralela, tangente...)
// y cotas que mandan; recortar, extender, equidistancia, simetría; zoom, deshacer y selección múltiple.

const M = { datos: null, planoId: null, edit: null, vista: null };
const ESTADOS_MAPA = { vencido: ['rojo', 'Vencido'], pendiente: ['ambar', 'Pendiente / próximo'], sin_dato: ['azul', 'Sin dato'],
  al_dia: ['verde', 'Al día'] };
const COLORES_PLANO = { gris: 'Gris', azul: 'Azul', verde: 'Verde', ambar: 'Ámbar', rojo: 'Rojo' };
const HERRAMIENTAS = {
  seleccionar: ['Seleccionar', 'S'], linea: ['Línea', 'L'], rect: ['Rectángulo', 'R'], rectc: ['Rect. desde el centro', ''],
  circulo: ['Círculo', 'C'], arco: ['Arco (3 puntos)', 'A'], poligono: ['Polígono', ''], texto: ['Texto', ''],
  cota: ['Cota', 'D'], recortar: ['Recortar', 'T'], extender: ['Extender', 'E'],
};
const AYUDA_HERRAMIENTA = {
  seleccionar: 'Tocá algo para elegirlo (Mayús suma a la selección) y arrastralo para moverlo; arrastrá en vacío para elegir con una caja. Supr borra.',
  linea: 'Tocá el inicio y cada punto siguiente: las líneas se encadenan. Doble clic o Esc termina. Escribí el largo (y "<ángulo") y Enter.',
  rect: 'Tocá una esquina y la opuesta. Podés escribir "ancho,alto" y Enter.',
  rectc: 'Tocá el centro y una esquina. Podés escribir "ancho,alto" y Enter.',
  circulo: 'Tocá el centro y un punto del borde. Podés escribir el radio y Enter.',
  arco: 'Tocá el inicio, el final y un punto por donde pasa.',
  poligono: 'Tocá el centro y un vértice.',
  texto: 'Tocá donde va el texto.',
  cota: 'Tocá una línea (largo), un círculo o arco (radio), dos puntos (distancia), un punto y una línea, o dos líneas (ángulo). Después escribí el valor.',
  recortar: 'Tocá el tramo de línea que sobra: se corta hasta las líneas que la cruzan.',
  extender: 'Tocá una línea cerca de la punta que querés estirar hasta la próxima línea o círculo.',
};
const SIMBOLO_RESTR = { horizontal: 'H', vertical: 'V', paralela: '∥', perpendicular: '⊥', igual: '=', tangente: 'T',
  puntoEnLinea: '◦', enCirculo: '○', medio: 'M', fija: 'F' };

VISTAS.mapa = async id => {
  M.datos = await api('/api/planos');
  const ids = M.datos.planos.map(p => p.id);
  const antes = M.planoId;
  M.planoId = ids.includes(Number(id)) ? Number(id) : ids.includes(M.planoId) ? M.planoId : ids[0] ?? null;
  if (M.planoId !== antes) M.vista = null;
  M.edit = null;
  pintarMapa();
};

const planoActual = () => M.datos.planos.find(p => p.id === M.planoId);
const equipoMapa = id => M.datos.equipos.find(e => e.id === id);
const fmt = (n, dec = 2) => Number(n).toLocaleString('es-AR', { maximumFractionDigits: dec });

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
      ${M.edit ? '' : `<p class="mapa-leyenda">${leyenda} <span class="sutil">Tocar una máquina muestra lo que tiene pendiente. Rueda: zoom; arrastrar: mover.</span></p>`}
      <div class="mapa-cuerpo">
        <div class="tarjeta mapa-lienzo"><svg id="mapa-svg" class="${M.edit ? 'editando herr-' + M.edit.herramienta : ''}"></svg>
          <div class="mapa-zoom botones"><button class="chico" onclick="zoomMapa(1/1.25)" title="Acercar">+</button>
            <button class="chico" onclick="zoomMapa(1.25)" title="Alejar">−</button>
            <button class="chico" onclick="ajustarVista(); pintarSvg()" title="Ver el plano entero">Ajustar</button></div></div>
        <aside class="tarjeta mapa-lado" id="mapa-lado"></aside>
      </div>`
    : `<div class="tarjeta"><p>Todavía no hay planos.</p>${S.usuario.es_admin
      ? '<p class="sutil">Un plano por nave o sector: se dibujan las paredes y los sectores, y después se ubican las máquinas.</p>'
      : '<p class="sutil">Los arma un administrador.</p>'}</div>`}`;
  if (!plano) return;
  if (!M.vista) ajustarVista();
  pintarSvg();
  pintarLado();
  const svg = $('#mapa-svg');
  svg.addEventListener('pointerdown', mapaAbajo);
  svg.addEventListener('pointermove', mapaMover);
  svg.addEventListener('pointerup', mapaArriba);
  svg.addEventListener('dblclick', mapaDobleClic);
  svg.addEventListener('wheel', ev => { ev.preventDefault(); zoomMapa(ev.deltaY > 0 ? 1.15 : 1 / 1.15, puntoSvg(ev)); }, { passive: false });
}

// ── la vista: zoom y desplazamiento (en metros, el viewBox del svg) ──
function ajustarVista() {
  const p = M.edit ? M.edit.plano : planoActual(), m = Math.max(p.ancho, p.alto) * 0.04;
  M.vista = { x: -m, y: -m, w: p.ancho + 2 * m, h: p.alto + 2 * m };
}

function zoomMapa(factor, centro) {
  const v = M.vista, c = centro || { x: v.x + v.w / 2, y: v.y + v.h / 2 };
  const p = M.edit ? M.edit.plano : planoActual(), max = Math.max(p.ancho, p.alto) * 4;
  const w = Math.min(max, Math.max(0.5, v.w * factor)), f = w / v.w;
  Object.assign(v, { x: c.x - (c.x - v.x) * f, y: c.y - (c.y - v.y) * f, w, h: v.h * f });
  pintarSvg();
}

/** Del puntero a metros del plano (sin imanes). */
function puntoSvg(ev) {
  const svg = $('#mapa-svg'), pt = svg.createSVGPoint();
  pt.x = ev.clientX; pt.y = ev.clientY;
  const p = pt.matrixTransform(svg.getScreenCTM().inverse());
  return { x: p.x, y: p.y };
}

/** Cuántos metros son n píxeles en pantalla (para que las tolerancias y los grosores no dependan del zoom). */
const px = n => n * M.vista.w / Math.max(1, $('#mapa-svg')?.clientWidth || 800);
/** Paso de la grilla según el zoom: que las celdas no queden más chicas que ~14 px. */
const pasoGrilla = () => [0.1, 0.25, 0.5, 1, 2, 5, 10, 25, 50, 100].find(p => p >= px(14)) || 100;

/** Lo que se dibuja: el croquis en edición (con sus cambios) o el guardado. */
function vistaPlano() {
  if (M.edit) return { plano: M.edit.plano, croquis: M.edit.croquis, puntos: M.edit.puntos };
  const plano = planoActual();
  plano._croquis ??= Croquis.convertir(plano.elementos);
  const puntos = new Map(M.datos.equipos.filter(e => e.plano_id === plano.id).map(e => [e.id, { x: e.plano_x, y: e.plano_y }]));
  return { plano, croquis: plano._croquis, puntos };
}

// ── dibujar ──
function pintarSvg() {
  const svg = $('#mapa-svg');
  if (!svg) return;
  const { plano, croquis: m, puntos } = vistaPlano(), E = M.edit, v = M.vista, u = px(1);
  svg.setAttribute('viewBox', `${v.x} ${v.y} ${v.w} ${v.h}`);
  svg.style.aspectRatio = `${v.w} / ${v.h}`;
  const P = pid => Croquis.punto(m, pid), sel = E?.sel || new Set();
  const paso = pasoGrilla();
  const grilla = E ? `<defs><pattern id="mapa-grilla" width="${paso}" height="${paso}" patternUnits="userSpaceOnUse">
      <path d="M ${paso} 0 L 0 0 0 ${paso}" class="pl-grilla" stroke-width="${u}"/></pattern></defs>
    <rect width="${plano.ancho}" height="${plano.alto}" fill="url(#mapa-grilla)"/>` : '';
  const ents = m.entidades.filter(e => E || !e.constr).map(e => {
    const s = sel.has('e' + e.id) ? ' sel' : '', c = e.constr ? ' constr' : '', g = `data-e="${e.id}" class="pl-${e.color || 'gris'}${s}${c}"`;
    const tocar = d => `<path d="${d}" class="pl-tocar" stroke-width="${u * 12}"/>`;
    if (e.tipo === 'linea') {
      const a = P(e.a), b = P(e.b), d = `M ${a.x} ${a.y} L ${b.x} ${b.y}`;
      return `<g ${g}><path d="${d}" class="pl-linea" stroke-width="${u * (e.constr ? 1.5 : 3)}"/>${tocar(d)}</g>`;
    }
    if (e.tipo === 'rect') {
      const ps = e.p.map(P), d = 'M ' + ps.map(p => `${p.x} ${p.y}`).join(' L ') + ' Z';
      const cx = ps.reduce((t, p) => t + p.x, 0) / 4, cy = ps.reduce((t, p) => t + p.y, 0) / 4;
      const w = Math.abs(ps[1].x - ps[0].x), h = Math.abs(ps[3].y - ps[0].y);
      const fs = Math.min(u * 16, h * 0.5, w / Math.max(4, (e.etiqueta || '').length) * 1.6);
      return `<g ${g}><path d="${d}" class="pl-rect" stroke-width="${u * 2}"/>${tocar(d)}
        ${e.etiqueta ? `<text x="${cx}" y="${cy}" font-size="${fs}" class="pl-etiqueta">${esc(e.etiqueta)}</text>` : ''}</g>`;
    }
    if (e.tipo === 'circulo') {
      const c0 = P(e.c), d = `M ${c0.x - e.r} ${c0.y} a ${e.r} ${e.r} 0 1 0 ${2 * e.r} 0 a ${e.r} ${e.r} 0 1 0 ${-2 * e.r} 0`;
      return `<g ${g}><path d="${d}" class="pl-circulo" stroke-width="${u * (e.constr ? 1.5 : 2.5)}"/>${tocar(d)}
        ${e.etiqueta ? `<text x="${c0.x}" y="${c0.y}" font-size="${Math.min(u * 16, e.r * 0.6)}" class="pl-etiqueta">${esc(e.etiqueta)}</text>` : ''}</g>`;
    }
    if (e.tipo === 'arco') {
      const c0 = P(e.c), a = P(e.a), b = P(e.b), r = Croquis.dist(c0, a);
      const barrido = ((Croquis.ang(c0, b) - Croquis.ang(c0, a)) % (2 * Math.PI) + 2 * Math.PI) % (2 * Math.PI);
      const d = `M ${a.x} ${a.y} A ${r} ${r} 0 ${barrido > Math.PI ? 1 : 0} 1 ${b.x} ${b.y}`;
      return `<g ${g}><path d="${d}" class="pl-linea" stroke-width="${u * (e.constr ? 1.5 : 3)}"/>${tocar(d)}</g>`;
    }
    const p = P(e.p);
    return `<g ${g}><text x="${p.x}" y="${p.y}" font-size="${u * 14 * (e.tamanio || 1)}" class="pl-texto">${esc(e.texto)}</text></g>`;
  }).join('');
  let extra = '';
  if (E) {
    const def = E.definidos;
    extra += m.cotas.map(k => dibujoCota(m, k, u, sel.has('c' + k.id))).join('');
    if (E.verRestricciones) extra += dibujoRestricciones(m, u, sel);
    // los puntos: negros si están totalmente definidos, azules si todavía se pueden mover
    extra += m.puntos.map(p => `<circle data-p="${p.id}" class="pl-punto${def?.has('px' + p.id) && def?.has('py' + p.id) ? ' def' : ''}${sel.has('p' + p.id) ? ' sel' : ''}"
      cx="${p.x}" cy="${p.y}" r="${u * 3.5}" stroke-width="${u}"/>`).join('');
    extra += dibujoPrevia(u);
  }
  const maquinas = [...puntos].map(([id, p]) => {
    const e = equipoMapa(id);
    if (!e) return '';
    const [color, texto] = ESTADOS_MAPA[e.estado] || ESTADOS_MAPA.al_dia;
    const s = sel.has('q' + id) ? ' sel' : '';
    return `<g data-equipo="${id}" class="mapa-punto punto-${color}${s}" transform="translate(${p.x} ${p.y})">
      <title>${esc(e.codigo)} · ${esc(e.nombre)} — ${texto}</title>
      <circle r="${u * 9}" stroke-width="${u * 2.5}"/><text y="${-u * 14}" font-size="${u * 12}" stroke-width="${u * 3}">${esc(e.codigo)}</text></g>`;
  }).join('');
  svg.innerHTML = `<rect width="${plano.ancho}" height="${plano.alto}" class="pl-borde" stroke-width="${u * 1.5}"/>${grilla}${ents}${extra}${maquinas}`;
}

/** Una cota: líneas de referencia, la de medida y el valor (que se toca para cambiarlo). */
function dibujoCota(m, k, u, elegida) {
  const P = pid => Croquis.punto(m, pid), E = eid => Croquis.entidad(m, eid);
  const seg = (a, b) => `<line x1="${a.x}" y1="${a.y}" x2="${b.x}" y2="${b.y}" stroke-width="${u}"/>`;
  let lineas = '', t;
  const paralela = (a, b) => {   // cota alineada a a-b, corrida (ox, oy) en la normal
    const L = Croquis.dist(a, b) || 1, n = { x: -(b.y - a.y) / L, y: (b.x - a.x) / L }, d = k.ox * n.x + k.oy * n.y;
    const a2 = { x: a.x + n.x * d, y: a.y + n.y * d }, b2 = { x: b.x + n.x * d, y: b.y + n.y * d };
    lineas = seg(a, a2) + seg(b, b2) + seg(a2, b2) + flecha(a2, b2, u) + flecha(b2, a2, u);
    t = { x: (a2.x + b2.x) / 2 + n.x * u * 8, y: (a2.y + b2.y) / 2 + n.y * u * 8 };
  };
  if (k.tipo === 'largo') { const l = E(k.e1); paralela(P(l.a), P(l.b)); }
  else if (k.tipo === 'distancia') paralela(P(k.p1), P(k.p2));
  else if (k.tipo === 'distpl') {
    const l = E(k.e1), a = P(l.a), b = P(l.b), p = P(k.p1), dx = b.x - a.x, dy = b.y - a.y, L2 = dx * dx + dy * dy || 1;
    const s = ((p.x - a.x) * dx + (p.y - a.y) * dy) / L2;
    paralela(p, { x: a.x + s * dx, y: a.y + s * dy });
  } else if (k.tipo === 'dx' || k.tipo === 'dy') {
    const a = P(k.p1), b = P(k.p2), h = k.tipo === 'dx';
    const base = h ? Math.min(a.y, b.y) + k.oy : Math.min(a.x, b.x) + k.ox;
    const a2 = h ? { x: a.x, y: base } : { x: base, y: a.y }, b2 = h ? { x: b.x, y: base } : { x: base, y: b.y };
    lineas = seg(a, a2) + seg(b, b2) + seg(a2, b2) + flecha(a2, b2, u) + flecha(b2, a2, u);
    t = h ? { x: (a.x + b.x) / 2, y: base - u * 8 } : { x: base - u * 8, y: (a.y + b.y) / 2 };
  } else if (k.tipo === 'radio') {
    const e = E(k.e1), c = P(e.c), r = e.tipo === 'circulo' ? e.r : Croquis.dist(c, P(e.a));
    const angulo = Math.atan2(k.oy || -1, k.ox || 1), q = { x: c.x + r * Math.cos(angulo), y: c.y + r * Math.sin(angulo) };
    lineas = seg(c, q) + flecha(c, q, u);
    t = { x: q.x + Math.cos(angulo) * u * 14, y: q.y + Math.sin(angulo) * u * 14 };
  } else if (k.tipo === 'angulo') {
    const l1 = E(k.e1), l2 = E(k.e2), a1 = P(l1.a), b1 = P(l1.b), a2 = P(l2.a), b2 = P(l2.b);
    const d1x = b1.x - a1.x, d1y = b1.y - a1.y, d2x = b2.x - a2.x, d2y = b2.y - a2.y, den = d1x * d2y - d1y * d2x;
    const s = Math.abs(den) < 1e-12 ? 0.5 : ((a2.x - a1.x) * d2y - (a2.y - a1.y) * d2x) / den, I = { x: a1.x + s * d1x, y: a1.y + s * d1y };
    const rr = u * 30 + Math.hypot(k.ox, k.oy), t1 = Math.atan2(d1y, d1x), t2 = t1 + (k.signo || 1) * k.valor * Math.PI / 180;
    const q1 = { x: I.x + rr * Math.cos(t1), y: I.y + rr * Math.sin(t1) }, q2 = { x: I.x + rr * Math.cos(t2), y: I.y + rr * Math.sin(t2) };
    lineas = `<path d="M ${q1.x} ${q1.y} A ${rr} ${rr} 0 0 ${(k.signo || 1) > 0 ? 1 : 0} ${q2.x} ${q2.y}" fill="none" stroke-width="${u}"/>`;
    const tm = (t1 + t2) / 2;
    t = { x: I.x + (rr + u * 12) * Math.cos(tm), y: I.y + (rr + u * 12) * Math.sin(tm) };
  }
  if (!t) return '';
  const texto = k.tipo === 'angulo' ? `${fmt(k.valor, 1)}°` : (k.tipo === 'radio' ? 'R ' : '') + fmt(k.valor);
  return `<g data-c="${k.id}" class="pl-cota${elegida ? ' sel' : ''}">${lineas}
    <text x="${t.x}" y="${t.y}" font-size="${u * 12}" stroke-width="${u * 3}">${texto}</text></g>`;
}

function flecha(a, b, u) {
  const L = Croquis.dist(a, b) || 1, ux = (b.x - a.x) / L, uy = (b.y - a.y) / L, s = u * 6;
  return `<path d="M ${a.x} ${a.y} l ${ux * s - uy * s * 0.4} ${uy * s + ux * s * 0.4} l ${uy * s * 0.8} ${-ux * s * 0.8} Z" class="pl-flecha"/>`;
}

/** Los íconos de las restricciones, al lado de lo que restringen (se tocan para elegirlas y borrarlas). */
function dibujoRestricciones(m, u, sel) {
  const cuenta = new Map(), salida = [];
  const lugar = r => {
    const P = pid => Croquis.punto(m, pid), e = r.e1 && Croquis.entidad(m, r.e1);
    if (r.p1) return P(r.p1);
    if (!e) return null;
    if (e.tipo === 'linea') { const a = P(e.a), b = P(e.b); return { x: (a.x + b.x) / 2, y: (a.y + b.y) / 2 }; }
    return P(e.c || e.p?.[0] || e.p);
  };
  for (const r of m.restricciones) {
    const p = lugar(r);
    if (!p) continue;
    const clave = `${p.x.toFixed(3)},${p.y.toFixed(3)}`, n = cuenta.get(clave) || 0;
    cuenta.set(clave, n + 1);
    const x = p.x + u * (10 + n * 16), y = p.y - u * 10;
    salida.push(`<g data-r="${r.id}" class="pl-restr${sel.has('r' + r.id) ? ' sel' : ''}"><title>${esc(Croquis.RESTRICCIONES[r.tipo])}</title>
      <rect x="${x - u * 7}" y="${y - u * 7}" width="${u * 14}" height="${u * 14}" rx="${u * 2}" stroke-width="${u}"/>
      <text x="${x}" y="${y}" font-size="${u * 10}">${SIMBOLO_RESTR[r.tipo]}</text></g>`);
  }
  return salida.join('');
}

/** Lo que se está dibujando (la previa), el imán, las guías y la caja de selección. */
function dibujoPrevia(u) {
  const E = M.edit, c = E.cursor;
  let s = '';
  const linea = (a, b, cls = 'pl-previa') => `<line x1="${a.x}" y1="${a.y}" x2="${b.x}" y2="${b.y}" class="${cls}" stroke-width="${u * 1.5}"/>`;
  if (E.guias?.x && c) s += linea({ x: E.guias.x.x, y: E.guias.x.y }, c, 'pl-guia');
  if (E.guias?.y && c) s += linea({ x: E.guias.y.x, y: E.guias.y.y }, c, 'pl-guia');
  const pts = E.previa?.pts || [];
  const h = E.herramienta;
  if (pts.length && c) {
    const a = pts[0];
    if (h === 'linea') s += linea(pts[pts.length - 1], c);
    else if (h === 'rect' || h === 'rectc') {
      const [p1, p2] = h === 'rect' ? [a, c] : [{ x: 2 * a.x - c.x, y: 2 * a.y - c.y }, c];
      s += `<rect x="${Math.min(p1.x, p2.x)}" y="${Math.min(p1.y, p2.y)}" width="${Math.abs(p2.x - p1.x)}" height="${Math.abs(p2.y - p1.y)}" class="pl-previa" stroke-width="${u * 1.5}"/>`;
    } else if (h === 'circulo' || h === 'poligono') {
      s += `<circle cx="${a.x}" cy="${a.y}" r="${Croquis.dist(a, c)}" class="pl-previa" stroke-width="${u * 1.5}"/>`;
    } else if (h === 'arco') {
      s += pts.length === 1 ? linea(a, c) : (() => { const k = Croquis.circuloPor3(pts[0], pts[1], c);
        return k ? `<circle cx="${k.x}" cy="${k.y}" r="${k.r}" class="pl-previa" stroke-width="${u * 1.5}"/>` : linea(pts[0], pts[1]); })();
    }
    if (h === 'linea' || h === 'circulo') {   // la medida mientras se dibuja
      const b = pts[pts.length - 1], L = Croquis.dist(b, c), g = Math.atan2(-(c.y - b.y), c.x - b.x) * 180 / Math.PI;
      s += `<text x="${c.x + u * 10}" y="${c.y + u * 18}" class="pl-medida" font-size="${u * 11}" stroke-width="${u * 3}">${fmt(L)} m${h === 'linea' ? ` · ${fmt((g + 360) % 360, 1)}°` : ''}${E.entrada ? ` → ${esc(E.entrada)}` : ''}</text>`;
    }
  }
  if (E.inferencia && c) s += `<text x="${c.x + u * 10}" y="${c.y - u * 8}" class="pl-inferencia" font-size="${u * 10}">${E.inferencia}</text>`;
  if (E.imanActual) {
    const k = E.imanActual, r = u * 5;
    s += k.tipo === 'punto' ? `<rect x="${k.x - r}" y="${k.y - r}" width="${2 * r}" height="${2 * r}" class="pl-iman" stroke-width="${u * 1.5}"/>`
      : k.tipo === 'medio' ? `<path d="M ${k.x} ${k.y - r} L ${k.x + r} ${k.y + r} L ${k.x - r} ${k.y + r} Z" class="pl-iman" stroke-width="${u * 1.5}"/>`
      : `<path d="M ${k.x - r} ${k.y - r} L ${k.x + r} ${k.y + r} M ${k.x + r} ${k.y - r} L ${k.x - r} ${k.y + r}" class="pl-iman" stroke-width="${u * 1.5}"/>`;
  }
  if (E.caja) {
    const { a, b } = E.caja;
    s += `<rect x="${Math.min(a.x, b.x)}" y="${Math.min(a.y, b.y)}" width="${Math.abs(b.x - a.x)}" height="${Math.abs(b.y - a.y)}" class="pl-caja" stroke-width="${u}"/>`;
  }
  return s;
}

// ── panel lateral ──
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
  const E = M.edit, libres = E.libres;
  const otroPlano = id => M.datos.planos.find(p => p.id === id)?.nombre;
  const fuera = M.datos.equipos.filter(e => !E.puntos.has(e.id));
  const boton = k => `<button class="${E.herramienta === k ? 'primario' : ''}" title="${HERRAMIENTAS[k][1] ? 'Tecla ' + HERRAMIENTAS[k][1] : ''}"
    onclick="herramientaMapa('${k}')">${HERRAMIENTAS[k][0]}</button>`;
  lado.innerHTML = `
    <form id="f-plano" class="campos-plano">
      <label>Nombre <input name="nombre" value="${esc(E.plano.nombre)}" maxlength="60"></label>
      <div class="fila-2"><label>Ancho (m) <input name="ancho" type="number" min="1" step="0.5" value="${E.plano.ancho}"></label>
        <label>Alto (m) <input name="alto" type="number" min="1" step="0.5" value="${E.plano.alto}"></label></div></form>
    <div class="botones mapa-historial"><button class="chico" onclick="deshacerMapa()" ${E.deshacer.length ? '' : 'disabled'} title="Ctrl+Z">↶ Deshacer</button>
      <button class="chico" onclick="rehacerMapa()" ${E.rehacer.length ? '' : 'disabled'} title="Ctrl+Y">↷ Rehacer</button>
      <span class="chip ${libres === 0 ? 'verde' : 'azul'}" title="Grados de libertad: cuánto se puede mover todavía sin romper restricciones ni cotas">${
        libres === 0 ? 'Totalmente definido' : libres == null ? '' : `${libres} grados de libertad`}</span></div>
    <h3>Dibujo</h3>
    <div class="mapa-herramientas">${['seleccionar', 'linea', 'rect', 'rectc', 'circulo', 'arco', 'poligono', 'texto'].map(boton).join('')}</div>
    <h3>Edición</h3>
    <div class="mapa-herramientas">${['cota', 'recortar', 'extender'].map(boton).join('')}</div>
    ${E.herramienta === 'poligono' ? `<label>Lados <input id="mapa-lados" type="number" min="3" max="24" value="${E.lados}"></label>` : ''}
    <div class="mapa-opciones">
      <label>Color de lo nuevo <select id="mapa-color">${opcionesSelect(Object.entries(COLORES_PLANO), E.color, null)}</select></label>
      <label class="check"><input type="checkbox" data-opcion="constr" ${E.constr ? 'checked' : ''}> Dibujar como construcción</label>
      <label class="check"><input type="checkbox" data-opcion="auto" ${E.auto ? 'checked' : ''}> Restricciones automáticas</label>
      <label class="check"><input type="checkbox" data-opcion="grilla" ${E.grilla ? 'checked' : ''}> Imán a la grilla</label>
      <label class="check"><input type="checkbox" data-opcion="verRestricciones" ${E.verRestricciones ? 'checked' : ''}> Mostrar restricciones</label></div>
    <p class="sutil mapa-ayuda">${E.colocar ? `Tocá el plano donde está <b>${esc(equipoMapa(E.colocar).codigo)}</b>.` : AYUDA_HERRAMIENTA[E.herramienta]}
      ${E.entrada ? `<br>Escribiendo: <b>${esc(E.entrada)}</b> (Enter para aplicar)` : ''}</p>
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
  $('#mapa-lados')?.addEventListener('input', ev => { E.lados = Math.max(3, Math.min(24, Number(ev.target.value) || 6)); });
  lado.querySelectorAll('[data-opcion]').forEach(c => c.addEventListener('change', () => { E[c.dataset.opcion] = c.checked; pintarSvg(); }));
  $('#f-plano').addEventListener('input', ev => {
    const { name, value } = ev.target;
    if (name === 'nombre') E.plano.nombre = value;
    else if (Number(value) > 0) { E.plano[name] = Number(value); pintarSvg(); }
  });
  activarPropiedades();
}

/** Lo elegido, por tipo: e (entidades), p (puntos), c (cotas), r (restricciones), q (máquinas). */
function elegidos() {
  const E = M.edit, m = E.croquis, s = [...E.sel];
  const de = t => s.filter(k => k[0] === t).map(k => Number(k.slice(1)));
  const ents = de('e').map(i => Croquis.entidad(m, i)).filter(Boolean);
  return { ents, lineas: ents.filter(e => e.tipo === 'linea'), curvas: ents.filter(e => /circulo|arco/.test(e.tipo)),
    puntos: de('p'), cotas: de('c').map(i => m.cotas.find(k => k.id === i)).filter(Boolean),
    restr: de('r').map(i => m.restricciones.find(r => r.id === i)).filter(Boolean), maquinas: de('q') };
}

/** Las restricciones que se pueden aplicar a lo elegido (como el panel de relaciones de SolidWorks). */
function restriccionesPosibles(x) {
  const { ents, lineas, curvas, puntos } = x, solo = ents.length + puntos.length;
  const op = [];
  if (lineas.length === 1 && solo === 1) op.push(['horizontal', { e1: lineas[0].id }], ['vertical', { e1: lineas[0].id }]);
  if (puntos.length === 2 && solo === 2) op.push(['coincidente'], ['horizontal', { p1: puntos[0], p2: puntos[1] }], ['vertical', { p1: puntos[0], p2: puntos[1] }]);
  if (lineas.length === 2 && solo === 2) op.push(['paralela', { e1: lineas[0].id, e2: lineas[1].id }],
    ['perpendicular', { e1: lineas[0].id, e2: lineas[1].id }], ['igual', { e1: lineas[0].id, e2: lineas[1].id }]);
  if (curvas.length === 2 && solo === 2) op.push(['igual', { e1: curvas[0].id, e2: curvas[1].id }], ['concentrico']);
  if (lineas.length === 1 && curvas.length === 1 && solo === 2) op.push(['tangente', { e1: lineas[0].id, e2: curvas[0].id }]);
  if (puntos.length === 1 && lineas.length === 1 && solo === 2) op.push(['puntoEnLinea', { p1: puntos[0], e1: lineas[0].id }], ['medio', { p1: puntos[0], e1: lineas[0].id }]);
  if (puntos.length === 1 && curvas.length === 1 && solo === 2) op.push(['enCirculo', { p1: puntos[0], e1: curvas[0].id }]);
  if (puntos.length && solo === puntos.length) op.push(['fija']);
  return op;
}

const NOMBRE_RESTR = { ...Croquis.RESTRICCIONES, coincidente: 'Coincidente', concentrico: 'Concéntrico' };

/** El panel de lo elegido: datos editables, restricciones posibles, operaciones. */
function propiedadesMapa() {
  const E = M.edit, m = E.croquis, x = elegidos();
  if (!E.sel.size) return '';
  const partes = [];
  if (x.maquinas.length === 1 && E.sel.size === 1) {
    const e = equipoMapa(x.maquinas[0]);
    return `<div class="mapa-prop"><b>${esc(e.codigo)} · ${esc(e.nombre)}</b>
      <div class="botones"><button class="chico peligro" onclick="borrarSeleccion()">Sacar del plano</button></div></div>`;
  }
  if (x.cotas.length === 1 && E.sel.size === 1) {
    const k = x.cotas[0], cambiable = ['distancia', 'dx', 'dy'].includes(k.tipo);
    partes.push(`<b>Cota: ${esc(Croquis.COTAS[k.tipo])}</b>
      <label>Valor ${k.tipo === 'angulo' ? '(°)' : '(m)'} <input data-cota="${k.id}" type="number" step="0.01" min="0" value="${+k.valor.toFixed(3)}"></label>
      ${cambiable ? `<div class="botones">${['distancia', 'dx', 'dy'].map(t => `<button class="chico ${k.tipo === t ? 'primario' : ''}" onclick="tipoCota(${k.id}, '${t}')">${Croquis.COTAS[t]}</button>`).join('')}</div>` : ''}`);
  }
  if (x.ents.length === 1 && E.sel.size === 1) {
    const e = x.ents[0];
    const color = `<label>Color <select data-prop="color">${opcionesSelect(Object.entries(COLORES_PLANO), e.color || 'gris', null)}</select></label>`;
    const nombre = { linea: 'Línea', rect: 'Rectángulo', circulo: 'Círculo', arco: 'Arco', texto: 'Texto' }[e.tipo];
    let campos = '';
    if (e.tipo === 'linea') {
      const a = Croquis.punto(m, e.a), b = Croquis.punto(m, e.b);
      campos = `<label>Largo (m) <input data-medida="largo" type="number" min="0.01" step="0.1" value="${+Croquis.dist(a, b).toFixed(3)}"></label>
        <label>Ángulo (°) <input data-medida="angulo" type="number" step="1" value="${+(((Math.atan2(-(b.y - a.y), b.x - a.x) * 180 / Math.PI) + 360) % 360).toFixed(2)}"></label>`;
    } else if (e.tipo === 'circulo' || e.tipo === 'arco') {
      const r = e.tipo === 'circulo' ? e.r : Croquis.dist(Croquis.punto(m, e.c), Croquis.punto(m, e.a));
      campos = `<label>Radio (m) <input data-medida="radio" type="number" min="0.01" step="0.1" value="${+r.toFixed(3)}"></label>`;
    }
    if (e.tipo === 'rect' || e.tipo === 'circulo') campos += `<label>Nombre del sector <input data-prop="etiqueta" maxlength="60" value="${esc(e.etiqueta || '')}"></label>`;
    if (e.tipo === 'texto') campos += `<label>Texto <input data-prop="texto" maxlength="80" value="${esc(e.texto)}"></label>
      <label>Tamaño <select data-prop="tamanio">${opcionesSelect([1, 2, 3, 4, 5].map(n => [n, n]), e.tamanio, null)}</select></label>`;
    partes.push(`<b>${nombre}</b>${campos}${color}${e.tipo !== 'texto' && e.tipo !== 'rect'
      ? `<label class="check"><input type="checkbox" data-prop="constr" ${e.constr ? 'checked' : ''}> Construcción (no se ve en el plano terminado)</label>` : ''}`);
  } else if (x.ents.length + x.puntos.length > 1 || (x.puntos.length && !x.ents.length)) {
    partes.push(`<b>${x.ents.length ? `${x.ents.length} elemento(s)` : ''}${x.ents.length && x.puntos.length ? ' y ' : ''}${x.puntos.length ? `${x.puntos.length} punto(s)` : ''} elegidos</b>`);
  }
  const posibles = restriccionesPosibles(x);
  if (posibles.length) partes.push(`<div class="mapa-sub">Restricciones</div><div class="botones">${posibles.map(([t, d], i) =>
    `<button class="chico" onclick="aplicarRestriccion(${i})" title="${esc(NOMBRE_RESTR[t])}">${SIMBOLO_RESTR[t] ? SIMBOLO_RESTR[t] + ' ' : ''}${esc(NOMBRE_RESTR[t])}</button>`).join('')}</div>`);
  // las restricciones que ya tiene lo elegido (para verlas y sacarlas)
  const ids = new Set(x.ents.map(e => e.id)), pts = new Set(x.puntos);
  const tiene = m.restricciones.filter(r => ids.has(r.e1) || ids.has(r.e2) || pts.has(r.p1) || pts.has(r.p2) || x.restr.includes(r));
  if (tiene.length) partes.push(`<div class="mapa-sub">Tiene</div><ul class="mapa-restr">${tiene.map(r =>
    `<li>${SIMBOLO_RESTR[r.tipo]} ${esc(Croquis.RESTRICCIONES[r.tipo])} <button class="chico" onclick="quitarRestriccion(${r.id})" title="Sacar">✕</button></li>`).join('')}</ul>`);
  if (x.ents.length) {
    const ejes = x.lineas.length && x.ents.length > 1;
    partes.push(`<div class="mapa-sub">Operaciones</div>
      <div class="fila-2"><label>Equidistancia (m) <input id="mapa-equi" type="number" min="0.01" step="0.05" value="${E.equidistancia}"></label>
        <label class="check"><input type="checkbox" id="mapa-equi-ambos" ${E.ambos ? 'checked' : ''}> A los dos lados</label></div>
      <div class="botones"><button class="chico" onclick="equidistanciaMapa()">Equidistancia</button>
        ${ejes ? '<button class="chico" onclick="simetriaMapa()" title="El eje es la última línea elegida">Simetría</button>' : ''}
        <button class="chico" onclick="construccionMapa()">Construcción sí/no</button>
        <button class="chico" onclick="copiarMapa(); pegarMapa()">Duplicar</button></div>`);
  }
  partes.push(`<div class="botones"><button class="chico peligro" onclick="borrarSeleccion()">Borrar</button></div>`);
  return `<div class="mapa-prop">${partes.join('')}</div>`;
}

function activarPropiedades() {
  const E = M.edit, cont = $('#mapa-propiedades');
  if (!cont) return;
  cont.querySelectorAll('[data-prop]').forEach(inp => inp.addEventListener(inp.type === 'checkbox' ? 'change' : 'input', () => {
    const e = elegidos().ents[0];
    if (!e) return;
    historia();
    e[inp.dataset.prop] = inp.type === 'checkbox' ? inp.checked : inp.dataset.prop === 'tamanio' ? Number(inp.value) : inp.value;
    pintarSvg();
  }));
  cont.querySelectorAll('[data-medida]').forEach(inp => inp.addEventListener('change', () => cambiarMedida(inp.dataset.medida, Number(String(inp.value).replace(',', '.')))));
  cont.querySelectorAll('[data-cota]').forEach(inp => {
    inp.addEventListener('change', () => {
      historia();
      if (!Croquis.cambiarCota(E.croquis, Number(inp.dataset.cota), Number(String(inp.value).replace(',', '.')))) {
        E.deshacer.pop(); avisar('Ese valor no se puede cumplir con las demás restricciones y cotas.', true);
      }
      recalcular();
    });
    if (E.enfocarCota) { inp.focus({ preventScroll: true }); inp.select(); E.enfocarCota = false; }   // sin mover la página: el dibujo sigue a la vista
  });
  $('#mapa-equi')?.addEventListener('input', ev => { E.equidistancia = Number(String(ev.target.value).replace(',', '.')) || E.equidistancia; });
  $('#mapa-equi-ambos')?.addEventListener('change', ev => { E.ambos = ev.target.checked; });
}

/** Cambiar el largo, el ángulo o el radio desde el panel: si hay una cota que lo fija, se cambia la cota; si no, se lleva la
 *  geometría y el resolvedor acomoda lo demás. */
function cambiarMedida(que, valor) {
  const E = M.edit, m = E.croquis, e = elegidos().ents[0];
  if (!e || !(valor >= 0)) return;
  historia();
  if (que === 'radio') {
    const k = m.cotas.find(c => c.tipo === 'radio' && c.e1 === e.id);
    if (k) Croquis.cambiarCota(m, k.id, valor);
    else if (e.tipo === 'circulo') { e.r = Math.max(0.01, valor); Croquis.resolver(m); }
    else { const c = Croquis.punto(m, e.c), a = Croquis.punto(m, e.a), b = Croquis.punto(m, e.b);
      const f = q => ({ x: c.x + (q.x - c.x) / Croquis.dist(c, q) * valor, y: c.y + (q.y - c.y) / Croquis.dist(c, q) * valor });
      Croquis.resolver(m, [{ pid: e.a, ...f(a) }, { pid: e.b, ...f(b) }]); }
  } else {
    const a = Croquis.punto(m, e.a), b = Croquis.punto(m, e.b), L = Croquis.dist(a, b) || 1;
    const k = que === 'largo' && m.cotas.find(c => c.tipo === 'largo' && c.e1 === e.id);
    if (k) Croquis.cambiarCota(m, k.id, valor);
    else {
      const g = que === 'angulo' ? -valor * Math.PI / 180 : Math.atan2(b.y - a.y, b.x - a.x), largo = que === 'largo' ? valor : L;
      Croquis.resolver(m, [{ pid: e.b, x: a.x + largo * Math.cos(g), y: a.y + largo * Math.sin(g) }, { pid: e.a, x: a.x, y: a.y }]);
    }
  }
  recalcular();
}

// ── edición: estado, historia, recálculo ──
function editarPlano() {
  const p = planoActual();
  M.edit = { plano: { id: p.id, nombre: p.nombre, ancho: p.ancho, alto: p.alto }, croquis: Croquis.clonar(Croquis.convertir(p.elementos)),
    herramienta: 'seleccionar', color: 'gris', constr: false, auto: true, grilla: true, verRestricciones: true, sel: new Set(),
    colocar: null, arrastre: null, previa: null, cursor: null, entrada: '', lados: 6, equidistancia: 0.2, ambos: false,
    deshacer: [], rehacer: [], definidos: null, libres: null,
    puntos: new Map(M.datos.equipos.filter(e => e.plano_id === p.id).map(e => [e.id, { x: e.plano_x, y: e.plano_y }])) };
  document.addEventListener('keydown', teclaMapa);
  recalcular(false);
  pintarMapa();
}

/** Grados de libertad (qué está totalmente definido) y repintar. */
function recalcular(pintar = true) {
  const E = M.edit, g = Croquis.libertad(E.croquis);
  E.definidos = g.definidos; E.libres = g.libres;
  if (pintar) { pintarSvg(); pintarLado(); }
}

function historia() {
  const E = M.edit;
  E.deshacer.push(JSON.stringify({ c: E.croquis, q: [...E.puntos] }));
  if (E.deshacer.length > 100) E.deshacer.shift();
  E.rehacer = [];
}

function restaurar(desde, hacia) {
  const E = M.edit;
  if (!desde.length) return;
  hacia.push(JSON.stringify({ c: E.croquis, q: [...E.puntos] }));
  const s = JSON.parse(desde.pop());
  E.croquis = s.c; E.puntos = new Map(s.q); E.sel = new Set();
  recalcular();
}
function deshacerMapa() { restaurar(M.edit.deshacer, M.edit.rehacer); }
function rehacerMapa() { restaurar(M.edit.rehacer, M.edit.deshacer); }

function cancelarEdicionPlano() {
  if (M.edit.deshacer.length && !confirm('¿Descartar los cambios del plano?')) return;
  terminarEdicion(); pintarMapa();
}

function terminarEdicion() { M.edit = null; document.removeEventListener('keydown', teclaMapa); }

function herramientaMapa(h) {
  Object.assign(M.edit, { herramienta: h, colocar: null, previa: null, entrada: '', imanActual: null, guias: null, inferencia: '' });
  if (h !== 'seleccionar' && h !== 'cota') M.edit.sel = new Set();
  $('#mapa-svg')?.setAttribute('class', 'editando herr-' + h);
  pintarSvg(); pintarLado();
}

function colocarEquipo(id) { Object.assign(M.edit, { colocar: id, sel: new Set() }); pintarLado(); }

function borrarSeleccion() {
  const E = M.edit, x = elegidos();
  if (!E.sel.size) return;
  historia();
  x.maquinas.forEach(id => E.puntos.delete(id));
  // un punto suelto elegido se va con lo que lo usa
  const conPuntos = E.croquis.entidades.filter(e => Croquis.puntosDe(e).some(p => x.puntos.includes(p))).map(e => e.id);
  Croquis.borrar(E.croquis, { entidades: [...x.ents.map(e => e.id), ...conPuntos], cotas: x.cotas.map(k => k.id), restricciones: x.restr.map(r => r.id) });
  E.sel = new Set();
  Croquis.resolver(E.croquis);
  recalcular();
}

function quitarRestriccion(rid) {
  historia();
  Croquis.borrar(M.edit.croquis, { restricciones: [rid] });
  M.edit.sel.delete('r' + rid);
  recalcular();
}

function aplicarRestriccion(i) {
  const E = M.edit, m = E.croquis, x = elegidos(), [tipo, datos] = restriccionesPosibles(x)[i];
  historia();
  let ok = true;
  if (tipo === 'coincidente') { Croquis.fusionar(m, x.puntos[0], x.puntos[1]); ok = Croquis.resolver(m).ok; }
  else if (tipo === 'concentrico') { Croquis.fusionar(m, x.curvas[0].c, x.curvas[1].c); ok = Croquis.resolver(m).ok; }
  else if (tipo === 'fija') ok = x.puntos.every(p => Croquis.restringir(m, { tipo: 'fija', p1: p }));
  else ok = Croquis.restringir(m, { tipo, ...datos });
  if (!ok) {
    restaurar(E.deshacer, []);
    return avisar(`${NOMBRE_RESTR[tipo]}: choca con las restricciones o cotas que ya hay.`, true);
  }
  E.sel = new Set([...E.sel].filter(k => k[0] !== 'p' || m.puntos.some(p => 'p' + p.id === k)));
  recalcular();
}

function tipoCota(cid, tipo) {
  const E = M.edit, k = E.croquis.cotas.find(c => c.id === cid);
  historia();
  E.croquis.cotas = E.croquis.cotas.filter(c => c !== k);
  const nueva = Croquis.agregarCota(E.croquis, { tipo, p1: k.p1, p2: k.p2, ox: k.ox, oy: k.oy });
  E.sel = new Set(['c' + nueva]);
  recalcular();
}

function equidistanciaMapa() {
  const E = M.edit, x = elegidos();
  historia();
  const nuevos = Croquis.equidistancia(E.croquis, x.ents.map(e => e.id), E.equidistancia, E.ambos);
  if (!nuevos.length) { E.deshacer.pop(); return avisar('Equidistancia: elegí líneas, círculos o arcos.', true); }
  Croquis.resolver(E.croquis);
  E.sel = new Set(nuevos.map(i => 'e' + i));
  recalcular();
}

function simetriaMapa() {
  const E = M.edit, orden = [...E.sel].filter(k => k[0] === 'e').map(k => Number(k.slice(1)));
  const eje = [...orden].reverse().find(i => Croquis.entidad(E.croquis, i)?.tipo === 'linea');
  historia();
  const nuevos = Croquis.simetria(E.croquis, orden, eje);
  E.sel = new Set(nuevos.map(i => 'e' + i));
  recalcular();
}

function construccionMapa() {
  historia();
  const x = elegidos(), todas = x.ents.every(e => e.constr);
  x.ents.filter(e => e.tipo !== 'texto' && e.tipo !== 'rect').forEach(e => { e.constr = !todas; });
  recalcular();
}

let PORTAPAPELES_MAPA = null;
function copiarMapa() {
  const x = elegidos();
  if (x.ents.length) PORTAPAPELES_MAPA = Croquis.copiar(M.edit.croquis, x.ents.map(e => e.id));
}
function pegarMapa() {
  const E = M.edit;
  if (!PORTAPAPELES_MAPA) return;
  historia();
  const d = pasoGrilla() * 2;
  E.sel = new Set(Croquis.pegar(E.croquis, PORTAPAPELES_MAPA, d, d).map(i => 'e' + i));
  recalcular();
}

// ── teclado ──
function teclaMapa(ev) {
  const E = M.edit;
  if (!E || !document.getElementById('mapa-svg')) return terminarEdicion();
  if (ev.target.closest?.('input, select, textarea')) return;
  const ctrl = ev.ctrlKey || ev.metaKey, k = ev.key;
  if (ctrl && k.toLowerCase() === 'z') { ev.preventDefault(); return deshacerMapa(); }
  if (ctrl && k.toLowerCase() === 'y') { ev.preventDefault(); return rehacerMapa(); }
  if (ctrl && k.toLowerCase() === 'c') { ev.preventDefault(); return copiarMapa(); }
  if (ctrl && k.toLowerCase() === 'v') { ev.preventDefault(); return pegarMapa(); }
  if (ctrl) return;
  // escribir una medida mientras se dibuja: largo, "largo<ángulo", "ancho,alto" o el radio
  if (E.previa?.pts.length && /^[0-9.,<]$/.test(k)) { ev.preventDefault(); E.entrada += k; pintarSvg(); return pintarLado(); }
  if (E.entrada && k === 'Backspace') { ev.preventDefault(); E.entrada = E.entrada.slice(0, -1); pintarSvg(); return pintarLado(); }
  if (E.entrada && k === 'Enter') { ev.preventDefault(); return aplicarEntrada(); }
  if (k === 'Delete' || k === 'Backspace') { ev.preventDefault(); return borrarSeleccion(); }
  if (k === 'Escape') {
    Object.assign(E, { colocar: null, previa: null, entrada: '', imanActual: null, guias: null, caja: null });
    if (E.herramienta === 'seleccionar') E.sel = new Set();
    pintarSvg(); return pintarLado();
  }
  const atajo = Object.entries(HERRAMIENTAS).find(([, [, t]]) => t && t.toLowerCase() === k.toLowerCase());
  if (atajo) { ev.preventDefault(); herramientaMapa(atajo[0]); }
}

// ── el puntero ──
/** Del puntero a un punto del croquis con imanes: punto/medio/sobre una línea o un círculo, guías, inferencia H/V y grilla.
 *  Devuelve { x, y, iman } (iman: lo que se pegó, para la restricción automática). */
function apuntar(ev, desde = null, excluir = []) {
  const E = M.edit, m = E.croquis, p = puntoSvg(ev), tol = px(10);
  let x = p.x, y = p.y, iman = Croquis.iman(m, x, y, tol, excluir), infer = '';
  E.guias = null;
  if (iman) ({ x, y } = iman);
  else {
    if (desde) {   // inferencia: horizontal o vertical respecto del punto anterior
      if (Math.abs(y - desde.y) < tol * 0.8) { y = desde.y; infer = 'H'; }
      else if (Math.abs(x - desde.x) < tol * 0.8) { x = desde.x; infer = 'V'; }
    }
    const g = Croquis.guias(m, x, y, tol * 0.8, excluir);
    if (!infer && g.x) x = g.x.x;
    if (infer !== 'H' && g.y) y = g.y.y;
    E.guias = { x: g.x && !infer ? g.x : null, y: g.y && infer !== 'H' ? g.y : null };
    if (E.grilla && !g.x && !g.y && !infer) {
      const s = pasoGrilla() / 2;
      x = Math.round(x / s) * s; y = Math.round(y / s) * s;
    }
  }
  E.imanActual = iman; E.inferencia = infer;
  return { x, y, iman, infer };
}

/** Crea (o reusa, si el imán pegó a un punto) el punto del croquis; devuelve su id y las restricciones a agregar. */
function puntoDe(q, nuevas) {
  const m = M.edit.croquis;
  if (q.iman?.tipo === 'punto') return q.iman.pid;
  const pid = Croquis.agregarPunto(m, q.x, q.y);
  if (M.edit.auto && q.iman?.tipo === 'medio') nuevas.push({ tipo: 'medio', p1: pid, e1: q.iman.eid });
  if (M.edit.auto && q.iman?.tipo === 'sobre') nuevas.push({ tipo: 'puntoEnLinea', p1: pid, e1: q.iman.eid });
  if (M.edit.auto && q.iman?.tipo === 'enCirculo') nuevas.push({ tipo: 'enCirculo', p1: pid, e1: q.iman.eid });
  return pid;
}

function terminarCreacion(nuevas) {
  const m = M.edit.croquis;
  for (const r of nuevas) Croquis.restringir(m, r);   // si una automática choca, simplemente no se agrega
  recalcular();
}

function mapaAbajo(ev) {
  const E = M.edit;
  if (!E && ev.button === 0) {   // en la vista: tocar una máquina abre su ficha
    const maquina = ev.target.closest('[data-equipo]');
    if (maquina) return fichaEquipoMapa(Number(maquina.dataset.equipo));
  }
  if (ev.button === 1 || (ev.button === 0 && ev.altKey) || (!E && ev.button === 0 && !ev.target.closest('[data-equipo]'))) {   // desplazar la vista
    M.paneo = { x: ev.clientX, y: ev.clientY, v: { ...M.vista } };
    try { ev.currentTarget.setPointerCapture(ev.pointerId); } catch { /* sigue igual */ }
    return;
  }
  if (!E) return;
  try { ev.currentTarget.setPointerCapture(ev.pointerId); } catch { /* sin captura igual se puede dibujar */ }
  const m = E.croquis, h = E.herramienta;
  if (E.colocar) {
    historia();
    E.puntos.set(E.colocar, apuntar(ev));
    Object.assign(E, { sel: new Set(['q' + E.colocar]), colocar: null });
    pintarSvg(); return pintarLado();
  }
  if (h === 'seleccionar') return abajoSeleccionar(ev);
  if (h === 'cota') return abajoCota(ev);
  if (h === 'recortar' || h === 'extender') {
    const g = ev.target.closest('[data-e]'), p = puntoSvg(ev);
    if (!g) return;
    historia();
    const hecho = (h === 'recortar' ? Croquis.recortar : Croquis.extender)(m, Number(g.dataset.e), p.x, p.y);
    if (!hecho) { E.deshacer.pop(); return avisar(h === 'recortar' ? 'Recortar funciona con líneas.' : 'No hay nada hasta donde estirarla.', true); }
    Croquis.resolver(m);
    return recalcular();
  }
  const anterior = E.previa?.pts.at(-1);
  const q = apuntar(ev, h === 'linea' ? anterior : null);
  if (h === 'texto') {
    const texto = prompt('Texto:');
    if (!texto?.trim()) return;
    historia();
    const nuevas = [];
    agregarEntidad({ tipo: 'texto', p: puntoDe(q, nuevas), texto: texto.trim().slice(0, 80), tamanio: 1 });
    return terminarCreacion(nuevas);
  }
  E.previa ??= { pts: [], ids: [], nuevas: [] };
  E.previa.pts.push({ x: q.x, y: q.y, iman: q.iman, infer: q.infer });
  avanzarDibujo();
}

/** Cada clic de una herramienta de dibujo: cuando tiene los puntos que necesita, crea la entidad. */
function avanzarDibujo() {
  const E = M.edit, m = E.croquis, h = E.herramienta, pr = E.previa, pts = pr.pts, n = pts.length;
  const necesarios = { linea: 2, rect: 2, rectc: 2, circulo: 2, poligono: 2, arco: 3 }[h];
  if (n < necesarios) return pintarSvg();
  historia();
  const nuevas = [];
  if (h === 'linea') {
    const [a, b] = pts.slice(-2);
    if (Croquis.dist(a, b) < 1e-6) { pts.pop(); E.deshacer.pop(); return; }
    const pa = pr.ultimo ?? puntoDe(a, nuevas), pb = puntoDe(b, nuevas);
    const lid = agregarEntidad({ tipo: 'linea', a: pa, b: pb });
    if (E.auto && b.infer === 'H') nuevas.push({ tipo: 'horizontal', e1: lid });
    if (E.auto && b.infer === 'V') nuevas.push({ tipo: 'vertical', e1: lid });
    if (pr.cotaLargo) { nuevas.push({ cota: { tipo: 'largo', e1: lid, valor: pr.cotaLargo } }); pr.cotaLargo = null; }
    // encadenada: la próxima línea sale de este punto; si se cerró sobre un punto existente, termina
    if (b.iman?.tipo === 'punto' && pr.ids.length) { E.previa = null; }
    else { pr.ultimo = pb; pr.ids.push(lid); E.previa.pts = [b]; }
  } else if (h === 'rect' || h === 'rectc') {
    let [a, b] = pts;
    if (h === 'rectc') a = { x: 2 * pts[0].x - b.x, y: 2 * pts[0].y - b.y };
    const x1 = Math.min(a.x, b.x), x2 = Math.max(a.x, b.x), y1 = Math.min(a.y, b.y), y2 = Math.max(a.y, b.y);
    if (x2 - x1 < 1e-6 || y2 - y1 < 1e-6) { E.previa = null; E.deshacer.pop(); return pintarSvg(); }
    const esq = [[x1, y1], [x2, y1], [x2, y2], [x1, y2]].map(([x, y]) => {   // las esquinas que tocó el imán reusan su punto
      const tocada = [a, b].find(p => Math.abs(p.x - x) < 1e-9 && Math.abs(p.y - y) < 1e-9);
      return tocada ? puntoDe(tocada, nuevas) : Croquis.agregarPunto(m, x, y);
    });
    const rid = agregarEntidad({ tipo: 'rect', p: esq, etiqueta: '' });
    if (pr.medidas) nuevas.push({ cota: { tipo: 'dx', p1: esq[0], p2: esq[1], valor: pr.medidas[0] } }, { cota: { tipo: 'dy', p1: esq[0], p2: esq[3], valor: pr.medidas[1] } });
    if (h === 'rectc') {   // el centro queda como punto de construcción en el medio de la diagonal
      const c = puntoDe(pts[0], nuevas), diag = agregarEntidad({ tipo: 'linea', a: esq[0], b: esq[2], constr: true });
      nuevas.push({ tipo: 'medio', p1: c, e1: diag });
    }
    E.previa = null;
    E.sel = new Set(['e' + rid]);
  } else if (h === 'circulo') {
    const r = Croquis.dist(pts[0], pts[1]);
    if (r < 1e-6) { E.previa = null; E.deshacer.pop(); return pintarSvg(); }
    const cid = agregarEntidad({ tipo: 'circulo', c: puntoDe(pts[0], nuevas), r, etiqueta: '' });
    if (pr.radio) nuevas.push({ cota: { tipo: 'radio', e1: cid, valor: pr.radio } });
    E.previa = null;
  } else if (h === 'poligono') {
    const c = pts[0], r = Croquis.dist(c, pts[1]), a0 = Croquis.ang(c, pts[1]), lados = E.lados;
    const ids = [...Array(lados).keys()].map(i => i === 0 ? puntoDe(pts[1], nuevas)
      : Croquis.agregarPunto(m, c.x + r * Math.cos(a0 + i * 2 * Math.PI / lados), c.y + r * Math.sin(a0 + i * 2 * Math.PI / lados)));
    const lineas = ids.map((pid, i) => agregarEntidad({ tipo: 'linea', a: pid, b: ids[(i + 1) % lados] }));
    // regular: todos los lados iguales y los vértices sobre una circunferencia de construcción
    const circ = agregarEntidad({ tipo: 'circulo', c: puntoDe(c, nuevas), r, constr: true });
    lineas.slice(1).forEach(l => nuevas.push({ tipo: 'igual', e1: lineas[0], e2: l }));
    ids.forEach(pid => nuevas.push({ tipo: 'enCirculo', p1: pid, e1: circ }));
    E.previa = null;
  } else if (h === 'arco') {
    const k = Croquis.circuloPor3(pts[0], pts[1], pts[2]);
    if (!k) { E.previa = null; E.deshacer.pop(); return pintarSvg(); }
    const t = a => Croquis.ang(k, a), [p, q, s] = pts;
    const enOrden = Croquis.enArco(t(s), t(p), t(q));   // si el tercer punto no queda entre inicio y fin, va al revés
    const pa = puntoDe(enOrden ? p : q, nuevas), pb = puntoDe(enOrden ? q : p, nuevas);
    agregarEntidad({ tipo: 'arco', c: Croquis.agregarPunto(m, k.x, k.y), a: pa, b: pb });
    E.previa = null;
  }
  const restr = nuevas.filter(r => !r.cota), cotas = nuevas.filter(r => r.cota).map(r => r.cota);
  for (const k of cotas) { const cid = Croquis.agregarCota(m, k); Croquis.cambiarCota(m, cid, k.valor); }
  E.entrada = '';
  terminarCreacion(restr);
}

function agregarEntidad(e) {
  const E = M.edit;
  return Croquis.agregar(E.croquis, { color: E.color, constr: e.constr ?? (E.constr && e.tipo !== 'texto' && e.tipo !== 'rect'), ...e });
}

/** Enter con una medida escrita: "12" (largo o radio), "12<30" (largo y ángulo), "4,3" (ancho y alto). */
function aplicarEntrada() {
  const E = M.edit, h = E.herramienta, pr = E.previa, txt = E.entrada.replace(/\s/g, '');
  E.entrada = '';
  if (!pr?.pts.length) return pintarLado();
  const a = pr.pts.at(-1), c = E.cursor || a;
  const num = s => Number(String(s).replace(',', '.'));
  if (h === 'linea') {
    const [l, g] = txt.split('<').map(num);
    if (!(l > 0)) return pintarLado();
    const ang = g != null && !isNaN(g) ? -g * Math.PI / 180 : Math.atan2(c.y - a.y, c.x - a.x);
    pr.cotaLargo = l;
    pr.pts.push({ x: a.x + l * Math.cos(ang), y: a.y + l * Math.sin(ang), infer: g === 0 || g === 180 ? 'H' : g === 90 || g === 270 ? 'V' : '' });
  } else if (h === 'rect' || h === 'rectc') {
    const [w, hh] = txt.split(/[,;x*]/).map(num);
    if (!(w > 0 && hh > 0)) return pintarLado();
    const sx = Math.sign(c.x - a.x) || 1, sy = Math.sign(c.y - a.y) || 1, f = h === 'rectc' ? 0.5 : 1;
    pr.medidas = [w, hh];
    pr.pts.push({ x: a.x + sx * w * f, y: a.y + sy * hh * f });
  } else if (h === 'circulo' || h === 'poligono') {
    const r = num(txt);
    if (!(r > 0)) return pintarLado();
    if (h === 'circulo') pr.radio = r;
    const g = Math.atan2(c.y - a.y, c.x - a.x) || 0;
    pr.pts.push({ x: a.x + r * Math.cos(g), y: a.y + r * Math.sin(g) });
  } else return pintarLado();
  avanzarDibujo();
}

function abajoSeleccionar(ev) {
  const E = M.edit, m = E.croquis, sumar = ev.shiftKey || ev.ctrlKey;
  const g = ev.target.closest('[data-p], [data-equipo], [data-c], [data-r], [data-e]');
  const p0 = puntoSvg(ev);
  if (!g) {   // en vacío: caja de selección
    if (!sumar) E.sel = new Set();
    E.caja = { a: p0, b: p0, sumar };
    pintarSvg(); return pintarLado();
  }
  const clave = g.dataset.p ? 'p' + g.dataset.p : g.dataset.equipo ? 'q' + g.dataset.equipo : g.dataset.c ? 'c' + g.dataset.c
    : g.dataset.r ? 'r' + g.dataset.r : 'e' + g.dataset.e;
  if (sumar) { E.sel.has(clave) ? E.sel.delete(clave) : E.sel.add(clave); }
  else if (!E.sel.has(clave)) E.sel = new Set([clave]);
  else { E.sel.delete(clave); E.sel.add(clave); }   // la última elegida queda al final (el eje de la simetría)
  // arrastre: los puntos de lo elegido (los de las entidades y los sueltos) siguen al puntero; el resolvedor cuida el resto
  const x = elegidos();
  const pids = [...new Set([...x.ents.flatMap(Croquis.puntosDe), ...x.puntos])];
  const original = new Map(pids.map(pid => { const p = Croquis.punto(m, pid); return [pid, { x: p.x, y: p.y }]; }));
  const maquinas = new Map(x.maquinas.map(id => [id, { ...E.puntos.get(id) }]));
  E.arrastre = { desde: p0, original, maquinas, cota: x.cotas.length === 1 && clave[0] === 'c' ? x.cotas[0] : null,
    cotaOrig: x.cotas[0] && { ox: x.cotas[0].ox, oy: x.cotas[0].oy }, foto: JSON.stringify({ c: E.croquis, q: [...E.puntos] }), movio: false };
  if (clave[0] === 'c' && ev.detail === 2) E.enfocarCota = true;
  pintarSvg(); pintarLado();
}

function abajoCota(ev) {
  const E = M.edit, m = E.croquis;
  const g = ev.target.closest('[data-p], [data-e]');
  if (!g) { E.sel = new Set(); return pintarSvg(); }
  const clave = g.dataset.p ? 'p' + g.dataset.p : 'e' + g.dataset.e;
  E.sel.add(clave);
  const x = elegidos(), c = puntoSvg(ev);
  let k = null;
  const desde = (a, b) => {   // dónde va la cota: del lado del clic
    const L = Croquis.dist(a, b) || 1, n = { x: -(b.y - a.y) / L, y: (b.x - a.x) / L }, mx = (a.x + b.x) / 2, my = (a.y + b.y) / 2;
    const s = Math.sign((c.x - mx) * n.x + (c.y - my) * n.y) || 1;
    return { ox: n.x * s * px(24), oy: n.y * s * px(24) };
  };
  if (x.lineas.length === 1 && E.sel.size === 1) {
    const l = x.lineas[0];
    k = { tipo: 'largo', e1: l.id, ...desde(Croquis.punto(m, l.a), Croquis.punto(m, l.b)) };
  } else if (x.curvas.length === 1 && E.sel.size === 1) {
    k = { tipo: 'radio', e1: x.curvas[0].id, ox: 1, oy: -1 };
  } else if (x.ents.length === 1 && x.ents[0].tipo === 'rect' && E.sel.size === 1) {   // un lado del rectángulo
    const r = x.ents[0], ps = r.p.map(pid => Croquis.punto(m, pid));
    const lados = [0, 1, 2, 3].map(i => { const a = ps[i], b = ps[(i + 1) % 4], L2 = (b.x - a.x) ** 2 + (b.y - a.y) ** 2;
      const t = Math.max(0, Math.min(1, ((c.x - a.x) * (b.x - a.x) + (c.y - a.y) * (b.y - a.y)) / L2));
      return { i, d: Math.hypot(a.x + t * (b.x - a.x) - c.x, a.y + t * (b.y - a.y) - c.y) }; }).sort((u, v) => u.d - v.d);
    const i = lados[0].i, a = r.p[i], b = r.p[(i + 1) % 4];
    k = { tipo: i % 2 === 0 ? 'dx' : 'dy', p1: a, p2: b, ox: i === 3 ? -px(24) : px(24), oy: i === 0 ? -px(24) : px(24) };
  } else if (x.puntos.length === 2 && E.sel.size === 2) {
    k = { tipo: 'distancia', p1: x.puntos[0], p2: x.puntos[1], ...desde(Croquis.punto(m, x.puntos[0]), Croquis.punto(m, x.puntos[1])) };
  } else if (x.puntos.length === 1 && x.lineas.length === 1 && E.sel.size === 2) {
    k = { tipo: 'distpl', p1: x.puntos[0], e1: x.lineas[0].id, ox: 0, oy: 0 };
  } else if (x.lineas.length === 2 && E.sel.size === 2) {
    const [l1, l2] = x.lineas, d = l => { const a = Croquis.punto(m, l.a), b = Croquis.punto(m, l.b); return [b.x - a.x, b.y - a.y]; };
    const [a, b] = [d(l1), d(l2)], paralelas = Math.abs(a[0] * b[1] - a[1] * b[0]) / (Math.hypot(...a) * Math.hypot(...b)) < 1e-6;
    k = paralelas ? { tipo: 'distpl', p1: l2.a, e1: l1.id, ox: 0, oy: 0 } : { tipo: 'angulo', e1: l1.id, e2: l2.id, ox: 0, oy: 0 };
  }
  if (!k) return pintarSvg();
  historia();
  const cid = Croquis.agregarCota(m, k);
  if (!Croquis.resolver(m).ok) {   // ya estaba definido: una cota más lo sobredefine
    restaurar(E.deshacer, []);
    return avisar('Esa medida ya queda fija por otras cotas o restricciones (sobredefinido).', true);
  }
  E.sel = new Set(['c' + cid]);
  E.enfocarCota = true;
  recalcular();
}

function mapaMover(ev) {
  if (M.paneo) {
    const v = M.paneo.v, f = v.w / Math.max(1, $('#mapa-svg').clientWidth);
    Object.assign(M.vista, { x: v.x - (ev.clientX - M.paneo.x) * f, y: v.y - (ev.clientY - M.paneo.y) * f });
    return pintarSvg();
  }
  const E = M.edit;
  if (!E) return;
  const a = E.arrastre, p = puntoSvg(ev);
  if (E.caja) { E.caja.b = p; return pintarSvg(); }
  if (a) {
    const dx = p.x - a.desde.x, dy = p.y - a.desde.y;
    if (!a.movio && Math.hypot(dx, dy) < px(3)) return;
    a.movio = true;
    if (a.cota) { Object.assign(a.cota, { ox: a.cotaOrig.ox + dx, oy: a.cotaOrig.oy + dy }); return pintarSvg(); }
    for (const [id, o] of a.maquinas) E.puntos.set(id, { x: o.x + dx, y: o.y + dy });
    if (a.original.size) {
      // un solo punto arrastrado se pega a otros puntos (sin crear la restricción: eso es "Coincidente")
      let tx = dx, ty = dy;
      if (a.original.size === 1) {
        const [pid, o] = [...a.original][0], q = apuntar(ev, null, [pid]);
        tx = q.x - o.x; ty = q.y - o.y;
      }
      Croquis.resolver(E.croquis, [...a.original].map(([pid, o]) => ({ pid, x: o.x + tx, y: o.y + ty })));
    }
    return pintarSvg();
  }
  // previa de lo que se dibuja
  if (E.herramienta !== 'seleccionar' && E.herramienta !== 'cota') {
    const anterior = E.previa?.pts.at(-1);
    const q = ['linea', 'rect', 'rectc', 'circulo', 'arco', 'poligono', 'texto'].includes(E.herramienta)
      ? apuntar(ev, E.herramienta === 'linea' ? anterior : null) : { ...p };
    E.cursor = { x: q.x, y: q.y };
    pintarSvg();
  }
}

function mapaArriba() {
  if (M.paneo) { M.paneo = null; return; }
  const E = M.edit;
  if (!E) return;
  if (E.caja) {
    const { a, b, sumar } = E.caja, x1 = Math.min(a.x, b.x), x2 = Math.max(a.x, b.x), y1 = Math.min(a.y, b.y), y2 = Math.max(a.y, b.y);
    E.caja = null;
    if (x2 - x1 > px(4) || y2 - y1 > px(4)) {
      const dentro = pid => { const p = Croquis.punto(E.croquis, pid); return p.x >= x1 && p.x <= x2 && p.y >= y1 && p.y <= y2; };
      const nuevos = E.croquis.entidades.filter(e => Croquis.puntosDe(e).every(dentro)).map(e => 'e' + e.id);
      for (const [id, q] of E.puntos) if (q.x >= x1 && q.x <= x2 && q.y >= y1 && q.y <= y2) nuevos.push('q' + id);
      E.sel = new Set([...(sumar ? E.sel : []), ...nuevos]);
    }
    pintarSvg(); return pintarLado();
  }
  const a = E.arrastre;
  E.arrastre = null;
  if (a?.movio) {   // un arrastre es un paso de deshacer
    E.deshacer.push(a.foto); E.rehacer = [];
    E.imanActual = null;
    recalcular();
  }
}

function mapaDobleClic(ev) {
  const E = M.edit;
  if (!E) return;
  if (E.herramienta === 'linea' && E.previa) { E.previa = null; E.cursor = null; pintarSvg(); return pintarLado(); }   // termina la cadena
  const g = ev.target.closest('[data-c]');
  if (g) { E.sel = new Set(['c' + g.dataset.c]); E.enfocarCota = true; pintarLado(); }
}

async function guardarPlano(boton) {
  const E = M.edit;
  $('#mapa-error').textContent = '';
  boton.disabled = true;
  try {
    Croquis.limpiar(E.croquis);
    await api('/api/planos/' + E.plano.id, { metodo: 'PUT', datos: { nombre: E.plano.nombre, ancho: E.plano.ancho, alto: E.plano.alto,
      elementos: E.croquis, equipos: [...E.puntos].map(([equipo_id, p]) => ({ equipo_id, x: +(+p.x).toFixed(2), y: +(+p.y).toFixed(2) })) } });
    const id = E.plano.id;
    terminarEdicion();
    avisar('Plano guardado.');
    await VISTAS.mapa(id);
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
