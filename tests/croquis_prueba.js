// Pruebas del motor del croquis (modulos/mantenimiento/frontend/croquis.js), sin navegador. Las corre tests/test_croquis.py.
const assert = require('assert');
const C = require('../modulos/mantenimiento/frontend/croquis.js');
const cerca = (a, b, tol = 1e-4) => Math.abs(a - b) < tol;
const P = (m, id) => C.punto(m, id);
const casos = {};

casos['convierte el formato viejo'] = () => {
  const m = C.convertir([{ tipo: 'rect', x: 1, y: 2, w: 10, h: 5, etiqueta: 'Moldeo', color: 'azul' },
    { tipo: 'linea', x1: 0, y1: 0, x2: 3, y2: 4 }, { tipo: 'texto', x: 1, y: 1, texto: 'Hola', tamanio: 2 }]);
  assert.strictEqual(m.v, 2);
  assert.deepStrictEqual(m.entidades.map(e => e.tipo), ['rect', 'linea', 'texto']);
  const r = m.entidades[0];
  assert.deepStrictEqual(r.p.map(p => [P(m, p).x, P(m, p).y]), [[1, 2], [11, 2], [11, 7], [1, 7]]);
  assert.strictEqual(C.convertir(m), m);   // ya convertido: igual
};

casos['horizontal y cota de largo mandan'] = () => {
  const m = C.nuevo();
  const l = C.agregar(m, { tipo: 'linea', a: C.agregarPunto(m, 0, 0), b: C.agregarPunto(m, 4, 1) });
  assert.ok(C.restringir(m, { tipo: 'fija', p1: m.entidades[0].a }));
  assert.ok(C.restringir(m, { tipo: 'horizontal', e1: l }));
  const e = C.entidad(m, l);
  assert.ok(cerca(P(m, e.a).y, P(m, e.b).y) && cerca(P(m, e.a).x, 0) && cerca(P(m, e.a).y, 0));
  const k = C.agregarCota(m, { tipo: 'largo', e1: l });
  assert.ok(C.cambiarCota(m, k, 10));
  assert.ok(cerca(C.dist(P(m, e.a), P(m, e.b)), 10) && cerca(P(m, e.a).x, 0));
  assert.ok(!C.cambiarCota(m, k, -3));   // un largo negativo no
};

casos['vertical que choca con horizontal se rechaza y deja todo como estaba'] = () => {
  const m = C.nuevo();
  const l = C.agregar(m, { tipo: 'linea', a: C.agregarPunto(m, 0, 0), b: C.agregarPunto(m, 5, 0) });
  assert.ok(C.restringir(m, { tipo: 'horizontal', e1: l }));
  C.agregarCota(m, { tipo: 'largo', e1: l });
  const antes = JSON.stringify(m.restricciones);
  assert.ok(!C.restringir(m, { tipo: 'vertical', e1: l }));
  assert.strictEqual(JSON.stringify(m.restricciones), antes);
};

