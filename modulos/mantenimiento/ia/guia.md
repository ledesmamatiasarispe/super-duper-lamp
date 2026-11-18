# Mantenimiento: cómo funciona

Guía para la IA de la barra de preguntas: la dinámica de cada pestaña de mantenimiento y cómo se conectan. Cada "##"
es una sección; "ir:" dice a qué pantalla lleva. Usuario = cualquiera que entra; administrador = el que configura.
Las pestañas, en orden: Inicio, Cronograma, Registros, Horómetros, Correctivos, Plan, Equipos e instructivos, Mapa,
Personal, Áreas (y Usuarios y Opciones, del sistema).

## La idea en una línea
ir: inicio
Cada equipo tiene un instructivo dividido en secciones (A, B, C…). Cada sección se programa en el Plan con una
frecuencia (mensual, trimestral, cada 1000 horas…): eso es una tarea, y las tareas arman solas el Cronograma, Inicio y
Horómetros. Cuando alguien hace el trabajo lo registra, y el Cronograma y el cumplimiento se actualizan solos.
Preventivo = lo programado (se registra como mantenimiento). Correctivo = una falla o rotura no programada.

## Cómo se configura la app desde cero
ir: equipos
El orden es: 1) Áreas (o se crean al cargar el equipo), 2) Equipos, 3) el instructivo de cada equipo, con sus
secciones, 4) el Plan: cada sección con su frecuencia (una por una con Nueva tarea, o todas juntas con Opciones →
Programar todos), 5) Personal. Desde ahí el trabajo diario es Inicio y registrar lo que se hace.

## Quién puede hacer qué
ir: usuarios
Cualquier usuario ve todo y puede: registrar mantenimientos y correctivos, cargar lecturas de horómetro, y cargar o
corregir especificaciones. Solo un administrador puede: crear, editar, marcar obsoleto o eliminar equipos; crear y
modificar instructivos y sus archivos; crear, editar o dar de baja tareas del Plan y usar Programar todos; anular un
registro; cargar un cambio de horómetro; dar de alta, editar o dar de baja personal y áreas; borrar una
especificación; dibujar planos y ubicar máquinas en el mapa; y manejar usuarios. Un botón que no aparece suele ser
porque el usuario no es administrador.

## Códigos
ir: equipos
Equipo: EQ-001, EQ-002… (se asigna solo al crearlo). Instructivo: IT01, IT02… Sección de instructivo: el código del
instructivo más la letra, IT01-A, IT01-B. Tarea del Plan: el código del equipo más un número, EQ-001-1, EQ-001-2.
En el Cronograma, Inicio y Registros la tarea aparece con su código, el equipo y la sección.

## Frecuencias
ir: plan
Quincenal (2 veces por mes), Mensual, Bimestral (cada 2 meses), Trimestral (3), Cuatrimestral (4), Semestral (6),
Anual (12): estas van al Cronograma. Por horas: cada tantas horas de uso del horómetro, va a Horómetros (solo para
equipos con horómetro). Según condición: se hace cuando hace falta, no se programa ni cuenta en el cumplimiento.
El mes de inicio fija los meses: una trimestral que arranca en febrero toca feb, may, ago y nov. Con meses específicos
("3, 9") toca solo esos meses.

## Inicio: lo que hay que hacer
ir: inicio
Junta lo pendiente de hoy: lo que toca este mes y no se registró, lo atrasado de meses anteriores del año y los
servicios por horas cercanos o vencidos. Se arma sola: no se carga nada acá. Cada fila tiene su botón Registrar.
"faltan 2" es una tarea que va más de una vez por mes. Arriba: Registrar mantenimiento, Registrar correctivo e
Imprimir lista del mes. La tarjeta Cumplimiento muestra el porcentaje del año. Lo atrasado de años anteriores no
aparece en Inicio: se ve en el Cronograma de ese año.

## Imprimir la lista del mes
ir: inicio
Inicio → Imprimir lista del mes: una hoja apaisada con lo atrasado, lo de este mes y los servicios por horas vencidos
o cercanos, con casilleros en blanco (hecho, fecha, realizó, observaciones) para llevar al taller. Lo que se hizo se
registra después en la app; el papel no cambia nada solo.

