from elevenlabs import ElevenLabs
from bot.utils.config import get_settings
import io

settings = get_settings()

client = ElevenLabs(
    api_key=settings.ELEVENLABS_API_KEY,
)

def transcribe_audio(audio_file: io.BytesIO) -> str:
    """
    Transcribe audio to text using ElevenLabs.

    Args:
        audio_file (io.BytesIO): Audio file to transcribe.

    Returns:
        str: Transcribed text.
    """
    result = client.speech_to_text.convert(
        model_id="scribe_v1",
        file=audio_file,
        num_speakers=1,
        diarize=False,
        tag_audio_events=True
    )
    return result.text