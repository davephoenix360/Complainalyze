from flask import Flask, request, jsonify
from elasticsearch import Elasticsearch, helpers, exceptions
import json
import time
import os
import psycopg2
from config import config
from dotenv import load_dotenv
from groq import Groq

app = Flask(__name__)
load_dotenv()


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
        cursor.execute("SELECT * FROM complaints WHERE _id IN %s", (tuple(related_ids),))
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
            {
                "role": "system",
                "content": system_prompt
            },
            {
                "role": "user",
                "content": 'Categorize this complaint: {0}\nUsing these similar complaints: {1}'.format(user_complaint, related_records_str)
            }
        ],
        model="llama3-8b-8192",
        response_format={"type": "json_object"}
    )

    return chat_completion.choices[0].message.content


if __name__ == "__main__":
    app.run(debug=True)
