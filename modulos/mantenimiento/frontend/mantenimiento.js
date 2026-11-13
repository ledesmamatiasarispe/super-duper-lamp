'use strict';
// ── Módulo MANTENIMIENTO (pantallas) ──
// Se carga después de nucleo.js y ayuda.js (el núcleo): usa sus utilidades (api, abrirModal, enviar, esc, irA, S...) y
// registra lo suyo: las pantallas en VISTAS, lo que carga al entrar en Nucleo.alEntrar, la tarjeta "Plan de
// mantenimiento" en Opciones y la pestaña que marca un instructivo. Sin lógica de negocio acá: valida el servidor.

S.opciones = null; S.tareas = []; S.anio = new Date().getFullYear();
Nucleo.pestanas.instructivos = 'equipos';   // un instructivo se abre desde Equipos e instructivos

const CATEGORIAS = { interno: 'Mantenimiento interno', externo: 'Proveedor externo' };
/** Personas agrupadas por categoría. modo 'trabajo': la genérica es "Otro (escribir nombre)";
 *  modo 'general' (responsable de una tarea, quién anotó): es la categoría en general. */
function personasSelect(valor, vacio = '— elegir —', modo = 'trabajo') {
  const sel = v => String(v) === String(valor ?? '') ? 'selected' : '';
  const grupos = Object.entries(CATEGORIAS).map(([cat, titulo]) => {
    const ps = S.opciones.personas.filter(p => p.categoria === cat && (p.activo || String(p.id) === String(valor)));
    const opts = ps.map(p => `<option value="${p.id}" ${sel(p.id)}>${esc(p.pide_nombre
      ? (modo === 'trabajo' ? `Otro ${cat === 'externo' ? 'proveedor' : 'operario'} (escribir nombre)` : `${titulo} (en general)`)
      : p.nombre)}</option>`).join('');
    return `<optgroup label="${titulo}">${opts}</optgroup>`;
  }).join('');
  return (vacio !== null ? `<option value="">${esc(vacio)}</option>` : '') + grupos;
}

/** La ficha de Personal del usuario que está usando el sistema: lo más común es registrar lo que hizo uno. */
const miFicha = () => S.opciones.personas.find(p => p.usuario_legajo === S.usuario.id && p.activo);

/** Si la persona elegida es genérica ("Mantenimiento interno"), muestra la casilla para escribir quién fue. */
function casillaNombre(f) {
  const ver = () => {
    const p = S.opciones.personas.find(x => String(x.id) === f.realizado_por_id.value);
    $('.p-nombre', f).classList.toggle('oculto', !p?.pide_nombre);
    $('.p-nombre span', f).textContent = p?.categoria === 'externo' ? 'Nombre del proveedor' : 'Nombre del operario';
  };
  f.realizado_por_id.addEventListener('change', ver); ver();
  return ver;
}

async function recargarOpciones() {
  [S.opciones, S.tareas] = await Promise.all([api('/api/opciones'), api('/api/tareas')]);
}

/** "Programar todos": lista lo que falta en el Plan con la frecuencia sugerida, editable, y lo guarda todo junto. */
async function modalProgramarTodos() {
  let lista;
  try { lista = await api('/api/tareas/sin-programar'); } catch (e) { return avisar(e.message, true); }
  if (!lista.length) return avisar('No queda nada por programar: todos los equipos tienen sus secciones en el Plan.');
  const frecuencias = S.opciones.frecuencias;
  abrirModal(`
    <h2>Programar todos</h2>
    <p class="sutil">${lista.length} secciones sin programar. Las que no tienen una frecuencia sugerida quedan sin marcar:
      elegirla y marcarlas, o dejarlas para después. Los meses de inicio vienen en enero: <b>Repartir meses</b> los distribuye
      para que no se junten los trabajos.</p>
    <form id="f-programar">
      <div class="campos"><label style="max-width:24rem">Responsable (para todas) <select name="responsable_id">${personasSelect('', '—', 'general')}</select></label></div>
      <div class="botones"><button type="button" class="repartir">Repartir meses</button>
        <span class="sutil carga" title="Trabajos por mes: lo que ya está en el Plan más lo marcado en esta lista"></span></div>
      <div class="tabla-wrap"><table><thead><tr><th><input type="checkbox" class="todas" title="Marcar o desmarcar todas"></th>
        <th>Equipo</th><th>Mantenimiento</th><th>Según la ficha</th><th>Frecuencia</th><th>Mes de inicio</th><th>Cada (h)</th></tr></thead><tbody>
        ${lista.map((t, i) => `<tr data-i="${i}"><td><input type="checkbox" class="usar" ${t.frecuencia ? 'checked' : ''}></td>
          <td><b>${esc(t.equipo_codigo)}</b> · ${esc(t.equipo)}</td><td>${esc(t.seccion)}</td><td>${esc(t.segun_ficha || '—')}</td>
          <td><select class="frecuencia">${opcionesSelect(frecuencias.filter(f => f !== 'Por horas' || t.usa_horometro).map(f => [f, f]), t.frecuencia, '— elegir —')}</select></td>
          <td><select class="mes">${opcionesSelect(MESES_LARGOS.map((m, j) => [j + 1, m]), t.mes_inicio, '—')}</select></td>
          <td><input class="horas" type="number" min="1" step="1" value="${t.cada_horas ?? ''}" style="width:6.5rem"></td></tr>`).join('')}
      </tbody></table></div>
      <p class="error"></p>
      <div class="botones"><button class="primario" type="submit">Programar</button><button type="button" onclick="cerrarModal()">Cancelar</button></div></form>`, true);
  const f = $('#f-programar');
  const filas = [...f.querySelectorAll('tbody tr')];
  const ver = tr => {
    const fr = $('.frecuencia', tr).value;
    $('.mes', tr).classList.toggle('oculto', !fr || fr === 'Por horas' || fr === 'Según condición');
    $('.horas', tr).classList.toggle('oculto', fr !== 'Por horas');
  };
  const contar = () => {
    const n = filas.filter(tr => $('.usar', tr).checked).length;
    $('button[type=submit]', f).textContent = `Programar ${n}`;
    Object.assign($('.todas', f), { checked: n === filas.length, indeterminate: n > 0 && n < filas.length });
    const carga = cargaPorMes(f, filas);
    $('.carga', f).textContent = 'Trabajos por mes: ' + carga.map((n, m) => `${MESES[m]} ${n}`).join(' · ');
  };
  $('.repartir', f).addEventListener('click', () => { repartirMeses(f, filas); contar(); });
  filas.forEach(tr => {
    ver(tr);
    $('.frecuencia', tr).addEventListener('change', () => {
      const fr = $('.frecuencia', tr).value;
      if (fr && fr !== 'Por horas' && fr !== 'Según condición' && !$('.mes', tr).value) $('.mes', tr).value = '1';
      if (fr) $('.usar', tr).checked = true;
      ver(tr); contar();
    });
    $('.usar', tr).addEventListener('change', contar);
  });
  $('.todas', f).addEventListener('change', ev => { filas.forEach(tr => { $('.usar', tr).checked = ev.target.checked; }); contar(); });
  contar();
  f.addEventListener('submit', ev => {
    ev.preventDefault();
    enviar(f, async d => {
      const elegidas = filas.filter(tr => $('.usar', tr).checked);
      if (!elegidas.length) throw new Error('No hay ninguna marcada.');
      const tareas = elegidas.map(tr => {
        const t = lista[tr.dataset.i], frecuencia = $('.frecuencia', tr).value;
        if (!frecuencia) throw new Error(`${t.equipo_codigo} ${t.seccion}: falta elegir la frecuencia (o desmarcarla).`);
        return { equipo_id: t.equipo_id, seccion_id: t.seccion_id, frecuencia, responsable_id: d.responsable_id,
                 mes_inicio: $('.mes', tr).value, cada_horas: $('.horas', tr).value };
      });
      const r = await api('/api/tareas/lote', { metodo: 'POST', datos: { tareas } });
      await recargarOpciones(); cerrarModal();
      avisar(`Se programaron ${r.length} tareas.`); irA('plan');
    });
  });
}

/** Cuántos trabajos caen en cada mes (0 = enero), igual que calendario.veces_por_mes: el Plan activo más las filas marcadas. */
function cargaPorMes(f, filas) {
  const intervalos = S.opciones.intervalos, carga = Array(12).fill(0);
  const sumar = (frecuencia, inicio, especificos) => {
    const veces = frecuencia === 'Quincenal' ? 2 : 1;
    const lista = String(especificos || '').split(',').map(Number).filter(Boolean);
    if (lista.length) return lista.forEach(m => { carga[m - 1] += veces; });
    const k = intervalos[frecuencia];
    if (!k || !inicio) return;
    for (let m = Number(inicio); m <= 12; m += k) carga[m - 1] += veces;
    for (let m = Number(inicio) - k; m >= 1; m -= k) carga[m - 1] += veces;
  };
  S.tareas.filter(t => t.activa).forEach(t => sumar(t.frecuencia, t.mes_inicio, t.meses_especificos));
  filas.filter(tr => $('.usar', tr).checked).forEach(tr => sumar($('.frecuencia', tr).value, $('.mes', tr).value));
  return carga;
}

/** Elige el mes de inicio de cada fila marcada para emparejar la carga mensual. Primero las más frecuentes
 *  (dejan el patrón de base) y después las espaciadas, cada una en la fase cuyos meses estén más libres. */
function repartirMeses(f, filas) {
  const intervalos = S.opciones.intervalos;
  const porMes = filas.filter(tr => $('.usar', tr).checked && intervalos[$('.frecuencia', tr).value]);
  porMes.forEach(tr => { $('.mes', tr).value = ''; });   // las que se reparten no cuentan hasta que se ubiquen
  porMes.sort((a, b) => intervalos[$('.frecuencia', a).value] - intervalos[$('.frecuencia', b).value]);
  for (const tr of porMes) {
    const k = intervalos[$('.frecuencia', tr).value], carga = cargaPorMes(f, filas);
    let mejor = 1, puntaje = Infinity;
    for (let inicio = 1; inicio <= k; inicio++) {
      const meses = carga.filter((_, m) => (m + 1 - inicio) % k === 0);
      const p = meses.reduce((s, n) => s + n, 0) * 1000 + Math.max(...meses);   // los meses más libres; a igualdad, sin picos
      if (p < puntaje) { puntaje = p; mejor = inicio; }
    }
    $('.mes', tr).value = String(mejor);
  }
  avisar(porMes.length ? `Se repartieron ${porMes.length} meses de inicio. Se pueden retocar a mano antes de guardar.`
    : 'No hay filas marcadas con frecuencia por meses para repartir.');
}

// ── registrar un mantenimiento (desde inicio, cronograma o registros) ──
async function modalRegistro(tareaId, fechaSugerida) {
  const tareas = S.tareas.filter(t => t.activa);
  const elegida = tareas.find(t => t.id === tareaId) || null;
  abrirModal(`
    <h2>Registrar mantenimiento</h2>
    <form id="f-registro">
      <div class="campos">
        <label class="ancho">Tarea del Plan
          <select name="tarea_id" required>${opcionesSelect(tareas.map(t => [t.id, `${t.codigo} · ${t.equipo} · ${t.seccion} (${t.frecuencia})`]), tareaId, '— elegir —')}</select></label>
      </div>
      <div id="r-checklist"></div>
      <div class="campos">
        <label>Fecha <input type="date" name="fecha" value="${fechaSugerida || hoyISO()}" max="${hoyISO()}" required></label>
        <label>Resultado <select name="resultado">${opcionesSelect(S.opciones.resultados.map(r => [r, r]), 'Realizado', null)}</select></label>
        <label>Realizado por <select name="realizado_por_id">${personasSelect(miFicha()?.id ?? elegida?.responsable_id)}</select></label>
        <label class="p-nombre oculto"><span>Nombre</span> <input name="realizado_por_nombre"></label>
        <label>Horas-hombre <input name="horas_hombre" inputmode="decimal"></label>
        <label id="r-horometro">Horómetro (h) <input name="horometro" type="number" min="0" step="1" placeholder="ej. 51020"></label>
        <label id="r-reprog" class="oculto">Reprogramado para <input type="date" name="reprogramado_para"></label>
        <label class="ancho">Novedades / observaciones <textarea name="novedades"></textarea></label>
        <label class="ancho">Repuestos utilizados <input name="repuestos"></label>
      </div>
      <p class="error"></p>
      <div class="botones"><button class="primario" type="submit">Guardar</button><button type="button" onclick="cerrarModal()">Cancelar</button></div>
    </form>`);
  const f = $('#f-registro');
  const verNombre = casillaNombre(f);
  const actualizar = async () => {
    const t = tareas.find(x => String(x.id) === f.tarea_id.value);
    $('#r-horometro').classList.toggle('oculto', !t?.usa_horometro);
    if (t && !f.realizado_por_id.value && t.responsable_id) { f.realizado_por_id.value = t.responsable_id; verNombre(); }
    $('#r-checklist').innerHTML = t ? await checklist(t) : '';
    cargarImagenes($('#r-checklist'));
  };
  f.tarea_id.addEventListener('change', actualizar);
  f.resultado.addEventListener('change', () => $('#r-reprog').classList.toggle('oculto', f.resultado.value !== 'Reprogramado'));
  f.addEventListener('submit', ev => {
    ev.preventDefault();
    enviar(f, async d => {
      if (!d.tarea_id) throw new Error('Elegir la tarea.');
      await api(`/api/tareas/${d.tarea_id}/registros`, { metodo: 'POST', datos: d });
      cerrarModal(); avisar('Registro guardado.'); irA(location.hash.slice(1) || 'inicio');
    });
  });
  actualizar();
}

/** Las actividades de la sección, para tenerlas a la vista mientras se registra. */
async function checklist(t) {
  try {
    const it = await api(`/api/instructivos/${t.instructivo_id}`);
    const sec = it.secciones.find(s => s.codigo === t.seccion);
    if (!sec) return '';
    return `<div class="checklist"><b>${esc(t.seccion)}</b> — ${esc(it.titulo)} (Rev. ${it.revision})
      ${actividadesHTML(sec.actividades)}${bloquesTras(it, sec.letra)}</div>`;
  } catch { return ''; }
}

