import sqlite3

# Connect to database (creates file if not exists)
conn = sqlite3.connect("timetable.db")
cursor = conn.cursor()





# Fetch and display all rows
cursor.execute("PRAGMA table_info(exams)")
columns = [col[1] for col in cursor.fetchall()]

print("Columns:", columns)

conn.close()