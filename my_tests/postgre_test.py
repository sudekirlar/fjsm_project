import psycopg2

def test_postgres_connection():
    try:
        connection = psycopg2.connect(
            host="localhost",
            port=5432,
            database="fjsm_database",
            user="postgres",
            password="su0180"
        )
        print("Bağlantı başarılı!")
        connection.close()
    except Exception as e:
        print("Bağlantı hatası:", e)

if __name__ == "__main__":
    test_postgres_connection()