// ── INICIO ──
VISTAS.inicio = async () => {
  const p = await api('/api/pendientes');
  const hoy = new Date(p.hoy + 'T00:00');
  const c = p.cumplimiento;
  // tablas a todo el ancho, una debajo de la otra: en columnas angostas los nombres largos quedaban cortados
  const tabla = (titulos, filas, vacio) => `<div class="tabla-wrap"><table><thead><tr>${titulos.map(t => `<th>${t}</th>`).join('')}</tr></thead>
    <tbody>${filas.join('') || `<tr><td colspan="${titulos.length}" class="vacio">${vacio}</td></tr>`}</tbody></table></div>`;
  const registrar = id => `<td class="botones"><button class="chico primario" onclick="modalRegistro(${id})">Registrar</button></td>`;
  const fila = (t, cuando) => `<tr><td><b>${esc(t.codigo)}</b></td><td>${esc(t.equipo)}</td>
    <td><a onclick="irA('instructivos/${t.instructivo_id}')">${esc(t.seccion)}</a></td><td>${esc(t.frecuencia)}</td>
    <td>${esc(cuando)}</td><td>${esc(t.responsable || '')}</td>${registrar(t.tarea_id)}</tr>`;
  const estadoHoras = s => ({ vencido: ['rojo', `Vencido por ${miles(-s.faltan)} h`], proximo: ['ambar', `Faltan ${miles(s.faltan)} h`],
    sin_lectura: ['azul', 'Sin lectura de horómetro'], falta_dato: ['azul', 'Falta el próximo inicial en el Plan'] }[s.estado]);
  const MANT = ['Tarea', 'Equipo', 'Mantenimiento', 'Frecuencia'];
  $('#vista').innerHTML = `
    <div class="encabezado"><h2>Hoy, ${hoy.getDate()} de ${MESES_LARGOS[hoy.getMonth()]}</h2>
      <div class="botones"><button class="primario" onclick="modalRegistro()">Registrar mantenimiento</button>
      <button onclick="modalCorrectivo()">Registrar correctivo</button>
      <button onclick="imprimirListaDelMes()">Imprimir lista del mes</button></div></div>
    ${hojaListaDelMes(p, hoy)}
    <div class="tarjeta inicio-cumplimiento"><h3>Cumplimiento ${hoy.getFullYear()}</h3>
      <span class="numero-grande">${c.porcentaje == null ? '—' : c.porcentaje + ' %'}</span>
      <span class="sutil">${c.esperadas ? `${c.cumplidas} de ${c.esperadas} servicios de los meses cerrados: ${c.a_tiempo} a tiempo (${c.porcentaje_a_tiempo} %) y ${c.cumplidas - c.a_tiempo} fuera de término.`
        : 'Todavía no cerró ningún mes desde que las tareas están en el Plan.'}</span></div>
    <div class="tarjeta"><h3>Este mes <span class="chip azul">${p.este_mes.length}</span></h3>
      ${tabla([...MANT, 'Pendiente', 'Responsable', ''], p.este_mes.map(t => fila(t, t.faltan > 1 ? `faltan ${t.faltan}` : '')), 'Nada pendiente.')}</div>
    <div class="tarjeta"><h3>Atrasados <span class="chip ${p.atrasados.length ? 'rojo' : 'verde'}">${p.atrasados.length}</span></h3>
      ${tabla([...MANT, 'De', 'Responsable', ''], p.atrasados.map(t => fila(t, MESES_LARGOS[t.mes - 1])), 'Nada atrasado.')}</div>
    <div class="tarjeta"><h3>Servicios por horas <span class="chip ${p.por_horas.some(s => s.estado === 'vencido') ? 'rojo' : 'azul'}">${p.por_horas.length}</span></h3>
      ${tabla(['Tarea', 'Equipo', 'Mantenimiento', 'Cada', 'Última lectura', 'Próximo a', 'Estado', ''], p.por_horas.map(s => {
        const [col, txt] = estadoHoras(s);
        return `<tr><td><b>${esc(s.codigo)}</b></td><td>${esc(s.equipo)}</td><td>${esc(s.seccion)}</td><td>${miles(s.cada_horas)} h</td>
          <td>${s.ultima_lectura == null ? '—' : miles(s.ultima_lectura) + ' h'}</td><td>${s.proximo == null ? '—' : miles(s.proximo) + ' h'}</td>
          <td><span class="chip ${col}">${txt}</span></td>${registrar(s.tarea_id)}</tr>`;
      }), 'Ninguno cerca de vencer.')}
      <p><a onclick="irA('horometros')">Ver horómetros</a></p></div>`;
};

/** La lista del mes para llevar al taller: en pantalla no se ve, y al imprimir reemplaza a todo lo demás.
 *  Las columnas de la derecha quedan en blanco para completarlas a mano y registrarlas después. */
function hojaListaDelMes(p, hoy) {
  const blancos = '<td class="casilla">☐</td><td></td><td></td><td></td>';
  const fila = (codigo, equipo, seccion, cuando, responsable) => `<tr><td><b>${esc(codigo)}</b></td><td>${esc(equipo)}</td>
    <td>${esc(seccion)}</td><td>${esc(cuando)}</td><td>${esc(responsable || '')}</td>${blancos}</tr>`;
  const filas = [
    ...p.atrasados.map(t => fila(t.codigo, t.equipo, t.seccion, `${t.frecuencia} · atrasada de ${MESES_LARGOS[t.mes - 1].toLowerCase()}`, t.responsable)),
    ...p.este_mes.map(t => fila(t.codigo, t.equipo, t.seccion, t.frecuencia + (t.faltan > 1 ? ` · ${t.faltan} veces` : ''), t.responsable)),
    ...p.por_horas.filter(s => s.estado === 'vencido' || s.estado === 'proximo').map(s => fila(s.codigo, s.equipo, s.seccion,
      `c/ ${miles(s.cada_horas)} h · ${s.estado === 'vencido' ? 'vencido' : 'a las ' + miles(s.proximo) + ' h'}`, s.responsable)),
  ];
  return `<div class="hoja-lista">
    <h2>Tareas de mantenimiento · ${MESES_LARGOS[hoy.getMonth()]} ${hoy.getFullYear()}</h2>
    <p class="sutil">Impreso el ${hoy.toLocaleDateString('es-AR')}. Marcar lo hecho y registrarlo después en la app.</p>
    <table><thead><tr><th>Tarea</th><th>Equipo</th><th>Mantenimiento</th><th>Frecuencia</th><th>Responsable</th>
      <th>Hecho</th><th class="fecha">Fecha</th><th class="realizo">Realizó</th><th class="obs">Observaciones</th></tr></thead>
    <tbody>${filas.join('') || '<tr><td colspan="9" class="vacio">No hay tareas pendientes este mes.</td></tr>'}</tbody></table></div>`;
}

function imprimirListaDelMes() {
  document.body.classList.add('imprimiendo-lista');
  addEventListener('afterprint', () => document.body.classList.remove('imprimiendo-lista'), { once: true });
  print();
}

// ── CRONOGRAMA ──
const SIMBOLO = { hecho: '✓', tarde: '✓', extra: '✓', cubre: '↩', vencido: '✗', pendiente: '○', reprogramado: '↻', no_realizado: '✗',
  no_aplica: '–', antes_alta: '·', vacio: '' };
const NOMBRE_ESTADO = { tarde: 'cumplido fuera de término', cubre: 'hecho acá, cubre un mes atrasado', antes_alta: 'antes de cargar la tarea' };
VISTAS.cronograma = async () => {
  const c = await api('/api/cronograma?anio=' + S.anio);
  const hoy = new Date(c.hoy + 'T00:00');
  const mesActual = hoy.getFullYear() === S.anio ? hoy.getMonth() : -1;
  let anterior = null;
  const filas = c.filas.map(f => {
    const nuevo = f.equipo_codigo !== anterior; anterior = f.equipo_codigo;
    const celdas = f.celdas.map((x, i) => {
      const txt = x.esperado > 1 ? `${x.hechos}/${x.esperado}` : SIMBOLO[x.estado];
      const tip = `${MESES_LARGOS[i]}: ${NOMBRE_ESTADO[x.estado] || x.estado.replace('_', ' ')}${x.detalle ? ' (' + x.detalle + ')' : ''}`;
      return `<td class="mes c-${x.estado}" title="${esc(tip)}" onclick="clicCelda(${f.tarea_id}, ${i + 1})">${txt}</td>`;
    }).join('');
    const freq = f.frecuencia === 'Por horas' ? `c/ ${miles(f.cada_horas)} h` : f.frecuencia;
    return `<tr class="${nuevo ? 'nuevo-equipo' : ''}"><td><b>${esc(f.codigo)}</b></td><td>${nuevo ? esc(f.equipo) : ''}</td>
      <td><a onclick="irA('instructivos/${f.instructivo_id}')">${esc(f.seccion)}</a></td><td>${esc(freq)}</td><td>${esc(f.responsable || '')}</td>${celdas}</tr>`;
  }).join('');
  const cu = c.cumplimiento;
  $('#vista').innerHTML = `
    <div class="encabezado"><h2>Cronograma ${S.anio}</h2>
      <div class="botones"><button onclick="S.anio--; irA('cronograma')">◄ ${S.anio - 1}</button>
        <button onclick="S.anio++; irA('cronograma')">${S.anio + 1} ►</button>
        <span class="chip ${cu.porcentaje == null ? '' : cu.porcentaje >= 90 ? 'verde' : cu.porcentaje >= 70 ? 'ambar' : 'rojo'}">Cumplimiento: ${cu.porcentaje == null ? '—' : cu.porcentaje + ' %'} (${cu.cumplidas}/${cu.esperadas})${cu.porcentaje == null ? '' : ` · a tiempo ${cu.porcentaje_a_tiempo} %`}</span>
        <button onclick="window.print()">Imprimir</button></div></div>
    <div class="tarjeta tabla-wrap"><table class="crono">
      <thead><tr><th>ID</th><th>Equipo</th><th>Mant.</th><th>Frecuencia</th><th>Responsable</th>
        ${MESES.map((m, i) => `<th class="mes ${i === mesActual ? 'actual' : ''}">${m}</th>`).join('')}</tr></thead>
      <tbody>${filas || '<tr><td colspan="17" class="vacio">No hay tareas en el Plan.</td></tr>'}</tbody></table>
      <div class="leyenda">
        <span><b class="c-pendiente">○</b> programado</span><span><b class="c-hecho">✓</b> hecho</span><span><b class="c-tarde">✓</b> fuera de término</span><span><b class="c-cubre">↩</b> hecho acá, cubre uno atrasado</span>
        <span><b class="c-vencido">✗</b> vencido</span><span><b class="c-reprogramado">↻</b> reprogramado</span>
        <span><b class="c-no_realizado">✗</b> no realizado</span><span><b class="c-no_aplica">–</b> no aplica</span>
        <span><b class="c-antes_alta">·</b> antes de cargar la tarea</span><span>Clic en un mes para registrar.</span></div></div>`;
};

function clicCelda(tareaId, mes) {
  // sugiere hoy si es el mes en curso; si no, el día 1 de ese mes (sin pasar de hoy)
  const hoy = hoyISO();
  const sugerida = `${S.anio}-${String(mes).padStart(2, '0')}-01`;
  modalRegistro(tareaId, hoy.slice(0, 7) === sugerida.slice(0, 7) || sugerida > hoy ? hoy : sugerida);
}

// ── REGISTROS ──
VISTAS.registros = async () => {
  const regs = await api('/api/registros?anio=' + S.anio);
  const color = { 'Realizado': 'verde', 'Con observaciones': 'verde', 'No realizado': 'rojo', 'Reprogramado': 'ambar' };
  $('#vista').innerHTML = `
    <div class="encabezado"><h2>Registros ${S.anio}</h2>
      <div class="botones"><button onclick="S.anio--; irA('registros')">◄</button><button onclick="S.anio++; irA('registros')">►</button>
      <button onclick="modalLectura()">Registrar lectura de horómetro</button>
      <button class="primario" onclick="modalRegistro()">Registrar mantenimiento</button></div></div>
    <div class="tarjeta tabla-wrap"><table><thead><tr><th>Fecha</th><th>Tarea</th><th>Equipo</th><th>Mant.</th><th>Resultado</th>
      <th>Realizado por</th><th>HH</th><th>Horómetro</th><th>Novedades</th><th>Repuestos</th><th></th></tr></thead><tbody>
      ${regs.map(r => `<tr><td>${fecha(r.fecha)}</td><td>${esc(r.tarea)}</td><td>${esc(r.equipo)}</td><td>${esc(r.seccion)}</td>
        <td><span class="chip ${color[r.resultado] || ''}">${esc(r.resultado)}</span>${r.reprogramado_para ? '<br><span class="sutil">→ ' + fecha(r.reprogramado_para) + '</span>' : ''}</td>
        <td>${esc(r.realizado_por || '')}</td><td>${r.horas_hombre ?? ''}</td><td>${r.horometro != null ? miles(r.horometro) : ''}</td>
        <td>${esc(r.novedades)}</td><td>${esc(r.repuestos)}</td>
        <td>${soloAdmin(`<button class="chico peligro" title="Borrar un registro cargado por error" onclick="anularRegistro(${r.id})">Anular</button>`)}</td></tr>`).join('')
        || '<tr><td colspan="11" class="vacio">Sin registros este año.</td></tr>'}
    </tbody></table></div>`;
};

async function anularRegistro(id) {
  if (!confirm('¿Anular este registro? Es para corregir una carga equivocada: se borra junto con su lectura de horómetro.')) return;
  try { await api('/api/registros/' + id, { metodo: 'DELETE' }); avisar('Registro anulado.'); irA('registros'); }
  catch (e) { avisar(e.message, true); }
}

