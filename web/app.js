const storiesContainer = document.getElementById('stories');
const { element, timestamp, time, state, entrance, reconcile, poll, updateStatus } = NewsUI;
const reportStatus = updateStatus();
let storiesSignature = null;

function renderStory(story, index) {
    const card = element('article', 'story-card');
    entrance(card, index);
    const sources = element('div', 'story-sources');
    (story.sources || []).forEach(source => sources.append(element('bdi', 'source-label', source)));
    card.append(sources, element('h2', '', story.representative_title));
    const info = element('div', 'story-info');
    const published = element('div', 'story-published');
    published.append(element('span', '', 'آخر نشر: '), time(story.last_published_at));
    const counts = element('div', 'story-counts');
    counts.append(element('span', '', `المقالات: ${story.article_count}`), element('span', '', `المصادر: ${story.source_count}`));
    info.append(published, counts);
    const link = element('a', 'story-link', 'مقارنة التغطية');
    link.href = `/compare?id=${encodeURIComponent(story.cluster_id)}`;
    link.setAttribute('aria-label', `مقارنة التغطية: ${story.representative_title}`);
    card.append(info, link);
    return card;
}

async function loadStories(signal) {
    const initial = storiesSignature === null;
    if (initial) storiesContainer.setAttribute('aria-busy', 'true');
    try {
        const response = await fetch('/stories', { cache: 'no-store', signal });
        if (!response.ok) throw new Error('Failed to load stories');
        const data = await response.json();
        // Compare only fields visible in the interface; normalize source ordering.
        const stories = data.map(story => ({
            cluster_id: story.cluster_id, representative_title: story.representative_title,
            sources: [...(story.sources || [])].sort(), article_count: story.article_count,
            source_count: story.source_count, last_published_at: story.last_published_at
        }));
        stories.sort((a, b) => {
            const dateA = timestamp(a.last_published_at), dateB = timestamp(b.last_published_at);
            return dateA === dateB ? Number(a.cluster_id) - Number(b.cluster_id) : dateA > dateB ? -1 : 1;
        });
        const signature = JSON.stringify(stories);
        if (signature !== storiesSignature) {
            if (stories.length) reconcile(storiesContainer, stories, story => story.cluster_id, renderStory, initial);
            else state(storiesContainer, 'لا توجد قصص متاحة حاليًا. يمكنك العودة لاحقًا.');
            storiesSignature = signature;
        }
        reportStatus('');
    } catch (error) {
        if (signal.aborted && document.hidden) return;
        if (initial) state(storiesContainer, 'تعذّر تحميل القصص. حاول مرة أخرى.', () => refreshStories());
        else reportStatus('تعذّر التحديث الآن. ستتم إعادة المحاولة تلقائيًا.');
    } finally {
        storiesContainer.setAttribute('aria-busy', 'false');
    }
}
const refreshStories = poll(loadStories);
