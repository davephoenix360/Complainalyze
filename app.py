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
    user_complaint: str = data["prompt"]

    esClient = Elasticsearch(
        cloud_id=os.getenv("ELASTIC_SEARCH_CLOUD_ID"),
        api_key=os.getenv("ELASTIC_SEARCH_API_KEY"),
    )

    groqClient = Groq(
        # This is the default and can be omitted
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

    related_ids = []

    for hit in response["hits"]["hits"]:
        related_ids.append(hit["_id"])

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

    related_records_str = ""

    for record in related_records:
        related_records_str += json.dumps(record[4]) + "\n"

    system_prompt = """Given a user's complaint as a regular text and a couple of stored similar complaints, categorize the 
    current user's complaint using the following keys in the similar complaints: 'product', 'issue', 'subproduct', and 'subissue'.
    Try as much as possible to use one of the given values of each of these keys only when they are related, otherwise you can form the best value for it.

    Return specifically in the JSON format below:
    {
        "product": str, 
        "complaint_what_happened": (The user's complaint)
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


@app.route("/agent", methods=["POST"])
def agent_extract():

    data = request.get_json()

    def voice_agent(fileName):
        client = speech.SpeechClient()
        with io.open(fileName, "rb") as f:
            content = f.read()
            audio = speech.RecognitionAudio(content=content)

        config = speech.RecognitionConfig(
            encoding=speech.RecognitionConfig.AudioEncoding.MP3,
            sample_rate_hertz=16000,
            language_code="en-US",
        )

        groqClient = Groq(
            # This is the default and can be omitted
            api_key=os.getenv("GROQ_API_KEY"),
        )

        response = client.recognize(config=config, audio=audio)

        system_prompt = """Given a user's complaint as a text transcription gotten from a video, try to extract the information from the transcript and return the
        extracted values as a json. Only look for the keys specified. Try as much as possible to get the required information but 
        if it is not available you can set the value to null.

        Return specifically in the JSON format below:
        {
            "_index": "complaint-public-v2",
            "_type": "_doc",
            "_score": null,
            "_source":
            {
                "product": str, 
                "complaint_what_happened": (The user's complaint)
                "date_sent_to_company": str(YYYY-MM-DDT12HH:MM-HH:MM)
                "issue": str, 
                "sub_product": str, 
                "sub_issue": str,
                "zip_code": str,
                "tags": str,
                "complaint_id": str,
                "timely": (Yes/No),
                "consumer_consent_provided": ("Consent provided"/"Consent Not Provided"),
                "company_response": str,
                "submitted_via": str ('web', 'letter', etc),
                "company": str,
                "date_received": str(YYYY-MM-DDT12HH:MM-HH:MM),
                "state": str (NY,SA,etc),
                "consumer_disputed": str,
                "company_public_response": str
            }
        }
        
        """

        chat_completion = groqClient.chat.completions.create(
            messages=[
                {"role": "system", "content": system_prompt},
                {
                    "role": "user",
                    "content": "Categorize this complaint: {0}".format(response),
                },
            ],
            model="llama3-8b-8192",
            response_format={"type": "json_object"},
        )

        return chat_completion.choices[0].message.content

    def text_agent(complaint: str):
        groqClient = Groq(
            # This is the default and can be omitted
            api_key=os.getenv("GROQ_API_KEY"),
        )

        system_prompt = """Given a user's complaint as a message they sent, try to extract the information from the transcript and return the
        extracted values as a json. Only look for the keys specified. Try as much as possible to get the required information but 
        if it is not available you can set the value to null.

        Return specifically in the JSON format below:
        {
            "_index": "complaint-public-v2",
            "_type": "_doc",
            "_score": null,
            "_source":
            {
                "product": str, 
                "complaint_what_happened": (The user's complaint)
                "date_sent_to_company": str(YYYY-MM-DDT12HH:MM-HH:MM)
                "issue": str, 
                "sub_product": str, 
                "sub_issue": str,
                "zip_code": str,
                "tags": str,
                "complaint_id": str,
                "timely": (Yes/No),
                "consumer_consent_provided": ("Consent provided"/"Consent Not Provided"),
                "company_response": str,
                "submitted_via": str ('web', 'letter', etc),
                "company": str,
                "date_received": str(YYYY-MM-DDT12HH:MM-HH:MM),
                "state": str (NY,SA,etc),
                "consumer_disputed": str,
                "company_public_response": str
            }
        }
        
        """

        chat_completion = groqClient.chat.completions.create(
            messages=[
                {"role": "system", "content": system_prompt},
                {
                    "role": "user",
                    "content": "Categorize this complaint: {0}".format(complaint),
                },
            ],
            model="llama3-8b-8192",
            response_format={"type": "json_object"},
        )

        return chat_completion.choices[0].message.content

    def image_agent(path):

        client = vision.ImageAnnotatorClient()
        with open(path, "rb") as image_file:
            content = image_file.read()

        image = vision.Image(content=content)

        response = client.text_detection(image=image)
        texts = response.text_annotations
        # print(' '.join([text.description for text in texts]))
        whole_text = " ".join([text.description for text in texts])

        if response.error.message:
            raise Exception(
                "{}\nFor more info on error messages, check: "
                "https://cloud.google.com/apis/design/errors".format(
                    response.error.message
                )
            )

        groqClient = Groq(
            # This is the default and can be omitted
            api_key=os.getenv("GROQ_API_KEY"),
        )

        system_prompt = """Given a the text gotten from the screenshot of a user's complaint, try to extract the information from the transcript and return the
        extracted values as a json. Only look for the keys specified. Try as much as possible to get the required information but 
        if it is not available you can set the value to null.

        Return specifically in the JSON format below:
        {
            "_index": "complaint-public-v2",
            "_type": "_doc",
            "_score": null,
            "_source":
            {
                "product": str, 
                "complaint_what_happened": (The user's complaint)
                "date_sent_to_company": str(YYYY-MM-DDT12HH:MM-HH:MM)
                "issue": str, 
                "sub_product": str, 
                "sub_issue": str,
                "zip_code": str,
                "tags": str,
                "complaint_id": str,
                "timely": (Yes/No),
                "consumer_consent_provided": ("Consent provided"/"Consent Not Provided"),
                "company_response": str,
                "submitted_via": str ('web', 'letter', etc),
                "company": str,
                "date_received": str(YYYY-MM-DDT12HH:MM-HH:MM),
                "state": str (NY,SA,etc),
                "consumer_disputed": str,
                "company_public_response": str
            }
        }
        
        """

        chat_completion = groqClient.chat.completions.create(
            messages=[
                {"role": "system", "content": system_prompt},
                {
                    "role": "user",
                    "content": "Categorize this complaint: {0}".format(whole_text),
                },
            ],
            model="llama3-8b-8192",
            response_format={"type": "json_object"},
        )

        return chat_completion.choices[0].message.content

    categorization_template = {
        "_index": "",
        "_type": "",
        "_id": "",
        "_score": None,
        "_source": {
            "product": "",
            "complaint_what_happened": "",
            "date_sent_to_company": "",
            "issue": "",
            "sub_product": "",
            "zip_code": "",
            "tags": None,
            "complaint_id": "",
            "timely": "",
            "consumer_consent_provided": "",
            "company_response": "",
            "submitted_via": "",
            "company": "",
            "date_received": "",
            "state": "",
            "consumer_disputed": "",
            "company_public_response": "",
            "sub_issue": "",
        },
        "sort": [],
    }

    return ""


if __name__ == "__main__":
    app.run(debug=True)
