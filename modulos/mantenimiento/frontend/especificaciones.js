'use strict';
// ── Especificaciones de cada equipo: el dato técnico (aceite, correas, presiones, torques...) y de dónde sale ──
// Se ven y se cargan desde Equipos e instructivos (botón "Especificaciones" de cada fila). La barra de preguntas las
// usa para contestar sin inventar, y cuando falta un dato ofrece cargarlo: window.asisAcciones.especificacion.

let _espFuentes = {};

async function _espTraer(equipoId) {
  const r = await api('/api/especificaciones' + (equipoId ? '?equipo_id=' + equipoId : ''));
  _espFuentes = r.fuentes;
  return r.especificaciones;
}

/** La lista de especificaciones de un equipo, con Agregar / Modificar / Borrar. */
async function modalEspecificaciones(equipoId) {
  const [lista, equipos] = await Promise.all([_espTraer(equipoId), api('/api/equipos?baja=true')]);
  const e = equipos.find(x => x.id === equipoId) || {};
  abrirModal(`
    <h2>Especificaciones · ${esc(e.codigo)} ${esc(e.nombre)}</h2>
    <p class="sutil">Los datos técnicos del equipo y de dónde salen. La barra de preguntas contesta con esto en vez de suponer.</p>
    ${lista.length ? `<div class="tabla-wrap"><table><thead><tr><th>Especificación</th><th>Valor</th><th>De dónde sale</th><th>Notas</th><th></th></tr></thead><tbody>
      ${lista.map(s => `<tr><td><b>${esc(s.nombre)}</b></td><td>${esc(s.valor)}${s.unidad ? ' ' + esc(s.unidad) : ''}</td>
        <td>${esc(s.fuente_texto)}${s.fuente_detalle ? `<br><span class="sutil">${esc(s.fuente_detalle)}</span>` : ''}</td>
        <td class="sutil">${esc(s.notas)}</td>
        <td class="botones"><button class="chico" onclick="modalEspecificacion(${equipoId}, ${s.id})">Modificar</button>
          ${soloAdmin(`<button class="chico peligro" onclick="borrarEspecificacion(${equipoId}, ${s.id})">Borrar</button>`)}</td></tr>`).join('')}
      </tbody></table></div>`
      : '<p>Todavía no tiene especificaciones cargadas.</p>'}
    <div class="botones"><button class="primario" onclick="modalEspecificacion(${equipoId})">Agregar especificación</button>
      <button type="button" onclick="cerrarModal()">Cerrar</button></div>`, true);
}

/** El formulario de una especificación. Sin equipo (desde la barra, cuando no se nombró la máquina) se elige ahí.
 *  `previo`: lo que ya se sabe (por ejemplo el nombre que salió de la pregunta). */
async function modalEspecificacion(equipoId, id, previo = {}) {
  const [lista, equipos] = await Promise.all([_espTraer(equipoId), api('/api/equipos')]);
  const s = id ? lista.find(x => x.id === id) : { fuente: 'manual', ...previo };
  const e = equipos.find(x => x.id === equipoId);
  abrirModal(`
    <h2>${id ? 'Modificar especificación' : 'Nueva especificación'}${e ? ' · ' + esc(e.codigo) + ' ' + esc(e.nombre) : ''}</h2>
    <form id="f-especificacion"><div class="campos">
      ${e ? '' : `<label class="ancho">Equipo <select name="equipo_id" required>${opcionesSelect(equipos.map(x => [x.id, `${x.codigo} · ${x.nombre}`]), '', 'Elegí el equipo')}</select></label>`}
      <label class="ancho">Especificación <input name="nombre" maxlength="80" required value="${esc(s.nombre || '')}" placeholder="Aceite, Correa del motor, Presión de trabajo…"></label>
      <label>Valor <input name="valor" maxlength="200" required value="${esc(s.valor || '')}" placeholder="ISO VG 46, SPZ 1060, 8…"></label>
      <label>Unidad (opcional) <input name="unidad" maxlength="20" value="${esc(s.unidad || '')}" placeholder="L, bar, Nm…"></label>
      <label>De dónde sale <select name="fuente">${opcionesSelect(Object.entries(_espFuentes), s.fuente, null)}</select></label>
      <label>Detalle de la fuente (opcional) <input name="fuente_detalle" maxlength="200" value="${esc(s.fuente_detalle || '')}" placeholder="Manual Cetec, pág. 12"></label>
      <label class="ancho">Notas (opcional) <textarea name="notas" maxlength="1000" rows="2">${esc(s.notas || '')}</textarea></label>
    </div>
    <p class="sutil">Cargá el dato tal como figura en la fuente. Si no estás seguro, poné «Técnico / experiencia» y aclaralo en notas.</p>
    <p class="error"></p>
    <div class="botones"><button class="primario" type="submit">Guardar</button>
      <button type="button" onclick="${equipoId ? `modalEspecificaciones(${equipoId})` : 'cerrarModal()'}">Cancelar</button></div></form>`);
  alEnviar($('#f-especificacion'), async d => {
    const destino = equipoId || Number(d.equipo_id);
    if (!destino) throw new Error('Elegí el equipo.');
    if (id) await api('/api/especificaciones/' + id, { metodo: 'PUT', datos: d });
    else await api(`/api/equipos/${destino}/especificaciones`, { metodo: 'POST', datos: d });
    avisar(`Especificación «${d.nombre.trim()}» guardada.`);
    if (location.hash.startsWith('#equipos')) VISTAS.equipos();
    modalEspecificaciones(destino);
  });
}

async function borrarEspecificacion(equipoId, id) {
  if (!confirm('¿Borrar esta especificación? Si el dato está mal, mejor modificalo.')) return;
  try { await api('/api/especificaciones/' + id, { metodo: 'DELETE' }); }
  catch (e) { return avisar(e.message, true); }
  if (location.hash.startsWith('#equipos')) VISTAS.equipos();
  modalEspecificaciones(equipoId);
}

// la barra de preguntas: "no hay nada cargado sobre el aceite del ETR-50" -> este formulario, ya completado
window.asisAcciones = window.asisAcciones || {};
window.asisAcciones.especificacion = d => modalEspecificacion(d.equipo_id || null, null, { nombre: d.nombre || '' });
window.asisAcciones.verEspecificaciones = d => modalEspecificaciones(d.equipo_id);

Ayuda.pasos['f-especificacion'] = () => [
  { el: () => Ayuda.h.campo('nombre'), titulo: 'Especificación', texto: 'Qué dato es: «Aceite», «Correa del motor», «Presión de trabajo». Uno por dato: si ya existe, se modifica ese.' },
  { el: () => [Ayuda.h.campo('valor'), Ayuda.h.campo('unidad')], titulo: 'Valor y unidad', texto: 'El dato tal como figura en la fuente (por ejemplo «ISO VG 46» o «8» con unidad «bar»).' },
  { el: () => [Ayuda.h.campo('fuente'), Ayuda.h.campo('fuente_detalle')], titulo: 'De dónde sale', texto: 'Manual del fabricante, placa del equipo, proveedor o experiencia del técnico. '
    + 'Es lo que le da confianza al dato: la barra de preguntas lo informa junto con el valor.' },
  { el: () => Ayuda.h.campo('notas'), titulo: 'Notas', texto: 'Lo que aclare el dato: equivalencias, cuándo se cambió, o «no estoy seguro» si la fuente es la experiencia.' },
];
