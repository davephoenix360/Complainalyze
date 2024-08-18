import psycopg2
from config import config
import json
from elasticsearch import Elasticsearch

client = Elasticsearch(
    cloud_id="5e49e803ee5747a4bfa67e9e9466768a:dXMtY2VudHJhbDEuZ2NwLmNsb3VkLmVzLmlvOjQ0MyRlMzViZWMyOTQyOGE0ZGNmODIyMjk2OTc4YzE0MDJjMCQ3OWRiYzc2N2UxNTQ0OTAwYTEyNzdiMWUzYzRiMmMyYg==",
    api_key="Q25iSVk1RUJPaXhKcFV2ajhMbkI6RG1xS0NpTnRTRVNnWTdxZmEzSUpSQQ==",
)


def load_data_to_es():

    connection = None
    try:
        params = config()
        print("Connecting to database")
        connection = psycopg2.connect(**params)

        # Create cursor
        crsr = connection.cursor()
        crsr.execute("SELECT * FROM complaints")
        res = crsr.fetchall()
        for r in res:
            complaint = r[4]
            client.index(index="complaints", id=r[0], document=complaint)

        crsr.close()
    except Exception as error:
        print(error)
    finally:
        if connection is not None:
            connection.close()
            print("Database conn terminated")


if __name__ == "__main__":
    load_data_to_es()