## Registrar un mantenimiento (preventivo)
ir: registros
Desde Inicio, Cronograma (tocando un casillero), Horómetros (tocando un casillero), el Mapa (tocando una máquina) o
Registros: es el mismo formulario. Se elige la tarea (o ya viene elegida) y se ven las actividades del instructivo.
Se carga: fecha (no futura; el mes de esa fecha queda cumplido), resultado, quién lo hizo (viene puesto quien está
cargando; si no está en la lista: "Otro" y se escribe el nombre), horas-hombre, horómetro (solo si el equipo tiene:
queda como lectura), novedades y repuestos usados. Cualquier usuario puede registrar.

## Resultados de un registro
ir: registros
Realizado y Con observaciones cuentan como hecho. No realizado deja el mes vencido (✗). Reprogramado pide para qué
fecha se pasó. No realizado y Reprogramado cuentan en contra del cumplimiento. No aplica: ese mes no correspondía
hacerlo, no cuenta ni a favor ni en contra. Si se hizo y no se anotó, se registra con la fecha real; si se hizo
tarde, con la fecha en que se hizo (queda como fuera de término).

## Cronograma anual
ir: cronograma
Una fila por tarea del Plan y una columna por mes. Nadie lo completa a mano: cambia cuando se registra. Símbolos:
○ programado, ✓ hecho, ✓ de otro color hecho fuera de término, ↩ hecho en ese mes y cubre uno atrasado, ✗ (cruz
roja) vencido, ✗ (cruz) no realizado, ↻ reprogramado, – no aplica, · la tarea todavía no estaba en el Plan, vacío no toca. "1/2" es
que va más de una vez por mes y se hizo una. Tocar un casillero abre el registro con la fecha sugerida (hoy en el mes en
curso; si no, el día 1 de ese mes). ◄ ► cambia de año (también para Registros, Correctivos, Personal y Áreas).
Las tareas por horas dicen "c/ 1000 h" y se siguen en Horómetros. Se imprime con Imprimir.

## Hecho fuera de término
ir: cronograma
Un trabajo hecho en un mes posterior al que tocaba cubre ese mes atrasado (queda ✓ de otro color, y el mes en que se
hizo muestra ↩), siempre que todavía no haya vuelto a tocar la tarea: si ya volvió a tocar, cubre la vez nueva y el
atrasado queda vencido. Cuenta como cumplido, pero no como "a tiempo".

## Cumplimiento
ir: cronograma
De los servicios que tocaban en los meses ya cerrados del año, cuántos se hicieron (Realizado o Con observaciones).
Lo hecho fuera de término cuenta como hecho, y al lado se ve cuántos fueron a tiempo. El mes en curso no cuenta todavía.
Los meses anteriores a que la tarea se cargara en el Plan tampoco. Verde desde 90 %, ámbar desde 70 %, rojo debajo.
Los correctivos y las tareas según condición no entran en el cumplimiento.

## Horómetros y servicios por horas
ir: horometros
Para los equipos con horómetro: un cuadro por equipo con la última lectura y, para cada servicio por horas, cada
cuántas horas va, a cuántas toca el próximo y cuánto falta (o por cuánto se pasó). El ▲ marca dónde está el equipo.
Cada columna es un bloque de horas; ◄ horas antes / horas después ► corren la grilla y Ahora la centra. Un servicio
aparece como cercano (ámbar, y en Inicio) cuando le faltan 100 horas o menos; vencido (rojo) cuando se pasó.
"Sin lectura": nunca se anotó el horómetro. "Falta dato": en el Plan falta a qué horas va el primer servicio.
Después del primero, el próximo se cuenta desde la lectura del último servicio hecho. Las lecturas no se cargan acá.

## Cargar una lectura de horómetro
ir: registros
En Registros → "Registrar lectura de horómetro": equipo (solo los que tienen horómetro), fecha, las horas que marca,
quién anotó y observaciones. Sirve cuando no se hizo ningún servicio; si se hizo, la lectura va en el mismo registro
del mantenimiento. Cualquier usuario puede cargarla. Las últimas lecturas se ven abajo en Horómetros.

## Cambio de horómetro
ir: horometros
Si el horómetro se rompe o se reemplaza y el nuevo arranca de otro número: Horómetros → "Cambio de horómetro"
(solo administradores), con la fecha, lo que marca el nuevo y, si se sabe, lo que marcaba el viejo al sacarlo. A cada
servicio por horas le queda lo mismo que le faltaba (si al B le faltaban 300 h, queda a 300 h de lo que marca el
nuevo). Si no se sabe lo que marcaba el viejo, se usa su última lectura y conviene revisar el próximo en el Plan.
En Últimas lecturas queda marcado como "horómetro nuevo".