// ── HORÓMETROS: el cronograma de los servicios por horas (solo vista; las lecturas se cargan en Registros) ──
const SIMBOLO_H = { hecho: '✓', tarde: '✗', vencido: '✗', proximo: '○', programado: '○', vacio: '' };
const CLASE_H = { hecho: 'c-hecho', tarde: 'c-vencido', vencido: 'c-vencido', proximo: 'c-reprogramado', programado: 'c-pendiente', vacio: '' };
S.corrimiento = 0;
VISTAS.horometros = async () => {
  const [equipos, lecturas] = await Promise.all([api('/api/horometros/grilla?corrimiento=' + S.corrimiento), api('/api/lecturas')]);
  const chip = f => ({ al_dia: ['verde', `Faltan ${miles(f.faltan)} h`], proximo: ['ambar', `Faltan ${miles(f.faltan)} h`],
    vencido: ['rojo', `Vencido por ${miles(-f.faltan)} h`], sin_lectura: ['azul', 'Sin lectura'], falta_dato: ['azul', 'Falta dato'] }[f.estado]);
  const tarjeta = e => {
    const cab = `<h3>${esc(e.codigo)} · ${esc(e.nombre)}</h3>
      <p>Última lectura: <b>${miles(e.ultima_lectura)} h</b> ${e.fecha_lectura ? '<span class="sutil">(' + fecha(e.fecha_lectura) + ')</span>' : ''}</p>`;
    if (!e.filas.length) return `<div class="tarjeta">${cab}<p class="sutil">Sin servicios por horas en el Plan.</p></div>`;
    const filas = e.filas.map(f => {
      const [col, txt] = chip(f);
      return `<tr><td><b>${esc(f.codigo)}</b></td><td><a onclick="irA('instructivos/${f.instructivo_id}')">${esc(f.seccion)}</a></td>
        <td>c/ ${miles(f.cada_horas)} h</td><td>${miles(f.proximo)} h<br><span class="chip ${col}">${txt}</span></td>
        ${f.celdas.map(c => `<td class="mes ${CLASE_H[c.estado]}" title="${esc(c.detalle.join('\n'))}" onclick="modalRegistro(${f.tarea_id})">${SIMBOLO_H[c.estado]}</td>`).join('')}</tr>`;
    }).join('');
    return `<div class="tarjeta tabla-wrap">${cab}<table class="crono"><thead><tr><th>ID</th><th>Mant.</th><th>Frecuencia</th><th>Próximo</th>
      ${e.bloques.map((b, i) => `<th class="mes ${i === e.actual ? 'actual' : ''}" title="${miles(b)} a ${miles(b + (e.bloques[1] - e.bloques[0]) - 1)} h">${b >= 10000 ? (b / 1000).toLocaleString('es-AR') + 'k' : miles(b)}${i === e.actual ? '<br>▲' : ''}</th>`).join('')}
      </tr></thead><tbody>${filas}</tbody></table></div>`;
  };
  $('#vista').innerHTML = `
    <div class="encabezado"><h2>Horómetros</h2>
      <div class="botones"><button onclick="S.corrimiento -= 6; irA('horometros')">◄ horas antes</button>
        <button onclick="S.corrimiento = 0; irA('horometros')">Ahora</button>
        <button onclick="S.corrimiento += 6; irA('horometros')">horas después ►</button>
        ${soloAdmin('<button onclick="modalCambioHorometro()">Cambio de horómetro</button>')}</div></div>
    <p class="sutil">Como el cronograma, pero para los servicios por uso: cada columna es un bloque de horas del horómetro (▲ = la última lectura).
      Las lecturas se cargan en Registros: al registrar un servicio o con "Registrar lectura de horómetro".</p>
    ${equipos.map(tarjeta).join('') || '<p class="sutil">Ningún equipo tiene horómetro.</p>'}
    <div class="leyenda tarjeta"><span><b class="c-hecho">✓</b> hecho</span><span><b class="c-reprogramado">○</b> próximo, cerca</span>
      <span><b class="c-pendiente">○</b> programado</span><span><b class="c-vencido">✗</b> vencido o hecho tarde</span>
      <span>Pasar el mouse por una celda para ver el detalle; clic para registrar.</span></div>
    <div class="tarjeta tabla-wrap"><h3>Últimas lecturas</h3><table><thead><tr><th>Fecha</th><th>Equipo</th><th>Horómetro</th><th>Anotó</th><th>Observaciones</th></tr></thead><tbody>
      ${lecturas.map(l => `<tr><td>${fecha(l.fecha)}</td><td>${esc(l.equipo_codigo)} · ${esc(l.equipo)}</td>
        <td>${miles(l.horas)} h${l.cambio ? ` <span class="chip ambar" title="${l.horas_anterior == null ? '' : 'El anterior marcaba ' + miles(l.horas_anterior) + ' h'}">horómetro nuevo</span>` : ''}</td>
        <td>${esc(l.anoto || '')}</td><td>${esc(l.observaciones)}</td></tr>`).join('') || '<tr><td colspan="5" class="vacio">Sin lecturas.</td></tr>'}</tbody></table></div>`;
};

/** Lectura suelta del horómetro, sin servicio: mantiene al día cuánto falta para el próximo. */
function modalLectura() {
  const equipos = S.opciones.equipos.filter(e => e.usa_horometro);
  abrirModal(`
    <h2>Registrar lectura de horómetro</h2>
    <form id="f-lectura"><div class="campos">
      <label class="ancho">Equipo <select name="equipo_id">${opcionesSelect(equipos.map(e => [e.id, `${e.codigo} · ${e.nombre}`]), equipos.length === 1 ? equipos[0].id : '', '— elegir —')}</select></label>
      <label>Fecha <input type="date" name="fecha" value="${hoyISO()}" max="${hoyISO()}"></label>
      <label>Horómetro (h) <input name="horas" type="number" min="0" step="1" required></label>
      <label>Anotó <select name="anoto_id">${personasSelect('', '—', 'general')}</select></label>
      <label class="ancho">Observaciones <input name="observaciones"></label>
    </div><p class="sutil">Si se hizo un servicio, registrarlo con "Registrar mantenimiento": su lectura se anota sola.</p><p class="error"></p>
    <div class="botones"><button class="primario" type="submit">Guardar</button><button type="button" onclick="cerrarModal()">Cancelar</button></div></form>`);
  const f = $('#f-lectura');
  f.addEventListener('submit', ev => {
    ev.preventDefault();
    enviar(f, async d => {
      if (!d.equipo_id) throw new Error('Elegir el equipo.');
      await api(`/api/equipos/${d.equipo_id}/lecturas`, { metodo: 'POST', datos: d });
      cerrarModal(); avisar('Lectura guardada.'); irA(location.hash.slice(1) || 'registros');
    });
  });
}

/** El horómetro se rompió o se cambió: el nuevo arranca de otro número y los servicios por horas se corren a esa escala. */
function modalCambioHorometro() {
  const equipos = S.opciones.equipos.filter(e => e.usa_horometro);
  abrirModal(`
    <h2>Cambio de horómetro</h2>
    <p class="sutil">Desde esta fecha las lecturas son del horómetro nuevo. A cada servicio por horas le queda lo mismo que le faltaba
      con el viejo: si al B le faltaban 300 h, queda a 300 h de lo que marca el nuevo.</p>
    <form id="f-cambio"><div class="campos">
      <label class="ancho">Equipo <select name="equipo_id">${opcionesSelect(equipos.map(e => [e.id, `${e.codigo} · ${e.nombre}`]), equipos.length === 1 ? equipos[0].id : '', '— elegir —')}</select></label>
      <label>Fecha del cambio <input type="date" name="fecha" value="${hoyISO()}" max="${hoyISO()}"></label>
      <label>Marca el nuevo (h) <input name="horas" type="number" min="0" step="1" required></label>
      <label>Marcaba el viejo al sacarlo (h) <input name="horas_anterior" type="number" min="0" step="1" placeholder="si se sabe"></label>
      <label>Anotó <select name="anoto_id">${personasSelect('', '—', 'general')}</select></label>
      <label class="ancho">Observaciones <input name="observaciones" placeholder="por qué se cambió"></label>
    </div><p class="sutil">Si no se sabe cuánto marcaba el viejo al sacarlo, se usa su última lectura: las horas trabajadas desde entonces
      no se cuentan, y conviene revisar el próximo de cada servicio en el Plan.</p><p class="error"></p>
    <div class="botones"><button class="primario" type="submit">Guardar</button><button type="button" onclick="cerrarModal()">Cancelar</button></div></form>`);
  const f = $('#f-cambio');
  f.addEventListener('submit', ev => {
    ev.preventDefault();
    enviar(f, async d => {
      if (!d.equipo_id) throw new Error('Elegir el equipo.');
      const r = await api(`/api/equipos/${d.equipo_id}/cambio-horometro`, { metodo: 'POST', datos: d });
      cerrarModal();
      const sin = r.servicios.filter(s => s.ahora == null).map(s => s.codigo);
      avisar(sin.length ? `Cambio guardado. Sin próximo (cargarlo en el Plan): ${sin.join(', ')}.` : 'Cambio de horómetro guardado.');
      recargarOpciones(); irA('horometros');
    });
  });
}

// ── CORRECTIVOS ──
function modalCorrectivo() {
  abrirModal(`
    <h2>Registrar correctivo</h2>
    <form id="f-correctivo"><div class="campos">
      <label>Equipo <select name="equipo_id" required>${opcionesSelect(S.opciones.equipos.map(e => [e.id, `${e.codigo} · ${e.nombre}`]), '', '— elegir —')}</select></label>
      <label>Fecha <input type="date" name="fecha" value="${hoyISO()}" max="${hoyISO()}"></label>
      <label class="ancho">Falla / síntoma <input name="falla" required></label>
      <label class="ancho">Causa <input name="causa"></label>
      <label class="ancho">Acción realizada <textarea name="accion"></textarea></label>
      <label>Horas de parada <input name="horas_parada" inputmode="decimal"></label>
      <label>Horas-hombre <input name="horas_hombre" inputmode="decimal"></label>
      <label>Realizado por <select name="realizado_por_id">${personasSelect('', '—')}</select></label>
      <label class="p-nombre oculto"><span>Nombre</span> <input name="realizado_por_nombre"></label>
      <label class="ancho">Repuestos utilizados <input name="repuestos"></label>
      <label class="ancho">Observaciones <input name="observaciones"></label>
      <label class="check ancho"><input type="checkbox" name="accion_sgc"> Requiere acción del SGC (abrir un RAC)</label>
    </div><p class="error"></p>
    <div class="botones"><button class="primario" type="submit">Guardar</button><button type="button" onclick="cerrarModal()">Cancelar</button></div></form>`);
  const f = $('#f-correctivo');
  casillaNombre(f);
  f.addEventListener('submit', ev => {
    ev.preventDefault();
    enviar(f, async d => {
      if (!d.equipo_id) throw new Error('Elegir el equipo.');
      await api(`/api/equipos/${d.equipo_id}/correctivos`, { metodo: 'POST', datos: d });
      cerrarModal(); avisar('Correctivo guardado.'); irA(location.hash.slice(1) || 'inicio');
    });
  });
}

VISTAS.correctivos = async () => {
  const lista = await api('/api/correctivos?anio=' + S.anio);
  const parada = lista.reduce((s, c) => s + (c.horas_parada || 0), 0);
  $('#vista').innerHTML = `
    <div class="encabezado"><h2>Correctivos ${S.anio}</h2>
      <div class="botones"><button onclick="S.anio--; irA('correctivos')">◄</button><button onclick="S.anio++; irA('correctivos')">►</button>
      <span class="chip">${lista.length} correctivos · ${parada.toLocaleString('es-AR')} h de parada</span>
      <button class="primario" onclick="modalCorrectivo()">Registrar correctivo</button></div></div>
    <div class="tarjeta tabla-wrap"><table><thead><tr><th>Fecha</th><th>Equipo</th><th>Sector</th><th>Falla</th><th>Causa</th><th>Acción</th>
      <th>Parada</th><th>HH</th><th>Repuestos</th><th>Realizado por</th><th>SGC</th></tr></thead><tbody>
      ${lista.map(c => `<tr><td>${fecha(c.fecha)}</td><td>${esc(c.equipo_codigo)} · ${esc(c.equipo)}</td><td>${esc(c.sector)}</td>
        <td>${esc(c.falla)}</td><td>${esc(c.causa)}</td><td>${esc(c.accion)}</td><td>${c.horas_parada ?? ''}</td><td>${c.horas_hombre ?? ''}</td>
        <td>${esc(c.repuestos)}</td><td>${esc(c.realizado_por || '')}</td><td>${c.accion_sgc ? '<span class="chip ambar">Sí</span>' : ''}</td></tr>`).join('')
        || '<tr><td colspan="11" class="vacio">Sin correctivos este año.</td></tr>'}</tbody></table></div>`;
};

// ── PLAN ──
VISTAS.plan = async () => {
  const tareas = await api('/api/tareas?baja=true');
  const cuando = t => t.frecuencia === 'Por horas' ? `cada ${miles(t.cada_horas)} h${t.proximo_inicial ? ' · 1º a ' + miles(t.proximo_inicial) + ' h' : ''}`
    : t.meses_especificos ? 'meses ' + t.meses_especificos.split(',').map(m => MESES[m - 1]).join(', ')
    : t.mes_inicio ? 'desde ' + MESES_LARGOS[t.mes_inicio - 1] : '';
  $('#vista').innerHTML = `
    <div class="encabezado"><h2>Plan de mantenimiento</h2>
      <div class="botones">${soloAdmin('<button class="primario" onclick="modalTarea()">Nueva tarea</button>')}</div></div>
    <p class="sutil">Cada tarea es una sección de un instructivo aplicada a un equipo, con su frecuencia. El cronograma sale de acá.</p>
    <div class="tarjeta tabla-wrap">${casillaOcultos('plan', tareas.filter(t => !t.activa).length)}<table ${tablaOcultos('plan')}><thead><tr><th>ID</th><th>Equipo</th><th>Mantenimiento</th><th>Frecuencia</th><th>Cuándo</th>
      <th>Responsable</th><th>Observaciones</th><th></th></tr></thead><tbody>
      ${tareas.map(t => `<tr class="${t.activa ? '' : 'baja'}"><td><b>${esc(t.codigo)}</b></td><td>${esc(t.equipo)}</td>
        <td><a onclick="irA('instructivos/${t.instructivo_id}')">${esc(t.seccion)}</a></td><td>${esc(t.frecuencia)}</td><td>${esc(cuando(t))}</td>
        <td>${esc(t.responsable || '')}</td><td>${esc(t.observaciones)}</td>
        <td class="botones">${soloAdmin(t.activa ? `<button class="chico" onclick="modalTarea(${t.id})">Editar</button>
          <button class="chico" onclick="altaTarea(${t.id}, false)">Dar de baja</button>` : `<button class="chico" onclick="altaTarea(${t.id}, true)">Reactivar</button>`)}</td></tr>`).join('')
        || '<tr><td colspan="8" class="vacio">El Plan está vacío.</td></tr>'}</tbody></table></div>`;
};

