<div align="right">
  <a href="README.md">
    <img src="https://img.shields.io/badge/Read%20in-English-blue?style=for-the-badge" alt="Read in English">
  </a>
  <a href="README.pt-br.md">
    <img src="https://img.shields.io/badge/Ler%20em-Portugu%C3%AAs-green?style=for-the-badge" alt="Ler em Português">
  </a>
</div>

# LMU RPC Mod

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![Release](https://img.shields.io/github/v/release/uWaazy/LMU-RPC-Mod?style=for-the-badge&color=green)](https://github.com/uWaazy/LMU-RPC-Mod/releases)
[![Discord](https://img.shields.io/discord/1463577784394973392?style=for-the-badge&logo=discord&logoColor=white&label=Soporte)](https://discord.gg/cE6B2azY73)

**LMU RPC Mod** es una aplicación independiente que lleva **Discord Rich Presence** a **Le Mans Ultimate**. Muestra a tus amigos qué conduces, dónde, tu posición en la clase y tu Driver Rating, con actualizaciones en tiempo real y detección automática.

![LMU RPC Banner](preview.png)

## 📸 Vistas Previas (Previews)

Mira cómo aparece tu estado en Discord en diferentes situaciones de juego:

<p align="center">
  <img src="img/preview1.png" alt="Menú" width="32%">
  <img src="img/preview2.png" alt="Práctica" width="32%">
  <img src="img/preview3.png" alt="Carrera" width="32%">
</p>

## 🎮 Qué muestra

```
Le Mans Ultimate
⏱ 43:20 | P5/12 (20 de 34) | Online
Barcelona | Mercedes-AMG LMGT3 | Práctica
```

| Línea | Contenido |
| :--- | :--- |
| 1 | Tiempo restante (o vuelta/fase) · **posición en tu clase** / coches de tu clase · `(coches en la sesión de plazas)` solo online · modo (Online / Fin de Semana) |
| 2 | Pista · Coche · Sesión (Práctica, Clasificación, Carrera...) |
| Imagen grande | Alterna **coche (10 s)** y **pista (5 s)**. Las pistas sin imagen se quedan en el coche |
| Icono pequeño | Tu **Driver Badge**. Pasa el ratón para ver `DR S1 (30%) \| SR G1 (10%) \| Good Driver` |

## 🛡️ Driver Rating, Safety Rating y Badges

El icono pequeño de la imagen es tu **Driver Contact Badge**, y su tooltip muestra tu **DR** (Driver Rating) y **SR** (Safety Rating) como *rank + tier (progreso %)*, p. ej.: `S1 (30%)` = Plata, tier 1, 30% de progreso.

Estos valores **no** existen en la memoria compartida del juego, así que el mod nunca inventa ni estima nada. Provienen del ticket de inicio de sesión del propio juego y del servicio comunitario **RaceOS** (`raceos.gg`). Es una API no oficial y sin documentar.

* **Opt-in:** desactivado hasta que pongas `racecontrol.raceos.enabled` en `true` en `config.json`. Al activarlo, el ticket de inicio de sesión de Steam generado por tu juego se envía a `raceos.gg` para buscar tu perfil. Nunca se lee ni se guarda ninguna contraseña de Steam.
* **Badges:** los 5 oficiales: Rookie, Good Driver, Trusted Driver, Warning y Probation (independientes del SR).
* **Siempre al día:** se renueva cada 5 minutos y se revisa de nuevo tras cada carrera (el juego actualiza DR / SR / badge al terminar la carrera, así que pueden subir, bajar o cambiar de badge).
* **Seguro ante fallos:** si el servicio no responde, se mantiene el último valor válido (con reintento automático). Una consulta fallida nunca sustituye datos reales por un valor por defecto.
* ¿Aún sin datos? El icono y el tooltip simplemente no aparecen.

```json
"racecontrol": {
  "enabled": true,
  "raceos": { "enabled": true },
  "local_refresh_seconds": 300,
  "post_race_schedule_seconds": [10, 20, 40, 60, 90, 120, 180, 300],
  "session_lookup": false
}
```
`session_lookup` (desactivado por defecto) también consulta a los demás pilotos de la sesión, por nombre.

## ✨ Características

*   **Detección Automática:** Coche, Pista, Clase y Tipo de Sesión.
*   **Estado Inteligente:** Menús, Práctica, Clasificación, Warmup o Carrera, Online u offline.
*   **Datos en Tiempo Real:** Tiempo restante o vueltas, posición en la clase y parrilla de la sesión.
*   **Posición por clase:** `P5/12` es tu posición entre los coches de tu propia clase.
*   **Alternancia Coche / Pista** en la imagen, con tiempos configurables.
*   **Driver Rating, Safety Rating y Badge** (opt-in, ver arriba).
*   **Multi-Idioma:** Español, Inglés y Portugués (detectado automáticamente).
*   **Inicio Automático:** opcional, junto con Windows.
*   **Cero Configuración:** solo abre y juega. Sin configurar IP ni puerto.

## ⚙️ Ajustes (`config.json`)

| Clave | Por defecto | Descripción |
| :--- | :---: | :--- |
| `show_party_size` | `true` | Muestra `(coches en la sesión de plazas)` en la línea 1 (solo online) |
| `cycle_track_image` | `true` | Alterna las imágenes de coche y pista |
| `cycle_car_seconds` | `10` | Segundos con la imagen del coche |
| `cycle_track_seconds` | `5` | Segundos con la imagen de la pista |
| `autostart` | `false` | Iniciar con Windows |
| `steamid` | `""` | Opcional. Solo para consultas manuales |
| `racecontrol.raceos.enabled` | `false` | DR / SR / Badge automáticos (ver arriba) |

Copia `config.example.json` como `config.json` para empezar. Los registros se guardan en `lmu_rpc.log`.

## 📥 Instalación

1.  Ve a la página de [**Releases**](https://github.com/uWaazy/LMU-RPC-Mod/releases).
2.  Descarga el archivo `.zip` más reciente (ej: `LMU_RPC_vX.Y.zip`).
3.  Extráelo en cualquier lugar de tu PC.
4.  Ejecuta `LMU_RPC.exe` e inicia el RPC desde la aplicación.
5.  ¡Abre **Le Mans Ultimate** y disfruta!

## 🧪 Ejecutar desde el código fuente

```bash
pip install -r requirements.txt
python lmu_rpc.py
```

Python 3.10+ en Windows. Para generar el `.exe` usa Python 3.11 o 3.12 (`python build.py`).

**Preview:** `pip install -r requirements-preview.txt` y luego `python lmu_preview.py` (o `run_preview.bat`) abre una versión editable de la app: elige coche, pista, sesión, tiempo, posición y rating a mano y mira en Discord al instante, sin el juego.

## 🛠️ Proyectos Relacionados

Echa un vistazo a **LMU Tools**, una aplicación de escritorio que ayuda a los pilotos a optimizar configuraciones de coche y estrategias de carrera de forma rápida e intuitiva.

[![LMU Tools](https://img.shields.io/badge/GitHub-LMU_Tools-blue?style=for-the-badge&logo=github)](https://github.com/uWaazy/LMU-Tools/tree/main)

## 🤝 Soporte y Feedback

¿Encontraste un error? ¿Tienes una sugerencia? ¡Únete a nuestro servidor de Discord!

[![Discord](https://img.shields.io/discord/1463577784394973392?style=for-the-badge&logo=discord&logoColor=white&label=Unirse%20a%20Discord)](https://discord.gg/cE6B2azY73)

---

**Desarrollado por uWaazy**

<a href="https://ko-fi.com/uwaazy" target="_blank">
  <img src="https://img.shields.io/badge/Support%20my%20Work-FF5E5B?style=for-the-badge&logo=kofi&logoColor=white" alt="Ko-fi Donate">
</a>
