'use strict';
// ── NÚCLEO: la pantalla base de todas las apps ──
// Pantalla única: cada vista pide sus datos a la API y se dibuja en #vista. Sin lógica de negocio acá: lo que se valida,
// lo valida el servidor y su mensaje se muestra tal cual.
//
// Lo que un MÓDULO usa o agrega (sus scripts se cargan después de este y de ayuda.js):
//   VISTAS.<nombre> = async (param) => {...}     una pantalla (el menú la abre con #<nombre>; #<nombre>/<param>)
//   Nucleo.alEntrar.push(async () => {...})      cargar lo que el módulo necesita al iniciar sesión (antes de la 1ra vista)
//   Nucleo.tarjetasOpciones.push({ orden, html: async () => '...', activar: () => {} })   una tarjeta en Opciones
//   Nucleo.pestanas.<vista> = '<pestaña>'       qué pestaña del menú se marca en una pantalla que no tiene la suya
//   Ayuda.pasos.<vista> = () => [...]; Ayuda.tour.push(...)   la ayuda de sus pantallas (ver ayuda.js)
//   y las utilidades: api, avisar, abrirModal, cerrarModal, leerForm, enviar, opcionesSelect, esc, fecha, miles, hoyISO,
//   irA, soloAdmin, casillaOcultos / tablaOcultos, S (estado: S.usuario...).
// Un módulo puede reemplazar VISTAS.inicio con su propia pantalla de inicio.

const MESES = ['Ene', 'Feb', 'Mar', 'Abr', 'May', 'Jun', 'Jul', 'Ago', 'Sep', 'Oct', 'Nov', 'Dic'];
const MESES_LARGOS = ['enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio', 'julio', 'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre'];
const S = { token: null, usuario: null };
const VISTAS = {};
const Nucleo = { alEntrar: [], tarjetasOpciones: [], pestanas: {} };