## Registros
ir: registros
El historial de los preventivos del año, del más nuevo al más viejo: fecha, tarea, equipo, sección, resultado (si se
reprogramó, para cuándo), quién, horas-hombre (HH), horómetro, novedades y repuestos. Anular (solo administradores)
es para una carga equivocada: borra el registro y su lectura, y el mes vuelve a quedar pendiente. Si el trabajo se
hizo mal no se anula: se registra otro. Un registro no se edita: se anula y se carga de nuevo.

## Correctivos
ir: correctivos
Las reparaciones no programadas (fallas, roturas, arreglos de urgencia) del año, con el total de horas de parada.
"Registrar correctivo" (desde acá o Inicio, cualquier usuario): equipo, fecha, falla o síntoma (obligatorio), causa,
acción realizada, horas de parada (cuánto no pudo trabajar), horas-hombre, quién, repuestos y observaciones. "Requiere
acción del SGC" se marca si la falla necesita una acción del sistema de calidad (abrir un RAC). Sirven para ver qué
equipos fallan más; también se suman por área y por persona.
Ejemplos de correctivos: se rompió una correa, se quemó un motor, se trabó un rodamiento, pierde aceite, se cortó un
cable, no arranca. Todo lo que se rompe o falla y se arregla se anota como correctivo, no en Especificaciones.

## Plan de mantenimiento
ir: plan
Qué se hace, a qué equipo y cada cuánto. Cada tarea = una sección de un instructivo del equipo + una frecuencia; cada
sección se programa una sola vez por equipo. Nueva tarea (administradores): primero el equipo, después la sección (solo
las de sus instructivos sin programar), después la frecuencia, el mes de inicio o meses específicos (o, por horas,
cada cuántas y a cuántas el primero) y el responsable, que se sugiere al registrar. Editar cambia frecuencia,
responsable u observaciones sin perder lo registrado. Dar de baja saca la tarea del Cronograma e Inicio pero conserva
sus registros; se reactiva con Ver ocultos → Reactivar. A un equipo obsoleto no se le programan tareas.

## Programar todos
ir: opciones
En Opciones → Plan de mantenimiento (administradores): lista de una vez las secciones de instructivo sin programar,
con la frecuencia sugerida por la tabla de frecuencias del instructivo ("Según la ficha"). Se revisa cada fila
(frecuencia, mes de inicio, cada cuántas horas), se elige un responsable para todas y se marcan las que se programan.
"Repartir meses" elige los meses de inicio para que los trabajos no se junten en los mismos meses; abajo dice cuántos
trabajos caen en cada mes. Las que no tienen frecuencia sugerida quedan sin marcar.

## Equipos e instructivos
ir: equipos
La lista de equipos: código EQ-… automático, nombre, área, marca/modelo, si tiene horómetro, su instructivo (código,
revisión y qué secciones están en el Plan; "sin programar" = todavía sin frecuencia, no aparece en el Cronograma;
"sin instructivo" = falta crearlo) y el estado (Vigente u Obsoleto, con fecha y motivo). Botones por equipo: Ver
instructivo (o Crear instructivo), Especificaciones (con cuántas tiene), Editar, Marcar obsoleto, Reactivar y
Eliminar. Abajo figuran los instructivos sin equipo asignado.

## Dar de alta un equipo nuevo
ir: equipos
Equipos → Nuevo equipo (administradores): nombre, área (si no existe, "+ Nueva área…"), marca/modelo y si tiene
horómetro. Si es parecido a uno que ya existe, se escribe su código o nombre en "¿Es parecido a otro equipo?" y
arranca con una copia de su instructivo (con imágenes y archivos), que después se ajusta sin tocar el original. Si se
deja vacío, al guardar se abre el editor del instructivo nuevo. Después hay que programar sus secciones en el Plan.

## Editar un equipo
ir: equipos
Editar (administradores) cambia nombre, área, marca/modelo y horómetro. También deja de usar un instructivo
(desmarcándolo: no se puede si tiene tareas activas en el Plan; queda como instructivo sin equipo), le copia el de un
equipo parecido si todavía no tiene, o le asigna un instructivo que haya quedado sin equipo.

