import psycopg2
from config import config
import json

def connect():
    connection = None
    try:
        params = config()
        print("Connecting to database")
        connection = psycopg2.connect(**params)
        
        #Create cursor
        crsr = connection.cursor()
        print("version:")
        crsr.execute('SELECT version()')
        db_version = crsr.fetchone()
        print(db_version)
        null = None
        # Insert data into the database
        # Read the JSON data from the file
        with open('complaints-2024-08-15_20_15.json', 'r') as file:
            data = json.load(file)
        
        # Insert data into the 'complaints' table
        for item in data:
            crsr.execute("""
                INSERT INTO complaints (_index, _type, _id, _score, _source, sort)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (
                item["_index"],
                item["_type"],
                item["_id"],
                item["_score"],
                json.dumps(item["_source"]),
                item["sort"]
            ))
        
        connection.commit()
        print("Data inserted successfully")
        
        crsr.close()
    except(Exception, psycopg2.DatabaseError) as error:
        print(error)
    finally:
        if connection is not None:
            connection.close()
            print("Database conn terminated")
            
if __name__ == "__main__":
    connect()