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
- Repositorio: github.com/ledesmamatiasarispe/super-duper-lamp.
