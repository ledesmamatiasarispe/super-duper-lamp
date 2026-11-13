CLAUDEREADME — memoria del proyecto para agentes de IA
=====================================================

Leé esto antes de tocar nada. Resume qué es la app, cómo está armada, sus reglas de negocio y los errores que ya
se cometieron una vez. Si cambiás algo de lo que dice acá, actualizalo en el mismo cambio.


1. QUÉ ES
---------
UltraMantenimiento (logo: omega invertida ℧ blanca, estilo Ultramarines, sobre azul #17324d; frontend/logo.svg e icono.svg, y el .ico del exe
en herramientas/ultramantenimiento.ico, generado por herramientas/icono.py con la misma geometría).
App web de MANTENIMIENTO PREVENTIVO y correctivo de una planta (Fundición Romero). Reemplaza una planilla Excel
de cronograma. La usan administradores (configuran) y usuarios de mantenimiento (registran trabajos), desde PCs y
tablets de planta en la red local. Todo en español rioplatense (textos, código, nombres).

La idea en una línea:
  Equipo -> Instructivo (dividido en Secciones A, B, C…) -> Plan (tarea = sección + equipo + frecuencia)
  -> Cronograma / Horómetros -> Registros (lo hecho) -> cumplimiento.


2. STACK Y ESTRUCTURA
---------------------
- Python 3.11, FastAPI, sqlite3 directo (sin ORM), PRAGMA foreign_keys ON. Frontend: SPA en JavaScript puro,
  sin build ni frameworks (index.html + app.js + styles.css; ayuda.js/ayuda.css aparte).
- Entorno: .venv en la raíz. Arrancar: `.venv\Scripts\python.exe -m app` (o iniciar.bat) -> http://localhost:8095
  (escucha en 0.0.0.0 para las tablets). MANT_PUERTO cambia el puerto, MANT_DB la base, MANT_NAVEGADOR=0 no abre
  el navegador en la versión compilada.

  app/
    __main__.py     arranque (uvicorn con el objeto app; compilado abre el navegador)
    main.py         rutas HTTP. DELGADAS: pasan el body (dict) crudo al servicio, sin lógica.
    servicios.py    ÚNICA puerta a los datos y a las reglas. Cada caso de uso = una transacción (`with transaccion()`).
                    Errores: ErrorDeNegocio -> 400, NoEncontrado -> 404 (los traduce main.py).
    db.py           esquema (ESQUEMA, CREATE IF NOT EXISTS), migraciones livianas (_agregar_columnas con
                    PRAGMA table_info, _migrar_areas…), datos de ejemplo. ROOT/data: en desarrollo la raíz del
                    proyecto; COMPILADA, la carpeta del .exe (ver punto 6).
    auth.py         sesiones con token Bearer (tabla sesiones), hash PBKDF2. auth.sesion vs auth.usuario_actual
                    (este último bloquea a quien tiene contraseña provisoria, debe_cambiar=1). solo_admin.
    usuarios.py     alta/baja de usuarios; siempre queda un admin activo; nadie se da de baja a sí mismo;
                    cada usuario tiene su ficha en personas (Mantenimiento interno).
    calendario.py   lógica pura del cronograma: frecuencias, estado de cada mes, servicios por horas.
    actualizador.py auto-actualización desde GitHub Releases (punto 6).
    version.py      VERSION y REPO.
  frontend/
    app.js          todas las pantallas: VISTAS.<nombre> = async () => {...}; navegación con irA('vista/param')
                    (usa history.replaceState). Helpers: api(), $(), esc(), abrirModal(), enviar(form, fn), avisar().
    ayuda.js        botón "Ayuda" (recorrido por pantalla) y "Tour completo" (toda la app). Pasos por pantalla en
                    PASOS; cada paso busca su elemento EN EL MOMENTO (por texto de botón o clase): si cambiás el texto
                    de un botón, revisá ayuda.js o ese paso desaparece sin error.
  herramientas/
    compilar.py               PyInstaller onedir -> dist/UltraMantenimiento/ + .zip + .sha256
    icono.py                  genera ultramantenimiento.ico (sin librerías de imágenes)
    instructivo_ejemplo.py    crea el instructivo "EJEMPLO · Bomba centrífuga" (usa todas las herramientas del editor)
    cargar_fichas.py          carga las fichas originales .xls (equipos EQ-001…028 + instructivos IT01…IT26); necesita
                              xlrd (requirements-dev). Tiene --simular. Equipos/áreas/responsables salen de una tabla
                              armada con CronogramaMantenimiento-2027.xlsm (los encabezados de varias fichas están mal).
  tests/            pytest con TestClient contra una base nueva por test (fixture `api` en test_api.py, admin logueado).
                    conftest.py pone MANT_REPO="" para que los tests no salgan a internet.
  .github/workflows/release.yml   al empujar un tag v*: tests + compilar + publicar el release.


