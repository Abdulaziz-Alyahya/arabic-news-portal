const articlesContainer = document.getElementById("articles");

const params = new URLSearchParams(window.location.search);
const clusterId = params.get("id");


function translateLabel(value) {

    const labels = {
        "unclear": "غير واضح",
        "independent": "مستقل",
        "left": "يسار",
        "center": "وسط",
        "right": "يمين",
        "progressive": "تقدمي",
        "conservative": "محافظ",
        "nationalist": "قومي",
        "Islamist": "إسلامي",
        "mixed": "مختلط",
        "high": "مرتفعة",
        "medium": "متوسطة",
        "low": "منخفضة"
    };

    return labels[value] || value;
}


function formatConfidence(value) {

    const number = Number(value);

    if (!isNaN(number)) {

        if (number >= 0.7) {
            return "مرتفعة";
        }

        if (number >= 0.4) {
            return "متوسطة";
        }

        return "منخفضة";
    }

    return translateLabel(value);
}


function formatDate(value) {

    if (!value) {
        return "التاريخ غير متوفر";
    }

    const date = new Date(value);

    if (isNaN(date.getTime())) {
        return value;
    }

    return date.toLocaleString("ar", {
        year: "numeric",
        month: "long",
        day: "numeric",
        hour: "numeric",
        minute: "2-digit"
    });
}


async function loadStory() {

    if (!clusterId) {

        articlesContainer.innerHTML = `
            <p>لم يتم تحديد القصة.</p>
        `;

        return;
    }

    try {

        // Get the articles inside this story
        const response = await fetch(
            `/stories/${clusterId}`
        );

        if (!response.ok) {
            throw new Error("Failed to load story");
        }

        const data = await response.json();


        // Get story information to display the story title
        const storiesResponse = await fetch(
            "/stories"
        );

        if (!storiesResponse.ok) {
            throw new Error("Failed to load story information");
        }

        const stories = await storiesResponse.json();

        const currentStory = stories.find(
            story => story.cluster_id === Number(clusterId)
        );

        if (currentStory) {

            const pageTitle =
                document.querySelector(".page-heading h2");

            pageTitle.textContent =
                currentStory.representative_title;
        }


        // Clear loading message
        articlesContainer.innerHTML = "";


        // Display articles
        data.articles.forEach(article => {

            const card = document.createElement("article");
            card.className = "article-card";

            const date = formatDate(article.date);

            const politicalAlignment =
                translateLabel(article.political_alignment);

            const ideologicalTendency =
                translateLabel(article.ideological_tendency);

            const confidence =
                formatConfidence(article.confidence);


            card.innerHTML = `
                <div class="article-source">
                    ${article.source}
                </div>

                <h3>${article.headline}</h3>

                <div class="article-date">
                    ${date}
                </div>

                <div class="orientation-info">

                    <div>
                        <strong>التوجه السياسي:</strong>
                        ${politicalAlignment}
                    </div>

                    <div>
                        <strong>التوجه الأيديولوجي:</strong>
                        ${ideologicalTendency}
                    </div>

                    <div>
                        <strong>درجة الثقة:</strong>
                        ${confidence}
                    </div>

                </div>

                <a
                    class="original-link"
                    href="${article.url}"
                    target="_blank"
                    rel="noopener noreferrer"
                >
                    فتح المقال الأصلي
                </a>
            `;

            articlesContainer.appendChild(card);
        });

    } catch (error) {

        articlesContainer.innerHTML = `
            <p>حدث خطأ أثناء تحميل المقالات.</p>
        `;

        console.error(error);
    }
}


loadStory();