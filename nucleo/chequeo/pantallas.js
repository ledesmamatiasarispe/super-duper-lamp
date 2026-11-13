'use strict';
// Chequeo de las pantallas SIN navegador: carga los scripts de la página (los del núcleo y los de cada módulo, en el
// mismo orden que index.html) en un único contexto, como hace el navegador con los <script> clásicos, sobre un DOM de
// mentira que acepta cualquier cosa. Detecta lo que en el navegador falla en silencio y deja las pantallas sin cargar:
//   - una constante o función global declarada en dos scripts ("Identifier 'X' has already been declared");
//   - un error al cargar (por ejemplo, un módulo que usa algo del núcleo que en esta versión no existe);
//   - pantallas del menú que ningún script registró en VISTAS.
// Uso: node pantallas.js <archivo.js>... [--vistas inicio,notas,...]   Imprime un JSON {errores: [...]}.
const fs = require('fs');
const vm = require('vm');

const args = process.argv.slice(2);
const iv = args.indexOf('--vistas');
const vistas = iv >= 0 ? args[iv + 1].split(',').filter(Boolean) : [];
const archivos = iv >= 0 ? args.slice(0, iv) : args;

// Un objeto que acepta cualquier cosa: propiedades, llamadas, new, iteración. Es el "DOM" de mentira.
function cualquiera() {
  const f = function () { return cualquiera(); };
  return new Proxy(f, {
    get(t, k) {
      if (k === Symbol.toPrimitive) return () => '';
      if (k === Symbol.iterator) return function* () {};
      if (k === 'then') return undefined;   // que no parezca una promesa
      if (!(k in t)) t[k] = cualquiera();
      return t[k];
    },
    set(t, k, v) { t[k] = v; return true; },
    apply() { return cualquiera(); },
    construct() { return cualquiera(); },
  });
}

const almacen = {};
const contexto = {
  console, setTimeout: () => 0, clearTimeout() {}, setInterval: () => 0, clearInterval() {},
  requestAnimationFrame: () => 0, URLSearchParams, Map, Set, Promise, JSON, Math, Date, Object, Array, Number, String,
  document: cualquiera(), location: { hash: '', search: '', reload() {} }, history: cualquiera(),
  localStorage: { getItem: k => almacen[k] ?? null, setItem: (k, v) => { almacen[k] = String(v); }, removeItem: k => { delete almacen[k]; } },
  getComputedStyle: () => cualquiera(), MutationObserver: function () { return cualquiera(); },
  FormData: function () { return cualquiera(); }, fetch: () => new Promise(() => {}), alert() {}, confirm: () => false, prompt: () => null,
  print() {}, innerWidth: 1300, innerHeight: 900, addEventListener() {}, removeEventListener() {},
};
contexto.window = contexto;
contexto.globalThis = contexto;
vm.createContext(contexto);

const errores = [];
for (const archivo of archivos) {
  let codigo;
  try { codigo = fs.readFileSync(archivo, 'utf8'); } catch (e) { errores.push(`${archivo}: no se pudo leer (${e.message})`); continue; }
  try { new vm.Script(codigo, { filename: archivo }).runInContext(contexto); }
  catch (e) { errores.push(`${archivo}: ${e.name}: ${e.message}`); }
}
if (vistas.length) {   // aunque haya otros errores: así se ven todos de una vez
  let registradas = [];
  try { registradas = Object.keys(vm.runInContext('VISTAS', contexto)); } catch (e) { errores.push(`no hay VISTAS: ${e.message}`); }
  for (const v of vistas) if (!registradas.includes(v)) errores.push(`la pestaña "${v}" no tiene pantalla (VISTAS.${v})`);
}
process.stdout.write(JSON.stringify({ errores }));
