# 🤖 Bot de Registro de Gastos Personales

Bot de Telegram que registra gastos a partir de mensajes de texto libre (ej: `850 nafta`), usando un LLM para extraer y clasificar los datos automáticamente según una taxonomía de finanzas personales (modelo 50/30/20), y guardando cada registro en una Google Sheet.

Proyecto de portfolio: código limpio, testeable, documentado y desplegable.

## Arquitectura

```
Usuario (Telegram)
      │
      ▼
Bot Python (long polling, sin webhook)
      │
      ├─► NVIDIA NIM API (extracción + categorización)
      │         │
      │         ▼
      │   Validación estricta contra taxonomía
      │         │
      │         ▼
      ├─► Google Sheets API (Service Account) — persistencia
      │
      ▼
Respuesta de confirmación al usuario (Telegram)
```

## Stack

- **Python 3.12+**
- **python-telegram-bot** v20+ (async, long polling)
- **NVIDIA NIM** (`meta/llama-3.1-70b-instruct`, API compatible con OpenAI)
- **gspread + google-auth** (Service Account, sin OAuth de usuario)
- **httpx** (cliente HTTP async)
- **pytest + pytest-asyncio** (43 tests, todos con mocks, sin credenciales reales)
- **Docker + docker-compose** (deploy en Oracle Cloud Free Tier)

## Uso del bot

| Acción | Comando |
|---|---|
| Registrar gasto | Texto libre: `850 nafta`, `15000 supermercado coto`, `cobré 500000 sueldo` |
| Corregir último gasto | `/corregir <campo> <valor>` — campos: `monto`, `moneda`, `macro_categoria`, `subcategoria`, `cuenta_origen`, `descripcion` |
| Borrar último gasto | `/borrar` |
| Ayuda | `/help` |

Ejemplo de confirmación:

```
✅ Cargado: -850 ARS - nafta
📁 Necesidades (50%) > Transporte y Movilidad
💳 Sin especificar
```

Si el LLM no logra clasificar el gasto tras un reintento, el bot te pide la categoría exacta y completa la carga con tu respuesta. Si no logra identificar el monto, te lo pide explícitamente.

> El bot **solo responde al chat autorizado** (`TELEGRAM_ALLOWED_CHAT_ID`). Cualquier otro usuario recibe silencio total.

## Setup local

### 1. Clonar e instalar