3. REGLAS DE NEGOCIO (no romperlas)
-----------------------------------
- DAR DE BAJA ≠ ELIMINAR. Baja/obsoleto oculta y conserva todo el historial; las tablas lo esconden y tienen un
  checkbox "Ver ocultos" (filas tr.baja). ELIMINAR es solo para lo cargado por error y solo si no tiene nada
  vinculado (equipo sin tareas/lecturas/correctivos, área sin equipos, instructivo nunca usado en el Plan).
- Marcar un equipo obsoleto da de baja sus tareas del Plan en la misma transacción. Reactivarlo NO reactiva tareas.
- CADA EQUIPO TIENE SUS PROPIOS INSTRUCTIVOS: un instructivo pertenece a un solo equipo (índice único
  ux_instructivo_equipos_instructivo). Para un equipo parecido se COPIA (crear_equipo(copiar_de=…) /
  copiar_instructivo_de_equipo): copia contenido, adjuntos (archivos duplicados), orden; ajusta título y la tabla
  "Datos del equipo"; revisión 0 sin historial; NO copia tareas del Plan.
- INSTRUCTIVOS: todo cambio es una REVISIÓN nueva con motivo obligatorio (la anterior se archiva en
  instructivo_versiones). Contenido: título, descripción, seguridad (fijos arriba) + en ORDEN LIBRE (campo `orden`,
  tokens "seccion:A", "bloque:<índice>", "repuestos"): secciones de actividades, bloques (texto, nota
  info/precaucion/peligro, tabla, imagen, grafico barras/linea/torta) y repuestos ({nombre, cantidad mínima}).
  _completar_orden arregla órdenes viejos/incompletos. Actividades: "# " = título de grupo, "- " = detalle.
  Adjuntos en data/adjuntos/<código>/ con nombre aleatorio; se valida la firma del archivo (no solo la extensión).
- PLAN: una tarea = sección + equipo + frecuencia. Solo secciones de los instructivos DE ESE equipo, y cada
  sección UNA sola vez por equipo (activa). Frecuencias por mes -> Cronograma; "Por horas" -> Horómetros
  (requiere equipo con horómetro); "Según condición" no se programa.
  "Programar todos" (Opciones, admin): lista cada sección que un equipo activo no tiene en el Plan, con la frecuencia
  sugerida por la tabla "Frecuencias" del instructivo (sv.tareas_sin_programar); se guardan todas o ninguna
  (sv.programar_tareas, mismas reglas que una tarea suelta vía _insertar_tarea). "Repartir meses" (solo pantalla,
  repartirMeses en app.js) elige los meses de inicio para emparejar la carga mensual contando el Plan activo; usa los
  intervalos de cal.INTERVALO_MESES que manda /api/opciones ("intervalos"), no una copia en JS.
- CUMPLIMIENTO: solo meses cerrados. A favor: Realizado, Con observaciones. En contra: No realizado,
  Reprogramado. Neutro: No aplica. "antes_alta" (mes previo a cargar la tarea) no cuenta.
- Las lecturas de horómetro se cargan desde Registros (en el registro del servicio o sueltas).
- "Realizado por": personas en categorías Mantenimiento interno / Proveedor externo; "Otro" pide escribir el nombre.
- Áreas: lista (tabla areas), equipos.area_id. Renombrar corrige todos sus equipos.


