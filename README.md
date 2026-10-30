# Spotifice

Spotifice es una aplicación distribuida de reproducción y gestión de música, desarrollada en Python con ZeroC Ice e IceStorm.

> **Nota de autoría:** Este proyecto se realizó como parte de la asignatura «Sistemas distribuidos». La profesora desarrolló gran parte del código, especialmente el esqueleto de la aplicación y las interfaces definidas en los archivos `.ice`.

## Funcionalidades

- Consulta de pistas y listas de reproducción disponibles en un servidor multimedia.
- Autenticación de usuarios y creación de sesiones para transmitir audio.
- Reproducción, pausa, detención y navegación entre pistas desde un reproductor.
- Descubrimiento de servidores y reproductores mediante IceStorm.
- Búsqueda distribuida de pistas y listas de reproducción.

La aplicación se organiza en varios procesos:

- **MediaServer** (`media_server.py`): carga los archivos MP3, las listas `.playlist` y los usuarios; ofrece el catálogo, autenticación y transmisión de audio.
- **MediaRender** (`media_render.py`): recibe órdenes de reproducción y reproduce el audio con GStreamer.
- **MediaDirectory** (`media_directory.py`): mantiene el registro de servidores y reproductores anunciados.
- **Media control** (`media_control.py`): cliente de ejemplo que se autentica, consulta el catálogo y envía órdenes al reproductor.
- **IceStorm**: servicio de publicación y suscripción usado para los anuncios y el descubrimiento.

Las interfaces RPC están especificadas en `spotifice_v0.ice`–`spotifice_v3.ice`. El código carga `spotifice_v3.ice` al iniciar.

## Requisitos

El proyecto está preparado para un entorno Linux con paquetes Debian/Ubuntu. Se necesitan Python 3, ZeroC Ice con IceStorm, GStreamer y sus bindings de Python, además de `make`, `wget` y `unzip` para descargar los archivos de audio de ejemplo.

En Debian o Ubuntu, los paquetes principales se pueden instalar con:

```bash
sudo apt update
sudo apt install make wget unzip zeroc-ice-all-dev zeroc-ice-all-runtime \
  python3-zeroc-ice python3-gi gstreamer1.0-plugins-base \
  gstreamer1.0-plugins-good python3-pytest
```

El reproductor usa la salida de audio predeterminada de GStreamer. Para ejecutar las pruebas también hace falta que el entorno tenga disponibles sus plugins y dependencias de audio.

## Preparación

Clona el repositorio y ejecuta los comandos desde su directorio raíz, ya que las rutas de los archivos de configuración son relativas:

```bash
git clone <URL_DEL_REPOSITORIO>
cd Spotifice
```

Los archivos MP3 no están incluidos en el repositorio. El objetivo `make media` descarga el archivo de música configurado en el `Makefile` y lo extrae en `media/`:

```bash
make media
```

El servidor lee las pistas de `media/`, las listas de reproducción de `playlists/` y las cuentas de `users.json`. Las listas `.playlist` contienen los nombres de archivo de sus pistas; asegúrate de que cada pista referenciada exista en `media/`.

## Ejecución

Inicia cada proceso en una terminal distinta desde el directorio raíz. IceStorm debe estar activo antes de iniciar los componentes:

```bash
icebox --Ice.Config=icebox.config
```

Después, inicia el servidor, el reproductor y el directorio:

```bash
python3 media_server.py server.config
python3 media_render.py render.config
python3 media_directory.py directory.config
```

En otra terminal, ejecuta el cliente de control para probar la reproducción:

```bash
python3 media_control.py control.config
```

Para arrancar esos cuatro procesos (servidor, reproductor, cliente de control y directorio) en paneles de `tmux`, también puedes usar:

```bash
./run.sh
```

`run.sh` no inicia IceStorm, por lo que debes arrancarlo previamente. El cliente de control usa las referencias definidas en `control.config` y las credenciales de ejemplo `user` / `secret`. Para probar la reproducción con ese cliente, debe haber al menos dos listas de reproducción cargadas.

Los puertos y las referencias de los servicios se configuran en `server.config`, `render.config`, `directory.config`, `control.config` e `icestorm.config`.

## Pruebas

Ejecuta la suite desde la raíz del proyecto:

```bash
make test
```

También se puede ejecutar directamente con `pytest -v test`.
