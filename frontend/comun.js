'use strict';
// ── BASE COMÚN ── MISMO ARCHIVO en UltraMantenimiento, Gestión Automotor y Edificios de Mamá (se carga después de
// app.js). Usa de app.js: S, $, esc, api, avisar, abrirModal, cerrarModal, irA. Cada app pone las tarjetas en su
// pantalla de ajustes con `${await tarjetasBase()}` y después llama a activarTarjetasBase(); entrar() llama a
// bannerPassword() y salir() a quitarBannerPassword().

/** Con una contraseña provisoria (la de fábrica o la que puso un administrador) se puede usar todo, pero queda este
 *  aviso arriba hasta cambiarla. */
function bannerPassword() {
  const b = $('#banner-password');
  if (!S.usuario?.debe_cambiar) return b?.remove();
  if (b) return;
  $('#vista').insertAdjacentHTML('beforebegin', `<div id="banner-password" class="banner-password no-imprimir" role="status">
    <span>Estás usando una contraseña provisoria. Cambiala en ${esc(PANTALLA_AJUSTES.titulo)}.</span>
    <button class="chico" type="button" onclick="irA('${PANTALLA_AJUSTES.vista}')">Ir a ${esc(PANTALLA_AJUSTES.titulo)}</button></div>`);
}

function quitarBannerPassword() { $('#banner-password')?.remove(); }

/** Cambiar la propia contraseña. */
function modalPassword() {
  abrirModal(`
    <h2>Cambiar contraseña</h2>
    <form id="f-password"><div class="campos">
      <label class="ancho">Contraseña actual <input type="password" name="actual" autocomplete="current-password" required></label>
      <label>Nueva (mínimo 6) <input type="password" name="nueva" autocomplete="new-password" required></label>
      <label>Repetir la nueva <input type="password" name="repetida" autocomplete="new-password" required></label>
    </div><p class="error"></p>
    <div class="botones"><button class="primario" type="submit">Guardar</button>
      <button type="button" onclick="cerrarModal()">Cancelar</button></div></form>`);
  const f = $('#f-password');
  enviarBase(f, async d => {
    if (d.nueva !== d.repetida) throw new Error('Las dos contraseñas nuevas no coinciden.');
    await api('/api/auth/password', { metodo: 'POST', datos: { actual: d.actual, nueva: d.nueva } });
    cerrarModal(); avisar('Contraseña cambiada.');
    S.usuario.debe_cambiar = false; bannerPassword();
    if (location.hash.slice(1) === PANTALLA_AJUSTES.vista) irA(PANTALLA_AJUSTES.vista);   // la tarjeta deja de decir "provisoria"
  });
}

/** Un formulario de acá: muestra el error del servidor en el propio formulario y no deja mandarlo dos veces. */
function enviarBase(form, accion) {
  form.addEventListener('submit', async ev => {
    ev.preventDefault();
    const err = $('.error', form), boton = $('button[type=submit], button.primario', form);
    if (err) err.textContent = '';
    if (boton) boton.disabled = true;
    try { await accion(Object.fromEntries(new FormData(form))); }
    catch (e) { if (err) err.textContent = e.message; else avisar(e.message, true); }
    finally { if (boton) boton.disabled = false; }
  });
}

/** Las tarjetas de la base en la pantalla de ajustes: Contraseña (todos) y, para un administrador, Puerto y Nombre y logo. */
async function tarjetasBase() {
  const admin = S.usuario.es_admin;
  const [marca, puerto] = admin ? await Promise.all([api('/api/marca'), api('/api/puerto')]) : [null, null];
  const password = `<div class="tarjeta" id="op-password"><h3>Contraseña</h3>
    ${S.usuario.debe_cambiar ? '<p><span class="chip ambar">Provisoria</span> Estás usando una contraseña provisoria: elegí una propia.</p>'
      : '<p class="sutil">Al cambiarla se cierran las otras sesiones abiertas con tu usuario.</p>'}
    <button class="primario" type="button" onclick="modalPassword()">Cambiar contraseña</button></div>`;
  if (!admin) return password;
  return password + `
    <div class="tarjeta" id="op-puerto"><h3>Puerto</h3>
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
        <p class="error"></p></form></div>`;
}

/** Nombre y logo: el servidor los pone en la página, así que después de cambiarlos se recarga entera. */
function activarTarjetasBase() {
  const fp = $('#f-puerto'), fn = $('#f-marca-nombre'), fl = $('#f-marca-logo');
  if (fp) enviarBase(fp, async d => {
    const r = await api('/api/puerto', { metodo: 'PUT', datos: { puerto: d.puerto } });
    avisar(`Guardado: la próxima vez que se abra, la app va a estar en http://localhost:${r.elegido}.`);
  });
  if (fn) enviarBase(fn, async d => { await api('/api/marca/nombre', { metodo: 'PUT', datos: { nombre: d.nombre } }); location.reload(); });
  if (fl) enviarBase(fl, async () => {
    const datos = new FormData(); datos.append('archivo', fl.archivo.files[0]);
    const r = await fetch('/api/marca/logo', { method: 'POST', headers: { Authorization: 'Bearer ' + S.token }, body: datos });
    const cuerpo = await r.json().catch(() => ({}));
    if (!r.ok) throw new Error(typeof cuerpo.detail === 'string' ? cuerpo.detail : 'No se pudo subir el logo.');
    location.reload();
  });
}

async function quitarLogo() {
  if (!confirm('¿Volver al logo original?')) return;
  try { await api('/api/marca/logo', { metodo: 'DELETE' }); location.reload(); } catch (e) { avisar(e.message, true); }
}