casos['rectángulo: sigue recto al arrastrar una esquina, y paralela/perpendicular/igual/tangente'] = () => {
  const m = C.convertir([{ tipo: 'rect', x: 0, y: 0, w: 4, h: 2 }]);
  const r = m.entidades[0];
  C.resolver(m, [{ pid: r.p[2], x: 7, y: 5 }]);
  const [a, b, c, d] = r.p.map(p => P(m, p));
  assert.ok(cerca(a.y, b.y) && cerca(b.x, c.x) && cerca(c.y, d.y) && cerca(d.x, a.x));
  assert.ok(cerca(c.x, 7, 1e-2) && cerca(c.y, 5, 1e-2));
  const m2 = C.nuevo();
  const l1 = C.agregar(m2, { tipo: 'linea', a: C.agregarPunto(m2, 0, 0), b: C.agregarPunto(m2, 4, 0.3) });
  const l2 = C.agregar(m2, { tipo: 'linea', a: C.agregarPunto(m2, 0, 2), b: C.agregarPunto(m2, 3, 3) });
  assert.ok(C.restringir(m2, { tipo: 'paralela', e1: l1, e2: l2 }));
  assert.ok(C.restringir(m2, { tipo: 'igual', e1: l1, e2: l2 }));
  const e1 = C.entidad(m2, l1), e2 = C.entidad(m2, l2);
  const d1 = [P(m2, e1.b).x - P(m2, e1.a).x, P(m2, e1.b).y - P(m2, e1.a).y], d2 = [P(m2, e2.b).x - P(m2, e2.a).x, P(m2, e2.b).y - P(m2, e2.a).y];
  assert.ok(cerca(d1[0] * d2[1] - d1[1] * d2[0], 0) && cerca(Math.hypot(...d1), Math.hypot(...d2)));
  const ci = C.agregar(m2, { tipo: 'circulo', c: C.agregarPunto(m2, 2, 5), r: 1 });
  assert.ok(C.restringir(m2, { tipo: 'tangente', e1: l2, e2: ci }));
  const cc = P(m2, C.entidad(m2, ci).c), a2 = P(m2, e2.a), b2 = P(m2, e2.b);
  const dl = Math.abs((cc.x - a2.x) * (b2.y - a2.y) - (cc.y - a2.y) * (b2.x - a2.x)) / C.dist(a2, b2);
  assert.ok(cerca(dl, C.entidad(m2, ci).r));
};

casos['grados de libertad: totalmente definido con fija + horizontal + largo'] = () => {
  const m = C.nuevo();
  const a = C.agregarPunto(m, 0, 0), b = C.agregarPunto(m, 4, 0);
  const l = C.agregar(m, { tipo: 'linea', a, b });
  let g = C.libertad(m);
  assert.strictEqual(g.libres, 4);
  C.restringir(m, { tipo: 'fija', p1: a });
  C.restringir(m, { tipo: 'horizontal', e1: l });
  g = C.libertad(m);
  assert.strictEqual(g.libres, 1);
  assert.ok(g.definidos.has('px' + a) && g.definidos.has('py' + b) && !g.definidos.has('px' + b));
  C.agregarCota(m, { tipo: 'largo', e1: l });
  g = C.libertad(m);
  assert.strictEqual(g.libres, 0);
  assert.ok(g.definidos.has('px' + b));
};

casos['recortar y extender'] = () => {
  const m = C.nuevo();
  const h = C.agregar(m, { tipo: 'linea', a: C.agregarPunto(m, 0, 0), b: C.agregarPunto(m, 10, 0) });
  C.agregar(m, { tipo: 'linea', a: C.agregarPunto(m, 4, -2), b: C.agregarPunto(m, 4, 2) });
  C.agregar(m, { tipo: 'linea', a: C.agregarPunto(m, 6, -2), b: C.agregarPunto(m, 6, 2) });
  assert.ok(C.recortar(m, h, 5, 0.1));   // saca el tramo del medio: quedan dos horizontales
  const hs = m.entidades.filter(e => e.tipo === 'linea' && cerca(P(m, e.a).y, P(m, e.b).y) && cerca(P(m, e.a).y, 0));
  const tramos = hs.map(e => [P(m, e.a).x, P(m, e.b).x].sort((x, y) => x - y)).sort((x, y) => x[0] - y[0]);
  assert.deepStrictEqual(tramos.map(t => t.map(v => +v.toFixed(6))), [[0, 4], [6, 10]]);
  const m2 = C.nuevo();
  const corta = C.agregar(m2, { tipo: 'linea', a: C.agregarPunto(m2, 0, 0), b: C.agregarPunto(m2, 3, 0) });
  C.agregar(m2, { tipo: 'circulo', c: C.agregarPunto(m2, 10, 0), r: 2 });
  assert.ok(C.extender(m2, corta, 3, 0));
  assert.ok(cerca(P(m2, C.entidad(m2, corta).b).x, 8));
};

