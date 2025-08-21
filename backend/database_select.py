# backend/database_select.py

def resolve_db_from_request(request) -> str:
    db = (request.args.get("db") or request.headers.get("X-DB") or "PG").upper()
    return "MONGO" if db == "MONGO" else "PG"

# Default'umuz PG, kullanıcı seçerse MONGO.