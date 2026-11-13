'use strict';
// ── CROQUIS: el motor del dibujo del mapa de planta (sin pantalla) ──
// Como el modo croquis de SolidWorks u Onshape: puntos compartidos, entidades que los usan, RESTRICCIONES (horizontal,
// paralela, tangente...) y COTAS que mandan (cambiar una cota mueve el dibujo). Un resolvedor numérico (Levenberg-
// Marquardt) mueve los puntos para cumplir todo a la vez, y un análisis de grados de libertad dice qué está totalmente
// definido. También: imanes, recortar, extender, equidistancia, simetría, copiar/pegar.
// No toca el DOM: mapa.js lo usa para dibujar y editar, y tests/test_croquis.py lo prueba con Node.
//
// Modelo (lo que se guarda en planos.elementos; la versión vieja, una lista de rect/linea/texto, se convierte sola):
//   { v: 2, sig, puntos: [{id, x, y}],
//     entidades: [ {id, tipo:'linea', a, b} | {id, tipo:'rect', p:[a,b,c,d], etiqueta} | {id, tipo:'circulo', c, r, etiqueta}
//                  | {id, tipo:'arco', c, a, b} (de a hacia b, sentido horario en pantalla) | {id, tipo:'texto', p, texto, tamanio} ]
//                  (todas con color y, las de trazo, constr: línea de construcción, no se ve en el plano terminado)
//     restricciones: [{id, tipo, e1, e2, p1, x, y}],   cotas: [{id, tipo, e1, e2, p1, p2, valor, signo, ox, oy}] }
// Todo en metros. Los ids son números únicos dentro del croquis (sig es el próximo).
const Croquis = (() => {
  const TOL = 1e-7;
  const RESTRICCIONES = {
    horizontal: 'Horizontal', vertical: 'Vertical', paralela: 'Paralela', perpendicular: 'Perpendicular', igual: 'Igual',
    tangente: 'Tangente', puntoEnLinea: 'Punto sobre línea', enCirculo: 'Punto sobre círculo', medio: 'Punto medio', fija: 'Fija',
  };
  const COTAS = { largo: 'Largo', distancia: 'Distancia', dx: 'Distancia horizontal', dy: 'Distancia vertical',
    angulo: 'Ángulo', radio: 'Radio', distpl: 'Distancia a la línea' };

  // ── modelo ──
  const nuevo = () => ({ v: 2, sig: 1, puntos: [], entidades: [], restricciones: [], cotas: [] });
  const clonar = m => JSON.parse(JSON.stringify(m));
  const id = m => m.sig++;
  const punto = (m, pid) => m.puntos.find(p => p.id === pid);
  const entidad = (m, eid) => m.entidades.find(e => e.id === eid);
  function agregarPunto(m, x, y) { const p = { id: id(m), x: +x, y: +y }; m.puntos.push(p); return p.id; }
  function agregar(m, ent) { ent.id = id(m); m.entidades.push(ent); return ent.id; }

  /** Los puntos que usa una entidad (los de definición: el centro de un círculo, las esquinas de un rectángulo...). */
  function puntosDe(e) {
    if (e.tipo === 'linea') return [e.a, e.b];
    if (e.tipo === 'rect') return [...e.p];
    if (e.tipo === 'circulo') return [e.c];
    if (e.tipo === 'arco') return [e.c, e.a, e.b];
    return [e.p];
  }

  /** El formato viejo (lista de rect/linea/texto) al croquis. */
  function convertir(elementos) {
    if (elementos && !Array.isArray(elementos) && elementos.v === 2) return elementos;
    const m = nuevo();
    for (const el of elementos || []) {
      const color = el.color || 'gris';
      if (el.tipo === 'linea') agregar(m, { tipo: 'linea', a: agregarPunto(m, el.x1, el.y1), b: agregarPunto(m, el.x2, el.y2), color });
      else if (el.tipo === 'rect') agregar(m, { tipo: 'rect', color, etiqueta: el.etiqueta || '', p: [agregarPunto(m, el.x, el.y),
        agregarPunto(m, el.x + el.w, el.y), agregarPunto(m, el.x + el.w, el.y + el.h), agregarPunto(m, el.x, el.y + el.h)] });
      else if (el.tipo === 'texto') agregar(m, { tipo: 'texto', p: agregarPunto(m, el.x, el.y), texto: el.texto, tamanio: el.tamanio || 1, color });
    }
    return m;
  }

  // ── geometría ──
  const dist = (a, b) => Math.hypot(b.x - a.x, b.y - a.y);
  const ang = (c, p) => Math.atan2(p.y - c.y, p.x - c.x);
  const norm = a => ((a % (2 * Math.PI)) + 2 * Math.PI) % (2 * Math.PI);

  /** Circunferencia por tres puntos (null si están alineados). */
  function circuloPor3(p, q, s) {
    const d = 2 * (p.x * (q.y - s.y) + q.x * (s.y - p.y) + s.x * (p.y - q.y));
    if (Math.abs(d) < 1e-12) return null;
    const a2 = p.x ** 2 + p.y ** 2, b2 = q.x ** 2 + q.y ** 2, c2 = s.x ** 2 + s.y ** 2;
    const x = (a2 * (q.y - s.y) + b2 * (s.y - p.y) + c2 * (p.y - q.y)) / d;
    const y = (a2 * (s.x - q.x) + b2 * (p.x - s.x) + c2 * (q.x - p.x)) / d;
    return { x, y, r: Math.hypot(p.x - x, p.y - y) };
  }

  /** ¿El ángulo t está dentro del arco que va de a1 a a2 en sentido creciente? */
  const enArco = (t, a1, a2) => norm(t - a1) <= norm(a2 - a1) + 1e-12;

  /** Los tramos rectos de una entidad (una línea, o los cuatro lados de un rectángulo), como pares de puntos. */
  function tramos(m, e) {
    if (e.tipo === 'linea') return [[punto(m, e.a), punto(m, e.b)]];
    if (e.tipo === 'rect') return e.p.map((pid, i) => [punto(m, pid), punto(m, e.p[(i + 1) % 4])]);
    return [];
  }

  /** Intersecciones de la recta p+t·(q-p) con una entidad: lista de t (sobre la recta, sin límites) dentro de la entidad. */
  function cortesConRecta(m, p, q, e) {
    const dx = q.x - p.x, dy = q.y - p.y, salida = [];
    for (const [a, b] of tramos(m, e)) {
      const ex = b.x - a.x, ey = b.y - a.y, den = dx * ey - dy * ex;
      if (Math.abs(den) < 1e-12) continue;
      const t = ((a.x - p.x) * ey - (a.y - p.y) * ex) / den, u = ((a.x - p.x) * dy - (a.y - p.y) * dx) / den;
      if (u >= -1e-9 && u <= 1 + 1e-9) salida.push(t);
    }
    if (e.tipo === 'circulo' || e.tipo === 'arco') {
      const c = punto(m, e.c), r = e.tipo === 'circulo' ? e.r : dist(c, punto(m, e.a));
      const fx = p.x - c.x, fy = p.y - c.y, A = dx * dx + dy * dy, B = 2 * (fx * dx + fy * dy), C = fx * fx + fy * fy - r * r;
      const disc = B * B - 4 * A * C;
      if (disc >= 0 && A > 0) {
        for (const t of [(-B - Math.sqrt(disc)) / (2 * A), (-B + Math.sqrt(disc)) / (2 * A)]) {
          if (e.tipo === 'circulo') { salida.push(t); continue; }
          const pt = { x: p.x + t * dx, y: p.y + t * dy };
          if (enArco(ang(c, pt), ang(c, punto(m, e.a)), ang(c, punto(m, e.b)))) salida.push(t);
        }
      }
    }
    return salida;
  }

  // ── el resolvedor ──
  // Cada residuo es { vars: [claves], f: v => número }: tiene que dar 0. Las variables son px<id>/py<id> de cada punto y
  // r<id> del radio de cada círculo.
  const kx = pid => 'px' + pid, ky = pid => 'py' + pid;

  function residuos(m) {
    const R = [], E = new Map(m.entidades.map(e => [e.id, e]));
    const add = (vars, f, origen) => R.push({ vars, f, origen });
    const linea = eid => { const e = E.get(eid); return e && e.tipo === 'linea' ? e : null; };
    const radioVars = e => e.tipo === 'circulo' ? ['r' + e.id] : [kx(e.c), ky(e.c), kx(e.a), ky(e.a)];
    const radio = (e, v) => e.tipo === 'circulo' ? v('r' + e.id) : Math.hypot(v(kx(e.a)) - v(kx(e.c)), v(ky(e.a)) - v(ky(e.c)));
    const dir = (e, v) => [v(kx(e.b)) - v(kx(e.a)), v(ky(e.b)) - v(ky(e.a))];
    const lv = e => [kx(e.a), ky(e.a), kx(e.b), ky(e.b)];
    // implícitas: un rectángulo tiene los lados horizontales y verticales; un arco, sus dos puntas a la misma distancia del centro
    for (const e of m.entidades) {
      if (e.tipo === 'rect') {
        const [a, b, c, d] = e.p;
        add([ky(a), ky(b)], v => v(ky(a)) - v(ky(b)), null);
        add([kx(b), kx(c)], v => v(kx(b)) - v(kx(c)), null);
        add([ky(c), ky(d)], v => v(ky(c)) - v(ky(d)), null);
        add([kx(d), kx(a)], v => v(kx(d)) - v(kx(a)), null);
      } else if (e.tipo === 'arco') {
        add([kx(e.c), ky(e.c), kx(e.a), ky(e.a), kx(e.b), ky(e.b)], v => Math.hypot(v(kx(e.a)) - v(kx(e.c)), v(ky(e.a)) - v(ky(e.c)))
          - Math.hypot(v(kx(e.b)) - v(kx(e.c)), v(ky(e.b)) - v(ky(e.c))), null);
      }
    }
    for (const r of m.restricciones) {
      const o = { r: r.id };
      const l1 = linea(r.e1), l2 = linea(r.e2), e1 = E.get(r.e1), e2 = E.get(r.e2);
      switch (r.tipo) {
        case 'horizontal':
          if (l1) add([ky(l1.a), ky(l1.b)], v => v(ky(l1.a)) - v(ky(l1.b)), o);
          else if (r.p1 && r.p2) add([ky(r.p1), ky(r.p2)], v => v(ky(r.p1)) - v(ky(r.p2)), o);
          break;
        case 'vertical':
          if (l1) add([kx(l1.a), kx(l1.b)], v => v(kx(l1.a)) - v(kx(l1.b)), o);
          else if (r.p1 && r.p2) add([kx(r.p1), kx(r.p2)], v => v(kx(r.p1)) - v(kx(r.p2)), o);
          break;
        case 'paralela': case 'perpendicular':
          if (l1 && l2) add([...lv(l1), ...lv(l2)], v => {
            const [ax, ay] = dir(l1, v), [bx, by] = dir(l2, v), n = Math.hypot(ax, ay) * Math.hypot(bx, by) || 1;
            return (r.tipo === 'paralela' ? ax * by - ay * bx : ax * bx + ay * by) / n;
          }, o);
          break;
        case 'igual':
          if (l1 && l2) add([...lv(l1), ...lv(l2)], v => Math.hypot(...dir(l1, v)) - Math.hypot(...dir(l2, v)), o);
          else if (e1 && e2 && /circulo|arco/.test(e1.tipo) && /circulo|arco/.test(e2.tipo))
            add([...radioVars(e1), ...radioVars(e2)], v => radio(e1, v) - radio(e2, v), o);
          break;
        case 'tangente': {
          const l = l1 || l2, c = [e1, e2].find(e => e && /circulo|arco/.test(e.tipo));
          if (l && c) add([...lv(l), kx(c.c), ky(c.c), ...radioVars(c)], v => {
            const [dx, dy] = dir(l, v), n = Math.hypot(dx, dy) || 1;
            return Math.abs(((v(kx(c.c)) - v(kx(l.a))) * dy - (v(ky(c.c)) - v(ky(l.a))) * dx) / n) - radio(c, v);
          }, o);
          break;
        }
        case 'puntoEnLinea':
          if (l1 && r.p1) add([kx(r.p1), ky(r.p1), ...lv(l1)], v => {
            const [dx, dy] = dir(l1, v), n = Math.hypot(dx, dy) || 1;
            return ((v(kx(r.p1)) - v(kx(l1.a))) * dy - (v(ky(r.p1)) - v(ky(l1.a))) * dx) / n;
          }, o);
          break;
        case 'enCirculo':
          if (e1 && r.p1 && /circulo|arco/.test(e1.tipo)) add([kx(r.p1), ky(r.p1), kx(e1.c), ky(e1.c), ...radioVars(e1)],
            v => Math.hypot(v(kx(r.p1)) - v(kx(e1.c)), v(ky(r.p1)) - v(ky(e1.c))) - radio(e1, v), o);
          break;
        case 'medio':
          if (l1 && r.p1) {
            add([kx(r.p1), kx(l1.a), kx(l1.b)], v => v(kx(r.p1)) - (v(kx(l1.a)) + v(kx(l1.b))) / 2, o);
            add([ky(r.p1), ky(l1.a), ky(l1.b)], v => v(ky(r.p1)) - (v(ky(l1.a)) + v(ky(l1.b))) / 2, o);
          }
          break;
        case 'fija':
          if (r.p1) { add([kx(r.p1)], v => v(kx(r.p1)) - r.x, o); add([ky(r.p1)], v => v(ky(r.p1)) - r.y, o); }
          break;
      }
    }
    for (const k of m.cotas) {
      const o = { c: k.id }, l1 = linea(k.e1), l2 = linea(k.e2), e1 = E.get(k.e1), s = k.signo || 1;
      switch (k.tipo) {
        case 'largo': if (l1) add(lv(l1), v => Math.hypot(...dir(l1, v)) - k.valor, o); break;
        case 'distancia': add([kx(k.p1), ky(k.p1), kx(k.p2), ky(k.p2)],
          v => Math.hypot(v(kx(k.p2)) - v(kx(k.p1)), v(ky(k.p2)) - v(ky(k.p1))) - k.valor, o); break;
        case 'dx': add([kx(k.p1), kx(k.p2)], v => s * (v(kx(k.p2)) - v(kx(k.p1))) - k.valor, o); break;
        case 'dy': add([ky(k.p1), ky(k.p2)], v => s * (v(ky(k.p2)) - v(ky(k.p1))) - k.valor, o); break;
        case 'radio': if (e1 && /circulo|arco/.test(e1.tipo)) add(radioVars(e1), v => radio(e1, v) - k.valor, o); break;
        case 'angulo':
          if (l1 && l2) add([...lv(l1), ...lv(l2)], v => {
            const [ax, ay] = dir(l1, v), [bx, by] = dir(l2, v);
            return Math.sin(Math.atan2(ax * by - ay * bx, ax * bx + ay * by) - s * k.valor * Math.PI / 180);
          }, o);
          break;
        case 'distpl':
          if (l1) add([kx(k.p1), ky(k.p1), ...lv(l1)], v => {
            const [dx, dy] = dir(l1, v), n = Math.hypot(dx, dy) || 1;
            return s * ((v(kx(k.p1)) - v(kx(l1.a))) * dy - (v(ky(k.p1)) - v(ky(l1.a))) * dx) / n - k.valor;
          }, o);
          break;
      }
    }
    return R;
  }

  /** Lee y escribe las variables del modelo. */
  function valores(m) {
    const P = new Map(m.puntos.map(p => [p.id, p])), C = new Map(m.entidades.filter(e => e.tipo === 'circulo').map(e => [e.id, e]));
    const leer = k => k[0] === 'r' ? C.get(+k.slice(1)).r : P.get(+k.slice(2))[k[1] === 'x' ? 'x' : 'y'];
    const escribir = (k, val) => { if (k[0] === 'r') C.get(+k.slice(1)).r = Math.max(1e-6, val); else P.get(+k.slice(2))[k[1] === 'x' ? 'x' : 'y'] = val; };
    return { leer, escribir };
  }

  /** Resuelve (A·x = b) con eliminación de Gauss y pivoteo parcial. A es n×n (se modifica). */
  function resolverLineal(A, b) {
    const n = b.length;
    for (let c = 0; c < n; c++) {
      let piv = c;
      for (let f = c + 1; f < n; f++) if (Math.abs(A[f][c]) > Math.abs(A[piv][c])) piv = f;
      if (Math.abs(A[piv][c]) < 1e-14) continue;
      [A[c], A[piv]] = [A[piv], A[c]]; [b[c], b[piv]] = [b[piv], b[c]];
      for (let f = c + 1; f < n; f++) {
        const k = A[f][c] / A[c][c];
        if (!k) continue;
        for (let j = c; j < n; j++) A[f][j] -= k * A[c][j];
        b[f] -= k * b[c];
      }
    }
    const x = new Array(n).fill(0);
    for (let c = n - 1; c >= 0; c--) {
      if (Math.abs(A[c][c]) < 1e-14) continue;
      let s = b[c];
      for (let j = c + 1; j < n; j++) s -= A[c][j] * x[j];
      x[c] = s / A[c][c];
    }
    return x;
  }

  /** Levenberg-Marquardt sobre una lista de residuos (con peso). Mueve lo mínimo: un punto que ningún residuo toca no se mueve. */
  function minimizar(m, R, iteraciones = 60) {
    if (!R.length) return 0;
    const { leer, escribir } = valores(m);
    const claves = [...new Set(R.flatMap(r => r.vars))], ix = new Map(claves.map((k, i) => [k, i]));
    const n = claves.length, x = claves.map(leer);
    const v = k => x[ix.get(k)];
    const costo = () => R.reduce((s, r) => s + (r.w || 1) * r.f(v) ** 2, 0);
    let c0 = costo(), lambda = 1e-4;
    for (let it = 0; it < iteraciones && c0 > 1e-20; it++) {
      const JtJ = Array.from({ length: n }, () => new Float64Array(n)), Jtr = new Float64Array(n);
      for (const r of R) {
        const w = r.w || 1, f0 = r.f(v), cols = [...new Set(r.vars)].map(k => ix.get(k)), g = [];
        for (const j of cols) {
          const h = 1e-7 * Math.max(1, Math.abs(x[j])), viejo = x[j];
          x[j] = viejo + h; const fp = r.f(v); x[j] = viejo - h; const fm = r.f(v); x[j] = viejo;
          g.push((fp - fm) / (2 * h));
        }
        cols.forEach((a, ia) => { Jtr[a] += w * g[ia] * f0; cols.forEach((b, ib) => { JtJ[a][b] += w * g[ia] * g[ib]; }); });
      }
      let mejoro = false;
      for (let intento = 0; intento < 8; intento++) {
        const A = JtJ.map((fila, i) => { const f = Array.from(fila); f[i] += lambda * (1 + fila[i]); return f; });
        const d = resolverLineal(A, Array.from(Jtr, z => -z));
        const viejo = x.slice();
        for (let i = 0; i < n; i++) x[i] += d[i];
        const c1 = costo();
        if (c1 < c0) { c0 = c1; lambda = Math.max(lambda / 3, 1e-12); mejoro = true; break; }
        for (let i = 0; i < n; i++) x[i] = viejo[i];
        lambda *= 10;
      }
      if (!mejoro) break;
    }
    claves.forEach((k, i) => escribir(k, x[i]));
    return c0;
  }

  /** Cumple restricciones y cotas. arrastres: [{pid, x, y}] = adonde lleva el puntero cada punto (lo más cerca posible
   *  sin romper nada). Devuelve { ok, conflictos: [{r}|{c}] } (ok=false: algo no se puede cumplir a la vez). */
  function resolver(m, arrastres = []) {
    const R = residuos(m);
    if (arrastres.length) {   // primero acercarse al puntero (con peso chico), después cumplir todo lo duro
      const A = arrastres.flatMap(a => [{ vars: [kx(a.pid)], f: v => v(kx(a.pid)) - a.x, w: 0.02 },
        { vars: [ky(a.pid)], f: v => v(ky(a.pid)) - a.y, w: 0.02 }]);
      minimizar(m, [...R, ...A], 40);
    }
    minimizar(m, R, 80);
    const { leer } = valores(m);
    const ix = k => leer(k);
    const conflictos = R.filter(r => r.origen && Math.abs(r.f(ix)) > 1e-5).map(r => r.origen);
    const implicitos = R.filter(r => !r.origen && Math.abs(r.f(ix)) > 1e-5);
    return { ok: !conflictos.length && !implicitos.length, conflictos };
  }

  /** Grados de libertad: qué puntos (y radios) quedan totalmente definidos por restricciones y cotas.
   *  Devuelve { libres: n, definidos: Set de claves (px<id>, py<id>, r<id>) }. */
  function libertad(m) {
    const R = residuos(m), { leer } = valores(m);
    const claves = [...m.puntos.flatMap(p => [kx(p.id), ky(p.id)]), ...m.entidades.filter(e => e.tipo === 'circulo').map(e => 'r' + e.id)];
    if (claves.length > 800) return { libres: null, definidos: new Set() };
    const ix = new Map(claves.map((k, i) => [k, i])), x = claves.map(leer), n = claves.length;
    const v = k => x[ix.get(k)];
    const J = R.map(r => {
      const fila = new Float64Array(n);
      for (const k of new Set(r.vars)) {
        const j = ix.get(k);
        if (j === undefined) continue;
        const h = 1e-6 * Math.max(1, Math.abs(x[j])), viejo = x[j];
        x[j] = viejo + h; const fp = r.f(v); x[j] = viejo - h; const fm = r.f(v); x[j] = viejo;
        fila[j] = (fp - fm) / (2 * h);
      }
      return fila;
    });
    // forma escalonada reducida: columnas pivote y libres
    const pivotes = [];
    let fila = 0;
    for (let c = 0; c < n && fila < J.length; c++) {
      let piv = fila;
      for (let f = fila + 1; f < J.length; f++) if (Math.abs(J[f][c]) > Math.abs(J[piv][c])) piv = f;
      if (Math.abs(J[piv][c]) < 1e-7) continue;
      [J[fila], J[piv]] = [J[piv], J[fila]];
      const p = J[fila][c];
      for (let j = 0; j < n; j++) J[fila][j] /= p;
      for (let f = 0; f < J.length; f++) {
        if (f === fila || !J[f][c]) continue;
        const k = J[f][c];
        for (let j = 0; j < n; j++) J[f][j] -= k * J[fila][j];
      }
      pivotes.push(c); fila++;
    }
    const esPivote = new Set(pivotes), libres = [...Array(n).keys()].filter(c => !esPivote.has(c));
    const moviles = new Set(libres);   // una variable se mueve si alguna dirección libre la toca
    for (const f of libres) pivotes.forEach((c, i) => { if (Math.abs(J[i][f]) > 1e-7) moviles.add(c); });
    return { libres: libres.length, definidos: new Set(claves.filter((k, i) => !moviles.has(i))) };
  }

  // ── edición ──
  /** Une dos puntos (coincidente): todo lo que usaba `quitar` pasa a usar `queda`. */
  function fusionar(m, queda, quitar) {
    if (queda === quitar) return;
    const cambiar = pid => pid === quitar ? queda : pid;
    for (const e of m.entidades) {
      if (e.tipo === 'linea') { e.a = cambiar(e.a); e.b = cambiar(e.b); }
      else if (e.tipo === 'rect') e.p = e.p.map(cambiar);
      else if (e.tipo === 'circulo') e.c = cambiar(e.c);
      else if (e.tipo === 'arco') { e.c = cambiar(e.c); e.a = cambiar(e.a); e.b = cambiar(e.b); }
      else e.p = cambiar(e.p);
    }
    for (const x of [...m.restricciones, ...m.cotas]) { if (x.p1) x.p1 = cambiar(x.p1); if (x.p2) x.p2 = cambiar(x.p2); }
    m.puntos = m.puntos.filter(p => p.id !== quitar);
    m.entidades = m.entidades.filter(e => !(e.tipo === 'linea' && e.a === e.b));
    limpiar(m);
  }

  /** Saca restricciones y cotas que apuntan a algo que ya no está, y los puntos que nadie usa. */
  function limpiar(m) {
    const E = new Set(m.entidades.map(e => e.id));
    const usados = new Set(m.entidades.flatMap(puntosDe));
    const vale = x => (!x.e1 || E.has(x.e1)) && (!x.e2 || E.has(x.e2)) && (!x.p1 || usados.has(x.p1)) && (!x.p2 || usados.has(x.p2));
    m.restricciones = m.restricciones.filter(vale);
    m.cotas = m.cotas.filter(x => vale(x) && !(x.p1 && x.p1 === x.p2));
    m.puntos = m.puntos.filter(p => usados.has(p.id));
  }

  /** Borra entidades, cotas y restricciones (por id). */
  function borrar(m, { entidades = [], cotas = [], restricciones = [] }) {
    m.entidades = m.entidades.filter(e => !entidades.includes(e.id));
    m.cotas = m.cotas.filter(c => !cotas.includes(c.id));
    m.restricciones = m.restricciones.filter(r => !restricciones.includes(r.id));
    limpiar(m);
  }

  /** ¿Cuántas entidades usan este punto? (para no mover un punto compartido al recortar o extender) */
  const usos = (m, pid) => m.entidades.filter(e => puntosDe(e).includes(pid)).length;

  /** Los cortes de una línea con todas las demás entidades, como t entre 0 y 1 (ordenados, sin repetir). */
  function cortesDeLinea(m, e) {
    const a = punto(m, e.a), b = punto(m, e.b), ts = [];
    for (const o of m.entidades) if (o.id !== e.id && o.tipo !== 'texto') ts.push(...cortesConRecta(m, a, b, o));
    return [...new Set(ts.filter(t => t > 1e-6 && t < 1 - 1e-6).map(t => +t.toFixed(9)))].sort((x, y) => x - y);
  }

  /** Recortar: saca el tramo de la línea entre los dos cortes que rodean el clic (o hasta la punta). */
  function recortar(m, eid, x, y) {
    const e = entidad(m, eid);
    if (!e || e.tipo !== 'linea') return false;
    const a = punto(m, e.a), b = punto(m, e.b), dx = b.x - a.x, dy = b.y - a.y, L2 = dx * dx + dy * dy;
    if (!L2) return false;
    const t = ((x - a.x) * dx + (y - a.y) * dy) / L2, cortes = cortesDeLinea(m, e);
    const desde = [0, ...cortes].filter(c => c <= t).pop(), hasta = [...cortes, 1].find(c => c >= t);
    const en = s => ({ x: a.x + s * dx, y: a.y + s * dy });
    const copiar = (pa, pb) => {   // la parte que queda conserva color, construcción, horizontal/vertical/paralela
      const nid = agregar(m, { tipo: 'linea', a: pa, b: pb, color: e.color, constr: e.constr });
      for (const r of m.restricciones.filter(r => r.e1 === eid && ['horizontal', 'vertical'].includes(r.tipo)))
        m.restricciones.push({ ...r, id: id(m), e1: nid });
      return nid;
    };
    if (desde === 0 && hasta === 1) { borrar(m, { entidades: [eid] }); return true; }
    if (desde > 0) { const q = en(desde); copiar(e.a, agregarPunto(m, q.x, q.y)); }
    if (hasta < 1) { const q = en(hasta); copiar(agregarPunto(m, q.x, q.y), e.b); }
    borrar(m, { entidades: [eid] });
    return true;
  }

  /** Extender: lleva la punta más cercana al clic hasta el primer corte con otra entidad. */
  function extender(m, eid, x, y) {
    const e = entidad(m, eid);
    if (!e || e.tipo !== 'linea') return false;
    const a = punto(m, e.a), b = punto(m, e.b);
    const desdeB = Math.hypot(x - b.x, y - b.y) <= Math.hypot(x - a.x, y - a.y);
    const [p, q] = desdeB ? [a, b] : [b, a];   // se estira del lado de q, más allá de t=1
    let mejor = Infinity;
    for (const o of m.entidades) if (o.id !== eid && o.tipo !== 'texto')
      for (const t of cortesConRecta(m, p, q, o)) if (t > 1 + 1e-6 && t < mejor) mejor = t;
    if (!isFinite(mejor)) return false;
    const nx = p.x + mejor * (q.x - p.x), ny = p.y + mejor * (q.y - p.y);
    const clave = desdeB ? 'b' : 'a';
    if (usos(m, e[clave]) > 1) e[clave] = agregarPunto(m, nx, ny); else Object.assign(punto(m, e[clave]), { x: nx, y: ny });
    return true;
  }

  /** Equidistancia: copia líneas (en cadena, con las esquinas unidas), círculos y arcos a distancia d. ambos: a los dos lados
   *  (una pared con espesor). Devuelve los ids nuevos. */
  function equidistancia(m, ids, d, ambos = false) {
    const nuevos = [];
    const lineas = ids.map(i => entidad(m, i)).filter(e => e && e.tipo === 'linea');
    const curvas = ids.map(i => entidad(m, i)).filter(e => e && /circulo|arco/.test(e.tipo));
    for (const lado of ambos ? [d, -d] : [d]) {
      for (const cadena of cadenas(m, lineas)) nuevos.push(...offsetCadena(m, cadena, lado));
      for (const c of curvas) {
        if (c.tipo === 'circulo') { if (c.r + lado > 1e-6) nuevos.push(agregar(m, { tipo: 'circulo', c: c.c, r: c.r + lado, color: c.color, constr: c.constr })); continue; }
        const cc = punto(m, c.c), r = dist(cc, punto(m, c.a)) + lado;
        if (r <= 1e-6) continue;
        const pa = ang(cc, punto(m, c.a)), pb = ang(cc, punto(m, c.b));
        nuevos.push(agregar(m, { tipo: 'arco', c: c.c, a: agregarPunto(m, cc.x + r * Math.cos(pa), cc.y + r * Math.sin(pa)),
          b: agregarPunto(m, cc.x + r * Math.cos(pb), cc.y + r * Math.sin(pb)), color: c.color, constr: c.constr }));
      }
    }
    return nuevos;
  }

  /** Agrupa líneas unidas por sus puntas en cadenas ordenadas: [{lineas: [e...], pts: [p0, p1, ... pn]}]. */
  function cadenas(m, lineas) {
    const quedan = new Set(lineas), salida = [];
    while (quedan.size) {
      const primera = quedan.values().next().value; quedan.delete(primera);
      let ls = [primera], pts = [primera.a, primera.b];
      for (const hacia of ['fin', 'inicio']) {
        for (;;) {
          const extremo = hacia === 'fin' ? pts[pts.length - 1] : pts[0];
          const sig = [...quedan].find(l => l.a === extremo || l.b === extremo);
          if (!sig) break;
          quedan.delete(sig);
          const otro = sig.a === extremo ? sig.b : sig.a;
          if (hacia === 'fin') { ls.push(sig); pts.push(otro); } else { ls.unshift(sig); pts.unshift(otro); }
        }
      }
      salida.push({ lineas: ls, pts });
    }
    return salida;
  }

  function offsetCadena(m, { lineas, pts }, d) {
    const P = pts.map(pid => punto(m, pid)), cerrada = pts[0] === pts[pts.length - 1] && pts.length > 2;
    const seg = P.slice(0, -1).map((p, i) => {   // cada tramo corrido d a su izquierda
      const q = P[i + 1], L = dist(p, q) || 1, nx = -(q.y - p.y) / L * d, ny = (q.x - p.x) / L * d;
      return [{ x: p.x + nx, y: p.y + ny }, { x: q.x + nx, y: q.y + ny }];
    });
    const corte = (s1, s2) => {
      const dx1 = s1[1].x - s1[0].x, dy1 = s1[1].y - s1[0].y, dx2 = s2[1].x - s2[0].x, dy2 = s2[1].y - s2[0].y;
      const den = dx1 * dy2 - dy1 * dx2;
      if (Math.abs(den) < 1e-12) return s1[1];
      const t = ((s2[0].x - s1[0].x) * dy2 - (s2[0].y - s1[0].y) * dx2) / den;
      return { x: s1[0].x + t * dx1, y: s1[0].y + t * dy1 };
    };
    const vert = [];
    for (let i = 0; i <= seg.length; i++) {
      if (i === 0) vert.push(cerrada ? corte(seg[seg.length - 1], seg[0]) : seg[0][0]);
      else if (i === seg.length) vert.push(cerrada ? vert[0] : seg[i - 1][1]);
      else vert.push(corte(seg[i - 1], seg[i]));
    }
    const ids = vert.map((p, i) => (cerrada && i === vert.length - 1 ? null : agregarPunto(m, p.x, p.y)));
    if (cerrada) ids[ids.length - 1] = ids[0];
    return lineas.map((l, i) => {
      const nid = agregar(m, { tipo: 'linea', a: ids[i], b: ids[i + 1], color: l.color, constr: l.constr });
      m.restricciones.push({ id: id(m), tipo: 'paralela', e1: nid, e2: l.id });
      return nid;
    });
  }

  /** Simetría: copia las entidades reflejadas respecto de la línea eje. Devuelve los ids nuevos. */
  function simetria(m, ids, eje) {
    const e = entidad(m, eje);
    if (!e || e.tipo !== 'linea') return [];
    const a = punto(m, e.a), b = punto(m, e.b), dx = b.x - a.x, dy = b.y - a.y, L2 = dx * dx + dy * dy;
    if (!L2) return [];
    const mapa = new Map();
    const reflejo = pid => {
      if (!mapa.has(pid)) {
        const p = punto(m, pid), t = ((p.x - a.x) * dx + (p.y - a.y) * dy) / L2, fx = a.x + t * dx, fy = a.y + t * dy;
        mapa.set(pid, Math.abs(p.x - fx) + Math.abs(p.y - fy) < 1e-9 ? pid : agregarPunto(m, 2 * fx - p.x, 2 * fy - p.y));
      }
      return mapa.get(pid);
    };
    return ids.filter(i => i !== eje).map(i => entidad(m, i)).filter(Boolean).map(o => {
      const copia = { ...clonar(o), id: undefined };
      if (o.tipo === 'linea') Object.assign(copia, { a: reflejo(o.a), b: reflejo(o.b) });
      else if (o.tipo === 'rect') { const ps = o.p.map(reflejo); copia.p = [ps[1], ps[0], ps[3], ps[2]]; ordenarRect(m, copia); }
      else if (o.tipo === 'circulo') copia.c = reflejo(o.c);
      else if (o.tipo === 'arco') Object.assign(copia, { c: reflejo(o.c), a: reflejo(o.b), b: reflejo(o.a) });   // el espejo invierte el sentido
      else copia.p = reflejo(o.p);
      return agregar(m, copia);
    });
  }

  /** Deja las esquinas de un rectángulo en orden: arriba-izq, arriba-der, abajo-der, abajo-izq (como espera el resolvedor). */
  function ordenarRect(m, r) {
    const ps = r.p.map(pid => punto(m, pid));
    const cx = ps.reduce((s, p) => s + p.x, 0) / 4, cy = ps.reduce((s, p) => s + p.y, 0) / 4;
    const de = (izq, arr) => r.p[ps.findIndex(p => (p.x < cx) === izq && (p.y < cy) === arr)];
    const orden = [de(true, true), de(false, true), de(false, false), de(true, false)];
    if (orden.every(Boolean)) r.p = orden;
  }

  /** Copia entidades (con sus puntos y las restricciones y cotas que quedan adentro) para pegarlas. */
  function copiar(m, ids) {
    const ents = ids.map(i => entidad(m, i)).filter(Boolean), pts = new Set(ents.flatMap(puntosDe)), E = new Set(ids);
    const adentro = x => (!x.e1 || E.has(x.e1)) && (!x.e2 || E.has(x.e2)) && (!x.p1 || pts.has(x.p1)) && (!x.p2 || pts.has(x.p2));
    return clonar({ puntos: m.puntos.filter(p => pts.has(p.id)), entidades: ents,
      restricciones: m.restricciones.filter(r => adentro(r) && r.tipo !== 'fija'), cotas: m.cotas.filter(adentro) });
  }

  function pegar(m, recorte, dx, dy) {
    const nuevo = new Map(), n = old => nuevo.get(old) ?? old;
    for (const p of recorte.puntos) nuevo.set(p.id, agregarPunto(m, p.x + dx, p.y + dy));
    const ents = new Map();
    for (const e of recorte.entidades) {
      const c = clonar(e);
      if (c.tipo === 'linea') { c.a = n(c.a); c.b = n(c.b); } else if (c.tipo === 'rect') c.p = c.p.map(n);
      else if (c.tipo === 'circulo') c.c = n(c.c); else if (c.tipo === 'arco') { c.c = n(c.c); c.a = n(c.a); c.b = n(c.b); } else c.p = n(c.p);
      ents.set(e.id, agregar(m, c));
    }
    const remap = x => ({ ...x, id: id(m), e1: x.e1 && ents.get(x.e1), e2: x.e2 && ents.get(x.e2), p1: x.p1 && n(x.p1), p2: x.p2 && n(x.p2) });
    m.restricciones.push(...recorte.restricciones.map(remap));
    m.cotas.push(...recorte.cotas.map(remap));
    return [...ents.values()];
  }

  // ── imanes ──
  /** Lo más cercano para pegar el puntero: un punto, el medio de una línea, un punto sobre una línea o un círculo.
   *  tol en metros. excluir: ids de puntos que se están moviendo. Devuelve {tipo, x, y, pid?, eid?} o null. */
  function iman(m, x, y, tol, excluir = []) {
    let mejor = null;
    const probar = (d, cand) => { if (d <= tol && (!mejor || d < mejor.d - 1e-9)) mejor = { ...cand, d }; };
    for (const p of m.puntos) if (!excluir.includes(p.id)) probar(Math.hypot(p.x - x, p.y - y), { tipo: 'punto', x: p.x, y: p.y, pid: p.id });
    if (mejor) return mejor;
    for (const e of m.entidades) {
      if (e.tipo !== 'linea' || excluir.includes(e.a) || excluir.includes(e.b)) continue;
      const a = punto(m, e.a), b = punto(m, e.b), mx = (a.x + b.x) / 2, my = (a.y + b.y) / 2;
      probar(Math.hypot(mx - x, my - y), { tipo: 'medio', x: mx, y: my, eid: e.id });
    }
    if (mejor) return mejor;
    for (const e of m.entidades) {
      if (e.tipo === 'linea' && !excluir.includes(e.a) && !excluir.includes(e.b)) {
        const a = punto(m, e.a), b = punto(m, e.b), dx = b.x - a.x, dy = b.y - a.y, L2 = dx * dx + dy * dy;
        if (!L2) continue;
        const t = Math.max(0, Math.min(1, ((x - a.x) * dx + (y - a.y) * dy) / L2)), px = a.x + t * dx, py = a.y + t * dy;
        probar(Math.hypot(px - x, py - y), { tipo: 'sobre', x: px, y: py, eid: e.id });
      } else if (e.tipo === 'circulo' || e.tipo === 'arco') {
        const c = punto(m, e.c), r = e.tipo === 'circulo' ? e.r : dist(c, punto(m, e.a)), d = Math.hypot(x - c.x, y - c.y) || 1;
        probar(Math.abs(d - r), { tipo: 'enCirculo', x: c.x + (x - c.x) / d * r, y: c.y + (y - c.y) / d * r, eid: e.id });
      }
    }
    return mejor;
  }

  /** Alineado horizontal/vertical con un punto existente (las líneas guía punteadas). */
  function guias(m, x, y, tol, excluir = []) {
    let gx = null, gy = null;
    for (const p of m.puntos) {
      if (excluir.includes(p.id)) continue;
      if (Math.abs(p.x - x) <= tol && (!gx || Math.abs(p.x - x) < Math.abs(gx.x - x))) gx = p;
      if (Math.abs(p.y - y) <= tol && (!gy || Math.abs(p.y - y) < Math.abs(gy.y - y))) gy = p;
    }
    return { x: gx, y: gy };
  }

  /** Medidas actuales de una cota (para mostrarla y para crearla con el valor que ya tiene). */
  function medir(m, k) {
    const P = pid => punto(m, pid), E = eid => entidad(m, eid);
    const largo = e => dist(P(e.a), P(e.b));
    switch (k.tipo) {
      case 'largo': return largo(E(k.e1));
      case 'distancia': return dist(P(k.p1), P(k.p2));
      case 'dx': return (k.signo || 1) * (P(k.p2).x - P(k.p1).x);
      case 'dy': return (k.signo || 1) * (P(k.p2).y - P(k.p1).y);
      case 'radio': { const e = E(k.e1); return e.tipo === 'circulo' ? e.r : dist(P(e.c), P(e.a)); }
      case 'angulo': {
        const l1 = E(k.e1), l2 = E(k.e2), a = [P(l1.b).x - P(l1.a).x, P(l1.b).y - P(l1.a).y], b = [P(l2.b).x - P(l2.a).x, P(l2.b).y - P(l2.a).y];
        return (k.signo || 1) * Math.atan2(a[0] * b[1] - a[1] * b[0], a[0] * b[0] + a[1] * b[1]) * 180 / Math.PI;
      }
      case 'distpl': {
        const l = E(k.e1), a = P(l.a), b = P(l.b), p = P(k.p1), dx = b.x - a.x, dy = b.y - a.y;
        return (k.signo || 1) * ((p.x - a.x) * dy - (p.y - a.y) * dx) / (Math.hypot(dx, dy) || 1);
      }
    }
    return 0;
  }

  /** Agrega una cota con la medida actual (positiva) y la deja lista: el valor se cambia después. */
  function agregarCota(m, k) {
    const c = { ...k, id: id(m), signo: 1, ox: k.ox || 0, oy: k.oy || 0 };
    const v = medir(m, c);
    if (v < 0) c.signo = -1;
    c.valor = +Math.abs(v).toFixed(3);
    m.cotas.push(c);
    return c.id;
  }

  /** Agrega una restricción y resuelve. Si choca con lo que ya hay (no se puede cumplir), la saca y devuelve false. */
  function restringir(m, r) {
    const copia = clonar(m);
    const rr = { ...r, id: id(m) };
    if (rr.tipo === 'fija') { const p = punto(m, rr.p1); rr.x = p.x; rr.y = p.y; }
    m.restricciones.push(rr);
    const res = resolver(m);
    if (!res.ok) { Object.assign(m, copia); return false; }
    return true;
  }

  /** Cambia el valor de una cota y resuelve; si no se puede, deja todo como estaba y devuelve false. */
  function cambiarCota(m, cid, valor) {
    const copia = clonar(m), k = m.cotas.find(c => c.id === cid);
    if (!k || !(valor > 0 || (k.tipo === 'angulo' && valor >= 0))) return false;
    k.valor = valor;
    if (!resolver(m).ok) { Object.assign(m, copia); return false; }
    return true;
  }

  return { RESTRICCIONES, COTAS, nuevo, clonar, convertir, punto, entidad, puntosDe, agregarPunto, agregar, resolver, libertad,
    fusionar, borrar, limpiar, recortar, extender, equidistancia, simetria, copiar, pegar, iman, guias, medir, agregarCota,
    restringir, cambiarCota, circuloPor3, ordenarRect, cortesDeLinea, enArco, ang, dist };
})();
if (typeof module !== 'undefined') module.exports = Croquis;   // para los tests con Node