// ── utilidades ──
const $ = (sel, raiz = document) => raiz.querySelector(sel);
const esc = v => String(v ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const hoyISO = () => { const d = new Date(); d.setMinutes(d.getMinutes() - d.getTimezoneOffset()); return d.toISOString().slice(0, 10); };
const fecha = iso => iso ? iso.slice(0, 10).split('-').reverse().join('/') : '';
const miles = n => n == null ? '—' : Number(n).toLocaleString('es-AR');
const CLAVE_TOKEN = (document.body.dataset.prefijo || 'app') + '_token';
const LOGIN = document.body.dataset.login || 'Usuario';   // cómo se llama el dato para entrar (Legajo, Usuario...)
const leerToken = () => { try { return localStorage.getItem(CLAVE_TOKEN); } catch { return null; } };
const guardarToken = t => { try { t ? localStorage.setItem(CLAVE_TOKEN, t) : localStorage.removeItem(CLAVE_TOKEN); } catch { /* sin almacenamiento */ } };

/** fetch a la API con la sesión. Si el pedido ni siquiera llega (app cerrada en la PC servidor, red caída), el navegador
 *  solo dice "Failed to fetch": se cambia por un mensaje que dice qué revisar. formulario: FormData (archivos). */
async function api(ruta, { metodo = 'GET', datos, formulario } = {}) {
  const opts = { method: metodo, headers: {} };
  if (S.token) opts.headers.Authorization = 'Bearer ' + S.token;
  if (datos !== undefined) { opts.headers['Content-Type'] = 'application/json'; opts.body = JSON.stringify(datos); }
  if (formulario) opts.body = formulario;   // el navegador pone el Content-Type con su separador
  let r;
  try { r = await fetch(ruta, opts); }
  catch { throw new Error('No se pudo conectar con el servidor: revisá que la app esté abierta en la PC servidor y que esta PC esté en la red.'); }
  if (r.status === 401 && !ruta.endsWith('/login')) { salir(); throw new Error('La sesión venció: iniciar sesión de nuevo.'); }
  const cuerpo = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(typeof cuerpo.detail === 'string' ? cuerpo.detail : 'No se pudo completar la operación.');
  return cuerpo;
}

let _avisoTimer;
function avisar(texto, mal = false) {
  const a = $('#aviso');
  a.textContent = texto; a.classList.toggle('mal', mal); a.classList.remove('oculto');
  clearTimeout(_avisoTimer); _avisoTimer = setTimeout(() => a.classList.add('oculto'), mal ? 6000 : 3000);
}

function abrirModal(html, grande = false) {
  $('#modal-cuerpo').innerHTML = html; $('#modal').classList.toggle('grande', grande); $('#modal').showModal();
}
function cerrarModal() { $('#modal').close(); }

/** Lee un formulario a un objeto: los checkbox dan true/false, el resto texto crudo (lo valida el servidor). */
function leerForm(form) {
  const d = {};
  for (const el of form.elements) {
    if (!el.name || el.type === 'file') continue;
    d[el.name] = el.type === 'checkbox' ? el.checked : el.value;
  }
  return d;
}

/** Ejecuta `accion(datos)` con el formulario: muestra el error del servidor en el propio formulario y no lo cierra. */
async function enviar(form, accion) {
  const err = $('.error', form), boton = $('button[type=submit], button.primario', form);
  if (err) err.textContent = '';
  if (boton) boton.disabled = true;
  try { await accion(leerForm(form)); }
  catch (e) { if (err) err.textContent = e.message; else avisar(e.message, true); }
  finally { if (boton) boton.disabled = false; }
}

/** Conecta el submit de un formulario con enviar(). */
function alEnviar(form, accion) {
  form.addEventListener('submit', ev => { ev.preventDefault(); enviar(form, accion); });
}

const opcionesSelect = (lista, valor, vacio = '') =>
  (vacio !== null ? `<option value="">${esc(vacio)}</option>` : '') +
  lista.map(([v, t]) => `<option value="${esc(v)}" ${String(v) === String(valor ?? '') ? 'selected' : ''}>${esc(t)}</option>`).join('');

const soloAdmin = html => S.usuario?.es_admin ? html : '';

// Lo dado de baja (filas tr.baja) no se muestra salvo que se marque "Ver ocultos" en esa tabla. Se recuerda por tabla.
S.verOcultos = {};
function casillaOcultos(clave, cantidad) {
  return `<label class="check ver-ocultos"><input type="checkbox" data-ocultos="${clave}" ${S.verOcultos[clave] ? 'checked' : ''}>
    Ver ocultos (${cantidad})</label>`;
}
const tablaOcultos = clave => `data-ocultos-tabla="${clave}" class="${S.verOcultos[clave] ? 'mostrar-ocultos' : ''}"`;
document.addEventListener('change', ev => {
  const clave = ev.target.dataset?.ocultos;
  if (!clave) return;
  S.verOcultos[clave] = ev.target.checked;
  document.querySelectorAll(`[data-ocultos-tabla="${clave}"]`).forEach(t => t.classList.toggle('mostrar-ocultos', ev.target.checked));
});

// ── sesión ──
async function entrar() {
  try { S.usuario = await api('/api/auth/yo'); } catch { return mostrarLogin(); }
  $('#login').classList.add('oculto'); $('#app').classList.remove('oculto');
  $('#usuario-nombre').textContent = S.usuario.nombre;
  document.querySelectorAll('.solo-admin').forEach(el => el.classList.toggle('oculto', !S.usuario.es_admin));
  bannerPassword();   // con una contraseña provisoria se puede usar todo, pero queda el aviso hasta cambiarla
  try { for (const f of Nucleo.alEntrar) await f(); } catch (e) { return avisar(e.message, true); }
  irA(location.hash.slice(1) || 'inicio');
  if (S.usuario.es_admin) preguntarActualizacion();
}

function mostrarLogin() { $('#app').classList.add('oculto'); $('#login').classList.remove('oculto'); $('#form-login [name=usuario]').focus(); }

function salir() {
  if (S.token) fetch('/api/auth/logout', { method: 'POST', headers: { Authorization: 'Bearer ' + S.token } }).catch(() => {});
  S.token = null; S.usuario = null; guardarToken(null); $('#banner-password')?.remove(); mostrarLogin();
}

/** Aviso amarillo, en todas las pantallas, mientras el usuario siga con una contraseña provisoria (la de fábrica o la
 *  que le puso un administrador). No bloquea nada: se va al cambiarla. */
function bannerPassword() {
  const b = $('#banner-password');
  if (!S.usuario?.debe_cambiar) return b?.remove();
  if (b) return;
  $('#vista').insertAdjacentHTML('beforebegin', `<div id="banner-password" class="banner-password no-imprimir" role="status">
    <span>Estás usando una contraseña provisoria. Cambiala en Opciones.</span>
    <button class="chico" type="button" onclick="irA('opciones')">Ir a Opciones</button></div>`);
}

function modalPassword() {
  abrirModal(`<h2>Cambiar contraseña</h2>
    <form id="f-password"><div class="campos">
      <label class="ancho">Contraseña actual <input type="password" name="actual" autocomplete="current-password" required></label>
      <label>Nueva (mínimo 6) <input type="password" name="nueva" autocomplete="new-password" required></label>
      <label>Repetir la nueva <input type="password" name="repetida" autocomplete="new-password" required></label>
    </div><p class="error"></p>
    <div class="botones"><button class="primario" type="submit">Guardar</button><button type="button" onclick="cerrarModal()">Cancelar</button></div></form>`);
  alEnviar($('#f-password'), async d => {
    if (d.nueva !== d.repetida) throw new Error('Las dos contraseñas nuevas no coinciden.');
    await api('/api/auth/password', { metodo: 'POST', datos: { actual: d.actual, nueva: d.nueva } });
    cerrarModal(); avisar('Contraseña cambiada.');
    S.usuario.debe_cambiar = false; bannerPassword();
    if (location.hash.slice(1) === 'opciones') irA('opciones');   // la tarjeta deja de decir "provisoria"
  });
}

// ── navegación ──
function irA(nombre) {
  const [vista, param] = String(nombre || 'inicio').split('/');
  if (!VISTAS[vista]) return irA('inicio');
  if (location.hash.slice(1) !== nombre) history.replaceState(null, '', '#' + nombre);
  const pestana = Nucleo.pestanas[vista] || vista;   // p. ej. un instructivo se abre desde la pestaña Equipos
  document.querySelectorAll('#menu a').forEach(a => a.classList.toggle('activo', a.dataset.vista === pestana));
  $('#vista').innerHTML = '<p class="sutil">Cargando…</p>';
  Promise.resolve(VISTAS[vista](param)).catch(e => { $('#vista').innerHTML = `<p class="error">${esc(e.message)}</p>`; });
}

/** Inicio de fábrica: un módulo lo reemplaza con el suyo (VISTAS.inicio = ...). */
VISTAS.inicio = async () => {
  $('#vista').innerHTML = `<div class="encabezado"><h2>Inicio</h2></div>
    <div class="tarjeta"><p>Hola, <b>${esc(S.usuario.nombre)}</b>.</p>
      <p class="sutil">Las pantallas de la app están en las pestañas de arriba. <b>Ayuda</b> explica la pantalla en la que estés.</p></div>`;
};

// ── actualizaciones ──
/** Al entrar un administrador: si hay una versión nueva (y no se pospuso), se pregunta si se instala. */
async function preguntarActualizacion() {
  let a;
  try { a = await api('/api/actualizacion'); } catch { return; }   // sin respuesta, se pregunta la próxima vez
  if (!a.preguntar) return;
  abrirModal(`<h2>Hay una versión nueva</h2>
    <p>Está disponible la versión <b>${esc(a.nueva)}</b> (la instalada es la ${esc(a.version)}). ¿Querés actualizar ahora?</p>
    ${a.notas ? `<div class="notas-version">${esc(a.notas)}</div>` : ''}
    <p class="sutil">La app se cierra y vuelve a abrir sola en menos de un minuto: avisá a quien la esté usando. Los datos no se tocan (antes se copia la base).</p>
    <p class="error"></p>
    <div class="botones"><button class="primario" id="act-si" ${a.instalable ? '' : 'disabled'}>Actualizar ahora</button>
      <button id="act-no">Ahora no (preguntar en una semana)</button></div>
    ${a.instalable ? '' : '<p class="sutil">Este release no trae el instalable: hay que actualizar a mano.</p>'}`);
  $('#act-no').addEventListener('click', async () => {
    try { const r = await api('/api/actualizacion/posponer', { metodo: 'POST' }); cerrarModal(); avisar(`No se vuelve a preguntar hasta el ${fecha(r.pospuesta_hasta)}. Se puede actualizar antes desde Opciones.`); }
    catch (e) { $('#modal .error').textContent = e.message; }
  });
  $('#act-si').addEventListener('click', () => instalarActualizacion());
}

/** Instala y espera a que la app vuelva con la versión nueva; entonces recarga la página. */
async function instalarActualizacion() {
  const antes = (await api('/api/version').catch(() => ({}))).version;
  abrirModal(`<h2>Actualizando…</h2><p>Bajando la versión nueva. Después la app se cierra y vuelve a abrir sola: esta página se recarga cuando esté lista.</p>
    <p class="error"></p>`);
  try { await api('/api/actualizacion/instalar', { metodo: 'POST' }); }
  catch (e) { $('#modal .error').textContent = e.message; $('#modal-cuerpo').insertAdjacentHTML('beforeend', '<div class="botones"><button onclick="cerrarModal()">Cerrar</button></div>'); return; }
  const inicio = Date.now();
  const esperar = async () => {
    try {
      const r = await fetch('/api/version');
      if (r.ok && (await r.json()).version !== antes) return location.reload();
    } catch { /* todavía reiniciando */ }
    if (Date.now() - inicio > 5 * 60 * 1000) {
      $('#modal .error').textContent = 'La app tarda en volver. Si no abre, iniciala de nuevo: el detalle queda en data\\actualizacion.log.';
      return;
    }
    setTimeout(esperar, 2000);
  };
  setTimeout(esperar, 3000);
}

async function buscarActualizacion(boton) {
  boton.disabled = true; boton.textContent = 'Buscando…';
  try { await api('/api/actualizacion/buscar', { metodo: 'POST' }); irA('opciones'); }
  catch (e) { avisar(e.message, true); boton.disabled = false; boton.textContent = 'Buscar ahora'; }
}

// ── OPCIONES ── (versión, contraseña y, para un administrador, puerto y nombre y logo; los módulos suman sus tarjetas)
VISTAS.opciones = async () => {
  const admin = S.usuario.es_admin;
  const [a, marca, puerto] = await Promise.all([api('/api/actualizacion'), admin ? api('/api/marca') : null, admin ? api('/api/puerto') : null]);
  let estado;
  if (!a.repo) estado = '<p class="sutil">Todavía no hay un repositorio de actualizaciones configurado.</p>';
  else if (a.error) estado = `<p class="error">${esc(a.error)}</p>`;
  else if (a.disponible) estado = `<p>Hay una versión nueva: <b>${esc(a.nueva)}</b>${a.url_release ? ` · <a href="${esc(a.url_release)}" target="_blank" rel="noopener">ver en GitHub</a>` : ''}</p>
    ${a.notas ? `<div class="notas-version">${esc(a.notas)}</div>` : ''}
    ${a.pospuesta_hasta ? `<p class="sutil">Se pospuso: al entrar no se vuelve a preguntar hasta el ${fecha(a.pospuesta_hasta)}.</p>` : ''}
    ${admin ? (a.compilada ? (a.instalable ? '<button class="primario" onclick="instalarActualizacion()">Actualizar ahora</button>'
      : '<p class="sutil">Este release no trae el instalable (.zip y .sha256): hay que actualizar a mano.</p>')
      : '<p class="sutil">Esta es la versión de desarrollo: se actualiza con git, no desde acá.</p>') : '<p class="sutil">La instala un administrador.</p>'}`;
  else estado = '<p>Estás usando la última versión.</p>';
  const tarjetas = [...Nucleo.tarjetasOpciones].sort((x, y) => (x.orden ?? 50) - (y.orden ?? 50));
  const extras = await Promise.all(tarjetas.map(t => t.html()));
  $('#vista').innerHTML = `
    <div class="encabezado"><h2>Opciones</h2></div>
    <div class="tarjeta" id="op-version"><h3>Versión y actualizaciones</h3>
      <p>Versión instalada: <b>${esc(a.version)}</b>${a.compilada ? '' : ' <span class="chip">desarrollo</span>'}</p>
      ${estado}
      ${a.repo ? `<p class="sutil">Se busca en GitHub (${esc(a.repo)}) cada vez que arranca la app${a.buscado_en ? ' · última búsqueda: ' + esc(a.buscado_en) : ''}.</p>` : ''}
      ${admin && a.repo ? '<button onclick="buscarActualizacion(this)">Buscar ahora</button>' : ''}</div>
    <div class="tarjeta" id="op-password"><h3>Contraseña</h3>
      ${S.usuario.debe_cambiar ? '<p><span class="chip ambar">Provisoria</span> Estás usando una contraseña provisoria: elegí una propia.</p>'
        : '<p class="sutil">Al cambiarla se cierran las otras sesiones abiertas con tu usuario.</p>'}
      <button class="primario" type="button" onclick="modalPassword()">Cambiar contraseña</button></div>
    ${extras.join('')}
    ${admin ? `<div class="tarjeta" id="op-puerto"><h3>Puerto</h3>
      <p>La app atiende en <b>http://localhost:${puerto.actual}</b>${puerto.actual !== puerto.elegido
        ? ` <span class="chip ambar">el ${puerto.elegido} estaba ocupado</span>` : ''}.</p>
      ${puerto.fijo ? `<p class="sutil">Lo fija la variable ${esc(puerto.variable)}: se cambia ahí.</p>` : `
      <form id="f-puerto" class="campos"><label>Puerto <input name="puerto" type="number" min="1024" max="65535" value="${puerto.elegido}"></label>
        <div class="botones"><button class="primario" type="submit">Guardar puerto</button></div><p class="error"></p></form>
      <p class="sutil">Vale desde la próxima vez que se abre la app. Sirve para que no choque con otro programa de esta PC
        (${puerto.defecto} es el de fábrica); si al abrirla está ocupado, arranca igual en el siguiente libre y lo avisa acá.
        Al cambiarlo, los accesos directos y las otras PC o tablets tienen que usar el número nuevo.</p>`}</div>
    <div class="tarjeta" id="op-marca"><h3>Nombre y logo</h3>
      <p class="sutil">Lo que se ve en la barra de arriba, en la pantalla de ingreso y en la pestaña del navegador.</p>
      <div class="marca-vista"><img src="${esc($('.marca img')?.getAttribute('src') || '')}" alt=""><b>${esc(marca.nombre)}</b></div>
      <form id="f-marca-nombre" class="campos"><label>Nombre de la app <input name="nombre" maxlength="40"
        value="${esc(marca.propio ? marca.nombre : '')}" placeholder="${esc(marca.defecto)}"></label>
        <div class="botones"><button class="primario" type="submit">Guardar nombre</button></div><p class="error"></p></form>
      <form id="f-marca-logo" class="campos"><label>Logo nuevo <input name="archivo" type="file" accept=".png,.jpg,.jpeg,.gif,.webp,.svg" required></label>
        <div class="botones"><button class="primario" type="submit">Subir logo</button>
          ${marca.logo ? '<button type="button" onclick="quitarLogo()">Volver al logo original</button>' : ''}</div>
        <p class="sutil">PNG, JPG, GIF, WEBP o SVG, hasta 2 MB. Mejor cuadrado y con fondo transparente: se muestra chico, al lado del nombre.</p>
        <p class="error"></p></form></div>` : ''}`;
  const fp = $('#f-puerto'), fn = $('#f-marca-nombre'), fl = $('#f-marca-logo');
  if (fp) alEnviar(fp, async d => {
    const r = await api('/api/puerto', { metodo: 'PUT', datos: { puerto: d.puerto } });
    avisar(`Guardado: la próxima vez que se abra, la app va a estar en http://localhost:${r.elegido}.`);
  });
  // el nombre y el logo los pone el servidor en la página: después de cambiarlos se recarga entera
  if (fn) alEnviar(fn, async d => { await api('/api/marca/nombre', { metodo: 'PUT', datos: { nombre: d.nombre } }); location.reload(); });
  if (fl) alEnviar(fl, async () => {
    const datos = new FormData(); datos.append('archivo', fl.archivo.files[0]);
    await api('/api/marca/logo', { metodo: 'POST', formulario: datos });
    location.reload();
  });
  tarjetas.forEach(t => t.activar?.());
};