function modalTarea(id, seccionId) {
  const t = S.tareas.find(x => x.id === id) || { seccion_id: seccionId };
  if (!id && seccionId) {   // desde un instructivo: si aplica a un solo equipo, ya viene elegido
    const eqs = S.opciones.secciones.find(s => s.id === seccionId)?.equipo_ids || [];
    if (eqs.length === 1) t.equipo_id = eqs[0];
  }
  abrirModal(`
    <h2>${id ? 'Editar tarea ' + esc(t.codigo) : 'Nueva tarea del Plan'}</h2>
    <form id="f-tarea"><div class="campos">
      <label class="ancho">Equipo <select name="equipo_id">${opcionesSelect(S.opciones.equipos.map(e => [e.id, `${e.codigo} · ${e.nombre}${e.usa_horometro ? ' (con horómetro)' : ''}`]), t.equipo_id, '— elegir —')}</select></label>
      <label class="ancho">Mantenimiento (sección del instructivo)
        <select name="seccion_id">${opcionesSelect(S.opciones.secciones.map(s => [s.id, `${s.codigo} · ${s.titulo} — ${s.resumen || ''}`]), t.seccion_id, '— elegir —')}</select></label>
      <label>Frecuencia <select name="frecuencia">${opcionesSelect(S.opciones.frecuencias.map(f => [f, f]), t.frecuencia || 'Mensual', null)}</select></label>
      <label class="p-mes">Mes de inicio <select name="mes_inicio">${opcionesSelect(MESES_LARGOS.map((m, i) => [i + 1, m]), t.mes_inicio, '—')}</select></label>
      <label class="p-mes">Meses específicos (opcional) <input name="meses_especificos" value="${esc(t.meses_especificos || '')}" placeholder="ej. 3, 9"></label>
      <label class="p-horas">Cada (h) <input name="cada_horas" type="number" min="0" step="1" value="${t.cada_horas ?? ''}"></label>
      <label class="p-horas">Primer servicio a las (h) <input name="proximo_inicial" type="number" min="0" step="1" value="${t.proximo_inicial ?? ''}"></label>
      <label>Responsable <select name="responsable_id">${personasSelect(t.responsable_id, '—', 'general')}</select></label>
      <label class="ancho">Observaciones <input name="observaciones" value="${esc(t.observaciones || '')}"></label>
    </div><p class="error"></p>
    <div class="botones"><button class="primario" type="submit">Guardar</button><button type="button" onclick="cerrarModal()">Cancelar</button></div></form>`);
  const f = $('#f-tarea');
  // las secciones que ese equipo ya tiene en el Plan no se ofrecen (salvo la de la tarea que se está editando)
  const filtrarSecciones = () => {
    const eq = f.equipo_id.value, elegida = f.seccion_id.value;
    // solo secciones de los instructivos de ese equipo, y que no estén ya en su Plan
    const ocupadas = new Set(S.tareas.filter(x => x.activa && String(x.equipo_id) === eq && x.id !== id).map(x => x.seccion_id));
    const libres = eq ? S.opciones.secciones.filter(s => s.equipo_ids.includes(Number(eq)) && !ocupadas.has(s.id)) : [];
    if (!eq) { f.seccion_id.innerHTML = '<option value="">— elegir primero el equipo —</option>'; return; }
    f.seccion_id.innerHTML = opcionesSelect(libres.map(s => [s.id, `${s.codigo} · ${s.titulo} — ${s.resumen || ''}`]),
      libres.some(s => String(s.id) === elegida) ? elegida : '',
      libres.length ? '— elegir —' : S.opciones.secciones.some(s => s.equipo_ids.includes(Number(eq)))
        ? '— ya tiene todo programado —' : '— no tiene instructivos asignados (ver Equipos) —');
  };
  f.equipo_id.addEventListener('change', filtrarSecciones); filtrarSecciones();
  const ver = () => {
    const fr = f.frecuencia.value;
    f.querySelectorAll('.p-mes').forEach(el => el.classList.toggle('oculto', fr === 'Por horas' || fr === 'Según condición'));
    f.querySelectorAll('.p-horas').forEach(el => el.classList.toggle('oculto', fr !== 'Por horas'));
  };
  f.frecuencia.addEventListener('change', ver); ver();
  f.addEventListener('submit', ev => {
    ev.preventDefault();
    enviar(f, async d => {
      await api(id ? '/api/tareas/' + id : '/api/tareas', { metodo: id ? 'PUT' : 'POST', datos: d });
      await recargarOpciones(); cerrarModal(); avisar('Plan actualizado.'); irA(location.hash.slice(1));
    });
  });
}

async function altaTarea(id, activa) {
  if (!activa && !confirm('¿Dar de baja la tarea? Deja de aparecer en el cronograma; sus registros se conservan.')) return;
  try { await api(`/api/tareas/${id}/${activa ? 'alta' : 'baja'}`, { metodo: 'POST' }); await recargarOpciones(); irA('plan'); }
  catch (e) { avisar(e.message, true); }
}

// ── EQUIPOS y PERSONAS ──
VISTAS.equipos = async () => {
  const [equipos, instructivos] = await Promise.all([api('/api/equipos?baja=true'), api('/api/instructivos')]);
  const itPorId = Object.fromEntries(instructivos.map(i => [i.id, i]));
  // sus instructivos (cada uno es solo de este equipo), con las secciones que tiene en el Plan
  const instructivoDe = e => e.instructivo_ids.map(iid => {
    const it = itPorId[iid];
    if (!it) return '';
    const secs = S.tareas.filter(t => t.equipo_id === e.id && t.activa && t.instructivo_id === iid).map(t => t.seccion.split('-').pop());
    return `<b>${esc(it.codigo)}</b> <span class="sutil">Rev. ${it.revision} · ${secs.length ? 'en el Plan: ' + secs.join(', ') : 'sin programar'}</span>
      ${it.vigente ? '' : ' <span class="chip rojo">obsoleto</span>'}`;
  }).filter(Boolean).join('<br>') || '<span class="chip ambar">sin instructivo</span>';
  const botonIt = e => e.instructivo_ids.length
    ? e.instructivo_ids.map(iid => `<button class="chico primario" onclick="irA('instructivos/${iid}')">Ver instructivo${e.instructivo_ids.length > 1 ? ' ' + esc(itPorId[iid]?.codigo || '') : ''}</button>`).join(' ')
    : soloAdmin(e.activo ? `<button class="chico primario" onclick="crearInstructivoDe(${e.id})">Crear instructivo</button>` : '');
  const asignados = new Set(equipos.flatMap(e => e.instructivo_ids));
  const sueltos = instructivos.filter(i => !asignados.has(i.id));
  $('#vista').innerHTML = `
    <div class="encabezado"><h2>Equipos e instructivos</h2><div class="botones">${soloAdmin('<button class="primario" onclick="modalEquipo()">Nuevo equipo</button>')}</div></div>
    <p class="sutil">Cada equipo tiene su instructivo: al dar de alta un equipo se crea a continuación. Un equipo que ya no está se
      <b>marca obsoleto</b> (su historial queda guardado); <b>Eliminar</b> es solo para uno cargado por error y aparece si no tiene nada vinculado.</p>
    <div class="tarjeta tabla-wrap">${casillaOcultos('equipos', equipos.filter(e => !e.activo).length)}<table ${tablaOcultos('equipos')}>
      <thead><tr><th>Código</th><th>Equipo</th><th>Sector</th><th>Marca / modelo</th><th>Horómetro</th><th>Instructivo</th><th>Estado</th><th></th></tr></thead><tbody>
      ${equipos.map(e => `<tr class="${e.activo ? '' : 'baja'}"><td><b>${esc(e.codigo)}</b></td><td>${esc(e.nombre)}</td><td>${esc(e.sector)}</td>
        <td>${esc(e.marca_modelo)}</td><td>${e.usa_horometro ? 'Sí' : 'No'}</td><td>${instructivoDe(e)}</td>
        <td>${e.activo ? '<span class="chip verde">Vigente</span>'
          : `<span class="chip rojo">Obsoleto</span><br><span class="sutil">${fecha(e.fecha_baja)}${e.motivo_baja ? ' · ' + esc(e.motivo_baja) : ''}</span>`}</td>
        <td class="botones">${botonIt(e)}
          ${soloAdmin(e.activo
            ? `<button class="chico" onclick="modalEquipo(${e.id})">Editar</button>
               <button class="chico" onclick="obsoletoEquipo(${e.id})">Marcar obsoleto</button>`
            : `<button class="chico" onclick="reactivarEquipo(${e.id})">Reactivar</button>`)}
          ${soloAdmin(e.vinculos ? '' : `<button class="chico peligro" onclick="eliminarEquipo(${e.id})">Eliminar</button>`)}</td></tr>`).join('')}
    </tbody></table></div>
    ${sueltos.length ? `<p class="sutil">Instructivos sin equipo asignado: ${sueltos.map(i =>
      `<a onclick="irA('instructivos/${i.id}')">${esc(i.codigo)} · ${esc(i.titulo)}</a>${i.vigente ? '' : ' (obsoleto)'}`).join(' · ')}.
      Se asignan desde Editar del equipo.</p>` : ''}`;
  S.equipos = equipos;
};

/** El instructivo de un equipo que todavía no tiene: el editor de alta, con el título ya puesto. */
function crearInstructivoDe(equipoId) {
  editarInstructivo(undefined, instructivoPara(S.equipos.find(x => x.id === equipoId)));
}

/** El instructivo nuevo de un equipo arranca con lo que se cargó del equipo: título, descripción y una ficha técnica.
 *  Es un punto de partida: se puede retocar antes de guardar. */
function instructivoPara(e) {
  const modelo = e.nombre + (e.marca_modelo ? ' ' + e.marca_modelo : '');
  return {
    equipo_id: e.id, codigo: e.codigo, titulo: modelo,
    descripcion: `Mantenimiento preventivo de ${modelo}${e.sector ? ', sector ' + e.sector : ''}.`,
    bloques: [{ tipo: 'tabla', ubicacion: 'general', datos: { titulo: 'Datos del equipo', encabezado: false, filas: [
      ['Código', e.codigo], ['Equipo', e.nombre], ['Sector', e.sector || '—'], ['Marca / modelo', e.marca_modelo || '—'],
      ['Horómetro', e.usa_horometro ? 'Sí: se anota la lectura en cada servicio' : 'No']] } }],
  };
}

/** Áreas para elegir: las de alta, más la que ya tenga el equipo; el admin puede crear una nueva desde ahí. */
function opcionesArea(actual) {
  const areas = S.opciones.areas.filter(a => a.activo || a.id === actual);
  return opcionesSelect(areas.map(a => [a.id, a.nombre + (a.activo ? '' : ' (de baja)')]), actual, '—')
    + (S.usuario.es_admin ? '<option value="__nueva">+ Nueva área…</option>' : '');
}

