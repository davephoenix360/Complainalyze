CREATE TABLE complaints (
    _id INTEGER PRIMARY KEY,
    _index TEXT,
    _type TEXT,
    _score FLOAT,
    _source JSON,
    sort INTEGER[]
);