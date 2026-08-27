import os
import json
import base64
import wave
import asyncio
import urllib.request
import urllib.error

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)


# =========================================================
# CONFIG
# =========================================================

TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
GEMINI_KEY = os.environ.get("GEMINI_API_KEY")

MODEL = "gemini-3.1-flash-tts-preview"

OUTPUT_FILE = "gemini_voice.wav"


if not TOKEN:
    raise RuntimeError("TELEGRAM_BOT_TOKEN missing")

if not GEMINI_KEY:
    raise RuntimeError("GEMINI_API_KEY missing")


# =========================================================
# GEMINI TTS
# =========================================================

def generate_tts(text):

    url = (
        "https://generativelanguage.googleapis.com/"
        "v1beta/interactions"
    )

    prompt = """
Speak the following Hindi narration as ONE continuous
YouTube movie-explanation voice-over.

VOICE STYLE:
- Natural Indian Hindi narrator.
- Clear pronunciation.
- Confident and energetic.
- Moderately fast.
- Smooth continuous delivery.

PACING:
- Do NOT pause after every sentence.
- Do NOT insert long silent gaps.
- Do NOT speak word by word.
- Do NOT add dramatic pauses.
- Keep the narration flowing continuously.
- Use only tiny natural breathing pauses when necessary.

TEXT RULES:
- Speak exactly the supplied Hindi text.
- Do not add words.
- Do not remove words.
- Do not summarize.
- Do not explain anything.

Hindi narration:

""" + text

    data = {
        "model": MODEL,
        "input": prompt,
        "response_format": {
            "type": "audio"
        },
        "generation_config": {
            "speech_config": [
                {
                    "voice": "Kore"
                }
            ]
        }
    }

    body = json.dumps(
        data,
        ensure_ascii=False
    ).encode("utf-8")

    request = urllib.request.Request(
        url,
        data=body,
        headers={
            "Content-Type": "application/json",
            "x-goog-api-key": GEMINI_KEY,
            "Api-Revision": "2026-05-20"
        },
        method="POST"
    )

    try:

        with urllib.request.urlopen(
            request,
            timeout=1800
        ) as response:

            result = json.loads(
                response.read().decode("utf-8")
            )

    except urllib.error.HTTPError as e:

        error = e.read().decode(
            "utf-8",
            errors="replace"
        )

        raise RuntimeError(
            f"Gemini HTTP {e.code}\n"
            + error[:3000]
        )

    except Exception as e:

        raise RuntimeError(
            f"Gemini connection error:\n{e}"
        )

    # -----------------------------------------------------
    # AUDIO FROM OUTPUT_AUDIO
    # -----------------------------------------------------

    output_audio = result.get("output_audio")

    if output_audio:

        encoded = output_audio.get("data")

        if encoded:

            return base64.b64decode(encoded)

    # -----------------------------------------------------
    # FALLBACK: STEPS
    # -----------------------------------------------------

    for step in result.get("steps", []):

        for content in step.get("content", []):

            if content.get("type") == "audio":

                encoded = content.get("data")

                if encoded:

                    return base64.b64decode(
                        encoded
                    )

    raise RuntimeError(
        "No audio returned by Gemini.\n\n"
        + json.dumps(
            result,
            ensure_ascii=False
        )[:3000]
    )


# =========================================================
# RETRY
# =========================================================

def generate_tts_retry(text):

    last_error = None

    for attempt in range(1, 4):

        try:

            print(
                f"🔊 Gemini TTS attempt "
                f"{attempt}/3"
            )

            return generate_tts(text)

        except Exception as e:

            last_error = e

            print(
                f"⚠️ Attempt {attempt} failed:"
            )

            print(e)

            if attempt < 3:

                import time

                time.sleep(
                    attempt * 5
                )

    raise RuntimeError(
        "TTS failed after 3 attempts.\n\n"
        + str(last_error)
    )


# =========================================================
# SAVE WAV
# =========================================================

def save_wav(
    filename,
    pcm_data
):

    with wave.open(
        filename,
        "wb"
    ) as audio:

        audio.setnchannels(1)
        audio.setsampwidth(2)
        audio.setframerate(24000)

        audio.writeframes(
            pcm_data
        )


# =========================================================
# START
# =========================================================

async def start(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    await update.message.reply_text(
        "🔊 GEMINI TTS BOT\n\n"
        "Hindi text bhejo.\n\n"
        "मैं उसे continuous voice-over "
        "में बदल दूँगा."
    )


# =========================================================
# TEXT TO SPEECH
# =========================================================

async def text_to_speech(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    text = update.message.text.strip()

    if not text:
        return

    status = await update.message.reply_text(
        "🔊 GEMINI TTS\n\n"
        "⏳ 1% — Text received"
    )

    try:

        await status.edit_text(
            "🔊 GEMINI TTS\n\n"
            "☁️ Gemini voice generate "
            "कर रहा है...\n\n"
            "⏳ 30%"
        )

        pcm = await asyncio.to_thread(
            generate_tts_retry,
            text
        )

        await status.edit_text(
            "🔊 GEMINI TTS\n\n"
            "🎵 Audio तैयार हो रहा है...\n\n"
            "⏳ 75%"
        )

        await asyncio.to_thread(
            save_wav,
            OUTPUT_FILE,
            pcm
        )

        await status.edit_text(
            "🔊 GEMINI TTS\n\n"
            "📤 Audio भेज रहा हूँ...\n\n"
            "⏳ 95%"
        )

        with open(
            OUTPUT_FILE,
            "rb"
        ) as audio:

            await update.message.reply_audio(
                audio=audio,
                filename="gemini_hindi_voice.wav",
                title="Gemini Hindi Voice"
            )

        await status.edit_text(
            "✅ DONE\n\n"
            "🔊 Continuous Hindi voice generated."
        )

    except Exception as e:

        print(
            "❌ ERROR:",
            repr(e)
        )

        try:

            await status.edit_text(
                "❌ ERROR\n\n"
                + str(e)[:3000]
            )

        except Exception:

            pass


# =========================================================
# MAIN
# =========================================================

def main():

    print("🔊 GEMINI TTS BOT")
    print("🚀 Starting...")
    print("TOKEN:", "OK")
    print("GEMINI:", "OK")

    app = (
        Application
        .builder()
        .token(TOKEN)
        .connect_timeout(120)
        .read_timeout(1800)
        .write_timeout(1800)
        .pool_timeout(120)
        .build()
    )

    app.add_handler(
        CommandHandler(
            "start",
            start
        )
    )

    app.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            text_to_speech
        )
    )

    print(
        "✅ TTS BOT IS RUNNING!"
    )

    app.run_polling(
        drop_pending_updates=True
    )


if __name__ == "__main__":
    main()