async function quitarLogo() {
  if (!confirm('¿Volver al logo original?')) return;
  try { await api('/api/marca/logo', { metodo: 'DELETE' }); location.reload(); } catch (e) { avisar(e.message, true); }
}

// ── USUARIOS ──
VISTAS.usuarios = async () => {
  if (!S.usuario.es_admin) return irA('inicio');
  const lista = await api('/api/usuarios');
  S.usuarios = lista;
  $('#vista').innerHTML = `
    <div class="encabezado"><h2>Usuarios</h2><div class="botones"><button class="primario" onclick="modalUsuario()">Nuevo usuario</button></div></div>
    <p class="sutil">Quiénes entran al sistema. Un <b>usuario</b> usa la app en el día a día; un <b>administrador</b> además configura
      y maneja los usuarios. Siempre tiene que quedar al menos un administrador activo.</p>
    <div class="tarjeta tabla-wrap">${casillaOcultos('usuarios', lista.filter(u => !u.activo).length)}<table ${tablaOcultos('usuarios')}>
      <thead><tr><th>${esc(LOGIN)}</th><th>Nombre</th><th>Rol</th><th>Estado</th><th></th></tr></thead><tbody>
      ${lista.map(u => `<tr class="${u.activo ? '' : 'baja'}"><td><b>${esc(u.usuario)}</b></td>
        <td>${esc(u.nombre)}${u.id === S.usuario.id ? ' <span class="sutil">(vos)</span>' : ''}</td>
        <td>${u.es_admin ? '<span class="chip azul">Administrador</span>' : '<span class="chip">Usuario</span>'}</td>
        <td>${u.activo ? (u.debe_cambiar ? '<span class="chip ambar">Contraseña provisoria</span>' : '<span class="chip verde">Activo</span>') : '<span class="chip rojo">De baja</span>'}</td>
        <td class="botones"><button class="chico" onclick="modalUsuario(${u.id})">Editar</button>
          ${u.id !== S.usuario.id ? `<button class="chico" onclick="modalRestablecer(${u.id})">Restablecer contraseña</button>
          <button class="chico ${u.activo ? 'peligro' : ''}" onclick="altaUsuario(${u.id}, ${!u.activo})">${u.activo ? 'Dar de baja' : 'Reactivar'}</button>` : ''}</td></tr>`).join('')}
    </tbody></table></div>`;
};

