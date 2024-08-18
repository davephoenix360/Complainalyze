from flask import Flask, request, jsonify
from elasticsearch import Elasticsearch, helpers, exceptions
import json
import time
import os
import psycopg2
from config import config
from dotenv import load_dotenv
from groq import Groq
import io
from google.oauth2 import service_account
from google.cloud import speech, vision
from langchain.agents import load_tools, initialize_agent
from langchain_groq import ChatGroq
from langchain.tools import BaseTool

load_dotenv()

app = Flask(__name__)


@app.route("/categorize", methods=["POST"])
def categorize_complaint():
    data = request.get_json()
    
    def voice_agent_process(response):
        # Placeholder function - implement actual logic later
        return " ".join([result.alternatives[0].transcript for result in response.results])

    def text_agent_process(complaint: str):
        # Placeholder function - implement actual logic later
        return complaint

    def image_agent_process(whole_text: str):
        # Placeholder function - implement actual logic later
        return whole_text

    def voice_agent(file_path):
        client = speech.SpeechClient()
        with io.open(file_path, "rb") as f:
            content = f.read()
            audio = speech.RecognitionAudio(content=content)

        config = speech.RecognitionConfig(
            encoding=speech.RecognitionConfig.AudioEncoding.MP3,
            sample_rate_hertz=16000,
            language_code="en-US",
        )

        response = client.recognize(config=config, audio=audio)
        return voice_agent_process(response)

    def text_agent(complaint: str):
        return text_agent_process(complaint)

    def image_agent(file_path):
        client = vision.ImageAnnotatorClient()
        with open(file_path, "rb") as image_file:
            content = image_file.read()
        
        image = vision.Image(content=content)
        
        response = client.text_detection(image=image)
        texts = response.text_annotations
        whole_text = ' '.join([text.description for text in texts])

        if response.error.message:
            raise Exception(
                "{}\nFor more info on error messages, check: "
                "https://cloud.google.com/apis/design/errors".format(response.error.message)
            )
        
        return image_agent_process(whole_text)

    audio_result = voice_agent(data.get("audio")) if data.get("audio") else None
    image_result = image_agent(data.get("image")) if data.get("image") else None
    text_result = text_agent(data.get("text")) if data.get("text") else None

    user_complaint = ""
    if audio_result:
        user_complaint += f"Audio Complaint: {audio_result}\n"
    if image_result:
        user_complaint += f"Image Complaint: {image_result}\n"
    if text_result:
        user_complaint += f"Text Complaint: {text_result}\n"

    esClient = Elasticsearch(
        cloud_id=os.getenv("ELASTIC_SEARCH_CLOUD_ID"),
        api_key=os.getenv("ELASTIC_SEARCH_API_KEY"),
    )

    groqClient = Groq(
        api_key=os.getenv("GROQ_API_KEY"),
    )

    response = esClient.search(
        index="complaints",
        size=5,
        query={
            "text_expansion": {
                "plot_embedding": {
                    "model_id": ".elser_model_2",
                    "model_text": user_complaint,
                }
            }
        },
    )

    related_ids = [hit["_id"] for hit in response["hits"]["hits"]]

    related_records = []
    connection = None
    try:
        params = config()
        print("Connecting to database")
        connection = psycopg2.connect(**params)

        cursor = connection.cursor()
        cursor.execute(
            "SELECT * FROM complaints WHERE _id IN %s", (tuple(related_ids),)
        )
        related_records = cursor.fetchall()
        cursor.close()

    except:
        print("error")

    finally:
        if connection is not None:
            connection.close()
            print("Database conn terminated")

    related_records_str = "\n".join([json.dumps(record[4]) for record in related_records])

    system_prompt = """Given a user's complaint (which may include information from audio, image, and text sources) and a couple of stored similar complaints, categorize the 
    current user's complaint using the following keys in the similar complaints: 'product', 'issue', 'subproduct', and 'subissue'.
    Try as much as possible to use one of the given values of each of these keys only when they are related, otherwise you can form the best value for it.
    Take into account all the information provided from different sources (audio, image, text) when categorizing.

    Return specifically in the JSON format below:
    {
        "product": str, 
        "complaint_what_happened": (The user's complaint, combining information from all sources)
        "issue": str, 
        "sub_product": str, 
        "sub_issue": str, 
    }
    
    """

    chat_completion = groqClient.chat.completions.create(
        messages=[
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": "Categorize this complaint: {0}\nUsing these similar complaints: {1}".format(
                    user_complaint, related_records_str
                ),
            },
        ],
        model="llama3-8b-8192",
        response_format={"type": "json_object"},
    )

    return chat_completion.choices[0].message.content


if __name__ == "__main__":
    app.run(debug=True)