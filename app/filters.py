KEYWORDS_SLOVENIA = [
    "slovenija", "slovenia", "ljubljana", "maribor", "celje",
    "koper", "kranj", "novo mesto", "ptuj", "nova gorica",
    "velenje", "domžale", "domzale", "kamnik", "izola", "piran",
    "sloveni", "držav", "drzav", "občina", "obcina", "vlada",
    "ministrstvo", "policija", "promet", "sodišče", "sodisce"
]

URL_HINTS = [
    "/novice/slovenija/",
    "/slovenija/",
    "/ljubljana/",
    "/maribor/",
    "/celje/",
    "/koper/",
    "/kranj/",
    "/novo-mesto/",
    "/ptuj/",
    "/nova-gorica/",
    "/gospodarstvo/",
    "/druzba/",
    "/kronika/",
    "/lokalno/",
]

EXCLUDE_HINTS = [
    "/sport/",
    "/sportklub.",
    "/magazin/",
    "/zdravje/",
    "/avtomoto/",
    "/kosarka/",
    "/nogomet/",
    "/zimski-sporti/",
    "/svet/"
]

def probably_about_slovenia(title: str, text: str, url: str = "") -> bool:
    url_l = url.lower()
    blob = f"{title} {text} {url}".lower()

    if any(x in url_l for x in EXCLUDE_HINTS):
        return False

    if any(x in url_l for x in URL_HINTS):
        return True

    return any(word in blob for word in KEYWORDS_SLOVENIA)