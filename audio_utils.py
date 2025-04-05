import logging
from gtts import gTTS
import streamlit as st
import io
from openai import OpenAI, OpenAIError
from dotenv import load_dotenv
import os

# Load environment variables
load_dotenv()
openai_api_key = os.getenv('OPENAI_API_KEY')
LOGGER = logging.getLogger('AudioUtils')

@st.cache_resource
def get_openai_client():
    """Returns a cached OpenAI client instance to avoid creating new clients for each request."""
    return OpenAI(api_key=openai_api_key)

def transcribe_audio(audio):
    """
    Transcribes audio to text using OpenAI whisper API.
    
    Args:
        audio: Either a dictionary containing audio data with 'bytes' key or the audio bytes directly.
        
    Returns:
        str: Transcribed text from the audio
    """
    client = get_openai_client()
    
    # Handle both dictionary format and direct bytes
    if isinstance(audio, dict) and 'bytes' in audio:
        audio_bytes = audio['bytes']
    else:
        audio_bytes = audio
    
    # Write data to a temporary WAV file with proper headers
    import tempfile
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp_file:
        temp_file.write(audio_bytes)
        temp_file_path = temp_file.name
    
    try:
        with open(temp_file_path, "rb") as audio_file:
            transcript = client.audio.transcriptions.create(
                model="whisper-1",
                file=audio_file,
                language='en'
            )
        output = transcript.text
        st.write(f"Transcribed: {output}")
        return output
    except OpenAIError as e:
        st.write(f"Error: {e}")
        return ""
    except Exception as e:
        st.write(f"Unexpected error in transcription: {e}")
        return ""
    finally:
        # Clean up temp file
        if os.path.exists(temp_file_path):
            os.remove(temp_file_path)


def text_to_speech(response):
    """
    Converts text to speech and saves it as a WAV file using gTTs library.
    
    Args:
        response (str): Text to be converted to speech.
    """
    try:
        # Log that TTS conversion is starting
        LOGGER.info("Converting text to speech...")
        
        tts = gTTS(text=response, lang='en')
        tts.save('response.wav')
        
        # Verify the file was created successfully
        if os.path.exists('response.wav'):
            LOGGER.info("Audio file created successfully")
        else:
            LOGGER.error("Audio file creation failed - file not found")
    except Exception as e:
        LOGGER.error(f"Error in text-to-speech conversion: {str(e)}")

def play_audio(file_name):
    """
    Plays audio file in the Streamlit app.
    
    Args:
        file_name (str): Name of the audio file.
    """
    try:
        audio_file = open(file_name, 'rb')
        audio_bytes = audio_file.read()
        st.audio(audio_bytes,format="audio/wav",)
    except Exception as e:
        print(e)