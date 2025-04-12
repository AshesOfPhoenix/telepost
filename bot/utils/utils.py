from elevenlabs import ElevenLabs
from bot.utils.config import get_settings
import io

settings = get_settings()

client = ElevenLabs(
    api_key=settings.ELEVENLABS_API_KEY,
)

def transcribe_audio(audio_file: io.BytesIO) -> str:
    result = client.speech_to_text.convert(
        model_id="scribe_v1",
        audio_file=audio_file
    )
    return result.text