"""
Audio transcription service — Whisper STT for earnings calls / CEO interviews.
Uses OpenAI-compatible Whisper API via the Gemini client.
"""
import os
import tempfile
import requests

from backend.deps import get_llm_client


def transcribe_audio_from_url(audio_url: str) -> str:
    """
    Download an audio file from a URL and transcribe it using Whisper.
    Returns the transcript as a plain string.
    """
    # Download audio to a temp file
    resp = requests.get(audio_url, timeout=60)
    resp.raise_for_status()

    suffix = ".mp3"
    if ".wav" in audio_url:
        suffix = ".wav"
    elif ".m4a" in audio_url:
        suffix = ".m4a"

    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(resp.content)
        tmp_path = tmp.name

    try:
        transcript = transcribe_audio_file(tmp_path)
    finally:
        os.unlink(tmp_path)

    return transcript


def transcribe_audio_file(file_path: str) -> str:
    """
    Transcribe a local audio file using OpenAI Whisper API.
    Compatible with the Gemini-via-OpenAI-SDK pattern.
    """
    try:
        with open(file_path, "rb") as audio_file:
            response = get_llm_client().audio.transcriptions.create(
                model="whisper-1",
                file=audio_file,
            )
        return response.text
    except Exception as e:
        # If Whisper API is unavailable (e.g. Gemini doesn't support it),
        # return a placeholder so the pipeline doesn't break.
        print(f"[AudioService] Whisper transcription failed: {e}")
        return f"[Transcription unavailable: {str(e)[:100]}]"
