import sqlite3

DATABASE_PATH = "data/articles.db"

connection = sqlite3.connect(DATABASE_PATH)
cursor = connection.cursor()

# Article-level orientation results for 20 selected Arabic articles.
# The analysis is based only on the article text.
# If there is not enough evidence for a clear ideological orientation,
# the result is marked as "unclear".

orientation_results = [
    (
        1,
        "unclear",
        "unclear",
        "unclear",
        0.30,
        "The article mainly reports military developments and humanitarian effects. There is not enough evidence to assign a clear political or ideological orientation.",
        "llm_article_analysis"
    ),
    (
        3,
        "unclear",
        "unclear",
        "unclear",
        0.25,
        "The article reports statements and developments related to Gaza, Hamas, Israel, and US mediation without enough evidence for a specific ideological orientation.",
        "llm_article_analysis"
    ),
    (
        10,
        "unclear",
        "unclear",
        "unclear",
        0.45,
        "The article contains criticism of Reform UK and summarizes analyses from several newspapers, but criticism of one political party is not enough to determine the article's ideology.",
        "llm_article_analysis"
    ),
    (
        43,
        "unclear",
        "unclear",
        "unclear",
        0.30,
        "The article reports a legal dispute over mail voting and presents the administration's position and the court decision without a clear ideological position of its own.",
        "llm_article_analysis"
    ),
    (
        54,
        "unclear",
        "unclear",
        "unclear",
        0.20,
        "The article presents both Turkish and Greek positions in a geopolitical dispute. There is not enough evidence for a specific ideological orientation.",
        "llm_article_analysis"
    ),
    (
        55,
        "unclear",
        "unclear",
        "unclear",
        0.35,
        "The article focuses on the arrest of a journalist and reports criticism from press and human-rights organizations together with the authorities' position. This is not enough to assign a specific ideology.",
        "llm_article_analysis"
    ),
    (
        56,
        "unclear",
        "unclear",
        "unclear",
        0.40,
        "The article critically examines a US military strategy toward Iran and discusses its possible consequences, but the criticism does not clearly establish a left, center, or right ideological position.",
        "llm_article_analysis"
    ),
    (
        58,
        "unclear",
        "unclear",
        "unclear",
        0.15,
        "The collected article body is very limited and mainly contains a live-news introduction, so there is not enough text for a reliable ideological classification.",
        "llm_article_analysis"
    ),
    (
        59,
        "unclear",
        "unclear",
        "unclear",
        0.40,
        "The article presents competing Palestinian positions about the electoral process and includes arguments from both supporters and critics. No clear article-level ideology can be identified.",
        "llm_article_analysis"
    ),
    (
        61,
        "unclear",
        "unclear",
        "unclear",
        0.40,
        "The article analyzes the Republican midterm campaign and discusses both party strategy and political difficulties. The analysis does not provide enough evidence for a specific ideology of the article itself.",
        "llm_article_analysis"
    ),
    (
        62,
        "unclear",
        "unclear",
        "unclear",
        0.30,
        "The article reports the Iraqi government's difficulties in disarming Iran-aligned armed groups and describes several political positions without expressing a clear ideological orientation.",
        "llm_article_analysis"
    ),
    (
        67,
        "unclear",
        "unclear",
        "unclear",
        0.35,
        "The article reports Israeli statements and Syrian objections concerning military activity in Syrian territory. Its framing is critical in places, but this is not enough to assign a specific left-right ideology.",
        "llm_article_analysis"
    ),
    (
        68,
        "unclear",
        "unclear",
        "unclear",
        0.25,
        "The article reports diplomatic and military developments involving Saudi Arabia, Pakistan, Iran, and the Houthis. It does not provide enough evidence for a specific ideological classification.",
        "llm_article_analysis"
    ),
    (
        74,
        "unclear",
        "unclear",
        "unclear",
        0.25,
        "The article summarizes a discussion about disagreements over Palestinian electoral mechanisms and identifies the participants and questions discussed without establishing a clear ideological position.",
        "llm_article_analysis"
    ),
    (
        75,
        "unclear",
        "unclear",
        "unclear",
        0.15,
        "The article is a short factual report about parties and lists registered for an Israeli election. There is too little evidence to identify an ideological orientation.",
        "llm_article_analysis"
    ),
    (
        87,
        "unclear",
        "unclear",
        "unclear",
        0.45,
        "The article focuses on migrants' concerns after an election result and includes personal experiences and different views. The subject matter alone is not enough to classify the article ideologically.",
        "llm_article_analysis"
    ),
    (
        92,
        "unclear",
        "unclear",
        "unclear",
        0.35,
        "The article discusses reported warnings before the October 7 attack and the actions of political leaders, but there is not enough evidence to assign the article a specific ideological orientation.",
        "llm_article_analysis"
    ),
    (
        96,
        "unclear",
        "unclear",
        "unclear",
        0.30,
        "The article reports political developments involving Merz, Trump, and AfD. Reporting criticism or support involving political actors does not by itself establish the article's ideology.",
        "llm_article_analysis"
    ),
    (
        100,
        "unclear",
        "unclear",
        "unclear",
        0.40,
        "The article analyzes factors connected to AfD's electoral success, but explaining the success of a political party does not mean that the article shares that party's ideology.",
        "llm_article_analysis"
    ),
    (
        103,
        "unclear",
        "unclear",
        "unclear",
        0.35,
        "The article discusses reactions to AfD's election result and political responses to it. The text does not provide enough evidence to assign the article itself a specific ideology.",
        "llm_article_analysis"
    )
]

for result in orientation_results:
    cursor.execute("""
        INSERT OR REPLACE INTO article_orientation (
            article_id,
            political_alignment,
            ideological_tendency,
            confidence,
            short_reason
        )
        VALUES (?, ?, ?, ?, ?)
    """, (
        result[0],  # article_id
        result[1],  # political_alignment
        result[2],  # ideological_tendency
        result[4],  # confidence
        result[5]   # short_reason
    ))

connection.commit()
connection.close()

print(f"Saved {len(orientation_results)} article orientation results.")