4. CÓMO TRABAJAR (convenciones)
-------------------------------
- Antes de escribir una función nueva, buscá si ya existe algo parecido en servicios.py y reusalo.
- Validar en servicios (nunca solo en el frontend). Números con _numero() (rechaza nan/inf, acepta coma decimal).
- Columnas nuevas: agregarlas en ESQUEMA y en _agregar_columnas (las bases existentes no se recrean).
  Migraciones de datos: función idempotente que corre al arrancar (ej. servicios.separar_instructivos_compartidos).
  ANTES de migrar la base real, copiarla: data/mantenimiento_antes_de_<cambio>.db.
- La base real es data/mantenimiento.db y TIENE DATOS DEL USUARIO: nunca probar contra ella. Para pruebas visuales,
  levantar otro servidor con MANT_DB apuntando a un archivo temporal y otro puerto (8096+).
- Tests: `.venv\Scripts\python.exe -m pytest -q` (todos tienen que pasar). Todo cambio de reglas lleva su test.
- Revisión visual: Edge headless (`msedge.exe --headless=new --screenshot=… --window-size=…`); para entrar logueado,
  una página temporal en frontend/_t.html (se sirve en /static/_t.html) que hace localStorage.setItem('mant_token', …)
  y carga /static/app.js. BORRARLA al terminar. Las capturas headless pueden agarrar animaciones a mitad de camino.
- Después de cambiar Python, reiniciar el servidor real (puerto 8095); los archivos del frontend se leen del disco.


5. ERRORES QUE YA PASARON (no repetir)
--------------------------------------
- NUNCA editar archivos fuente con Get-Content/Set-Content de PowerShell 5.1: rompe los acentos (ANSI/UTF-8 + BOM).
  Tampoco heredocs de bash con acentos para scripts Python (salen mal codificados): usar la herramienta de edición
  o un .py escrito con Write.
- En app.js, NO asignar `VISTAS.x = …` antes de la línea `const VISTAS = {}` (zona muerta temporal: corta la carga de
  TODA la app y la pantalla queda en blanco). Declarar `async function vistaX()` y registrarla después.
- Variables `let`/`const` de app.js no existen si app.js falla antes de llegar a ellas (las function sí, por hoisting):
  si un test en página suelta da "X is not defined", cargá una copia de index.html, no una página vacía.
- uvicorn compilado: pasar el objeto app, no el string "app.main:app".
- Ayuda guiada en headless: requestAnimationFrame casi no corre, así que el recuadro quedaba atrasado. ubicar() se llama
  enseguida, además del rAF.


6. VERSIÓN COMPILADA Y ACTUALIZACIONES
--------------------------------------
- Compilar: `.venv\Scripts\python.exe herramientas\compilar.py` -> dist/UltraMantenimiento/ (exe + _internal) y
  dist/UltraMantenimiento-v<VERSION>-win64.zip + .sha256. Compilada, los datos van en <carpeta del exe>/data
  (NUNCA dentro de _internal: cada actualización reemplaza el código).
- Publicar: subir VERSION en app/version.py, commit, tag "v"+VERSION, push del tag -> GitHub Actions publica el release.
- Actualizador (app/actualizador.py): al arrancar consulta el último release de REPO; si es más nuevo, a un ADMIN
  (solo en la compilada) se le pregunta al entrar. "Ahora no" = config.actualizacion_pospuesta_hasta (+7 días).
  Instalar: baja el .zip, exige y verifica el .sha256, descomprime en data/actualizacion/, y un .bat en %TEMP% espera
  que el proceso termine, hace robocopy /E (sin /MIR, excluye data/), relanza el exe y limpia. Log en
  data/actualizacion.log. Probado de punta a punta con un servidor local (MANT_API_ACTUALIZACION).
- La consulta a GitHub se guarda 6 horas si salió bien, y 10 minutos si falló (_REINTENTO_SEGUNDOS). Un 404 en
  releases/latest (repo sin releases) no es un error.
- LÍMITE DE GITHUB: la API sin usuario permite 60 consultas por hora POR IP, y toda la red de la planta sale con la misma
  IP. Si un agente consulta la API en bucle (por ejemplo, para vigilar un release), la app de los usuarios empieza a ver
  "HTTP 403". _explicar_http lo traduce a un mensaje con la hora en que se libera. Para vigilar un release, consultar
  pocas veces o mirar la página de Actions en el navegador.
