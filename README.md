# IoT Sound Effect — Teclado de Sonidos

Convierte un **teclado numérico USB** (por ejemplo, un Gear Head KP2200U) en una **botonera de efectos de sonido** en Windows: cada tecla reproduce un MP3 o WAV en lugar de escribir números.

- Funciona con **cualquier teclado numérico USB**: la primera vez, un asistente te pide presionar una tecla y lo detecta solo.
- No necesitas permisos de administrador ni instalar drivers.
- Solo usa Python estándar (sin `pip install`), o el `.exe` listo para usar.
- Si presionas una tecla mientras otro sonido está sonando, se ignora hasta que termine.

> **Requisitos:** Windows 10 u 11.

## Instalación

### Opción A: `.exe` (sin Python)
1. Ve a [Releases](../../releases) y descarga `TecladoSonidos-windows.zip`.
2. Descomprímelo en una carpeta fija, por ejemplo `Documentos\TecladoSonidos`.
3. Doble clic en **`iniciar.bat`**.

> El `.exe` no está firmado digitalmente. Si Windows SmartScreen lo bloquea, haz clic en **Más información → Ejecutar de todos modos**.

### Opción B: con Python
1. Instala [Python 3.9 o superior](https://www.python.org/downloads/windows/) (deja marcada la opción del *py launcher*).
2. Clona o descarga este repositorio.
3. Doble clic en **`iniciar.bat`**.

## Primera vez: elegir el teclado
Al iniciar por primera vez se abre una ventana:

```
Presiona cualquier tecla del teclado que quieres convertir en botonera...

  Detectado: Teclado USB VID_04D9 PID_1505  (VID 04D9 / PID 1505)
  Usar este teclado? [S/N]
```

Presiona una tecla **del teclado numérico** y confirma con `S`. Se guarda en `config.json` y la botonera queda funcionando en segundo plano. Para cambiar de teclado, usa **`configurar.bat`**.

El proyecto **no trae audios**: cada persona pone los suyos (ver [Poner tus sonidos](#poner-tus-sonidos)). Si la carpeta `sonidos/` está vacía, el asistente ofrece crear **sonidos de prueba** para comprobar que todo funciona.

## Uso

| Archivo | Para qué sirve |
|---|---|
| `iniciar.bat` | Arranca la botonera (suena un bip de encendido) |
| `configurar.bat` | Elige otro teclado |
| `detener.bat` | Cierra la botonera |

- **La luz de Num Lock es el interruptor:** encendida = las teclas suenan; apagada = funcionan normal (flechas, Inicio, Fin…).
- Al **desconectar** el teclado elegido (bip grave), los sonidos se desactivan solos. Al volver a conectarlo (bip agudo), se activan otra vez.
- Para que arranque con Windows: presiona `Win + R`, escribe `shell:startup` y crea ahí un acceso directo a `iniciar.bat`.
- El sonido sale por la salida de audio predeterminada de Windows (parlantes, audífonos Bluetooth, etc.).

> ⚠️ **Importante:** Windows no informa de qué teclado viene una tecla antes de que el programa tenga que decidir si la bloquea. Por eso, mientras el teclado elegido esté conectado, **el bloque numérico de cualquier teclado con Num Lock encendido** (también el de la laptop o el del teclado principal) reproduce sonidos. Las letras y demás teclas funcionan normal. Para escribir números, usa la fila de números de arriba o `detener.bat`.

## Poner tus sonidos
Copia tus archivos en la carpeta **`sonidos/`** con el **nombre de la tecla**. El programa los busca en cada pulsación, así que no hace falta reiniciarlo. La misma guía está en `sonidos/LEEME.txt`.

| Tecla | Nombre del archivo | Tecla | Nombre del archivo |
|---|---|---|---|
| `/` | `dividir.mp3` | `7` `8` `9` | `7.mp3` `8.mp3` `9.mp3` |
| `*` | `multiplicar.mp3` | `4` `5` `6` | `4.mp3` `5.mp3` `6.mp3` |
| `-` | `menos.mp3` | `1` `2` `3` | `1.mp3` `2.mp3` `3.mp3` |
| `+` | `mas.mp3` | `0` | `0.mp3` |
| `Enter` | `enter.mp3` | `000` | `000.mp3` |
| `.` / `Del` | `punto.mp3` | Conectar / desconectar (opcional) | `on.mp3` / `off.mp3` |

Ejemplo: para que la tecla `7` reproduzca `aplausos.mp3`, cópialo a `sonidos/` y renómbralo a `7.mp3`.

- Acepta `.mp3` y `.wav`. Si existen los dos con el mismo nombre, se usa el `.mp3`.
- Una tecla sin archivo no hace nada, así que puedes borrar los que no uses. Al iniciar, `teclado_sonidos.log` lista las teclas que no tienen sonido.
- Activa en el Explorador **Vista → Mostrar → Extensiones de nombre de archivo** para no terminar con nombres como `7.mp3.mp3`.
- Mientras un sonido suena, las demás teclas se ignoran, así que conviene usar audios cortos (1–5 s).
- Sonidos de prueba: `py generar_sonidos_prueba.py` crea un `.wav` por tecla.
- Todo el contenido de `sonidos/` (menos `LEEME.txt`) está en `.gitignore`, para no publicar por accidente audio con derechos de autor.
- Para usar otros nombres de archivo, edita `teclas` en `config.json` (por ejemplo, `"0x47": "aplausos"` hace que la tecla 7 busque `aplausos.mp3`).

### Notas sobre algunas teclas
- **`000`**: el teclado envía tres "0" seguidos. El programa lo detecta y reproduce `000.mp3`.
- **`BS` (borrar)**: no tiene sonido por defecto, porque envía la misma señal que el Backspace de cualquier teclado. Si igual quieres que suene, agrega `"0x0E": "borrar"` en `teclas` dentro de `config.json` y pon un archivo `borrar.mp3`.

## Configuración avanzada (`config.json`)
```json
{
  "dispositivo": {"vid": "04D9", "pid": "1505", "nombre": "Gear Head KP2200U"},
  "teclas": {"0x47": "7", "0xE01C": "enter", "...": "..."}
}
```
- `teclas`: *scan code* → nombre del sonido. `0xE0xx` indica una tecla extendida. Mira `config.ejemplo.json` para ver el mapa completo.

## Problemas frecuentes
| Problema | Qué revisar |
|---|---|
| No suena nada | Revisa `teclado_sonidos.log`. Comprueba que el teclado esté conectado (al conectarlo suena el bip de encendido) y que su luz de Num Lock esté encendida. |
| Suena por otro dispositivo | Cambia la salida de audio predeterminada de Windows. |
| Quiero escribir números | Usa la fila de números del teclado principal, o `detener.bat`. |
| Elegí el teclado equivocado | Usa `configurar.bat`. |

## Cómo funciona (para desarrolladores)
- `teclado_sonidos.py` usa la API Win32 con `ctypes`:
  - Un hook **`WH_KEYBOARD_LL`** intercepta las teclas del bloque numérico.
  - **Raw Input** (`RIDEV_DEVNOTIFY`) detecta si el teclado elegido (por VID/PID) está conectado.
  - **MCI** (`winmm`) reproduce MP3 y WAV.
- El hook decide si bloquea una tecla **antes** de que Windows genere el `WM_INPUT` que identifica el dispositivo. Una tecla bloqueada nunca llega a Raw Input. Por eso no se puede filtrar por teclado sin un driver como [Interception](https://github.com/oblitum/Interception), que requiere administrador.
- El `.exe` se genera con PyInstaller en GitHub Actions al publicar un tag `v*` (ver `.github/workflows/release.yml`).

## Licencia
[MIT](LICENSE)
