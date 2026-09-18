import sqlite3

DATABASE_PATH = "data/articles.db"

connection = sqlite3.connect(DATABASE_PATH)
cursor = connection.cursor()

source_profiles = [
    (
        "Al Jazeera",
        "unclear",
        "unclear",
        "low",
        "Al Jazeera is partly funded by the Qatari government, but this alone is not enough to assign a clear political or ideological orientation."
    ),
    (
        "DW Arabic",
        "independent",
        "unclear",
        "medium",
        "DW is publicly funded by Germany, but its editorial independence is protected by law. No specific ideological tendency is assigned in this version."
    )
]

cursor.executemany("""
INSERT OR REPLACE INTO source_profiles (
    source_name,
    political_alignment,
    ideological_tendency,
    confidence,
    short_note
)
VALUES (?, ?, ?, ?, ?)
""", source_profiles)

connection.commit()
connection.close()

print("Source profiles saved successfully.")