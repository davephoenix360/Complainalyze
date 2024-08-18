import io
from google.oauth2 import service_account
from google.cloud import speech
import dotenv
dotenv.load_dotenv()

client = speech.SpeechClient()

fileName = "What is Fortnite's Best Shotgun_.mp3";
with io.open(fileName, 'rb') as f:
    content = f.read()
    audio = speech.RecognitionAudio(content=content)

config = speech.RecognitionConfig(
    encoding=speech.RecognitionConfig.AudioEncoding.MP3,
    sample_rate_hertz=16000,
    language_code='en-US'
)

response = client.recognize(config=config, audio=audio)

print(response)