async function modalEquipo(id) {
  const [equipos, instructivos] = await Promise.all([api('/api/equipos?baja=true'), api('/api/instructivos')]);
  const e = id ? equipos.find(x => x.id === id) : { instructivo_ids: [] };
  const itPorId = Object.fromEntries(instructivos.map(i => [i.id, i]));
  // para "parecido a otro equipo": los equipos vigentes con instructivo vigente (puede haber cientos: se busca escribiendo).
  // Los equipos no comparten instructivo: del elegido se COPIA, y la copia es del equipo nuevo.
  const modelos = equipos.filter(x => x.activo && x.id !== id && x.instructivo_ids.some(i => itPorId[i]?.vigente));
  const textoModelo = x => `${x.codigo} · ${x.nombre}${x.marca_modelo ? ' ' + x.marca_modelo : ''} — ${x.instructivo_ids.map(i => itPorId[i]?.codigo).filter(Boolean).join(', ')}`;
  const propios = e.instructivo_ids.map(i => itPorId[i]).filter(Boolean);
  const asignados = new Set(equipos.flatMap(x => x.instructivo_ids));
  const sueltos = instructivos.filter(i => i.vigente && !asignados.has(i.id));   // sin equipo: se pueden asignar
  const copiar = `<div class="campos"><label class="ancho">${id ? 'Copiar el instructivo de un equipo parecido (opcional)' : '¿Es parecido a otro equipo? Copiar su instructivo (opcional)'}
      <input name="igual_a" list="eq-iguales" autocomplete="off" placeholder="Escribí el código o el nombre para buscar">
      <datalist id="eq-iguales">${modelos.map(x => `<option value="${esc(textoModelo(x))}">`).join('')}</datalist></label></div>`;
  abrirModal(`
    <h2>${id ? 'Editar ' + esc(e.codigo) : 'Nuevo equipo'}</h2>
    <form id="f-equipo"><div class="campos">
      <label class="ancho">Nombre <input name="nombre" value="${esc(e.nombre || '')}" required></label>
      <label>Área <select name="area_id">${opcionesArea(e.area_id)}</select></label>
      <label>Marca / modelo <input name="marca_modelo" value="${esc(e.marca_modelo || '')}"></label>
      <label class="check ancho"><input type="checkbox" name="usa_horometro" ${e.usa_horometro ? 'checked' : ''}> Tiene horómetro (se pide la lectura en cada servicio)</label>
    </div>
    ${id ? `<h3>Instructivo</h3>
      ${propios.length ? `<div class="campos">${propios.map(i => `<label class="check"><input type="checkbox" name="it_${i.id}" checked>
          ${esc(i.codigo)} · ${esc(i.titulo)}${i.vigente ? '' : ' <span class="chip rojo">obsoleto</span>'}</label>`).join('')}</div>
        <p class="sutil">Desmarcar solo para dejar de usarlo en este equipo (no se puede si tiene tareas activas en el Plan): queda como instructivo sin equipo.</p>`
        : `<p class="sutil">Todavía no tiene instructivo: se crea con "Crear instructivo" en la tabla, o se copia el de un equipo parecido acá abajo.</p>${copiar}`}
      ${sueltos.length ? `<div class="campos"><label class="ancho">Asignar un instructivo sin equipo (opcional)
        <select name="suelto">${opcionesSelect(sueltos.map(i => [i.id, `${i.codigo} · ${i.titulo}`]), '', '—')}</select></label></div>` : ''}` : copiar}
    <p class="sutil">${id ? '' : 'Si es parecido a uno que ya está, elegilo: el equipo nuevo arranca con una <b>copia</b> de su instructivo, que después se ajusta sin tocar el original. '
      + 'Si lo dejás vacío, al guardar se abre el instructivo nuevo para cargarlo. El código (EQ-…) se asigna solo.'}</p>
    <p class="error"></p>
    <div class="botones"><button class="primario" type="submit">Guardar</button><button type="button" onclick="cerrarModal()">Cancelar</button></div></form>`);
  const f = $('#f-equipo');
  // "+ Nueva área…": se crea ahí mismo y queda elegida
  f.area_id.addEventListener('change', async () => {
    if (f.area_id.value !== '__nueva') return;
    const nombre = prompt('Nombre del área nueva (ej. Moldeo, Fusión):');
    try {
      const a = nombre ? await api('/api/areas', { metodo: 'POST', datos: { nombre } }) : null;
      if (a) S.opciones.areas.push(a);
      f.area_id.innerHTML = opcionesArea(a ? a.id : e.area_id);
    } catch (err) { avisar(err.message, true); f.area_id.innerHTML = opcionesArea(e.area_id); }
  });
  f.addEventListener('submit', ev => {
    ev.preventDefault();
    enviar(f, async d => {
      // se resuelve antes de guardar nada: un texto que no es de la lista no puede dejar un equipo a medias
      const buscado = (d.igual_a || '').trim();
      const modelo = buscado ? modelos.find(x => textoModelo(x) === buscado) : null;
      if (buscado && !modelo) throw new Error('Equipo parecido: elegí uno de la lista que aparece al escribir, o dejalo vacío.');
      let guardado, copias = [];
      try {
        if (!id) {   // alta: la copia va en la misma operación, así no queda un equipo creado a medias
          guardado = await api('/api/equipos', { metodo: 'POST', datos: { ...d, copiar_de: modelo?.id } });
          copias = guardado.instructivos_copiados;
        } else {
          guardado = await api('/api/equipos/' + id, { metodo: 'PUT', datos: d });
          const ids = [...propios.filter(i => d['it_' + i.id]).map(i => i.id), ...(d.suelto ? [Number(d.suelto)] : [])];
          await api(`/api/equipos/${id}/instructivos`, { metodo: 'PUT', datos: { instructivo_ids: ids } });
          if (modelo) copias = (await api(`/api/equipos/${id}/copiar-instructivo`, { metodo: 'POST', datos: { desde: modelo.id } })).instructivos_copiados;
        }
      } finally { await recargarOpciones(); }
      cerrarModal();
      if (copias.length) {   // se abre la copia para revisarla: es del equipo nuevo y se ajusta sin tocar el original
        avisar(`${guardado.codigo}: se copió ${copias.map(x => x.desde).join(', ')} como ${copias.map(x => x.codigo).join(', ')}. Revisalo y, con Modificar, ajustá lo que cambie.`);
        return irA('instructivos/' + copias[0].id);
      }
      if (!id) {   // equipo nuevo, sin parecido: se crea su instructivo
        avisar(`${guardado.codigo} creado. Ahora cargá su instructivo.`);
        return editarInstructivo(undefined, instructivoPara(guardado));
      }
      avisar('Equipo guardado.'); irA('equipos');
    });
  });
}

async function obsoletoEquipo(id) {
  const e = S.equipos.find(x => x.id === id);
  const tareas = S.tareas.filter(t => t.equipo_id === id && t.activa).map(t => t.codigo);
  const motivo = prompt(`Marcar obsoleto ${e.codigo} · ${e.nombre}.\n` +
    (tareas.length ? `Se darán de baja sus tareas del Plan: ${tareas.join(', ')}.\n` : '') +
    'Su historial queda guardado. Motivo (ej. se vendió, se desarmó):');
  if (!motivo) return;
  try {
    const r = await api(`/api/equipos/${id}/obsoleto`, { metodo: 'POST', datos: { motivo } });
    await recargarOpciones();
    avisar(`${e.codigo} marcado obsoleto` + (r.tareas_dadas_de_baja.length ? ` y ${r.tareas_dadas_de_baja.length} tarea(s) dadas de baja.` : '.'));
    irA('equipos');
  } catch (err) { avisar(err.message, true); }
}

async function reactivarEquipo(id) {
  try { await api(`/api/equipos/${id}/alta`, { metodo: 'POST' }); await recargarOpciones(); avisar('Equipo reactivado. Sus tareas se reactivan desde el Plan.'); irA('equipos'); }
  catch (e) { avisar(e.message, true); }
}

async function eliminarEquipo(id) {
  const e = S.equipos.find(x => x.id === id);
  if (!confirm(`Eliminar ${e.codigo} · ${e.nombre}: es solo para un equipo cargado por error y se borra sin dejar rastro. ¿Eliminar?`)) return;
  try { await api('/api/equipos/' + id, { metodo: 'DELETE' }); await recargarOpciones(); avisar('Equipo eliminado.'); irA('equipos'); }
  catch (err) { avisar(err.message, true); }
}

// ── PERSONAL: operarios y proveedores, con el seguimiento de lo que hizo cada uno ──
VISTAS.personal = async () => {
  const lista = await api('/api/personas/seguimiento?anio=' + S.anio);
  const tarjeta = (cat, titulo) => {
    const ps = lista.filter(p => p.categoria === cat);
    const externo = cat === 'externo';
    const filas = ps.map(p => {
      const nombre = p.pide_nombre
        ? `<i>Otros, sin dar de alta</i>${p.nombres_libres.length ? `<br><span class="sutil">Escritos a mano: ${p.nombres_libres.map(esc).join(', ')}</span>` : ''}`
        : `<b>${esc(p.nombre)}</b>${p.usuario_legajo ? ` <span class="chip azul" title="Usuario del sistema: nombre y alta se manejan en Usuarios">usuario · leg. ${p.usuario_legajo}</span>` : ''}${p.contacto ? `<br><span class="sutil">${esc(p.contacto)}</span>` : ''}`;
      const total = p.preventivos + p.correctivos;
      return `<tr class="${p.activo ? '' : 'baja'}"><td>${nombre}</td><td>${p.preventivos}</td><td>${p.correctivos}</td>
        <td>${p.horas_hombre ? p.horas_hombre.toLocaleString('es-AR') : ''}</td><td>${fecha(p.ultimo)}</td>
        <td class="botones">${total ? `<button class="chico" onclick="verTrabajos(${p.id})">Ver trabajos</button>` : ''}
          ${p.pide_nombre ? '' : soloAdmin(`<button class="chico" onclick="modalPersona('${cat}', ${p.id})">Editar</button>
            ${p.usuario_legajo ? '' : `<button class="chico" onclick="altaPersona(${p.id}, ${!p.activo})">${p.activo ? 'Dar de baja' : 'Reactivar'}</button>`}`)}</td></tr>`;
    }).join('');
    return `<div class="tarjeta tabla-wrap"><div class="botones" style="justify-content:space-between"><h3>${titulo}</h3>
        ${soloAdmin(`<button class="primario chico" onclick="modalPersona('${cat}')">${externo ? 'Nuevo proveedor' : 'Nuevo operario'}</button>`)}</div>
      ${casillaOcultos('personal-' + cat, ps.filter(p => !p.activo).length)}
      <table ${tablaOcultos('personal-' + cat)}><thead><tr><th>${externo ? 'Proveedor' : 'Operario'}</th><th>Preventivos</th><th>Correctivos</th><th>HH</th><th>Último</th><th></th></tr></thead>
      <tbody>${filas}</tbody></table></div>`;
  };
  $('#vista').innerHTML = `
    <div class="encabezado"><h2>Personal y proveedores ${S.anio}</h2>
      <div class="botones"><button onclick="S.anio--; irA('personal')">◄</button><button onclick="S.anio++; irA('personal')">►</button></div></div>
    <p class="sutil">Quiénes hacen los trabajos y cuántos hicieron en el año. Los usuarios del sistema aparecen solos en Mantenimiento interno. Al registrar se elige de estas listas;
      si alguien no está, se usa "Otro" y se escribe el nombre: aparece acá abajo de su categoría, para darlo de alta.</p>
    ${tarjeta('interno', 'Mantenimiento interno')}${tarjeta('externo', 'Proveedores externos')}`;
};

function modalPersona(categoria, id) {
  const p = id ? S.opciones.personas.find(x => x.id === id) : {};
  const externo = categoria === 'externo';
  abrirModal(`
    <h2>${id ? 'Editar ' + esc(p.nombre) : externo ? 'Nuevo proveedor externo' : 'Nuevo operario de mantenimiento'}</h2>
    <form id="f-persona"><input type="hidden" name="categoria" value="${categoria}"><div class="campos">
      <label class="ancho">${externo ? 'Proveedor (empresa o persona)' : 'Nombre y apellido'} <input name="nombre" value="${esc(p.nombre || '')}" required ${p.usuario_legajo ? 'readonly title="Es un usuario: el nombre se cambia en Usuarios"' : ''}></label>
      <label class="ancho">${externo ? 'Contacto y rubro (teléfono, mail, qué hace)' : 'Contacto (opcional)'} <input name="contacto" value="${esc(p.contacto || '')}"></label>
    </div><p class="error"></p>
    <div class="botones"><button class="primario" type="submit">Guardar</button><button type="button" onclick="cerrarModal()">Cancelar</button></div></form>`);
  const f = $('#f-persona');
  f.addEventListener('submit', ev => {
    ev.preventDefault();
    enviar(f, async d => {
      await api(id ? '/api/personas/' + id : '/api/personas', { metodo: id ? 'PUT' : 'POST', datos: d });
      await recargarOpciones(); cerrarModal(); avisar('Guardado.'); irA('personal');
    });
  });
}

async function altaPersona(id, activo) {
  if (!activo && !confirm('¿Dar de baja? Deja de aparecer para elegir; sus trabajos se siguen contando.')) return;
  try { await api(`/api/personas/${id}/${activo ? 'alta' : 'baja'}`, { metodo: 'POST' }); await recargarOpciones(); irA('personal'); }
  catch (e) { avisar(e.message, true); }
}

async function verTrabajos(id) {
  const p = S.opciones.personas.find(x => x.id === id);
  const trabajos = await api(`/api/personas/${id}/trabajos?anio=${S.anio}`);
  abrirModal(`
    <h2>${esc(p.pide_nombre ? 'Otros — ' + CATEGORIAS[p.categoria] : p.nombre)} · ${S.anio}</h2>
    <div class="tabla-wrap"><table><thead><tr><th>Fecha</th><th>Tipo</th><th>Equipo</th><th>Detalle</th><th>HH</th>${p.pide_nombre ? '<th>Nombre</th>' : ''}</tr></thead><tbody>
      ${trabajos.map(t => `<tr><td>${fecha(t.fecha)}</td><td><span class="chip ${t.tipo === 'Correctivo' ? 'ambar' : 'azul'}">${t.tipo}</span></td>
        <td>${esc(t.equipo_codigo)} · ${esc(t.equipo)}</td><td>${esc(t.detalle)}${t.horas_parada ? ` <span class="sutil">(${t.horas_parada} h parada)</span>` : ''}</td>
        <td>${t.horas_hombre ?? ''}</td>${p.pide_nombre ? `<td>${esc(t.nombre_libre)}</td>` : ''}</tr>`).join('')}
    </tbody></table></div>
    <div class="botones" style="margin-top:1rem"><button onclick="cerrarModal()">Cerrar</button></div>`);
}

// ── ÁREAS: lista de áreas de la planta, con lo que pasó en cada una en el año ──
VISTAS.areas = async () => {
  const lista = await api('/api/areas/seguimiento?anio=' + S.anio);
  $('#vista').innerHTML = `
    <div class="encabezado"><h2>Áreas ${S.anio}</h2>
      <div class="botones"><button onclick="S.anio--; irA('areas')">◄</button><button onclick="S.anio++; irA('areas')">►</button>
        ${soloAdmin('<button class="primario" onclick="nuevaArea()">Nueva área</button>')}</div></div>
    <p class="sutil">Las áreas de la planta. Cada equipo se asigna a una; renombrar un área la corrige en todos sus equipos.</p>
    <div class="tarjeta tabla-wrap">${casillaOcultos('areas', lista.filter(a => !a.activo).length)}<table ${tablaOcultos('areas')}>
      <thead><tr><th>Área</th><th>Equipos</th><th>Preventivos</th><th>Correctivos</th><th>Horas de parada</th><th></th></tr></thead><tbody>
      ${lista.map(a => `<tr class="${a.activo ? '' : 'baja'}"><td><b>${esc(a.nombre)}</b></td><td>${a.equipos}</td><td>${a.preventivos}</td>
        <td>${a.correctivos}</td><td>${a.horas_parada ? a.horas_parada.toLocaleString('es-AR') : ''}</td>
        <td class="botones">${soloAdmin(`<button class="chico" onclick="renombrarArea(${a.id}, '${esc(a.nombre).replace(/'/g, "\\'")}')">Renombrar</button>
          <button class="chico" onclick="altaArea(${a.id}, ${!a.activo})">${a.activo ? 'Dar de baja' : 'Reactivar'}</button>
          ${a.equipos_total ? '' : `<button class="chico peligro" onclick="eliminarArea(${a.id})">Eliminar</button>`}`)}</td></tr>`).join('')
        || '<tr><td colspan="6" class="vacio">No hay áreas cargadas.</td></tr>'}
    </tbody></table></div>`;
};

