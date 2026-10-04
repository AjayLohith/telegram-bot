from dataclasses import dataclass


@dataclass(frozen=True)
class SourceDefinition:
    name: str
    url: str
    tier: int  # 1: Primary/Official, 2: High-Quality Journalism, 3: Specialist
    category: str


CATEGORY_SOURCES: dict[str, list[SourceDefinition]] = {
    "ai": [
        SourceDefinition("Google AI Blog", "https://blog.google/technology/ai/rss/", 1, "ai"),
        SourceDefinition("OpenAI Blog", "https://openai.com/blog/rss/", 1, "ai"),
        SourceDefinition("DeepMind", "https://www.deepmind.com/blog/rss.xml", 1, "ai"),
        SourceDefinition("Microsoft Research", "https://www.microsoft.com/en-us/research/feed/", 1, "ai"),
        SourceDefinition("AI Safety & Misuse News", "https://news.google.com/rss/search?q=%22AI+misuse%22+OR+%22deepfake%22+OR+%22AI+safety%22+OR+%22AI+scam%22+OR+%22Generative+AI%22&hl=en-IN&gl=IN&ceid=IN:en", 2, "ai"),
        SourceDefinition("Viral AI Tech & Tools", "https://news.google.com/rss/search?q=%22artificial+intelligence%22+OR+%22viral+AI%22+OR+ChatGPT+OR+%22Claude+AI%22&hl=en-IN&gl=IN&ceid=IN:en", 3, "ai"),
    ],
    "world": [
        SourceDefinition("BBC World", "https://feeds.bbci.co.uk/news/world/rss.xml", 2, "world"),
        SourceDefinition("The Hindu World", "https://www.thehindu.com/news/international/feeder/default.rss", 2, "world"),
        SourceDefinition("Nature Climate & Earth", "https://news.google.com/rss/search?q=%22geography%22+OR+%22climate+change%22+OR+%22natural+phenomenon%22+OR+%22geopolitics%22&hl=en-IN&gl=IN&ceid=IN:en", 2, "world"),
        SourceDefinition("World Geography & Borders", "https://news.google.com/rss/search?q=%22international+borders%22+OR+%22geospatial%22+OR+%22seismic%22+OR+%22environment%22&hl=en-IN&gl=IN&ceid=IN:en", 3, "world"),
    ],
    "cinema": [
        SourceDefinition("Telugu Cinema Buzz & Tollywood", "https://news.google.com/rss/search?q=Tollywood+OR+%22Telugu+movie%22+OR+%22Telugu+cinema%22+OR+%22Tollywood+buzz%22&hl=en-IN&gl=IN&ceid=IN:en", 2, "cinema"),
        SourceDefinition("Upcoming Telugu & Indian Releases", "https://news.google.com/rss/search?q=%22Telugu+movie+release%22+OR+%22Tollywood+box+office%22+OR+%22Telugu+teaser%22+OR+%22Telugu+trailer%22&hl=en-IN&gl=IN&ceid=IN:en", 2, "cinema"),
        SourceDefinition("Indian Movies & Box Office", "https://news.google.com/rss/search?q=%22Indian+cinema%22+OR+%22Indian+movies%22+OR+%22box+office%22+movie+India&hl=en-IN&gl=IN&ceid=IN:en", 2, "cinema"),
        SourceDefinition("Movie Industry Buzz", "https://news.google.com/rss/search?q=%22movie+industry%22+OR+%22film+industry%22+Tollywood+OR+Indian+cinema&hl=en-IN&gl=IN&ceid=IN:en", 3, "cinema"),
    ],
    "telugu": [
        SourceDefinition("The Hindu Andhra Pradesh", "https://www.thehindu.com/news/national/andhra-pradesh/feeder/default.rss", 2, "telugu"),
        SourceDefinition("Eenadu AP State News", "https://news.google.com/rss/search?q=%22Andhra+Pradesh%22+Amaravati+OR+Visakhapatnam+OR+Polavaram+OR+%22AP+government%22&hl=en-IN&gl=IN&ceid=IN:en", 2, "telugu"),
        SourceDefinition("AP Regional Developments", "https://news.google.com/rss/search?q=%22Andhra+Pradesh+news%22+OR+%22AP+Cabinet%22+OR+%22AP+Assembly%22+OR+%22Andhra+development%22&hl=en-IN&gl=IN&ceid=IN:en", 2, "telugu"),
        SourceDefinition("AP Welfare & State Infrastructure", "https://news.google.com/rss/search?q=%22Andhra+Pradesh%22+schemes+OR+infrastructure+OR+welfare+AP&hl=en-IN&gl=IN&ceid=IN:en", 3, "telugu"),
    ],
    "india": [
        SourceDefinition("The Hindu National", "https://www.thehindu.com/news/national/feeder/default.rss", 2, "india"),
        SourceDefinition("Indian Express National", "https://news.google.com/rss/search?q=%22Indian+Express%22+India+news+OR+ISRO+OR+economy&hl=en-IN&gl=IN&ceid=IN:en", 2, "india"),
        SourceDefinition("India Science & Tech", "https://news.google.com/rss/search?q=ISRO+OR+%22India+economy%22+OR+%22government+policy%22+India&hl=en-IN&gl=IN&ceid=IN:en", 2, "india"),
        SourceDefinition("PIB & National Developments", "https://news.google.com/rss/search?q=%22national+news%22+India+technology+OR+infrastructure&hl=en-IN&gl=IN&ceid=IN:en", 3, "india"),
    ],
}

CATEGORY_DISPLAY_NAMES: dict[str, str] = {
    "ai": "🤖 AI & VIRAL TECH NEWS",
    "world": "🌍 GEOGRAPHY / WORLD NEWS",
    "cinema": "🎬 CINEMA & MOVIE BUZZ",
    "telugu": "🟡 ANDHRA PRADESH STATE NEWS (ఆంధ్రప్రదేశ్)",
    "india": "🇮🇳 INDIA NATIONAL NEWS",
}

CATEGORY_SHORT_LABELS: dict[str, str] = {
    "ai": "🤖 AI",
    "world": "🌍 World",
    "cinema": "🎬 Cinema",
    "telugu": "🟡 AP State (తెలుగు)",
    "india": "🇮🇳 India",
}
