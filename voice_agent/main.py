from dotenv import load_dotenv
import speech_recognition as sr
from openai import OpenAI
from gtts import gTTS
from playsound import playsound
import os

load_dotenv()

gemini_api_key = os.getenv("GEMINI_API_KEY")
client = OpenAI(
    api_key=gemini_api_key,
    base_url="https://generativelanguage.googleapis.com/v1beta/openai/"
)

def main():
    r = sr.Recognizer() # Create a Recognizer object for speech to text conversion
    with sr.Microphone() as source: # Access the microphone /Use the microphone as the audio source
        r.adjust_for_ambient_noise(source) # Adjust for ambient noise to improve recognition accuracy
        r.pause_threshold = 2 # Set the pause threshold to 2 second means that if there is a pause of 2 seconds, it will consider the speech input as complete
        
        print("Speak something...") # Prompt the user to speak
        audio = r.listen(source=source) # Listen for the user's speech input and store it in the audio variable
        
        print("Processing Audio... (STT)") # Indicate that the audio is being processed for speech to text conversion
        stt = r.recognize_google(audio) # Use Google's speech recognition service to convert the audio to text and store it in the stt variable
        print(f"You said: {stt}") # Print the recognized text to the console
        
        
        SYSTEM_PROMPT = """
        You are an expert voice agent. You are given the transcript of what 
        user has said using voice.
        You need need to output as if you are a voice agent and whatever you speak
        will be converted to audio and played to the user.
        
        #INSTRUCTION
        1. Always keep your responses concise and to the point, ideally under **20 words**.
        2. Avoid using complex vocabulary or technical jargon. Use simple and clear language that is easy for anyone to understand.
        
        """
        response = client.chat.completions.create(
            model="gemini-3-flash-preview",
            messages=[
                {
                    "role": "system",
                    "content": SYSTEM_PROMPT
                },
                {
                    "role": "user",
                    "content": stt
                }
            ]
        )
        print(f"Voice Agent: {response.choices[0].message.content}") # Print the response from the voice agent to the console
        
        print("Processing Audio... (TTS)") # Indicate that the response is being processed for text to speech conversion
        tts = gTTS(text=response.choices[0].message.content, lang='en')
        tts.save("response.mp3")
        playsound("response.mp3") # Play the generated audio response to the user
        
main()

    