async function nuevaArea() {
  const nombre = prompt('Nombre del área nueva (ej. Moldeo, Fusión):');
  if (!nombre) return;
  try { await api('/api/areas', { metodo: 'POST', datos: { nombre } }); await recargarOpciones(); irA('areas'); }
  catch (e) { avisar(e.message, true); }
}

async function renombrarArea(id, actual) {
  const nombre = prompt('Nuevo nombre del área (se corrige en todos sus equipos):', actual);
  if (!nombre || nombre === actual) return;
  try { await api('/api/areas/' + id, { metodo: 'PUT', datos: { nombre } }); await recargarOpciones(); irA('areas'); }
  catch (e) { avisar(e.message, true); }
}

async function altaArea(id, activo) {
  try { await api(`/api/areas/${id}/${activo ? 'alta' : 'baja'}`, { metodo: 'POST' }); await recargarOpciones(); irA('areas'); }
  catch (e) { avisar(e.message, true); }
}

async function eliminarArea(id) {
  if (!confirm('Eliminar es solo para un área creada por error (no tiene equipos). ¿Eliminar?')) return;
  try { await api('/api/areas/' + id, { metodo: 'DELETE' }); await recargarOpciones(); irA('areas'); }
  catch (e) { avisar(e.message, true); }
}

// ── INSTRUCTIVOS ──
VISTAS.instructivos = async id => {
  if (id) return verInstructivo(Number(id));
  irA('equipos');   // la lista de instructivos vive en "Equipos e instructivos"
};

// ── adjuntos: se piden con la sesión (fetch + blob) porque un <img src> no manda el header Bearer ──
const _blobs = new Map();
async function urlAdjunto(id) {
  if (_blobs.has(id)) return _blobs.get(id);
  const r = await fetch('/api/adjuntos/' + id, { headers: { Authorization: 'Bearer ' + S.token } });
  if (!r.ok) throw new Error(r.status === 404 ? 'El archivo ya no está.' : 'No se pudo abrir el archivo.');
  const url = URL.createObjectURL(await r.blob());
  _blobs.set(id, url);
  return url;
}
function cargarImagenes(raiz = document) {
  raiz.querySelectorAll('img[data-adjunto]:not([src])').forEach(img =>
    urlAdjunto(Number(img.dataset.adjunto)).then(u => { img.src = u; }).catch(() => { img.alt = 'Imagen no disponible'; }));
}
async function abrirAdjunto(id) {
  const a = S.adjuntosVistos?.get(id) || {};
  try {
    const url = await urlAdjunto(id);
    if ((a.tipo || '').startsWith('image/') || a.tipo === 'application/pdf') return window.open(url, '_blank');
    const enlace = Object.assign(document.createElement('a'), { href: url, download: a.nombre || 'archivo' });
    document.body.appendChild(enlace); enlace.click(); enlace.remove();
  } catch (e) { avisar(e.message, true); }
}
const tamanio = n => n >= 1048576 ? (n / 1048576).toLocaleString('es-AR', { maximumFractionDigits: 1 }) + ' MB' : Math.max(1, Math.round(n / 1024)) + ' KB';
const extension = nombre => (nombre.split('.').pop() || '').toUpperCase();

// ── bloques de contenido (traídos de Procedimientos de GNC API) ──
const TIPOS_BLOQUE = { texto: 'Texto', nota: 'Nota destacada', tabla: 'Tabla / ficha técnica', imagen: 'Imagen', grafico: 'Gráfico' };
const NIVELES_NOTA = { info: 'Nota', precaucion: 'Precaución', peligro: 'Peligro' };
const COLORES = ['#1f5f99', '#2e7d32', '#b26a00', '#c0392b', '#6a4c93', '#00838f', '#8d6e63', '#546e7a'];

/** Gráfico como SVG propio: sin librerías, y se imprime nítido. */
function graficoSVG(d) {
  const filas = d.filas, u = d.unidad ? ' ' + d.unidad : '';
  const num = v => Number(v).toLocaleString('es-AR', { maximumFractionDigits: 2 });
  if (d.forma === 'torta') {
    const total = filas.reduce((t, [, v]) => t + v, 0) || 1;
    const cx = 120, cy = 120, r = 105;
    let ang = -Math.PI / 2;
    const porciones = filas.map(([, v], i) => {
      const a2 = ang + 2 * Math.PI * v / total, color = COLORES[i % COLORES.length];
      const p = v >= total ? `<circle cx="${cx}" cy="${cy}" r="${r}" fill="${color}"/>`
        : `<path d="M${cx},${cy} L${cx + r * Math.cos(ang)},${cy + r * Math.sin(ang)} A${r},${r} 0 ${a2 - ang > Math.PI ? 1 : 0} 1 ${cx + r * Math.cos(a2)},${cy + r * Math.sin(a2)} Z" fill="${color}"/>`;
      ang = a2;
      return p;
    }).join('');
    const leyenda = filas.map(([et, v], i) => `<g transform="translate(260,${20 + i * 22})"><rect width="14" height="14" rx="2" fill="${COLORES[i % COLORES.length]}"/>
      <text x="20" y="12">${esc(et)}: ${num(v)}${esc(u)} (${Math.round(100 * v / total)} %)</text></g>`).join('');
    return `<svg viewBox="0 0 640 ${Math.max(240, 30 + filas.length * 22)}" class="svg-grafico" role="img">${porciones}${leyenda}</svg>`;
  }
  const W = 640, H = 260, m = { l: 52, r: 12, t: 22, b: 40 };
  const vals = filas.map(f => f[1]);
  let max = Math.max(0, ...vals), min = Math.min(0, ...vals);
  if (max === min) max = min + 1;
  const y = v => m.t + (H - m.t - m.b) * (max - v) / (max - min);
  const paso = (W - m.l - m.r) / filas.length, x = i => m.l + paso * (i + 0.5);
  const guias = [min, (min + max) / 2, max].map(v => `<line x1="${m.l}" x2="${W - m.r}" y1="${y(v)}" y2="${y(v)}" class="g-guia"/>
    <text x="${m.l - 6}" y="${y(v) + 4}" text-anchor="end">${num(v)}</text>`).join('');
  const etiquetas = filas.map(([et], i) => `<text x="${x(i)}" y="${H - m.b + 16}" text-anchor="middle">${esc(et.length > 12 ? et.slice(0, 11) + '…' : et)}</text>`).join('');
  let marcas;
  if (d.forma === 'linea') {
    marcas = `<polyline fill="none" stroke="${COLORES[0]}" stroke-width="2.5" points="${filas.map(([, v], i) => `${x(i)},${y(v)}`).join(' ')}"/>`
      + filas.map(([, v], i) => `<circle cx="${x(i)}" cy="${y(v)}" r="3.5" fill="${COLORES[0]}"/><text x="${x(i)}" y="${y(v) - 8}" text-anchor="middle">${num(v)}</text>`).join('');
  } else {
    const bw = Math.min(48, paso * 0.6);
    marcas = filas.map(([, v], i) => `<rect x="${x(i) - bw / 2}" y="${Math.min(y(v), y(0))}" width="${bw}" height="${Math.max(1, Math.abs(y(v) - y(0)))}" rx="2" fill="${COLORES[0]}"/>
      <text x="${x(i)}" y="${v >= 0 ? y(v) - 5 : y(v) + 14}" text-anchor="middle">${num(v)}</text>`).join('');
  }
  return `<svg viewBox="0 0 ${W} ${H}" class="svg-grafico" role="img">${guias}${marcas}${etiquetas}${u ? `<text x="${m.l}" y="12" class="g-unidad">${esc(d.unidad)}</text>` : ''}</svg>`;
}

function bloqueHTML(b) {
  const d = b.datos;
  if (b.tipo === 'texto') return `<div class="b-texto">${d.titulo ? `<h4>${esc(d.titulo)}</h4>` : ''}${d.texto ? `<p>${esc(d.texto)}</p>` : ''}</div>`;
  if (b.tipo === 'nota') return `<div class="b-nota ${d.nivel}"><b>${NIVELES_NOTA[d.nivel]}:</b> ${esc(d.texto)}</div>`;
  if (b.tipo === 'tabla') {
    const [cab, ...resto] = d.encabezado ? d.filas : [null, ...d.filas];
    return `<figure class="b-tabla">${d.titulo ? `<figcaption>${esc(d.titulo)}</figcaption>` : ''}<table>
      ${cab ? `<thead><tr>${cab.map(c => `<th>${esc(c)}</th>`).join('')}</tr></thead>` : ''}
      <tbody>${resto.map(f => `<tr>${f.map(c => `<td>${esc(c)}</td>`).join('')}</tr>`).join('')}</tbody></table></figure>`;
  }
  if (b.tipo === 'imagen') return `<figure class="b-imagen ${d.ancho}"><img data-adjunto="${d.adjunto_id}" alt="${esc(d.epigrafe || 'Imagen')}">${d.epigrafe ? `<figcaption>${esc(d.epigrafe)}</figcaption>` : ''}</figure>`;
  if (b.tipo === 'grafico') return `<figure class="b-grafico">${d.titulo ? `<figcaption>${esc(d.titulo)}</figcaption>` : ''}${graficoSVG(d)}</figure>`;
  return '';
}
/** Los bloques que en el orden del documento siguen a la sección, hasta la próxima sección o los repuestos. */
function bloquesTras(it, letra) {
  const desde = it.orden.indexOf('seccion:' + letra), html = [];
  for (const t of it.orden.slice(desde + 1)) {
    if (!t.startsWith('bloque:')) break;
    html.push(bloqueHTML(it.bloques[t.slice(7)]));
  }
  return html.join('');
}

/** Actividades numeradas (los títulos de grupo no consumen número) con su detalle como sub-pasos. */
const actividadesHTML = acts => `<ol class="actividades">${acts.map(a => a.es_grupo ? `<li class="grupo">${esc(a.texto)}</li>`
  : `<li>${esc(a.texto)}${a.detalle ? `<ul class="detalle">${a.detalle.split('\n').filter(x => x.trim()).map(x => `<li>${esc(x)}</li>`).join('')}</ul>` : ''}</li>`).join('')}</ol>`;

function docInstructivo(it, { revisionVieja = false } = {}) {
  const lista = (xs, vacio) => xs.length ? `<ul>${xs.map(x => `<li>${esc(x)}</li>`).join('')}</ul>` : `<p class="sutil">${vacio}</p>`;
  S.adjuntosVistos = S.adjuntosVistos || new Map();
  (it.archivos || []).forEach(a => S.adjuntosVistos.set(a.id, a));
  // debajo de la seguridad, todo en el orden elegido en el editor: secciones, bloques y repuestos
  const secciones = new Map(it.secciones.map(s => [s.letra, s]));
  const cuerpo = it.orden.map(t => {
    if (t === 'repuestos') return `<h3>Repuestos e insumos</h3>${it.repuestos.length ? `<table class="repuestos-doc"><thead><tr><th>Repuesto / insumo</th><th>Cant. mínima</th></tr></thead>
      <tbody>${it.repuestos.map(r => `<tr><td>${esc(r.nombre)}</td><td>${r.cantidad == null ? '—' : miles(r.cantidad)}</td></tr>`).join('')}</tbody></table>`
      : '<p class="sutil">Sin repuestos indicados.</p>'}`;
    if (t.startsWith('bloque:')) return bloqueHTML(it.bloques[t.slice(7)]);
    const s = secciones.get(t.slice(8));
    return `<div class="seccion-cab"><span>${esc(s.codigo || (it.codigo + '-' + s.letra))}</span>
        ${s.tareas ? `<span class="no-imprimir">${s.tareas.length ? s.tareas.map(t => `<span class="chip verde" title="${esc(t.equipo)}">☑ ${esc(t.codigo)} · ${esc(t.frecuencia === 'Por horas' ? 'c/ ' + miles(t.cada_horas) + ' h' : t.frecuencia)}</span>`).join(' ')
          : '<span class="chip rojo">☐ sin programar</span>'}</span>` : ''}</div>
      ${actividadesHTML(s.actividades)}`;
  }).join('');
  return `<div class="doc">
    ${it.vigente === 0 ? `<div class="franja-obsoleto">OBSOLETO desde ${fecha(it.fecha_baja)} — ${esc(it.motivo_baja || '')}</div>` : ''}
    ${revisionVieja ? `<div class="franja-obsoleto">Revisión ${it.revision} reemplazada el ${fecha(it.reemplazada_en)}: ${esc(it.motivo)}</div>` : ''}
    <div class="doc-cabecera"><div><div class="codigo">${esc(it.codigo || '')} · ${esc(it.titulo)}</div><div class="sutil">Instructivo de mantenimiento</div></div>
      <div style="text-align:right">Rev. ${it.revision}<br><span class="sutil">${fecha(it.fecha_revision)}</span></div></div>
    ${it.descripcion ? `<p>${esc(it.descripcion)}</p>` : ''}
    <h3>Seguridad</h3>${lista(it.seguridad, 'Sin indicaciones de seguridad.')}
    ${cuerpo}
    ${(it.archivos || []).length ? `<h3>Archivos adjuntos</h3><ul class="adjuntos-doc">${it.archivos.map(a => `<li>
      <a onclick="abrirAdjunto(${a.id})">${esc(a.nombre)}</a> <span class="sutil">(${extension(a.nombre)}, ${tamanio(a.tamanio)})</span></li>`).join('')}</ul>` : ''}
  </div>`;
}

