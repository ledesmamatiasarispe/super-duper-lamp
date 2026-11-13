'use strict';
// ── Módulo MANTENIMIENTO: la Ayuda de sus pantallas y sus pasos del Tour completo ──
// El motor es del núcleo (nucleo/frontend/ayuda.js); acá solo los pasos, registrados en Ayuda.pasos y Ayuda.tour.
(function () {
  const { uno, enVista, boton, tarjeta, campo, botonModal, menu } = Ayuda.h;
  const COMO_VER_OCULTOS = 'Marcá <b>Ver ocultos</b> (el número dice cuántos hay) y aparecen tachados, con el botón para reactivarlos. Se recuerda mientras navegás.';
  const VER_OCULTOS = 'Lo dado de baja <b>no se borra</b>: queda oculto para no estorbar. ' + COMO_VER_OCULTOS;
  /** Un símbolo del cronograma con los mismos colores que su leyenda. */
  const sim = (estado, c) => `<b class="ayuda-simbolo c-${estado}">${c}</b>`;
  /** El primer instructivo de algún equipo (S.equipos lo llena la pantalla de Equipos, que el tour visita antes). */
  const algunInstructivo = () => {
    const e = (typeof S !== 'undefined' && S.equipos || []).find(x => x.instructivo_ids?.length);
    return e ? 'instructivos/' + e.instructivo_ids[0] : null;
  };

  Object.assign(Ayuda.pasos, {
    inicio: () => [
      { titulo: 'Inicio: lo que hay que hacer', texto: 'Esta pantalla junta lo que está pendiente <b>hoy</b>: lo que toca este mes, lo que quedó atrasado y los servicios por horas que se acercan. '
        + 'Se arma sola con las tareas del <b>Plan</b> y lo que ya se registró: no hay que cargar nada acá.' },
      { el: () => boton('Registrar mantenimiento'), titulo: 'Registrar mantenimiento', texto: 'Para anotar un <b>preventivo</b> que se hizo: elegís la tarea, ves sus actividades del instructivo, y cargás fecha, resultado, quién lo hizo y las novedades. '
        + 'Es el mismo formulario que se abre desde el Cronograma y desde Registros.' },
      { el: () => boton('Registrar correctivo'), titulo: 'Registrar correctivo', texto: 'Para una <b>falla o rotura</b> que no estaba programada: qué falló, la causa, qué se hizo y cuántas horas estuvo parado el equipo. Se ve después en la pestaña Correctivos.' },
      { el: () => boton('Imprimir lista del mes'), titulo: 'Imprimir lista del mes', texto: 'Imprime en una hoja apaisada lo atrasado, lo de este mes y los servicios por horas vencidos o próximos, '
        + 'con casilleros en blanco (hecho, fecha, quién, observaciones) para llevar al taller. Lo que se hizo se registra después acá.' },
      { el: () => tarjeta('Cumplimiento'), titulo: 'Cumplimiento del año', texto: 'De todos los servicios que tocaban en los <b>meses ya cerrados</b>, cuántos se hicieron. Lo hecho <b>fuera de término</b> (en un mes posterior, antes de que volviera a tocar) cuenta como hecho, y abajo se ve cuántos fueron <b>a tiempo</b>. El mes en curso todavía no cuenta: hay tiempo hasta fin de mes. '
        + 'Cuentan como hechos los registrados como <b>Realizado</b> o <b>Con observaciones</b>.' },
      { el: () => tarjeta('Este mes'), titulo: 'Este mes', texto: 'Las tareas que tocan este mes y todavía no se registraron. Cuando una se registra, desaparece de la lista. '
        + 'Si dice <b>"faltan 2"</b> es una tarea que se hace más de una vez por mes (por ejemplo, quincenal).' },
      { el: () => enVista('table tbody tr button')?.closest('tr'), titulo: 'Cada tarea pendiente', texto: 'Una fila por tarea: el código, el equipo, la sección del instructivo (tocala para ver qué actividades lleva), la frecuencia y el responsable. '
        + '<b>Registrar</b> abre el formulario con esa tarea ya elegida.' },
      { el: () => tarjeta('Atrasados'), titulo: 'Atrasados', texto: 'Lo que tocaba en <b>meses anteriores</b> y no se registró: en el Cronograma figura como vencido (✗). '
        + 'Si se hizo y no se anotó, registralo con la fecha real; si se hizo tarde, con la fecha en que se hizo.' },
      { el: () => tarjeta('Servicios por horas'), titulo: 'Servicios por horas', texto: 'Los servicios que dependen de las <b>horas de uso</b> del equipo (su horómetro), no del calendario. Aparecen acá cuando están cerca o vencidos, '
        + 'o cuando falta un dato: <b>"Sin lectura"</b> es que nunca se anotó el horómetro de ese equipo. <b>Ver horómetros</b> lleva a la grilla completa.' },
    ],

    cronograma: () => [
      { titulo: 'Cronograma anual', texto: 'La planilla del año: una fila por cada tarea del <b>Plan</b> (una sección del instructivo aplicada a un equipo) y una columna por mes. '
        + 'Se completa sola a medida que se registran los mantenimientos.' },
      { el: () => conTexto('.encabezado button', '◄', vista()), titulo: 'Cambiar de año', texto: 'Con <b>◄</b> y <b>►</b> pasás al año anterior o al siguiente. El año elegido se usa también en Registros, Correctivos, Personal y Áreas.' },
      { el: () => enVista('.encabezado .chip'), titulo: 'Cumplimiento', texto: 'Servicios hechos (a tiempo o fuera de término) sobre los que tocaban en los meses ya cerrados, y al lado cuántos fueron a tiempo. Verde desde 90 %, ámbar desde 70 %, rojo por debajo.' },
      { el: () => boton('Imprimir'), titulo: 'Imprimir', texto: 'Imprime la planilla (o la guarda como PDF), sin el menú ni los botones.' },
      { el: () => { const f = enVista('.crono tbody tr'); return f ? [...f.children].slice(0, 5) : null; }, titulo: 'Cada fila es una tarea', texto: 'El código de la tarea, el equipo, la sección del instructivo (tocala para abrirlo), la frecuencia y el responsable. '
        + 'Los servicios <b>por horas</b> dicen "c/ 1000 h": esos se siguen en <b>Horómetros</b>, no por mes.' },
      { el: () => enVista('.crono thead th.mes.actual'), titulo: 'El mes en curso', texto: 'La columna resaltada es el mes actual.' },
      { el: () => {   // un casillero con algo adentro: del mes en curso si hay, si no cualquiera
          const i = [...vista().querySelectorAll('.crono thead th')].findIndex(t => t.classList.contains('actual'));
          const llenos = todos('.crono tbody td.mes', vista()).filter(td => td.textContent.trim());
          return llenos.find(td => [...td.parentNode.children].indexOf(td) === i) || llenos[0] || enVista('.crono tbody td.mes');
        }, titulo: 'Tocá un mes para registrar', texto: `Cada casillero muestra cómo está ese mes: ${sim('pendiente', '○')} programado, ${sim('hecho', '✓')} hecho, ${sim('tarde', '✓')} hecho fuera de término (en un mes posterior, que muestra ${sim('cubre', '↩')}), ${sim('vencido', '✗')} vencido, ${sim('reprogramado', '↻')} reprogramado. Si va más de una vez por mes muestra "1/2". `
        + 'Al tocarlo se abre el registro de esa tarea con la fecha ya sugerida: hoy si es el mes en curso, o el día 1 de ese mes. En la computadora, dejando el mouse encima se ve el detalle.' },
      { el: () => enVista('.leyenda'), titulo: 'Qué significa cada símbolo', texto: 'Un casillero <b>vacío</b> es que ese mes no toca. <b>–</b> es que se registró <b>No aplica</b>, y <b>·</b> que la tarea todavía no estaba cargada en el Plan: '
        + 'ninguno de los dos cuenta como atraso. Reprogramado y no realizado sí cuentan en contra del cumplimiento.' },
    ],

    registros: () => [
      { titulo: 'Registros del año', texto: 'El historial de todos los <b>preventivos</b> registrados en el año, del más nuevo al más viejo. Los correctivos (fallas) tienen su propia pestaña.' },
      { el: () => conTexto('.encabezado button', '◄', vista()), titulo: 'Cambiar de año', texto: 'Para ver los registros de otro año.' },
      { el: () => boton('Registrar lectura de horómetro'), titulo: 'Lectura de horómetro', texto: 'Para anotar las <b>horas que marca el horómetro</b> de un equipo cuando no se hizo ningún servicio. Así Inicio y Horómetros saben cuánto falta para el próximo. '
        + 'Si se hizo un servicio, no hace falta: la lectura se carga en el mismo registro.' },
      { el: () => boton('Registrar mantenimiento'), titulo: 'Registrar mantenimiento', texto: 'Para anotar un preventivo hecho. Es el mismo formulario que en Inicio y en el Cronograma.' },
      { el: () => enVista('table thead'), titulo: 'Qué se ve de cada registro', texto: 'Fecha, tarea, equipo, sección del instructivo, el <b>resultado</b> (si se reprogramó, abajo dice para cuándo), quién lo hizo, horas-hombre, '
        + 'la lectura del horómetro si tenía, novedades y repuestos usados.' },
      { el: () => boton('Anular'), titulo: 'Anular (solo administradores)', texto: 'Es solo para <b>corregir una carga equivocada</b>: borra el registro junto con su lectura de horómetro, y el mes vuelve a quedar pendiente. '
        + 'Si el trabajo se hizo mal, no se anula: se registra otro con lo que corresponda.' },
    ],

    horometros: () => [
      { titulo: 'Horómetros', texto: 'Como el cronograma, pero para los servicios que van por <b>horas de uso</b>: un cuadro por cada equipo con horómetro. '
        + 'Las lecturas no se cargan acá: se cargan en <b>Registros</b>, al registrar un servicio o con "Registrar lectura de horómetro".' },
      { el: () => enVista('.encabezado .botones'), titulo: 'Moverse por las horas', texto: 'Cada columna es un bloque de horas. <b>◄ horas antes</b> y <b>horas después ►</b> corren la grilla; <b>Ahora</b> la vuelve a centrar en la última lectura.' },
      { el: () => boton('Cambio de horómetro'), titulo: 'Cambio de horómetro', texto: 'Si el horómetro se rompe o se reemplaza, el nuevo arranca de otro número. '
        + 'Se anota acá (fecha, lo que marca el nuevo y, si se sabe, lo que marcaba el viejo): desde esa fecha las lecturas son del nuevo, '
        + 'y a cada servicio por horas le queda lo mismo que le faltaba. Solo administradores.' },
      { el: () => enVista('.tarjeta h3 + p'), titulo: 'Última lectura', texto: 'Lo último que se anotó del horómetro de ese equipo y en qué fecha. Todo lo de abajo se calcula desde este número.' },
      { el: () => enVista('.tarjeta table.crono tbody tr'), titulo: 'Cada servicio por horas', texto: 'Código y sección del instructivo, cada cuántas horas se hace y a cuántas horas toca el <b>próximo</b>, con cuánto falta (o por cuánto se pasó). '
        + '<b>Sin lectura</b>: nunca se anotó el horómetro. <b>Falta dato</b>: en el Plan falta a qué horas va el primer servicio.' },
      { el: () => enVista('.tarjeta table.crono th.actual'), titulo: 'Dónde está el equipo', texto: 'El <b>▲</b> marca el bloque de horas de la última lectura.' },
      { el: () => enVista('.tarjeta table.crono td.mes'), titulo: 'Tocá un casillero para registrar', texto: `Abre el registro de ese servicio. ${sim('hecho', '✓')} hecho, ${sim('pendiente', '○')} programado (${sim('reprogramado', '○')} si ya está cerca), ${sim('vencido', '✗')} vencido o hecho tarde.` },
      { el: () => tarjeta('Últimas lecturas'), titulo: 'Últimas lecturas', texto: 'Las lecturas anotadas, de todos los equipos: las de los servicios y las sueltas.' },
    ],

    correctivos: () => [
      { titulo: 'Correctivos', texto: 'Las <b>reparaciones no programadas</b> del año: fallas, roturas, arreglos de urgencia. Sirven para ver qué equipos fallan más y cuánto tiempo estuvieron parados.' },
      { el: () => enVista('.encabezado .chip'), titulo: 'Resumen', texto: 'Cuántos correctivos hubo en el año y el total de horas de parada.' },
      { el: () => boton('Registrar correctivo'), titulo: 'Registrar correctivo', texto: 'Equipo, falla o síntoma, causa, qué se hizo, horas de parada, horas-hombre, quién lo hizo y repuestos.' },
      { el: () => conTexto('#vista th', 'SGC'), titulo: 'Acción del SGC', texto: 'Dice <b>Sí</b> cuando al registrar se marcó que la falla requiere una acción del sistema de calidad (abrir un RAC).' },
    ],

    plan: () => [
      { titulo: 'Plan de mantenimiento', texto: 'Acá se decide <b>qué se hace, a qué equipo y cada cuánto</b>. Cada tarea es una <b>sección de un instructivo</b> aplicada a un equipo, con su frecuencia. '
        + 'El Cronograma, Inicio y Horómetros salen de esta lista.' },
      { el: () => boton('Nueva tarea'), titulo: 'Nueva tarea (solo administradores)', texto: 'Primero se elige el equipo y después la sección: solo aparecen las de sus instructivos que todavía no están programadas. '
        + 'Después la frecuencia: por mes (con mes de inicio o meses específicos), <b>por horas</b> (cada cuántas y a cuántas va el primero) o según condición.' },
      { el: () => enVista('.ver-ocultos'), titulo: 'Ver ocultos', texto: VER_OCULTOS },
      { el: () => enVista('table tbody tr:not(.baja)'), titulo: 'Cada tarea', texto: 'Código de la tarea, equipo, la sección del instructivo (tocala para ver sus actividades), la frecuencia y <b>cuándo</b>: '
        + 'desde qué mes, en qué meses, o cada cuántas horas y a cuántas el primer servicio.' },
      { el: () => boton('Editar'), titulo: 'Editar', texto: 'Cambia la frecuencia, el responsable o las observaciones. Lo ya registrado no se pierde.' },
      { el: () => boton('Dar de baja'), titulo: 'Dar de baja no es eliminar', texto: 'La tarea deja de aparecer en el Cronograma y en Inicio, pero <b>sus registros se conservan</b>. Se puede reactivar desde <b>Ver ocultos</b>.' },
    ],

    equipos: () => [
      { titulo: 'Equipos e instructivos', texto: 'La lista de equipos de la planta, cada uno con su <b>instructivo</b> de mantenimiento: el documento con la seguridad, las actividades y los repuestos.' },
      { el: () => boton('Nuevo equipo'), titulo: 'Nuevo equipo (solo administradores)', texto: 'Nombre, área, marca/modelo y si tiene horómetro. El código (EQ-…) se pone solo. '
        + 'Si es <b>parecido a otro equipo</b> que ya está, elegilo y arranca con una <b>copia</b> de su instructivo; si no, al guardar se abre el instructivo nuevo para cargarlo.' },
      { el: () => enVista('.ver-ocultos'), titulo: 'Ver ocultos', texto: 'Los equipos marcados obsoletos no se borran: quedan ocultos con todo su historial. ' + COMO_VER_OCULTOS },
      { el: () => enVista('table tbody tr:not(.baja) td:nth-child(6)'), titulo: 'Su instructivo', texto: 'Código y revisión del instructivo, y qué secciones ya están <b>en el Plan</b> (A, B…). '
        + 'Si dice <b>sin programar</b>, el instructivo existe pero todavía no se le asignó una frecuencia: no va a aparecer en el Cronograma.' },
      { el: () => boton('Ver instructivo'), titulo: 'Ver instructivo', texto: 'Abre el documento para leerlo o imprimirlo.' },
      { el: () => boton('Crear instructivo'), titulo: 'Crear instructivo', texto: 'Aparece en un equipo que todavía no tiene. Arranca con los datos del equipo ya puestos.' },
      { el: () => boton('Editar'), titulo: 'Editar el equipo', texto: 'Cambia sus datos o deja de usar un instructivo. Si todavía no tiene, le podés copiar el de un equipo parecido, o asignarle uno que haya quedado sin equipo.' },
      { el: () => boton('Marcar obsoleto'), titulo: 'Marcar obsoleto', texto: 'Para un equipo que <b>ya no está</b> (se vendió, se desarmó). Pide el motivo y da de baja sus tareas del Plan, pero <b>su historial queda guardado</b>. '
        + 'Si vuelve, se reactiva desde Ver ocultos (sus tareas se reactivan aparte, en el Plan).' },
      { el: () => boton('Eliminar'), titulo: 'Eliminar', texto: 'Solo para un equipo <b>cargado por error</b>: lo borra sin dejar rastro. Por eso aparece únicamente en los que no tienen nada vinculado.' },
      { el: () => conTexto('#vista p.sutil', 'Instructivos sin equipo'), titulo: 'Instructivos sueltos', texto: 'Instructivos que no están asignados a ningún equipo. Se asignan desde <b>Editar</b> del equipo.' },
    ],

    instructivo: () => [
      { titulo: 'El instructivo', texto: 'El documento de mantenimiento del equipo: lo que hay que hacer, en orden, y con qué cuidados. Es lo que se imprime para tener en el taller.' },
      { el: () => conTexto('#vista .encabezado a', 'Equipos'), titulo: 'Volver', texto: 'Vuelve a la lista de equipos e instructivos.' },
      { el: () => boton('Imprimir'), titulo: 'Imprimir / PDF', texto: 'Imprime el documento limpio, sin botones ni el historial.' },
      { el: () => enVista('.doc-cabecera'), titulo: 'Cabecera', texto: 'Código y nombre del instructivo, y la <b>revisión</b> vigente con su fecha. Cada vez que se modifica, sube la revisión.' },
      { el: () => conTexto('#vista .doc h3', 'Seguridad'), titulo: 'Seguridad', texto: 'Lo que hay que tener en cuenta antes de empezar: bloqueos, elementos de protección, etc.' },
      { el: () => enVista('.doc .seccion-cab'), titulo: 'Secciones', texto: 'El instructivo se divide en <b>secciones</b> (A, B, C…): grupos de actividades que se hacen juntas. Cada una se programa en el Plan con <b>su propia frecuencia</b> '
        + '(por ejemplo, A mensual y B cada 1000 h). El cartel verde dice con qué tarea y cada cuánto está programada; <b>sin programar</b> quiere decir que todavía no.' },
      { el: () => enVista('.doc ol.actividades'), titulo: 'Actividades', texto: 'Los pasos numerados de la sección. Los títulos en negrita agrupan pasos, y los puntos de abajo son el detalle de cada uno. '
        + 'Al registrar un mantenimiento, esta lista se muestra en el formulario para tenerla a la vista.' },
      { el: () => conTexto('#vista .doc h3', 'Repuestos'), titulo: 'Repuestos e insumos', texto: 'Lo que conviene tener a mano para hacer el mantenimiento, con la cantidad mínima cuando está indicada.' },
      { el: () => conTexto('#vista .doc h3', 'Archivos adjuntos'), titulo: 'Archivos adjuntos', texto: 'Planos, manuales u otros archivos del equipo. Tocá el nombre para abrirlo o descargarlo.' },
      { el: () => boton('Modificar'), titulo: 'Modificar (solo administradores)', texto: 'Abre el editor. Al guardar se crea una <b>revisión nueva</b>: la anterior queda en el historial, con el motivo del cambio.' },
      { el: () => boton('Programar en el Plan'), titulo: 'Programar en el Plan', texto: 'Aparece cuando alguna sección todavía no está programada: abre una tarea nueva del Plan con esa sección ya elegida, para ponerle la frecuencia.' },
      { el: () => boton('Marcar obsoleto'), titulo: 'Marcar obsoleto', texto: 'Cuando el instructivo ya no se usa: queda guardado para consulta, con una franja roja de <b>OBSOLETO</b>.' },
      { el: () => boton('Eliminar'), titulo: 'Eliminar', texto: 'Solo para uno <b>creado por error</b>. Si alguna vez se usó, se marca obsoleto.' },
      { el: () => tarjeta('Historial de revisiones'), titulo: 'Historial de revisiones', texto: 'Cada revisión anterior, con qué cambió, quién y cuándo. <b>Ver</b> muestra cómo era el documento en esa revisión.' },
    ],

    editor: () => [
      { titulo: 'Editor del instructivo', texto: 'Acá se escribe el instructivo. Si se está modificando uno que ya existe, al guardar <b>sube la revisión</b> y la anterior queda guardada en el historial.' },
      { el: () => { const f = document.getElementById('f-it'); return f ? [f.titulo, f.descripcion].map(x => x?.closest('label')) : null; }, titulo: 'Título y descripción', texto: 'El nombre del equipo o del instructivo, y una línea que diga de qué se trata.' },
      { el: () => document.getElementById('f-it')?.seguridad?.closest('label'), titulo: 'Seguridad', texto: 'Una indicación por renglón. Va siempre al principio del documento.' },
      { el: () => document.getElementById('ed-contenido'), titulo: 'El contenido, en orden', texto: 'Todo lo que va debajo de la seguridad, en el orden en que se va a leer: secciones de actividades, bloques (texto, notas, tablas, imágenes, gráficos) y los repuestos.' },
      { el: () => enVista('#ed-contenido .posicion'), titulo: 'Mover con el número', texto: 'El número es la <b>posición</b> en el documento. Para mover algo, cambiale el número: el resto se acomoda solo y lo movido se resalta un momento.' },
      { el: () => enVista('#ed-contenido .editor-seccion textarea'), titulo: 'Actividades de una sección', texto: 'Una actividad por renglón; se numeran solas. Un renglón que empieza con <b>#</b> es un título de grupo, y uno que empieza con <b>-</b> es un detalle de la actividad de arriba. '
        + 'Cada sección se programa después en el Plan con su propia frecuencia.' },
      { el: () => enVista('#ed-contenido .editor-seccion .chip.verde') || boton('Quitar sección'), titulo: 'Secciones programadas', texto: 'Una sección que ya está <b>en el Plan</b> muestra su tarea y no se puede quitar mientras siga programada. Las que no están programadas tienen el botón <b>Quitar sección</b>.' },
      { el: () => enVista('#ed-contenido table.lista-editable'), titulo: 'Repuestos e insumos', texto: 'Un repuesto por renglón, con la <b>cantidad mínima</b> que conviene tener (opcional; acepta decimales con coma): escribilo abajo y tocá <b>Agregar</b> (o Enter). '
        + 'Cada uno se puede corregir ahí mismo o quitar con <b>Eliminar</b>. '
        + 'Para cambiar el orden, arrastralo con el mouse desde la manija <b>⠿</b>. Lo que quede escrito abajo sin agregar también se guarda.' },
      { el: () => enVista('#ed-contenido + .botones'), titulo: 'Agregar contenido', texto: 'Suma al final una sección de actividades nueva (la letra sigue sola) o un bloque: <b>texto</b>, <b>nota destacada</b> (nota, precaución o peligro), '
        + '<b>tabla</b> (celdas separadas con |), <b>imagen</b> o <b>gráfico</b>. Después lo llevás a su lugar con el número.' },
      { el: () => document.getElementById('ed-adjuntos'), titulo: 'Imágenes y archivos', texto: 'Subí fotos para mostrar en el documento (se agregan como bloque de imagen) o archivos como planos, manuales o planillas, que se listan al final para descargar. '
        + 'Un archivo que nadie usa se puede borrar. En un instructivo nuevo, esto se habilita después de crearlo.' },
      { el: () => document.getElementById('f-it')?.motivo?.closest('label'), titulo: 'Motivo del cambio', texto: 'Qué se cambió y por qué. Queda en el historial de revisiones: es obligatorio.' },
      { el: () => uno('#f-it > .botones .primario'), titulo: 'Guardar', texto: 'Guarda el instructivo (o la revisión nueva). <b>Cancelar</b> o <b>Después</b> salen sin guardar lo escrito.' },
    ],

    mapa: () => [
      { titulo: 'Mapa de planta', texto: 'Planos de la planta dibujados en la app, con las máquinas como puntos. Puede haber uno por nave o sector; cada máquina está en un solo plano.' },
      { el: () => enVista('.mapa-pestanas'), titulo: 'Los planos', texto: 'Cada botón abre un plano.' },
      { el: () => enVista('.mapa-leyenda'), titulo: 'El color de cada máquina', texto: 'Es lo mismo que muestra Inicio: <b>rojo</b> si tiene algo vencido o atrasado, <b>ámbar</b> si le toca algo este mes o un servicio por horas está cerca, '
        + '<b>azul</b> si a un servicio por horas le falta un dato (lectura o próximo inicial) y <b>verde</b> si está al día.' },
      { el: () => enVista('#mapa-svg'), titulo: 'Tocar una máquina', texto: 'Muestra lo que tiene pendiente, con el botón <b>Registrar</b> para cargarlo ahí mismo.' },
      { el: () => boton('Nuevo plano'), titulo: 'Nuevo plano (solo administradores)', texto: 'Nombre y medidas en metros del área a dibujar. Al crearlo se abre para dibujar.' },
      { el: () => boton('Editar este plano'), titulo: 'Editar (solo administradores)', texto: 'Se dibuja sobre una grilla: <b>Rectángulo</b> para naves, sectores o salas (con nombre y color), <b>Línea / pared</b> y <b>Texto</b>. '
        + 'Con <b>Seleccionar / mover</b> se elige algo para cambiarlo, arrastrarlo o borrarlo (tecla Supr). Las máquinas se ponen con <b>Ubicar</b> y después un toque en el plano; '
        + 'una que estaba en otro plano se muda. Nada se guarda hasta <b>Guardar plano</b>.' },
      { el: () => boton('Eliminar plano'), titulo: 'Eliminar plano', texto: 'Borra solo el dibujo: sus máquinas quedan sin ubicar y su historial no se toca.' },
    ],
    personal: () => [
      { titulo: 'Personal y proveedores', texto: 'Quiénes hacen los trabajos, y cuántos preventivos y correctivos hizo cada uno en el año, con sus horas-hombre.' },
      { el: () => tarjeta('Mantenimiento interno'), titulo: 'Mantenimiento interno', texto: 'Los operarios de mantenimiento. Los usuarios del sistema aparecen solos acá (su nombre se cambia en Usuarios).' },
      { el: () => tarjeta('Proveedores externos'), titulo: 'Proveedores externos', texto: 'Empresas o personas de afuera que hacen trabajos, con su contacto y rubro.' },
      { el: () => conTexto('#vista td', 'Otros, sin dar de alta'), titulo: 'Otros, sin dar de alta', texto: 'Al registrar, si quien hizo el trabajo no está en la lista se elige "Otro" y se escribe el nombre. Esos nombres aparecen acá, para darlos de alta si hace falta.' },
      { el: () => boton('Ver trabajos'), titulo: 'Ver trabajos', texto: 'La lista de todo lo que hizo esa persona en el año.' },
      { el: () => enVista('.ver-ocultos'), titulo: 'Ver ocultos', texto: 'Dar de baja a alguien lo saca de las listas para elegir, pero <b>sus trabajos se siguen contando</b>. ' + COMO_VER_OCULTOS },
    ],

    areas: () => [
      { titulo: 'Áreas', texto: 'Las áreas de la planta, con cuántos equipos tiene cada una y lo que pasó en el año: preventivos, correctivos y horas de parada.' },
      { el: () => boton('Nueva área'), titulo: 'Nueva área', texto: 'También se puede crear desde el formulario del equipo, con "+ Nueva área…".' },
      { el: () => boton('Renombrar'), titulo: 'Renombrar', texto: 'Corrige el nombre en <b>todos</b> sus equipos de una vez.' },
      { el: () => boton('Eliminar'), titulo: 'Eliminar', texto: 'Solo aparece en un área sin equipos: es para una creada por error. Para dejar de usarla, se da de baja.' },
      { el: () => enVista('.ver-ocultos'), titulo: 'Ver ocultos', texto: VER_OCULTOS },
    ],



    // ── formularios del modal ──
    'f-registro': () => [
      { el: () => campo('tarea_id'), titulo: 'La tarea', texto: 'Qué mantenimiento se hizo: código, equipo, sección del instructivo y frecuencia. Si se abrió desde una tarea, ya viene elegida.' },
      { el: () => uno('#r-checklist .checklist'), titulo: 'Las actividades, a la vista', texto: 'Lo que dice el instructivo para esa sección, para repasar que no falte nada.' },
      { el: () => campo('fecha'), titulo: 'Fecha', texto: 'Cuándo se hizo. No puede ser una fecha futura. El mes de esta fecha es el que queda cumplido en el Cronograma.' },
      { el: () => campo('resultado'), titulo: 'Resultado', texto: '<b>Realizado</b> y <b>Con observaciones</b> cuentan como hecho. <b>No realizado</b> deja el mes marcado con ✗ en el Cronograma. '
        + '<b>Reprogramado</b> pide para qué fecha se pasó. Esos dos cuentan en contra del cumplimiento. <b>No aplica</b>, cuando ese mes no correspondía hacerlo: no cuenta ni a favor ni en contra.' },
      { el: () => campo('realizado_por_id'), titulo: 'Realizado por', texto: 'Viene puesto el usuario que está cargando. Si fue alguien que no está en la lista, elegí <b>"Otro … (escribir nombre)"</b> y aparece la casilla para escribirlo.' },
      { el: () => campo('horas_hombre'), titulo: 'Horas-hombre', texto: 'Cuántas horas de trabajo llevó, sumando a todos los que participaron.' },
      { el: () => campo('horometro'), titulo: 'Horómetro', texto: 'Solo aparece si el equipo tiene horómetro: anotá las horas que marca. Queda como lectura del equipo y desde ahí se cuenta el próximo servicio por horas.' },
      { el: () => [campo('novedades'), campo('repuestos')], titulo: 'Novedades y repuestos', texto: 'Lo que se encontró o quedó pendiente, y los repuestos que se usaron.' },
      { el: () => botonModal('Guardar'), titulo: 'Guardar', texto: 'Si falta algo o hay un dato mal, el aviso aparece en rojo arriba de este botón y el formulario no se cierra.' },
    ],
    'f-correctivo': () => [
      { el: () => campo('equipo_id'), titulo: 'Equipo', texto: 'El equipo que falló.' },
      { el: () => [campo('falla'), campo('causa'), campo('accion')], titulo: 'Qué pasó', texto: 'La <b>falla</b> o lo que se notó (obligatorio), la <b>causa</b> si se encontró, y la <b>acción</b>: qué se hizo para arreglarlo.' },
      { el: () => [campo('horas_parada'), campo('horas_hombre')], titulo: 'Horas', texto: '<b>Horas de parada</b>: cuánto tiempo el equipo no pudo trabajar. <b>Horas-hombre</b>: cuánto trabajo llevó el arreglo.' },
      { el: () => campo('realizado_por_id'), titulo: 'Realizado por', texto: 'Quién lo arregló. Si no está en la lista, elegí "Otro" y escribí el nombre.' },
      { el: () => campo('accion_sgc'), titulo: 'Acción del SGC', texto: 'Marcalo si la falla requiere una acción del sistema de calidad (abrir un RAC).' },
    ],
    'f-lectura': () => [
      { el: () => campo('equipo_id'), titulo: 'Equipo', texto: 'Solo aparecen los equipos que tienen horómetro.' },
      { el: () => campo('horas'), titulo: 'Horómetro', texto: 'Las horas que marca ahora. Con esto se recalcula cuánto falta para cada servicio por horas de ese equipo.' },
      { el: () => campo('anoto_id'), titulo: 'Anotó', texto: 'Quién leyó el horómetro (opcional).' },
    ],
    'f-tarea': () => [
      { el: () => campo('equipo_id'), titulo: 'Primero, el equipo', texto: 'Al elegirlo, la lista de abajo muestra solo las secciones de sus instructivos que todavía no están en el Plan.' },
      { el: () => campo('seccion_id'), titulo: 'La sección del instructivo', texto: 'Qué grupo de actividades se va a programar. Si dice "no tiene instructivos asignados", hay que asignarle uno desde Equipos.' },
      { el: () => campo('frecuencia'), titulo: 'Frecuencia', texto: 'Cada cuánto se hace. Las mensuales, trimestrales, etc. van al Cronograma; <b>Por horas</b> va a Horómetros; <b>Según condición</b> se hace cuando hace falta y no se programa.' },
      { el: () => [campo('mes_inicio'), campo('meses_especificos')], titulo: 'Qué meses', texto: 'El <b>mes de inicio</b> fija desde cuándo se cuenta (una trimestral que arranca en febrero toca feb, may, ago y nov). '
        + 'O escribí los <b>meses específicos</b> separados con coma, por ejemplo "3, 9".' },
      { el: () => [campo('cada_horas'), campo('proximo_inicial')], titulo: 'Por horas', texto: '<b>Cada</b> cuántas horas de uso, y a cuántas horas va el <b>primer servicio</b>. Después del primero, el próximo se cuenta desde la lectura del último servicio hecho.' },
      { el: () => campo('responsable_id'), titulo: 'Responsable', texto: 'Quién se encarga normalmente. Al registrar, se sugiere como "Realizado por".' },
    ],
    'f-equipo': () => [
      { el: () => campo('nombre'), titulo: 'Nombre', texto: 'Cómo se lo conoce en planta. El código (EQ-…) se asigna solo.' },
      { el: () => campo('area_id'), titulo: 'Área', texto: 'Dónde está. Si el área no existe, elegí <b>"+ Nueva área…"</b> y se crea ahí mismo.' },
      { el: () => campo('usa_horometro'), titulo: 'Horómetro', texto: 'Marcalo si el equipo tiene horómetro: así se puede programar por horas de uso y se pide la lectura en cada servicio.' },
      { el: () => campo('igual_a'), titulo: 'Equipo parecido: copiar su instructivo', texto: 'Si ya hay uno parecido, escribí su código o nombre y elegilo de la lista: el equipo arranca con una <b>copia</b> de su instructivo (con imágenes y archivos), '
        + 'con la ficha y el título ya cambiados al equipo nuevo. Cada uno queda independiente: cambiar uno no toca al otro. Si lo dejás vacío, se carga uno nuevo.' },
    ],
  });

  // Usuarios y Opciones son del núcleo: acá se suma lo propio de mantenimiento.
  const usuariosNucleo = Ayuda.pasos.usuarios, opcionesNucleo = Ayuda.pasos.opciones;
  Ayuda.pasos.usuarios = () => [...usuariosNucleo(),
    { titulo: 'Usuarios y Personal', texto: 'Cada usuario figura solo en <b>Personal</b> (Mantenimiento interno), con su mismo nombre y su misma alta. Se entra con el <b>legajo</b>.' }];
  Ayuda.pasos.opciones = () => [...opcionesNucleo(),
    { el: () => boton('Programar todos'), titulo: 'Programar todos (solo administradores)', texto: 'Arma de una vez las tareas del Plan que faltan: una por cada sección de instructivo que un equipo todavía no tiene programada. '
      + 'La frecuencia viene sugerida por la tabla «Frecuencias» del instructivo; se revisa en la lista (frecuencia, mes de inicio, horas) y se guardan todas juntas. '
      + '<b>Repartir meses</b> elige los meses de inicio para que los trabajos no se junten en los mismos meses, contando también lo que ya está en el Plan.' }];

  // El editor de instructivo no cambia el hash (se reconoce por su formulario) y un instructivo cuelga de Equipos.
  Ayuda.detectores.push(() => document.getElementById('f-it') ? 'editor' : null);
  Ayuda.detectores.push(() => {
    const [v, param] = (location.hash.slice(1) || 'inicio').split('/');
    return v === 'instructivos' ? (param ? 'instructivo' : 'equipos') : null;
  });

  Ayuda.tour.push(
    { ir: 'inicio', titulo: 'La idea en una línea', texto: 'Cada <b>equipo</b> tiene un <b>instructivo</b> dividido en <b>secciones</b>. Cada sección se programa en el <b>Plan</b> con una frecuencia, y eso arma el <b>Cronograma</b>. '
      + 'Cuando alguien hace el trabajo, lo <b>registra</b>, y el Cronograma y el cumplimiento se actualizan solos.' },

    // 1. equipos
    { ir: 'equipos', el: () => menu('equipos'), titulo: '1 · Equipos', texto: 'Todo empieza por los <b>equipos</b> de la planta: cada uno con su código (EQ-…), su <b>área</b>, marca/modelo y si tiene <b>horómetro</b>.' },
    { ir: 'equipos', el: () => enVista('table'), titulo: 'Un instructivo por equipo', texto: 'Cada equipo tiene <b>su propio</b> instructivo: al crear el equipo se crea el suyo. Si es <b>parecido a otro</b> que ya existe (dos compresores iguales), se elige ese y '
      + 'el nuevo arranca con una <b>copia</b> de su instructivo, para no cargar todo de nuevo. Desde ahí cada uno cambia por su lado.' },
    { ir: 'equipos', el: () => enVista('.ver-ocultos'), titulo: 'Dar de baja no es eliminar', texto: 'Es una regla de toda la app: un equipo que ya no está se marca <b>obsoleto</b> y queda oculto, <b>con todo su historial</b>. '
      + '<b>Eliminar</b> es solo para lo cargado por error y aparece únicamente si no tiene nada vinculado. Lo oculto se ve con <b>Ver ocultos</b>.' },

    // 2. instructivo
    { ir: algunInstructivo, el: () => enVista('.doc-cabecera'), titulo: '2 · El instructivo', texto: 'El documento que dice <b>cómo</b> se hace el mantenimiento. Arriba siempre van la descripción y la <b>seguridad</b>; lo demás va en el orden que se elija al editarlo.' },
    { ir: algunInstructivo, el: () => enVista('.doc .seccion-cab'), titulo: 'Secciones', texto: 'Las franjas oscuras son las <b>secciones</b> (A, B, C…): grupos de actividades que se hacen juntas. Son la pieza clave, porque <b>cada sección se programa por separado</b>: '
      + 'por ejemplo, la A todos los meses y la B cada 1000 horas.' },
    { ir: algunInstructivo, el: () => tarjeta('Historial de revisiones'), titulo: 'Revisiones', texto: 'Un instructivo no se pisa: cada cambio crea una <b>revisión nueva</b> con el motivo, quién y cuándo, y las anteriores se pueden consultar. '
      + 'Para eso es el botón <b>Modificar</b> (solo administradores).' },

    // 3. plan
    { ir: 'plan', el: () => menu('plan'), titulo: '3 · El Plan', texto: 'Acá se decide <b>qué se hace, a qué equipo y cada cuánto</b>. Cada fila es una <b>tarea</b> = una sección del instructivo + un equipo + una frecuencia.' },
    { ir: 'plan', el: () => enVista('table'), titulo: 'Reglas del Plan', texto: 'Solo se pueden programar secciones de los instructivos <b>de ese equipo</b>, y cada sección <b>una sola vez</b> por equipo (no hay dos tareas haciendo lo mismo). '
      + 'Las frecuencias por mes (mensual, trimestral…) van al <b>Cronograma</b>; las <b>por horas</b> van a <b>Horómetros</b>; las "según condición" no se programan.' },
    { ir: 'plan', el: () => boton('Dar de baja'), titulo: 'Tareas que se dejan de hacer', texto: 'Se dan de baja: dejan de aparecer en el Cronograma y en Inicio, pero lo ya registrado se conserva.' },

    // 4. cronograma
    { ir: 'cronograma', el: () => menu('cronograma'), titulo: '4 · Cronograma', texto: 'Sale <b>solo</b> del Plan: una fila por tarea, una columna por mes. Nadie lo completa a mano: cada casillero cambia cuando se registra el trabajo.' },
    { ir: 'cronograma', el: () => enVista('.leyenda'), titulo: 'El estado de cada mes', texto: `${sim('pendiente', '○')} toca y no se hizo todavía, ${sim('hecho', '✓')} hecho, ${sim('tarde', '✓')} hecho fuera de término (se hizo en un mes posterior, antes de que volviera a tocar), ${sim('vencido', '✗')} vencido o no realizado, ${sim('reprogramado', '↻')} reprogramado. `
      + 'Tocando un casillero se registra ese trabajo directamente.' },
    { ir: 'cronograma', el: () => enVista('.encabezado .chip'), titulo: 'Cumplimiento', texto: 'Hechos sobre los que tocaban, contando solo los <b>meses ya cerrados</b> (el mes en curso todavía tiene tiempo). '
      + 'Cuentan como hechos <b>Realizado</b> y <b>Con observaciones</b>; <b>No realizado</b> y <b>Reprogramado</b> cuentan en contra; <b>No aplica</b> no cuenta.' },

    // 5. horómetros
    { ir: 'horometros', el: () => menu('horometros'), titulo: '5 · Horómetros', texto: 'El "cronograma" de los servicios <b>por horas de uso</b>. Para cada equipo con horómetro muestra la última lectura y cuánto falta para cada servicio.' },
    { ir: 'horometros', titulo: 'De dónde salen las horas', texto: 'Las lecturas se cargan en <b>Registros</b>: al registrar un servicio se anota lo que marca el horómetro, o se carga una lectura suelta. '
      + 'Después del primer servicio, el próximo se cuenta desde la lectura del último hecho.' },

    // 6. registros
    { ir: 'registros', el: () => menu('registros'), titulo: '6 · Registros', texto: 'El historial de todos los <b>preventivos</b> hechos en el año. Cada registro dice qué tarea, cuándo, con qué resultado, quién, horas-hombre, novedades y repuestos usados.' },
    { ir: 'registros', el: () => boton('Registrar mantenimiento'), titulo: 'Registrar', texto: 'El mismo formulario se abre desde Inicio, desde el Cronograma y desde acá. Muestra las actividades del instructivo para tenerlas a la vista mientras se carga.' },
    { ir: 'registros', el: () => boton('Anular'), titulo: 'Corregir un error', texto: 'Un registro mal cargado lo <b>anula</b> un administrador, y el mes vuelve a quedar pendiente. Si el trabajo se hizo mal, no se anula: se registra otro.' },

    // 7. correctivos
    { ir: 'correctivos', el: () => menu('correctivos'), titulo: '7 · Correctivos', texto: 'Las <b>fallas y arreglos no programados</b>: qué falló, la causa, qué se hizo y cuántas horas estuvo parado el equipo. '
      + 'No entran en el cumplimiento, pero muestran qué equipos fallan más. Si la falla necesita una acción de calidad, se marca <b>SGC</b>.' },

    // 8. personal, áreas, usuarios
    { ir: 'personal', el: () => menu('personal'), titulo: '8 · Personal', texto: 'Quién hace los trabajos: <b>Mantenimiento interno</b> (los usuarios aparecen solos) y <b>Proveedores externos</b>. '
      + 'Para cada uno se ve cuántos preventivos y correctivos hizo en el año, con sus horas-hombre.' },
    { ir: 'areas', el: () => menu('areas'), titulo: '9 · Áreas', texto: 'Las áreas de la planta. Cada equipo pertenece a una, y acá se ve por área: equipos, preventivos, correctivos y horas de parada del año.' },
    { ir: 'usuarios', si: () => !!(typeof S !== 'undefined' && S.usuario?.es_admin), el: () => menu('usuarios'), titulo: '10 · Usuarios', texto: 'Quiénes entran. Un <b>usuario</b> ve todo y registra trabajos; un <b>administrador</b> además configura equipos, instructivos, Plan y personal. '
      + 'Siempre queda al menos un administrador activo.' },

    // cierre: el día a día
    { ir: 'inicio', el: () => menu('inicio'), titulo: 'El día a día: Inicio', texto: 'Con todo configurado, el trabajo diario empieza acá: lo que toca <b>este mes</b>, lo <b>atrasado</b> y los servicios por horas que se acercan, cada uno con su botón para registrarlo.' },

  );
})();
