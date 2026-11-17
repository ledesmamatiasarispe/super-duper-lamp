# Mantenimiento: cómo funciona

Guía para la IA de la barra de preguntas: la dinámica de cada pestaña de mantenimiento y cómo se conectan. Cada "##"
es una sección; "ir:" dice a qué pantalla lleva. Usuario = cualquiera que entra; administrador = el que configura.

## La idea en una línea
ir: inicio
Cada equipo tiene un instructivo dividido en secciones (A, B, C…). Cada sección se programa en el Plan con una
frecuencia (mensual, trimestral, cada 1000 horas…): eso es una tarea, y las tareas arman solas el Cronograma, Inicio y
Horómetros. Cuando alguien hace el trabajo lo registra, y el Cronograma y el cumplimiento se actualizan solos.
Preventivo = lo programado (se registra como mantenimiento). Correctivo = una falla o rotura no programada.

## Inicio: lo que hay que hacer
ir: inicio
Junta lo pendiente de hoy: lo que toca este mes y no se registró, lo atrasado de meses anteriores y los servicios por
horas cercanos o vencidos. Se arma sola: no se carga nada acá. Cada fila tiene su botón Registrar. "faltan 2" es una
tarea que va más de una vez por mes. Arriba: Registrar mantenimiento, Registrar correctivo e Imprimir lista del mes
(hoja apaisada con casilleros para llevar al taller; lo hecho se registra después). La tarjeta Cumplimiento muestra el
porcentaje del año.

## Registrar un mantenimiento (preventivo)
ir: registros
Desde Inicio, Cronograma (tocando un casillero), Horómetros (tocando un casillero) o Registros: es el mismo formulario.
Se elige la tarea (o ya viene elegida) y se ven las actividades del instructivo. Se carga: fecha (no futura; el mes de
esa fecha queda cumplido), resultado, quién lo hizo (si no está en la lista: "Otro" y se escribe el nombre),
horas-hombre, horómetro (solo si el equipo tiene: queda como lectura), novedades y repuestos usados.
Resultados: Realizado y Con observaciones cuentan como hecho; No realizado deja el mes vencido (✗); Reprogramado pide
para cuándo; esos dos cuentan en contra del cumplimiento. No aplica: ese mes no correspondía, no cuenta.
Si se hizo y no se anotó, se registra con la fecha real; si se hizo tarde, con la fecha en que se hizo.

## Cronograma anual
ir: cronograma
Una fila por tarea del Plan y una columna por mes. Nadie lo completa a mano: cambia cuando se registra. Símbolos:
○ programado, ✓ hecho, ✓ de otro color hecho fuera de término (en un mes posterior, que muestra ↩), ✗ vencido o no
realizado, ↻ reprogramado, – no aplica, · la tarea todavía no estaba en el Plan, vacío no toca. "1/2" es que va más de
una vez por mes. Tocar un casillero abre el registro con la fecha sugerida. ◄ ► cambia de año (también para Registros,
Correctivos, Personal y Áreas). Las tareas por horas dicen "c/ 1000 h" y se siguen en Horómetros. Se imprime con Imprimir.

## Cumplimiento
ir: cronograma
De los servicios que tocaban en los meses ya cerrados del año, cuántos se hicieron (Realizado o Con observaciones).
Lo hecho fuera de término cuenta como hecho, y al lado se ve cuántos fueron a tiempo. El mes en curso no cuenta todavía.
Verde desde 90 %, ámbar desde 70 %, rojo debajo. Los correctivos no entran en el cumplimiento.

## Horómetros y servicios por horas
ir: horometros
Para los equipos con horómetro: un cuadro por equipo con la última lectura y, para cada servicio por horas, cada
cuántas horas va, a cuántas toca el próximo y cuánto falta (o por cuánto se pasó). El ▲ marca dónde está el equipo.
"Sin lectura": nunca se anotó el horómetro. "Falta dato": en el Plan falta a qué horas va el primer servicio.
Después del primero, el próximo se cuenta desde la lectura del último servicio hecho. Las lecturas no se cargan acá.

## Cargar una lectura de horómetro
ir: registros
En Registros → "Registrar lectura de horómetro": equipo (solo los que tienen), las horas que marca y quién anotó.
Sirve cuando no se hizo ningún servicio; si se hizo, la lectura va en el mismo registro del mantenimiento.

## Cambio de horómetro
ir: horometros
Si el horómetro se rompe o se reemplaza y el nuevo arranca de otro número: Horómetros → "Cambio de horómetro"
(solo administradores), con la fecha, lo que marca el nuevo y, si se sabe, lo que marcaba el viejo. A cada servicio por
horas le queda lo mismo que le faltaba.

## Registros
ir: registros
El historial de los preventivos del año, del más nuevo al más viejo: fecha, tarea, equipo, sección, resultado, quién,
horas-hombre, horómetro, novedades y repuestos. Anular (solo administradores) es para una carga equivocada: borra el
registro y su lectura, y el mes vuelve a quedar pendiente. Si el trabajo se hizo mal no se anula: se registra otro.

## Correctivos
ir: correctivos
Las reparaciones no programadas (fallas, roturas, arreglos de urgencia) del año, con el total de horas de parada.
"Registrar correctivo" (desde acá o Inicio): equipo, falla o síntoma (obligatorio), causa, acción (qué se hizo),
horas de parada (cuánto no pudo trabajar), horas-hombre, quién y repuestos. "Acción del SGC" se marca si la falla
requiere una acción del sistema de calidad (abrir un RAC). Sirven para ver qué equipos fallan más.
Ejemplos de correctivos: se rompió una correa, se quemó un motor, se trabó un rodamiento, pierde aceite, se cortó un
cable, no arranca. Todo lo que se rompe o falla y se arregla se anota como correctivo, no en Especificaciones.