```bash
git clone https://github.com/winttita/expense-tracker-bot.git
cd expense-tracker-bot
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Credenciales

Copiá `.env.example` a `.env` y completá:

#### a) Telegram

1. Hablale a **@BotFather** en Telegram → `/newbot` → te da el `TELEGRAM_BOT_TOKEN`.
2. Para obtener tu `TELEGRAM_ALLOWED_CHAT_ID`: mandale cualquier mensaje a tu bot y abrí en el navegador:
   ```
   https://api.telegram.org/bot<TU_TOKEN>/getUpdates
   ```
   Buscá `"chat":{"id":12345678...` → ese número es tu chat ID.

#### b) NVIDIA NIM

1. Creá una cuenta en [build.nvidia.com](https://build.nvidia.com).
2. Generá una API key (empieza con `nvapi-...`) → `NVIDIA_API_KEY`.

#### c) Google Sheets (Service Account)

1. Andá a [Google Cloud Console](https://console.cloud.google.com) → creá un proyecto.
2. Habilitá **Google Sheets API** y **Google Drive API** (APIs y servicios → Biblioteca).
3. IAM y administración → **Cuentas de servicio** → Crear cuenta de servicio (nombre cualquiera, sin roles a nivel proyecto).
4. En la cuenta creada → pestaña **Claves** → Agregar clave → **JSON** → se descarga un archivo.
5. **Copiá el `client_email`** del JSON (ej: `bot-gastos@proyecto.iam.gserviceaccount.com`).
6. Creá tu Google Sheet y **compartila con ese email** con permiso de **Editor**.
7. Copiá el ID de la sheet desde la URL: `https://docs.google.com/spreadsheets/d/<ESTE_ES_EL_ID>/edit` → `GOOGLE_SHEET_ID`.
8. En `.env`, pegá en `GOOGLE_SERVICE_ACCOUNT_JSON` el **contenido completo del JSON en una sola línea** (o la ruta al archivo).

> 💡 No hace falta escribir los encabezados a mano: si la hoja está vacía, el bot los crea solo al arrancar (`Fecha | Monto | Moneda | Macro-Categoría | Subcategoría | Cuenta/Origen | Descripción`).

### 3. Correr

```bash
python -m src.main            # lee .env del directorio actual
python -m src.main .env       # o pasale la ruta al archivo .env explícitamente
```

### 4. Tests

```bash
pytest
```

Los 43 tests corren sin credenciales: mockean NVIDIA NIM y Google Sheets.

## Despliegue (Oracle Cloud Free Tier)

Long polling = **sin puertos abiertos, sin HTTPS, sin certificados**. El bot solo hace conexiones salientes.

1. Creá una VM **Always Free** (Ubuntu 22.04, VM.Standard.E2.1.Micro) en [Oracle Cloud](https://cloud.oracle.com).
2. Conectate por SSH e instalá Docker:

   ```bash
   sudo apt update && sudo apt install -y docker.io docker-compose-v2
   sudo usermod -aG docker $USER && newgrp docker
   ```

3. Cloná el repo y configurá:

   ```bash
   git clone https://github.com/winttita/expense-tracker-bot.git
   cd expense-tracker-bot
   cp .env.example .env   # editá con tus credenciales: nano .env
   ```

4. Levantá el servicio:

   ```bash
   docker compose up -d --build
   docker compose logs -f   # ver logs
   ```

El contenedor usa `restart: unless-stopped`: sobrevive reinicios de la VM.

## Decisiones de diseño

- **Long polling, no webhook**: elimina la necesidad de HTTPS público, certificados y puertos abiertos. El bot se conecta hacia afuera a la API de Telegram. Simplifica radicalmente el despliegue en una VM gratuita.
- **Service Account en vez de OAuth de usuario**: evita el flujo de login interactivo (que había dado problemas con n8n). La sheet se comparte una sola vez con el email del service account y listo.
- **Validación estricta de taxonomía**: el LLM (open-weight) puede alucinar categorías. La taxonomía es una constante en el código que sirve al prompt *y* a la validación; si la respuesta no matchea exactamente, se reintenta una vez con feedback explícito y, si aún falla, se deriva al usuario en vez de guardar basura.
- **`/corregir` y `/borrar` sobre la última fila**: sin base de datos auxiliar. Es un bot de un solo usuario, así que "última fila" = "último gasto".
- **Fecha generada por el backend** (zona `America/Argentina/Buenos_Aires`): nunca se confía en el LLM para datos derivables.
- **Secrets por entorno**: ningún secreto en el repo; `.env` y credenciales JSON están en `.gitignore`.

## Estructura

```
├── src/
│   ├── main.py            # entrypoint, arranca el bot en polling
│   ├── config.py          # carga de variables de entorno
│   ├── taxonomia.py       # TAXONOMIA (fuente de verdad) + validación
│   ├── models.py          # modelo Gasto
│   ├── llm_client.py      # NVIDIA NIM + parseo robusto de JSON
│   ├── sheets_client.py   # append/corregir/borrar sobre Google Sheets
│   └── handlers.py        # comandos y flujo de conversación
├── tests/                 # 43 tests, sin credenciales reales
├── Dockerfile
├── docker-compose.yml
└── .env.example
```

## Backlog (fuera de alcance v1)

- Resúmenes automáticos semanales/mensuales.
- Múltiples gastos en un mismo mensaje.
- Conversión de moneda ARS/USD.
- Comandos de consulta ("¿cuánto gasté esta semana?").
- Multi-usuario.
