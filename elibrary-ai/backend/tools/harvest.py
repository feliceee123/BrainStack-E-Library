import re, json, sys, concurrent.futures as cf, urllib.request, urllib.error, xml.etree.ElementTree as ET
slugs = [l.strip() for l in open("slugs.txt") if l.strip()]
slugs = list(dict.fromkeys(slugs))
NS = {"dc": "http://purl.org/dc/elements/1.1/", "o": "http://www.idpf.org/2007/opf"}
def fetch(slug):
    url = f"https://raw.githubusercontent.com/standardebooks/{slug}/master/src/epub/content.opf"
    try:
        with urllib.request.urlopen(url, timeout=20) as r:
            root = ET.fromstring(r.read())
    except Exception as e:
        return slug, None
    md = root.find("o:metadata", NS)
    g = lambda t: [e.text or "" for e in md.findall(f"dc:{t}", NS)]
    title = (g("title") or [""])[0]
    creators = g("creator")
    desc = (g("description") or [""])[0]
    subjects = g("subject")
    return slug, dict(slug=slug, title=title.strip(), author=", ".join(creators) or "Unknown", description=desc.strip(), subjects=subjects)
out, missing = [], []
with cf.ThreadPoolExecutor(16) as ex:
    for slug, d in ex.map(fetch, slugs):
        (out if d else missing).append(d or slug)
json.dump(out, open("raw.json", "w"), indent=1)
print(len(out), "found;", len(missing), "missing")
open("missing.txt","w").write("\n".join(missing))