function modalUsuario(id) {
  const u = id ? S.usuarios.find(x => x.id === id) : null;
  abrirModal(`<h2>${u ? 'Editar ' + esc(u.nombre) : 'Nuevo usuario'}</h2>
    <form id="f-usuario"><div class="campos">
      <label>${esc(LOGIN)} (para entrar) <input name="usuario" value="${esc(u?.usuario || '')}" ${u ? 'disabled' : 'required'} autocomplete="off"></label>
      <label>Nombre <input name="nombre" value="${esc(u?.nombre || '')}" required></label>
      ${u ? '' : '<label class="ancho">Contraseña provisoria (mínimo 6; le queda un aviso hasta que la cambie en Opciones) <input name="password" type="text" autocomplete="off" required></label>'}
      <label class="check ancho"><input type="checkbox" name="es_admin" ${u?.es_admin ? 'checked' : ''}> Administrador (configura el sistema y maneja usuarios)</label>
    </div><p class="error"></p>
    <div class="botones"><button class="primario" type="submit">Guardar</button><button type="button" onclick="cerrarModal()">Cancelar</button></div></form>`);
  alEnviar($('#f-usuario'), async d => {
    await api(u ? '/api/usuarios/' + id : '/api/usuarios', { metodo: u ? 'PUT' : 'POST', datos: d });
    cerrarModal(); avisar(u ? 'Usuario actualizado.' : `Usuario creado: entra con su ${LOGIN.toLowerCase()} y la contraseña provisoria.`);
    if (u && id === S.usuario.id) return entrar();   // si se cambió a sí mismo, refresca nombre y rol
    irA('usuarios');
  });
}