async function verInstructivo(id) {
  const it = await api('/api/instructivos/' + id);
  const admin = S.usuario.es_admin;
  $('#vista').innerHTML = `
    <div class="encabezado no-imprimir"><a onclick="irA('equipos')">← Equipos e instructivos</a>
      <div class="botones"><button onclick="window.print()">Imprimir / PDF</button>
        ${admin && it.vigente ? `<button class="primario" onclick="editarInstructivo(${id})">Modificar</button>
          ${it.secciones.some(s => !s.tareas.length) ? `<button onclick="programarSeccion(${id})">Programar en el Plan</button>` : ''}
          <button onclick="obsoletoInstructivo(${id})">Marcar obsoleto</button>
          <button class="peligro" onclick="eliminarInstructivo(${id})">Eliminar</button>` : ''}</div></div>
    <div class="tarjeta">${docInstructivo(it)}</div>
    <div class="tarjeta no-imprimir"><h3>Historial de revisiones</h3>
      ${it.versiones.length ? `<table><thead><tr><th>Rev.</th><th>Qué cambió al pasar a la siguiente</th><th>Quién</th><th>Cuándo</th><th></th></tr></thead><tbody>
        ${it.versiones.map(v => `<tr><td>${v.revision}</td><td>${esc(v.motivo)}</td><td>${esc(v.creado_por)}</td><td>${fecha(v.creado_en)}</td>
          <td><button class="chico" onclick="verRevision(${id}, ${v.revision})">Ver</button></td></tr>`).join('')}</tbody></table>`
        : '<p class="sutil">Revisión original, sin cambios todavía.</p>'}
      <p class="sutil">Creado por ${esc(it.creado_por)} el ${fecha(it.creado_en)} · última modificación: ${esc(it.modificado_por)}, ${fecha(it.modificado_en)}</p></div>`;
  cargarImagenes($('#vista'));
}

async function verRevision(id, rev) {
  const [v, actual] = await Promise.all([api(`/api/instructivos/${id}/revisiones/${rev}`), api('/api/instructivos/' + id)]);
  abrirModal(`${docInstructivo({ ...v, codigo: actual.codigo, secciones: v.secciones.map(s => ({ ...s, codigo: actual.codigo + '-' + s.letra })) }, { revisionVieja: true })}
    <div class="botones" style="margin-top:1rem"><button onclick="cerrarModal()">Cerrar</button></div>`);
  cargarImagenes($('#modal'));
}

function programarSeccion(id) {
  // abre el alta de tarea con la primera sección sin programar ya elegida
  api('/api/instructivos/' + id).then(it => {
    const sec = it.secciones.find(s => !s.tareas.length);
    const op = S.opciones.secciones.find(s => s.codigo === sec?.codigo);
    modalTarea(undefined, op?.id);
  });
}

/** Editor. Arriba, fijos: título, descripción y seguridad. Debajo, el contenido en el orden del documento: secciones de
 *  actividades, bloques (texto, nota, tabla, imagen, gráfico) y repuestos. El número al costado es la posición: cambiarlo mueve.
 *  Actividades: una por línea; "# " = título de grupo; "- " = detalle (sub-paso) de la actividad de arriba. */
let ED = null;   // estado del editor abierto: contenido en orden (items), adjuntos del instructivo y los listados en "Archivos adjuntos"

const textoActividades = acts => acts.map(a => (a.es_grupo ? '# ' : '') + a.texto
  + (a.detalle ? '\n' + a.detalle.split('\n').filter(x => x.trim()).map(x => '- ' + x).join('\n') : '')).join('\n');

async function editarInstructivo(id, para) {
  // alta: siempre "para" un equipo (ver instructivoPara): arranca con sus datos y se vincula al crearlo
  const it = id ? await api('/api/instructivos/' + id)
    : { titulo: para?.titulo || '', descripcion: para?.descripcion || '', seguridad: [], repuestos: [], secciones: [{ letra: 'A', actividades: [] }],
        bloques: para?.bloques || [], archivos: [], adjuntos: [], orden: [...(para?.bloques || []).map((b, i) => 'bloque:' + i), 'seccion:A', 'repuestos'] };
  const secciones = new Map(it.secciones.map(s => [s.letra, s]));
  ED = { id, codigo: it.codigo || 'IT', adjuntos: it.adjuntos, archivos: it.archivos.map(a => a.id),
    items: it.orden.map(t => {
      if (t === 'repuestos') return { t: 'repuestos', lista: it.repuestos.map(r => ({ ...r })) };
      if (t.startsWith('bloque:')) return { t: 'bloque', b: structuredClone(it.bloques[t.slice(7)]) };
      const sec = secciones.get(t.slice(8));
      return { t: 'seccion', letra: sec.letra, texto: textoActividades(sec.actividades), tareas: sec.tareas || [] };
    }) };
  $('#vista').innerHTML = `
    <div class="encabezado"><h2>${id ? `Modificar ${esc(it.codigo)} (Rev. ${it.revision} → ${it.revision + 1})` : `Instructivo de ${esc(para?.codigo || '')}`}</h2></div>
    <form id="f-it" class="tarjeta">
      <div class="campos">
        <label class="ancho">Título <input name="titulo" value="${esc(it.titulo)}" required></label>
        <label class="ancho">Descripción <input name="descripcion" value="${esc(it.descripcion)}"></label>
        <label class="ancho">Seguridad (una indicación por línea) <textarea name="seguridad" rows="4">${esc(it.seguridad.join('\n'))}</textarea></label>
      </div>
      <h3>Contenido</h3>
      <p class="sutil">Va debajo de la seguridad, en el orden de los números: para mover algo, cambiale el número.
        Cada sección es un grupo de actividades que se hacen juntas, con su propia frecuencia en el Plan (por ejemplo A mensual, B cada 1000 h);
        en sus actividades, una línea que empieza con <b>#</b> es un título de grupo y una que empieza con <b>-</b> es un detalle de la de arriba.</p>
      <div id="ed-contenido"></div>
      <div class="botones"><button type="button" class="chico" onclick="edAgregarSeccion()">+ Sección de actividades</button>
        ${Object.entries(TIPOS_BLOQUE).map(([t, n]) => `<button type="button" class="chico" onclick="edAgregarBloque('${t}')">+ ${n}</button>`).join('')}</div>

      <h3 style="margin-top:1.4rem">Imágenes y archivos</h3>
      <div id="ed-adjuntos"></div>

      ${id ? '<div class="campos" style="margin-top:1rem"><label class="ancho">Motivo del cambio (queda en el historial de revisiones) <input name="motivo" required></label></div>' : ''}
      <p class="error"></p>
      <div class="botones"><button class="primario" type="submit">${id ? 'Guardar revisión ' + (it.revision + 1) : 'Crear instructivo'}</button>
        <button type="button" onclick="irA(${id ? `'instructivos/${id}'` : "'equipos'"})">${id ? 'Cancelar' : 'Después'}</button></div>
    </form>`;
  edPintar();
  edPintarAdjuntos();
  const f = $('#f-it');
  f.addEventListener('submit', ev => {
    ev.preventDefault();
    const lineas = t => t.split('\n').map(x => x.trim()).filter(Boolean);
    enviar(f, async d => {
      // el orden viaja aparte: "seccion:A", "bloque:<posición en bloques>", "repuestos"
      const secciones = [], bloques = [], orden = [];
      let repuestos = [], ultima = 'general';
      for (const x of edLeer()) {
        if (x.t === 'seccion') { secciones.push({ letra: x.letra, actividades: edLeerActividades(x.texto) }); orden.push('seccion:' + x.letra); ultima = x.letra; }
        else if (x.t === 'bloque') { orden.push('bloque:' + bloques.length); bloques.push({ ...x.b, ubicacion: ultima }); }
        else { repuestos = x.lista; orden.push('repuestos'); }
      }
      const datos = {
        titulo: d.titulo, descripcion: d.descripcion, motivo: d.motivo, seguridad: lineas(d.seguridad),
        repuestos, secciones, bloques, orden, archivos: ED.archivos, equipo_id: para?.equipo_id,
      };
      const r = await api(id ? '/api/instructivos/' + id : '/api/instructivos', { metodo: id ? 'PUT' : 'POST', datos });
      await recargarOpciones(); avisar(id ? `Guardada la revisión ${r.revision}.` : `Creado ${r.codigo} para ${para?.codigo || 'el equipo'}. Falta programarlo en el Plan.`);
      irA('instructivos/' + r.id);
    });
  });
}

/** Lista editable en tabla (repuestos: nombre + cantidad mínima): cada renglón se puede corregir, quitar o arrastrar
 *  (por la manija ⠿) a otra posición; abajo, campos para agregar (Enter o botón). leerListaEditable la devuelve en el orden de pantalla. */
const ENTER_AGREGA = `onkeydown="if (event.key === 'Enter') { event.preventDefault(); listaAgregar(this); }"`;

function listaEditable(clave, items, placeholder) {
  return `<table class="lista-editable" data-lista="${clave}">
    <thead><tr><th></th><th>Repuesto / insumo</th><th>Cant. mínima</th><th></th></tr></thead>
    <tbody>${items.map(listaRenglon).join('')}</tbody>
    <tfoot><tr><td></td><td><input data-nuevo placeholder="${esc(placeholder)}" ${ENTER_AGREGA}></td>
      <td><input data-nueva-cantidad class="cantidad" inputmode="decimal" placeholder="—" ${ENTER_AGREGA}></td>
      <td><button type="button" class="chico" onclick="listaAgregar(this)">Agregar</button></td></tr></tfoot></table>`;
}

function listaRenglon(r) {
  return `<tr ondragstart="listaArrastrar(event, this)" ondragover="listaSobrevolar(event, this)" ondrop="event.preventDefault()" ondragend="listaSoltar(this)">
    <td class="manija" title="Arrastrar para reordenar" onmousedown="this.parentNode.draggable = true" onmouseup="this.parentNode.draggable = false">⠿</td>
    <td><input data-item value="${esc(r.nombre)}"></td>
    <td><input data-cantidad class="cantidad" inputmode="decimal" placeholder="—" value="${esc(r.cantidad == null ? '' : String(r.cantidad).replace('.', ','))}"></td>
    <td><button type="button" class="chico peligro" onclick="this.closest('tr').remove()">Eliminar</button></td></tr>`;
}

function listaAgregar(el) {
  const tabla = el.closest('table'), campo = $('[data-nuevo]', tabla), cant = $('[data-nueva-cantidad]', tabla);
  if (campo.value.trim()) $('tbody', tabla).insertAdjacentHTML('beforeend', listaRenglon({ nombre: campo.value.trim(), cantidad: cant.value.trim() || null }));
  campo.value = ''; cant.value = ''; campo.focus();
}

function leerListaEditable(clave) {
  const tabla = $(`table[data-lista="${clave}"]`), campo = $('[data-nuevo]', tabla);
  // la cantidad viaja como se tipeó ("1,5"): la valida el servidor
  const items = [...tabla.querySelectorAll('tbody tr')].map(tr => ({ nombre: $('[data-item]', tr).value.trim(), cantidad: $('[data-cantidad]', tr).value.trim() || null }));
  if (campo.value.trim()) items.push({ nombre: campo.value.trim(), cantidad: $('[data-nueva-cantidad]', tabla).value.trim() || null });   // lo que quedó escrito abajo sin "Agregar" también cuenta
  return items.filter(r => r.nombre);
}

// arrastre: el renglón solo se vuelve arrastrable al agarrar la manija, para no estorbar la edición del texto
let LISTA_ARRASTRADO = null;

function listaArrastrar(ev, tr) {
  LISTA_ARRASTRADO = tr; tr.classList.add('arrastrando');
  ev.dataTransfer.effectAllowed = 'move'; ev.dataTransfer.setData('text/plain', '');
}

function listaSobrevolar(ev, tr) {
  if (!LISTA_ARRASTRADO || tr.parentNode !== LISTA_ARRASTRADO.parentNode) return;   // solo dentro de la misma lista
  ev.preventDefault();
  if (tr === LISTA_ARRASTRADO) return;
  const r = tr.getBoundingClientRect();
  tr.parentNode.insertBefore(LISTA_ARRASTRADO, ev.clientY < r.top + r.height / 2 ? tr : tr.nextSibling);
}

function listaSoltar(tr) {
  tr.classList.remove('arrastrando'); tr.draggable = false; LISTA_ARRASTRADO = null;
}