casos['equidistancia une las esquinas (pared con espesor) y simetría invierte el arco'] = () => {
  const m = C.nuevo();
  const p0 = C.agregarPunto(m, 0, 0), p1 = C.agregarPunto(m, 10, 0), p2 = C.agregarPunto(m, 10, 10);
  const l1 = C.agregar(m, { tipo: 'linea', a: p0, b: p1 }), l2 = C.agregar(m, { tipo: 'linea', a: p1, b: p2 });
  const nuevos = C.equidistancia(m, [l1, l2], 0.5);
  assert.strictEqual(nuevos.length, 2);
  const [n1, n2] = nuevos.map(i => C.entidad(m, i));
  assert.strictEqual(n1.b, n2.a);   // la esquina queda compartida
  const esq = P(m, n1.b);
  assert.ok(cerca(esq.x, 9.5) && cerca(esq.y, 0.5));
  const ej = C.agregar(m, { tipo: 'linea', a: C.agregarPunto(m, 20, -5), b: C.agregarPunto(m, 20, 5) });
  const arco = C.agregar(m, { tipo: 'arco', c: C.agregarPunto(m, 15, 0), a: C.agregarPunto(m, 16, 0), b: C.agregarPunto(m, 15, 1) });
  const [copia] = C.simetria(m, [arco, ej], ej);
  const k = C.entidad(m, copia);
  assert.ok(cerca(P(m, k.c).x, 25) && cerca(P(m, k.a).x, 25) && cerca(P(m, k.a).y, 1) && cerca(P(m, k.b).x, 24));
};

casos['fusionar puntos (coincidente), borrar limpia, copiar y pegar'] = () => {
  const m = C.nuevo();
  const l1 = C.agregar(m, { tipo: 'linea', a: C.agregarPunto(m, 0, 0), b: C.agregarPunto(m, 5, 0) });
  const l2 = C.agregar(m, { tipo: 'linea', a: C.agregarPunto(m, 5.1, 0.1), b: C.agregarPunto(m, 5, 5) });
  C.fusionar(m, C.entidad(m, l1).b, C.entidad(m, l2).a);
  assert.strictEqual(C.entidad(m, l1).b, C.entidad(m, l2).a);
  assert.strictEqual(m.puntos.length, 3);
  C.agregarCota(m, { tipo: 'largo', e1: l2 });
  const pegadas = C.pegar(m, C.copiar(m, [l1, l2]), 10, 0);
  assert.strictEqual(pegadas.length, 2);
  assert.strictEqual(m.cotas.length, 2);   // la cota de l2 viajó con la copia
  C.borrar(m, { entidades: [l2] });
  assert.strictEqual(m.cotas.length, 1);   // la cota del borrado se fue
  assert.strictEqual(m.puntos.length, 2 + 3);
};

casos['imán: punto, medio, sobre la línea y guías'] = () => {
  const m = C.nuevo();
  C.agregar(m, { tipo: 'linea', a: C.agregarPunto(m, 0, 0), b: C.agregarPunto(m, 10, 0) });
  assert.strictEqual(C.iman(m, 0.1, 0.1, 0.5).tipo, 'punto');
  assert.strictEqual(C.iman(m, 5.1, 0.2, 0.5).tipo, 'medio');
  const s = C.iman(m, 7.3, 0.3, 0.5);
  assert.ok(s.tipo === 'sobre' && cerca(s.y, 0) && cerca(s.x, 7.3));
  assert.strictEqual(C.iman(m, 7, 3, 0.5), null);
  assert.ok(C.guias(m, 10.2, 6, 0.5).x);
};

const salida = [];
for (const [nombre, f] of Object.entries(casos)) {
  try { f(); } catch (e) { salida.push(`${nombre}: ${e.message}\n${e.stack.split('\n').slice(1, 3).join('\n')}`); }
}
process.stdout.write(JSON.stringify({ casos: Object.keys(casos).length, errores: salida }));