function modalRestablecer(id) {
  const u = S.usuarios.find(x => x.id === id);
  abrirModal(`<h2>Restablecer contraseña de ${esc(u.nombre)}</h2>
    <p>Para quien se olvidó la suya: le ponés una provisoria y se la pasás; le queda un aviso hasta que elija una propia en Opciones. Se le cierran las sesiones abiertas.</p>
    <form id="f-restablecer"><div class="campos"><label class="ancho">Contraseña provisoria (mínimo 6) <input name="password" type="text" autocomplete="off" required></label></div>
    <p class="error"></p><div class="botones"><button class="primario" type="submit">Restablecer</button><button type="button" onclick="cerrarModal()">Cancelar</button></div></form>`);
  alEnviar($('#f-restablecer'), async d => {
    await api(`/api/usuarios/${id}/password`, { metodo: 'POST', datos: d }); cerrarModal(); avisar('Contraseña restablecida.'); irA('usuarios');
  });
}

async function altaUsuario(id, activo) {
  if (!activo && !confirm('¿Dar de baja este usuario? No va a poder entrar (se le cierra la sesión); lo que registró se conserva.')) return;
  try { await api(`/api/usuarios/${id}/${activo ? 'alta' : 'baja'}`, { metodo: 'POST' }); irA('usuarios'); }
  catch (e) { avisar(e.message, true); }
}

// ── arranque: cuando ya cargaron los scripts de los módulos (registraron sus VISTAS, Nucleo.alEntrar...) ──
window.addEventListener('DOMContentLoaded', () => {
  $('#form-login').addEventListener('submit', async ev => {
    ev.preventDefault();
    $('#login-error').textContent = '';
    try {
      const r = await api('/api/auth/login', { metodo: 'POST', datos: leerForm(ev.target) });
      S.token = r.token; guardarToken(r.token); ev.target.reset(); entrar();
    } catch (e) { $('#login-error').textContent = e.message; }
  });
  $('#salir').addEventListener('click', salir);
  $('#mi-password').addEventListener('click', () => modalPassword());
  $('#mis-opciones').addEventListener('click', () => irA('opciones'));
  $('#menu').addEventListener('click', ev => {
    const a = ev.target.closest('a[data-vista]');
    if (a) { ev.preventDefault(); irA(a.dataset.vista); }
  });
  window.addEventListener('hashchange', () => S.usuario && irA(location.hash.slice(1)));
  S.token = leerToken();
  if (S.token) entrar(); else mostrarLogin();
});
