from database import get_connection

conn = get_connection()
conn.execute("DELETE FROM resources WHERE resource_code = ''")
conn.commit()
conn.close()
print("Cleaned up blank resource(s).")