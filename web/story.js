const articlesContainer = document.getElementById('articles');
const clusterId = new URLSearchParams(window.location.search).get('id');
const { element, time, state, entrance, reconcile, poll, updateStatus } = NewsUI;
const reportStatus = updateStatus();
let articleSignature = null;

function translateLabel(value) {
    const labels = {
        unclear: 'غير واضح', independent: 'مستقل', left: 'يسار', center: 'وسط', right: 'يمين',
        progressive: 'تقدمي', conservative: 'محافظ', nationalist: 'قومي', Islamist: 'إسلامي',
        mixed: 'مختلط', high: 'مرتفعة', medium: 'متوسطة', low: 'منخفضة'
    };
    return value === null || value === undefined || value === '' ? 'غير واضح' : labels[value] || String(value);
}
function formatConfidence(value) {
    if (value === null || value === undefined || String(value).trim() === '') return 'غير واضح';
    const number = Number(value);
    if (Number.isFinite(number)) return number >= 0.7 ? 'مرتفعة' : number >= 0.4 ? 'متوسطة' : 'منخفضة';
    return translateLabel(value);
}
function originalURL(value) {
    try {
        const url = new URL(value);
        return ['https:', 'http:'].includes(url.protocol) ? url.href : null;
    } catch (_) { return null; }
}
function renderArticle(article, index) {
    const card = element('article', 'article-card');
    entrance(card, index);
    const source = element('div', 'article-source');
    source.append(element('bdi', '', article.source));
    card.append(source, element('h2', '', article.headline), time(article.date, 'article-date'));
    const orientation = element('section', 'orientation-info');
    const captions = { article: 'تقدير على مستوى المقال', source: 'تقدير على مستوى المصدر', none: 'لا يتوفر تقدير للتوجه' };
    orientation.append(element('p', 'orientation-caption', captions[article.orientation_level] || captions.none));
    const list = element('dl');
    const fields = [
        ['التوجه السياسي', translateLabel(article.political_alignment)],
        ['التوجه الأيديولوجي', translateLabel(article.ideological_tendency)],
        ['درجة الثقة', formatConfidence(article.confidence)]
    ];
    fields.forEach(([label, value]) => {
        const row = element('div', 'orientation-row');
        row.append(element('dt', '', label), element('dd', '', value));
        list.append(row);
    });
    orientation.append(list);
    card.append(orientation);
    const url = originalURL(article.url);
    if (url) {
        const link = element('a', 'original-link', 'فتح المقال الأصلي');
        link.href = url;
        link.target = '_blank';
        link.rel = 'noopener noreferrer';
        link.setAttribute('aria-label', `فتح المقال الأصلي من ${article.source} (في علامة تبويب جديدة)`);
        card.append(link);
    } else card.append(element('p', 'article-date', 'رابط المقال غير متوفر'));
    return card;
}

async function loadTitle(signal) {
    // A failed summary request must not hide successfully loaded articles.
    try {
        const response = await fetch('/stories', { cache: 'no-store', signal });
        if (!response.ok) return;
        const stories = await response.json();
        const story = stories.find(item => item.cluster_id === Number(clusterId));
        if (story) {
            const title = document.getElementById('page-title');
            if (title.textContent !== story.representative_title) title.textContent = story.representative_title;
            document.title = `${story.representative_title} | مقارنة الأخبار العربية`;
        }
    } catch (_) { /* Keep the existing title during transient failures. */ }
}

async function loadStory(signal) {
    const initial = articleSignature === null;
    if (initial) articlesContainer.setAttribute('aria-busy', 'true');
    try {
        const response = await fetch(`/stories/${encodeURIComponent(clusterId)}`, { cache: 'no-store', signal });
        if (response.status === 404) {
            if (initial) state(articlesContainer, 'هذه القصة غير متاحة حاليًا. عد إلى القصص لاختيار قصة أخرى.');
            else reportStatus('هذه القصة غير متاحة للتحديث الآن.');
            return;
        }
        if (!response.ok) throw new Error('Failed to load story');
        const data = await response.json();
        const articles = data.articles.map(article => ({
            article_id: article.article_id, source: article.source, headline: article.headline,
            date: article.date, url: article.url, orientation_level: article.orientation_level,
            political_alignment: article.political_alignment, ideological_tendency: article.ideological_tendency,
            confidence: article.confidence
        }));
        const signature = JSON.stringify(articles);
        if (signature !== articleSignature) {
            if (articles.length) reconcile(articlesContainer, articles, article => article.article_id, renderArticle, initial);
            else state(articlesContainer, 'لا توجد مقالات متاحة لهذه القصة.');
            articleSignature = signature;
        }
        reportStatus('');
        await loadTitle(signal);
    } catch (error) {
        if (signal.aborted && document.hidden) return;
        if (initial) state(articlesContainer, 'تعذّر تحميل المقالات. حاول مرة أخرى.', () => refreshStory());
        else reportStatus('تعذّر التحديث الآن. ستتم إعادة المحاولة تلقائيًا.');
    } finally {
        articlesContainer.setAttribute('aria-busy', 'false');
    }
}
let refreshStory;
if (!clusterId || !/^\d+$/.test(clusterId)) {
    state(articlesContainer, 'لم يتم تحديد قصة صالحة. عد إلى القصص واختر قصة للمقارنة.');
    articlesContainer.setAttribute('aria-busy', 'false');
} else refreshStory = poll(loadStory);