function edLeerActividades(texto) {
  const acts = [];
  for (const crudo of texto.split('\n')) {
    const l = crudo.trim();
    if (!l) continue;
    const anterior = acts[acts.length - 1];
    if (l.startsWith('-') && anterior && !anterior.es_grupo) anterior.detalle = (anterior.detalle ? anterior.detalle + '\n' : '') + l.replace(/^-\s*/, '');
    else if (l.startsWith('#')) acts.push({ texto: l.replace(/^#\s*/, ''), es_grupo: true });
    else acts.push({ texto: l, es_grupo: false, detalle: '' });
  }
  return acts;
}

// cada bloque del editor: los campos llevan data-c="<campo>"; edLeerBloque los vuelve a armar
function edCamposBloque(b) {
  const d = b.datos || {};
  const imagenes = ED.adjuntos.filter(a => a.es_imagen);
  if (b.tipo === 'texto') return `<label>Título (opcional) <input data-c="titulo" value="${esc(d.titulo || '')}"></label>
    <label>Texto <textarea data-c="texto" rows="3">${esc(d.texto || '')}</textarea></label>`;
  if (b.tipo === 'nota') return `<label>Tipo <select data-c="nivel">${opcionesSelect(Object.entries(NIVELES_NOTA), d.nivel || 'precaucion', null)}</select></label>
    <label>Texto <textarea data-c="texto" rows="2">${esc(d.texto || '')}</textarea></label>`;
  if (b.tipo === 'tabla') return `<label>Título (opcional) <input data-c="titulo" value="${esc(d.titulo || '')}"></label>
    <label class="check"><input type="checkbox" data-c="encabezado" ${d.encabezado !== false ? 'checked' : ''}> La primera fila es el encabezado</label>
    <label><span>Filas: una por renglón, celdas separadas con <b>|</b></span> <textarea data-c="filas" rows="${Math.max(4, (d.filas || []).length + 1)}" placeholder="Dato | Valor&#10;Presión de trabajo | 8 bar">${esc((d.filas || []).map(f => f.join(' | ')).join('\n'))}</textarea></label>`;
  if (b.tipo === 'imagen') return imagenes.length ? `<div class="campos">
      <label>Imagen <select data-c="adjunto_id">${opcionesSelect(imagenes.map(a => [a.id, a.nombre]), d.adjunto_id, '— elegir —')}</select></label>
      <label>Ancho <select data-c="ancho">${opcionesSelect([['chico', 'Chico'], ['mediano', 'Mediano'], ['completo', 'Todo el ancho']], d.ancho || 'mediano', null)}</select></label>
      <label class="ancho">Epígrafe (opcional) <input data-c="epigrafe" value="${esc(d.epigrafe || '')}"></label></div>
      ${d.adjunto_id ? `<img class="ed-miniatura" data-adjunto="${d.adjunto_id}" alt="">` : ''}`
    : `<p class="sutil">Primero subí una imagen en "Imágenes y archivos"${ED.id ? '' : ' (se puede después de crear el instructivo)'}.</p>`;
  if (b.tipo === 'grafico') return `<div class="campos">
      <label>Forma <select data-c="forma">${opcionesSelect([['barras', 'Barras'], ['linea', 'Línea'], ['torta', 'Torta']], d.forma || 'barras', null)}</select></label>
      <label>Unidad (opcional) <input data-c="unidad" value="${esc(d.unidad || '')}" placeholder="h, kg, °C…"></label>
      <label class="ancho">Título (opcional) <input data-c="titulo" value="${esc(d.titulo || '')}"></label></div>
    <label><span>Valores: uno por renglón, <b>etiqueta: número</b></span> <textarea data-c="filas" rows="${Math.max(4, (d.filas || []).length + 1)}" placeholder="Enero: 12&#10;Febrero: 9,5">${esc((d.filas || []).map(([e, v]) => `${e}: ${v}`).join('\n'))}</textarea></label>`;
  return '';
}

/** Dibuja ED.items. Quien cambia la lista primero junta lo tipeado con edLeer(), para no perderlo al redibujar. */
function edPintar() {
  const n = ED.items.length, posiciones = Array.from({ length: n }, (_, k) => [k + 1, k + 1]);
  const filasDe = t => t.split('\n').length;
  $('#ed-contenido').innerHTML = ED.items.map((x, i) => {
    let nombre, accion = '', cuerpo;
    if (x.t === 'seccion') {
      nombre = 'Sección ' + esc(ED.codigo + '-' + x.letra);
      accion = x.tareas.length ? `<span class="chip verde">en el Plan: ${x.tareas.map(t => esc(t.codigo)).join(', ')}</span>`
        : `<button type="button" class="chico peligro" onclick="edQuitar(${i})">Quitar sección</button>`;
      cuerpo = `<textarea data-c="actividades" rows="${Math.max(4, filasDe(x.texto) + 1)}" placeholder="Una actividad por línea.&#10;# Título de grupo&#10;- Detalle de la actividad de arriba">${esc(x.texto)}</textarea>`;
    } else if (x.t === 'repuestos') {
      nombre = 'Repuestos e insumos';
      cuerpo = listaEditable('repuestos', x.lista, 'Repuesto o insumo, por ejemplo: Filtro de aceite');
    } else {
      nombre = TIPOS_BLOQUE[x.b.tipo];
      accion = `<button type="button" class="chico peligro" onclick="edQuitar(${i})" title="Quitar">✕</button>`;
      cuerpo = edCamposBloque(x.b);
    }
    return `<div class="editor-item ${x.t === 'bloque' ? 'editor-bloque' : 'editor-seccion'}${x.t === 'seccion' ? ' actividades-ed' : ''}">
      <div class="botones editor-cab"><select class="posicion" title="Posición en el documento" onchange="edMoverA(${i}, this.value)">${opcionesSelect(posiciones, i + 1, null)}</select>
        <b>${nombre}</b><span class="empuje"></span>${accion}</div>
      ${cuerpo}</div>`;
  }).join('');
  $('#ed-contenido').querySelectorAll('select[data-c=adjunto_id]').forEach(sel => sel.addEventListener('change', () => { ED.items = edLeer(); edPintar(); }));
  cargarImagenes($('#ed-contenido'));
}

/** Lo que hay en pantalla, en orden: cada tarjeta corresponde a ED.items en la misma posición. */
function edLeer() {
  return [...$('#ed-contenido').children].map((el, i) => {
    const x = ED.items[i];
    if (x.t === 'seccion') return { ...x, texto: $('[data-c=actividades]', el).value };
    if (x.t === 'repuestos') return { t: 'repuestos', lista: leerListaEditable('repuestos') };
    return { t: 'bloque', b: edLeerBloque(el, x.b.tipo) };
  });
}

function edLeerBloque(el, tipo) {
  const v = c => { const x = el.querySelector(`[data-c="${c}"]`); return x ? (x.type === 'checkbox' ? x.checked : x.value) : undefined; };
  const renglones = t => (t || '').split('\n').map(x => x.trim()).filter(Boolean);
  let datos;
  if (tipo === 'texto') datos = { titulo: v('titulo'), texto: v('texto') };
  else if (tipo === 'nota') datos = { nivel: v('nivel'), texto: v('texto') };
  else if (tipo === 'tabla') datos = { titulo: v('titulo'), encabezado: v('encabezado'), filas: renglones(v('filas')).map(l => l.split('|').map(c => c.trim())) };
  else if (tipo === 'imagen') datos = { adjunto_id: v('adjunto_id') || null, ancho: v('ancho'), epigrafe: v('epigrafe') };
  else datos = { forma: v('forma'), unidad: v('unidad'), titulo: v('titulo'),
    filas: renglones(v('filas')).map(l => { const k = l.lastIndexOf(':'); return k < 0 ? [l, ''] : [l.slice(0, k).trim(), l.slice(k + 1).trim()]; }) };
  return { tipo, ubicacion: 'general', datos };
}

/** Lleva el ítem i a la posición elegida (1 = primero) y lo deja a la vista, resaltado un momento. */
function edMoverA(i, posicion) {
  ED.items = edLeer();
  const [x] = ED.items.splice(i, 1);
  ED.items.splice(Number(posicion) - 1, 0, x);
  edPintar();
  const el = $('#ed-contenido').children[Number(posicion) - 1];
  el.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
  el.classList.add('movido'); setTimeout(() => el.classList.remove('movido'), 1200);
}
function edQuitar(i) {
  ED.items = edLeer();
  ED.items.splice(i, 1);
  edPintar();
  edPintarAdjuntos();
}
function edAgregar(item) {
  ED.items = edLeer();
  ED.items.push(item);
  edPintar();
}
function edAgregarSeccion() {
  const usadas = ED.items.filter(x => x.t === 'seccion').map(x => x.letra);
  const letra = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'.split('').find(l => !usadas.includes(l));
  if (!letra) return avisar('Ya están usadas las 26 secciones, de la A a la Z.', true);
  edAgregar({ t: 'seccion', letra, texto: '', tareas: [] });
}
function edAgregarBloque(tipo) {
  edAgregar({ t: 'bloque', b: { tipo, ubicacion: 'general', datos: tipo === 'nota' ? { nivel: 'precaucion' } : tipo === 'tabla' ? { encabezado: true } : {} } });
}

/** Los adjuntos del instructivo: subir, listar en el documento (los que no son imagen) y borrar los que nadie usa. */
function edPintarAdjuntos() {
  if (!ED.id) {
    $('#ed-adjuntos').innerHTML = '<p class="sutil">Primero creá el instructivo; después, con Modificar, le agregás imágenes y archivos.</p>';
    return;
  }
  const enBloques = new Set(edLeer().filter(x => x.t === 'bloque' && x.b.tipo === 'imagen').map(x => Number(x.b.datos.adjunto_id)));
  $('#ed-adjuntos').innerHTML = `
    <p class="sutil">Imágenes (jpg, png, gif, webp) para usar en bloques de imagen, y archivos (PDF, planos dwg/dxf, Word, Excel, txt, csv, zip) que
      se listan al final del documento para descargar. Hasta 20 MB cada uno. Se guardan en la carpeta de la app.</p>
    ${ED.adjuntos.length ? `<table class="tabla-adjuntos"><tbody>${ED.adjuntos.map(a => {
      const usado = a.en_uso || enBloques.has(a.id) || ED.archivos.includes(a.id);
      return `<tr><td>${a.es_imagen ? `<img class="ed-miniatura chica" data-adjunto="${a.id}" alt="">` : `<span class="chip">${extension(a.nombre)}</span>`}</td>
        <td><a onclick="S.adjuntosVistos = S.adjuntosVistos || new Map(); S.adjuntosVistos.set(${a.id}, ${esc(JSON.stringify({ nombre: a.nombre, tipo: a.tipo }))}); abrirAdjunto(${a.id})">${esc(a.nombre)}</a>
          <br><span class="sutil">${tamanio(a.tamanio)} · ${esc(a.creado_por || '')}</span></td>
        <td>${a.es_imagen ? (enBloques.has(a.id) ? '<span class="chip verde">en un bloque</span>' : `<button type="button" class="chico" onclick="edImagenABloque(${a.id})">Poner en el documento</button>`)
          : `<label class="check"><input type="checkbox" ${ED.archivos.includes(a.id) ? 'checked' : ''} onchange="edListarArchivo(${a.id}, this.checked)"> En "Archivos adjuntos"</label>`}</td>
        <td>${usado ? '' : `<button type="button" class="chico peligro" title="Subido de más: ninguna revisión lo usa" onclick="edBorrarAdjunto(${a.id})">Borrar</button>`}</td></tr>`;
    }).join('')}</tbody></table>` : ''}
    <label class="subir"><input type="file" id="ed-subir" multiple accept=".jpg,.jpeg,.png,.gif,.webp,.pdf,.dwg,.dxf,.doc,.docx,.xls,.xlsx,.txt,.csv,.zip">
      <span class="boton-falso">Subir imágenes o archivos</span></label> <span id="ed-subiendo" class="sutil"></span>`;
  cargarImagenes($('#ed-adjuntos'));
  $('#ed-subir').addEventListener('change', async ev => {
    for (const archivo of ev.target.files) {
      $('#ed-subiendo').textContent = 'Subiendo ' + archivo.name + '…';
      try {
        const fd = new FormData(); fd.append('archivo', archivo);
        const r = await fetch(`/api/instructivos/${ED.id}/adjuntos`, { method: 'POST', headers: { Authorization: 'Bearer ' + S.token }, body: fd });
        const cuerpo = await r.json().catch(() => ({}));
        if (!r.ok) throw new Error(`${archivo.name}: ${typeof cuerpo.detail === 'string' ? cuerpo.detail : 'no se pudo subir.'}`);
        ED.adjuntos.push({ ...cuerpo, en_uso: false });
        if (cuerpo.es_imagen) edImagenABloque(cuerpo.id, false); else ED.archivos.push(cuerpo.id);
      } catch (e) { avisar(e.message, true); }
    }
    $('#ed-subiendo').textContent = '';
    edPintarAdjuntos();
  });
}
function edImagenABloque(adjuntoId, repintar = true) {
  edAgregar({ t: 'bloque', b: { tipo: 'imagen', ubicacion: 'general', datos: { adjunto_id: adjuntoId, ancho: 'mediano' } } });
  if (repintar) edPintarAdjuntos();
}
function edListarArchivo(adjuntoId, si) {
  ED.archivos = ED.archivos.filter(x => x !== adjuntoId);
  if (si) ED.archivos.push(adjuntoId);
  edPintarAdjuntos();
}
async function edBorrarAdjunto(adjuntoId) {
  const a = ED.adjuntos.find(x => x.id === adjuntoId);
  if (!confirm(`¿Borrar "${a.nombre}"? Es para un archivo subido de más: se borra de la carpeta.`)) return;
  try {
    await api('/api/adjuntos/' + adjuntoId, { metodo: 'DELETE' });
    ED.adjuntos = ED.adjuntos.filter(x => x.id !== adjuntoId);
    edPintarAdjuntos();
  } catch (e) { avisar(e.message, true); }
}

async function obsoletoInstructivo(id) {
  const motivo = prompt('Motivo por el que queda obsoleto (ej. el equipo se dio de baja):');
  if (!motivo) return;
  try { await api(`/api/instructivos/${id}/obsoleto`, { metodo: 'POST', datos: { motivo } }); await recargarOpciones(); avisar('Marcado obsoleto: queda guardado para consulta.'); irA('instructivos/' + id); }
  catch (e) { avisar(e.message, true); }
}

async function eliminarInstructivo(id) {
  if (!confirm('Eliminar es solo para un instructivo creado por error: se borra sin dejar rastro. Si alguna vez se usó, marcarlo obsoleto. ¿Eliminar?')) return;
  try { await api('/api/instructivos/' + id, { metodo: 'DELETE' }); await recargarOpciones(); avisar('Instructivo eliminado.'); irA('instructivos'); }
  catch (e) { avisar(e.message, true); }
}

// Al entrar: las listas de los formularios (personas, equipos, secciones...) y el Plan.
Nucleo.alEntrar.push(recargarOpciones);

// En Opciones, para un administrador: programar de una vez lo que falta en el Plan.
Nucleo.tarjetasOpciones.push({
  orden: 20,
  html: async () => S.usuario.es_admin ? `<div class="tarjeta" id="op-plan"><h3>Plan de mantenimiento</h3>
    <p class="sutil">Programa de una vez todas las secciones de instructivos que los equipos todavía no tienen en el Plan.
      La frecuencia viene sugerida por la tabla «Frecuencias» de cada instructivo; antes de guardar se revisa y se corrige.</p>
    <button class="primario" onclick="modalProgramarTodos()">Programar todos</button></div>` : '',
});
