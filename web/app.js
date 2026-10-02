const storiesContainer = document.getElementById("stories");


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


async function loadStories() {

    try {

        // The API is served from the same website
        const response = await fetch("/stories");

        if (!response.ok) {
            throw new Error("Failed to load stories");
        }

        const stories = await response.json();

        storiesContainer.innerHTML = "";

        stories.forEach(story => {

            const card = document.createElement("article");
            card.className = "story-card";

            const sources = story.sources
                .map(source => `<span class="source-label">${source}</span>`)
                .join("");

            const date = formatDate(story.last_published_at);

            card.innerHTML = `
                <h3>${story.representative_title}</h3>

                <div class="story-info">
                    <div>عدد المقالات: ${story.article_count}</div>
                    <div>عدد المصادر: ${story.source_count}</div>
                    <div>آخر نشر: ${date}</div>
                </div>

                <div class="story-sources">
                    ${sources}
                </div>

                <a
                    class="story-link"
                    href="/compare?id=${story.cluster_id}"
                >
                    مقارنة التغطية
                </a>
            `;

            storiesContainer.appendChild(card);
        });

    } catch (error) {

        storiesContainer.innerHTML = `
            <p>حدث خطأ أثناء تحميل القصص.</p>
        `;

        console.error(error);
    }
}


loadStories();