## Marcar obsoleto, reactivar o eliminar un equipo
ir: equipos
Marcar obsoleto: un equipo que ya no está (se vendió, se desarmó); pide motivo, da de baja sus tareas del Plan y
conserva todo el historial; no se lo puede ubicar en el mapa ni programar. Reactivar (con Ver ocultos) lo vuelve a
poner vigente; sus tareas se reactivan aparte, en el Plan. Eliminar: solo para uno cargado por error, aparece
únicamente si no tiene nada vinculado y lo borra sin dejar rastro.

## Especificaciones (datos técnicos)
ir: equipos
Por equipo: aceite, correas, presiones, torques, filtros… con su valor, unidad y de dónde sale (manual del fabricante,
placa del equipo, proveedor, técnico/experiencia u otra), el detalle (por ejemplo "manual, pág. 12") y notas.
Cualquiera las carga o modifica desde Equipos → Especificaciones; borrar es de administrador. Un nombre no se repite en
el mismo equipo. La barra de preguntas contesta con ellas, y cuando falta un dato ofrece "Cargar especificación". Son
datos fijos del equipo (qué lleva), no lo que le pasó: una rotura o un arreglo va en Correctivos.

## El instructivo
ir: equipos
El documento de mantenimiento del equipo: cabecera (código, revisión y fecha), seguridad, secciones con sus actividades
numeradas (cada una con un cartel verde que dice con qué tarea y cada cuánto está programada), repuestos e insumos
(con cantidad mínima) y archivos adjuntos (planos, manuales). Se abre desde Equipos → Ver instructivo, o tocando la
sección en Inicio, Cronograma, Plan u Horómetros. Imprimir / PDF saca el documento limpio. "Programar en el Plan"
aparece si una sección no está programada.

## Revisiones del instructivo
ir: equipos
Un instructivo no se pisa: Modificar (administradores) abre el editor y al guardar crea la revisión siguiente (Rev. 1 →
Rev. 2) con el motivo del cambio, que es obligatorio. El Historial de revisiones muestra cada una con qué cambió, quién
y cuándo, y Ver muestra cómo era el documento en esa revisión. Marcar obsoleto: ya no se usa, queda para consulta con
una franja roja. Eliminar: solo uno creado por error; si alguna vez se usó, se marca obsoleto.

## Editar un instructivo
ir: equipos
Título, descripción, seguridad (una indicación por renglón) y el contenido en orden: secciones de actividades (una por
renglón; "#" al principio es un título de grupo, "-" es un detalle de la de arriba), bloques de texto, notas
destacadas (nota, precaución o peligro), tablas (celdas con |), imágenes y gráficos, y la lista de repuestos (con
cantidad mínima; se reordena arrastrando ⠿). El número de cada bloque es su posición: se cambia para moverlo. Una
sección que está en el Plan no se puede quitar. Abajo, motivo del cambio y Guardar revisión.

## Imágenes y archivos del instructivo
ir: equipos
En el editor del instructivo (administradores), "Subir imágenes o archivos": imágenes jpg, png, gif o webp para poner
en el documento (Poner en el documento), y archivos PDF, planos dwg/dxf, Word, Excel, txt, csv o zip, que se listan al
final para descargar. Un archivo que ninguna revisión usa se puede borrar. En un instructivo nuevo se habilita después
de crearlo.

## Mapa de planta
ir: mapa
Planos de la planta con las máquinas como puntos, uno por nave o sector; cada máquina está en un solo plano. Color de
cada máquina: rojo si tiene algo vencido o atrasado, ámbar si le toca algo este mes o un servicio por horas está
cerca, azul si falta un dato (lectura o primer servicio) y verde si está al día. Tocar una máquina (en el plano o en la
lista "Máquinas en este plano") muestra lo pendiente con su botón Registrar. La rueda del mouse acerca y aleja,
arrastrando se mueve, Ajustar lo muestra entero.

