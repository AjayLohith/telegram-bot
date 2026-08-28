from app.news.deduplication import are_headlines_duplicate, deduplicate_articles, normalize_headline


def test_normalize_headline():
    assert normalize_headline("OpenAI Announces GPT-5: A New Era!") == "openai announces gpt 5 a new era"
    assert normalize_headline("ISRO Launches Chandrayaan-4 Mission...") == "isro launches chandrayaan 4 mission"


def test_are_headlines_duplicate():
    t1 = "OpenAI launches new GPT-5 frontier AI model today"
    t2 = "OpenAI launches new GPT-5 frontier model today"
    assert are_headlines_duplicate(t1, t2) is True

    t3 = "Google DeepMind reveals major breakthrough in quantum computing"
    assert are_headlines_duplicate(t1, t3) is False


def test_deduplicate_articles_list():
    articles = [
        {"title": "ISRO successfully launches new earth observation satellite - The Hindu", "url": "http://a.com"},
        {"title": "ISRO successfully launches new earth observation satellite - Indian Express", "url": "http://b.com"},
        {"title": "Anime studio MAPPA reveals new original series trailer", "url": "http://c.com"},
    ]
    deduped = deduplicate_articles(articles)
    assert len(deduped) == 2
    assert deduped[0]["url"] == "http://a.com"
    assert deduped[1]["url"] == "http://c.com"