- Repositorio: github.com/ledesmamatiasarispe/super-duper-lamp (PÚBLICO: el actualizador baja los releases sin token;
  no subir nunca datos, la base ni contraseñas). El push se hace por HTTPS: la clave SSH de esta PC no está registrada.
- GitHub a veces responde 500/502 al push o al publicar el release ("Server Error", "Too many retries" en
  softprops/action-gh-release). No es un error del proyecto: se reintenta el push (y se verifica con git ls-remote) o
  se hace "Re-run failed jobs" en Actions.
- Releases publicados: v1.0.0 (logo herradura), v1.0.1 (logo omega ℧), v1.0.2 (botón "Programar todos" en Opciones,
  mensaje del límite de GitHub + reintento a los 10 minutos), v1.0.3 ("Repartir meses" dentro de Programar todos;
  la página pide app.js/styles.css con ?v=VERSION y se sirve sin caché, así después de actualizar no hace falta Ctrl+F5),
  v1.0.4 (Inicio con las tablas a todo el ancho, una debajo de la otra: en columnas se cortaban los nombres),
  v1.0.5 (botón "Imprimir lista del mes" en Inicio: hoja apaisada con casilleros para completar a mano),
  v1.0.6 (cambio de horómetro en Horómetros: tramos de lecturas y próximos corridos al horómetro nuevo; el
  cumplimiento del año no cuenta los meses anteriores al alta de la tarea).


7. DATOS REALES Y MIGRACIONES YA HECHAS
---------------------------------------
- separar_instructivos_compartidos ya corrió sobre la base real: IT01 estaba compartido por EQ-001 y EQ-003; EQ-003
  quedó con su copia IT03. La función sigue corriendo al arrancar (es idempotente) por si aparece otra base vieja.
- El instructivo de ejemplo ("EJEMPLO · Bomba centrífuga") está cargado en la base real, revisión 1, con código EJ01.
- 2026-11-06: se borraron los datos de prueba (EQ-001..003, IT01..03, 7 tareas) y se cargaron las 26 fichas originales
  con herramientas/cargar_fichas.py: 28 equipos (códigos = cronograma 2027), IT01..IT26 + IT27 (copia de IT06 para
  la Noyera N° 2). La ficha 25 (Amoladoras) no se cargó: no es un preventivo. El Plan quedó VACÍO: se programa con "Programar todos" (v1.0.2).
  Copia previa: data/mantenimiento_antes_de_fichas.db y data/adjuntos_antes_de_fichas/.
- 2026-11-06: se cargaron 25 correctivos del historial en papel PG713.01 (2023-12 a 2025-12, todos con SGC = Sí) y
  las personas Vallejo, Matías Arispe, Damián, Néstor y Pedro (estos dos dados de baja: renunciaron en 2026-10).
  El script tiene los datos adentro, por eso NO está en el repo: quedó en data/cargar_correctivos.py. Las fallas se
  redactaron a mano (la planilla solo las traía en el Horno). Una persona por correctivo; las demás en observaciones.
  Copia previa: data/mantenimiento_antes_de_correctivos.db.
- 2026-11-12: se cargó el CronogramaMantenimiento-2026.xlsx (data/cargar_cronograma_2026.py, fuera del repo): 76 registros
  Realizado (cada "v" de la hoja PROGRAMA; día 15, o 10/25 en las quincenales; quién = Mantenimiento interno "Sin dato
  (cronograma 2026)") y el próximo servicio de B/C/D de los compresores. No entraron: los A de los compresores (sin
  lectura de horómetro), Durómetro (sin instructivo), los B de las noyeras (sin programar), la C del elevador de arena.
  Como las tareas son del 2026-11, esos registros caen antes del alta: se ven en la grilla y no cuentan en el
  cumplimiento (ver cronograma()). Copia previa: data/mantenimiento_antes_de_cronograma_2026.db.
- Copias de seguridad tomadas antes de cada migración, en data/: mantenimiento_antes_de_orden.db,
  mantenimiento_antes_de_separar_instructivos.db, mantenimiento_antes_de_ejemplo.db.