## Plan de mantenimiento
ir: plan
Qué se hace, a qué equipo y cada cuánto. Cada tarea = una sección de un instructivo del equipo + una frecuencia; cada
sección se programa una sola vez por equipo. Nueva tarea (administradores): primero el equipo, después la sección (solo
las de sus instructivos sin programar), después la frecuencia: por mes (con mes de inicio o meses específicos, como
"3, 9"; una trimestral que arranca en febrero toca feb, may, ago y nov), por horas (cada cuántas y a cuántas el
primero; va a Horómetros) o según condición (no se programa). Responsable: se sugiere al registrar.
Editar cambia frecuencia, responsable u observaciones sin perder lo registrado. Dar de baja saca la tarea del
Cronograma e Inicio pero conserva sus registros (se reactiva con Ver ocultos).

## Programar todos
ir: opciones
En Opciones (administradores): arma de una vez las tareas que faltan, una por cada sección de instructivo sin
programar, con la frecuencia sugerida por la tabla de frecuencias del instructivo. "Repartir meses" elige los meses de
inicio para que los trabajos no se junten.

## Equipos e instructivos
ir: equipos
La lista de equipos (código EQ-… automático, área, marca/modelo, si tiene horómetro) con su instructivo y qué
secciones están en el Plan ("sin programar" = todavía no tiene frecuencia y no aparece en el Cronograma).
Nuevo equipo (administradores): si es parecido a uno que ya existe, se lo elige y arranca con una copia de su
instructivo (cada uno queda independiente); si no, se abre un instructivo nuevo. Si el área no existe: "+ Nueva área…".
Marcar obsoleto: un equipo que ya no está; pide motivo, da de baja sus tareas y conserva el historial. Eliminar: solo
uno cargado por error, sin nada vinculado. Botón Especificaciones: los datos técnicos del equipo.

## Especificaciones (datos técnicos)
ir: equipos
Por equipo: aceite, correas, presiones, torques, filtros… con su valor, unidad y de dónde sale (manual del fabricante,
placa, proveedor, técnico u otra) y el detalle (por ejemplo "manual, pág. 12"). Cualquiera las carga o corrige desde
Equipos → Especificaciones; borrar es de administrador. Un nombre no se repite en el mismo equipo. La barra de
preguntas contesta con ellas, y cuando falta un dato ofrece "Cargar especificación". Son datos fijos del equipo
(qué lleva), no lo que le pasó: una rotura o un arreglo va en Correctivos.

## El instructivo
ir: equipos
El documento de mantenimiento del equipo: cabecera (código, revisión y fecha), seguridad, secciones con sus actividades
numeradas, repuestos e insumos (con cantidad mínima), y archivos adjuntos (planos, manuales). Cada sección se programa
por separado (por ejemplo A mensual y B cada 1000 h). Imprimir saca el documento limpio. Modificar (administradores)
crea una revisión nueva con motivo obligatorio; las anteriores quedan en el historial y se pueden ver. "Programar en el
Plan" aparece si una sección no está programada. Obsoleto: ya no se usa, queda para consulta.

## Editar un instructivo
ir: equipos
Título, descripción, seguridad (una indicación por renglón) y el contenido en orden: secciones de actividades (una por
renglón; "#" al principio es un título de grupo, "-" es un detalle de la de arriba), bloques de texto, notas
destacadas, tablas (celdas con |), imágenes y gráficos, y la lista de repuestos. El número de cada bloque es su
posición: se cambia para moverlo. Una sección que está en el Plan no se puede quitar. Fotos y archivos se suben abajo.

## Mapa de planta
ir: mapa
Planos de la planta con las máquinas como puntos, uno por nave o sector. Color de cada máquina: rojo si tiene algo
vencido o atrasado, ámbar si le toca algo este mes o un servicio por horas está cerca, azul si falta un dato (lectura o
primer servicio) y verde si está al día. Tocar una máquina muestra lo pendiente con su botón Registrar. Los
administradores crean y dibujan planos (como un croquis de CAD: líneas, rectángulos, cotas y restricciones) y ubican
las máquinas; eliminar un plano no toca el historial.

## Personal y proveedores
ir: personal
Quién hace los trabajos: mantenimiento interno (los usuarios aparecen solos) y proveedores externos (con contacto y
rubro), con cuántos preventivos y correctivos hizo cada uno en el año y sus horas-hombre. "Ver trabajos" lista lo que
hizo. Los nombres escritos como "Otro" al registrar aparecen en "Otros, sin dar de alta". Dar de baja a alguien lo
saca de las listas, pero sus trabajos se siguen contando.

## Áreas
ir: areas
Las áreas de la planta con cuántos equipos tiene cada una y, en el año, preventivos, correctivos y horas de parada.
Renombrar corrige el nombre en todos sus equipos. Eliminar solo aparece en un área sin equipos; si no, se da de baja.

## Usuarios y legajo
ir: usuarios
Cada usuario figura solo en Personal (mantenimiento interno). Se entra con el legajo. Un usuario ve todo y registra
trabajos; un administrador además configura equipos, instructivos, Plan y personal.