## Dibujar un plano y ubicar las máquinas
ir: mapa
Administradores: Nuevo plano (nombre y medidas en metros) y Editar este plano. Se dibuja como un croquis de CAD: línea,
rectángulo, círculo, arco, polígono y texto, con cotas y restricciones (horizontal, paralela, tangente…); se puede
escribir la medida ("12", "12<30", "4,3"). Para ubicar una máquina: en "Máquinas sin ubicar acá" tocar Ubicar y después
el lugar en el plano. Nada se guarda hasta Guardar plano. Eliminar plano borra solo el dibujo: sus máquinas quedan sin
ubicar y su historial no se toca.

## Personal y proveedores
ir: personal
Quién hace los trabajos: Mantenimiento interno (los usuarios aparecen solos, con su legajo; su nombre se cambia en
Usuarios) y Proveedores externos (con contacto y rubro), con cuántos preventivos y correctivos hizo cada uno en el año,
sus horas-hombre y la fecha del último. "Ver trabajos" lista lo que hizo. Los nombres escritos como "Otro" al
registrar aparecen en "Otros, sin dar de alta". Nuevo operario y Nuevo proveedor (administradores) los dan de alta.
Dar de baja a alguien lo saca de las listas para elegir, pero sus trabajos se siguen contando.

## Áreas
ir: areas
Las áreas de la planta con cuántos equipos tiene cada una y, en el año, preventivos, correctivos y horas de parada.
Nueva área (o "+ Nueva área…" al cargar un equipo). Renombrar corrige el nombre en todos sus equipos. Dar de baja la
saca de las listas para elegir. Eliminar solo aparece en un área sin equipos (creada por error).

## Usuarios y legajo
ir: usuarios
Cada usuario figura solo en Personal (mantenimiento interno), con su mismo nombre y su misma alta. Se entra con el
legajo. Un usuario ve todo y registra trabajos; un administrador además configura equipos, instructivos, Plan y
personal.

## Qué hago si me equivoqué al cargar un registro
ir: registros
Un registro no se edita. Un administrador lo anula en Registros (botón Anular) y se vuelve a cargar bien: el mes vuelve
a quedar pendiente hasta el registro nuevo. Si lo cargó un usuario común, le pide a un administrador. Los
correctivos, en cambio, no se editan ni se anulan desde la app: conviene revisarlos antes de guardar.

## Qué hago si se rompió una máquina
ir: correctivos
Se registra un correctivo: Inicio o Correctivos → Registrar correctivo, con el equipo, la falla, la causa si se
encontró, qué se hizo, las horas de parada y los repuestos. Si necesita una acción de calidad, marcar "Requiere acción
del SGC". No va como mantenimiento preventivo ni en Especificaciones.

## Qué hago si una tarea no aparece en el Cronograma o en Inicio
ir: plan
Revisar: que la sección del instructivo esté programada en el Plan (en Equipos dice "sin programar" si no); que la
tarea no esté dada de baja (Plan → Ver ocultos); que no sea por horas (esas van a Horómetros) o según condición (no se
programan); que en ese mes toque (mes de inicio y frecuencia); y que el equipo no esté obsoleto. En Inicio desaparece
apenas se registra.

## Qué hago si un servicio por horas dice Sin lectura o Falta dato
ir: horometros
"Sin lectura": cargar lo que marca el horómetro en Registros → Registrar lectura de horómetro. "Falta dato": en el
Plan, Editar la tarea y completar "Primer servicio a las (h)". Mientras falte, en el mapa la máquina se ve azul.

## Qué hago si una máquina se ve roja o ámbar en el mapa
ir: inicio
Rojo: tiene algo vencido o atrasado; ámbar: le toca algo este mes o un servicio por horas está a 100 horas o menos.
Tocarla en el mapa muestra qué es, con su botón Registrar; también figura en Inicio. Al registrarlo vuelve a verde.

## Qué hago si llega una máquina nueva
ir: equipos
Un administrador la da de alta en Equipos → Nuevo equipo (copiando el instructivo de una parecida si hay), revisa o
carga su instructivo, programa sus secciones en el Plan (Nueva tarea o Programar todos), carga sus especificaciones y,
si se usa el mapa, la ubica en su plano con Editar este plano → Ubicar.

## Qué hago si entra un operario o un proveedor nuevo
ir: personal
Si va a usar la app, un administrador le crea un usuario (Usuarios → Nuevo usuario) y aparece solo en Personal. Si no
usa la app, se carga en Personal → Nuevo operario o Nuevo proveedor (administradores). Mientras no esté, al registrar
se elige "Otro" y se escribe el nombre.
