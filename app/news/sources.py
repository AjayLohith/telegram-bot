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
        SourceDefinition("MIT Technology Review AI", "https://news.google.com/rss/search?q=%22MIT+Technology+Review%22+AI+OR+LLM&hl=en-IN&gl=IN&ceid=IN:en", 2, "ai"),
        SourceDefinition("Hacker News AI", "https://news.google.com/rss/search?q=AI+OR+LLM+OR+%22Generative+AI%22+OR+%22machine+learning%22&hl=en-IN&gl=IN&ceid=IN:en", 3, "ai"),
    ],
    "world": [
        SourceDefinition("BBC World", "https://feeds.bbci.co.uk/news/world/rss.xml", 2, "world"),
        SourceDefinition("The Hindu World", "https://www.thehindu.com/news/international/feeder/default.rss", 2, "world"),
        SourceDefinition("Nature Climate & Earth", "https://news.google.com/rss/search?q=%22geography%22+OR+%22climate+change%22+OR+%22natural+phenomenon%22+OR+%22geopolitics%22&hl=en-IN&gl=IN&ceid=IN:en", 2, "world"),
        SourceDefinition("World Geography & Borders", "https://news.google.com/rss/search?q=%22international+borders%22+OR+%22geospatial%22+OR+%22seismic%22+OR+%22environment%22&hl=en-IN&gl=IN&ceid=IN:en", 3, "world"),
    ],
    "anime": [
        SourceDefinition("Anime News Network", "https://www.animenewsnetwork.com/newsfeed.xml", 2, "anime"),
        SourceDefinition("Crunchyroll News", "https://news.google.com/rss/search?q=%22Crunchyroll+News%22+OR+%22Anime+News+Network%22+anime+announcement&hl=en-IN&gl=IN&ceid=IN:en", 2, "anime"),
        SourceDefinition("Anime Official Releases", "https://news.google.com/rss/search?q=anime+announcement+OR+%22new+season%22+OR+%22release+date%22+OR+%22trailer%22+anime&hl=en-IN&gl=IN&ceid=IN:en", 3, "anime"),
    ],
    "telugu": [
        SourceDefinition("The Hindu Andhra Pradesh", "https://www.thehindu.com/news/national/andhra-pradesh/feeder/default.rss", 2, "telugu"),
        SourceDefinition("The Hindu Telangana", "https://www.thehindu.com/news/national/telangana/feeder/default.rss", 2, "telugu"),
        SourceDefinition("Deccan Chronicle AP/Telangana", "https://news.google.com/rss/search?q=%22Andhra+Pradesh%22+OR+%22Telangana%22+news&hl=en-IN&gl=IN&ceid=IN:en", 2, "telugu"),
        SourceDefinition("Telugu Regional & Cinema", "https://news.google.com/rss/search?q=Tollywood+OR+%22Telugu+cinema%22+OR+%22Andhra+development%22&hl=en-IN&gl=IN&ceid=IN:en", 3, "telugu"),
    ],
    "india": [
        SourceDefinition("The Hindu National", "https://www.thehindu.com/news/national/feeder/default.rss", 2, "india"),
        SourceDefinition("Indian Express National", "https://news.google.com/rss/search?q=%22Indian+Express%22+India+news+OR+ISRO+OR+economy&hl=en-IN&gl=IN&ceid=IN:en", 2, "india"),
        SourceDefinition("India Science & Tech", "https://news.google.com/rss/search?q=ISRO+OR+%22India+economy%22+OR+%22government+policy%22+India&hl=en-IN&gl=IN&ceid=IN:en", 2, "india"),
        SourceDefinition("PIB & National Developments", "https://news.google.com/rss/search?q=%22national+news%22+India+technology+OR+infrastructure&hl=en-IN&gl=IN&ceid=IN:en", 3, "india"),
    ],
}

CATEGORY_DISPLAY_NAMES: dict[str, str] = {
    "ai": "🤖 AI NEWS",
    "world": "🌍 GEOGRAPHY / WORLD NEWS",
    "anime": "🍥 ANIME NEWS",
    "telugu": "🟡 TELUGU NEWS",
    "india": "🇮🇳 INDIA NEWS",
}

CATEGORY_SHORT_LABELS: dict[str, str] = {
    "ai": "🤖 AI",
    "world": "🌍 Geography/World",
    "anime": "🍥 Anime",
    "telugu": "🟡 Telugu",
    "india": "🇮🇳 India",
}
