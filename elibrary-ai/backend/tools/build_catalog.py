import json, re, html
raw = json.load(open("raw.json"))

A = lambda t: set(t.split())
OVERRIDE = {
 "mary-shelley_frankenstein": "Horror & Gothic", "oscar-wilde_the-picture-of-dorian-gray": "Horror & Gothic",
 "robert-louis-stevenson_the-strange-case-of-dr-jekyll-and-mr-hyde": "Horror & Gothic", "henry-james_the-turn-of-the-screw": "Horror & Gothic",
 "edgar-allan-poe_tales-of-mystery-and-imagination": "Horror & Gothic", "edgar-allan-poe_the-narrative-of-arthur-gordon-pym-of-nantucket": "Adventure",
 "oscar-wilde_the-importance-of-being-earnest": "Drama", "oscar-wilde_an-ideal-husband": "Drama", "oscar-wilde_lady-windermeres-fan": "Drama",
 "arthur-conan-doyle_the-lost-world": "Science Fiction & Fantasy", "g-k-chesterton_the-man-who-was-thursday": "Mystery",
 "g-k-chesterton_the-napoleon-of-notting-hill": "Science Fiction & Fantasy", "george-macdonald_phantastes": "Science Fiction & Fantasy",
 "charlotte-perkins-gilman_herland": "Science Fiction & Fantasy", "charlotte-perkins-gilman_the-yellow-wall-paper": "Horror & Gothic",
 "edward-bellamy_looking-backward": "Science Fiction & Fantasy", "voltaire_candide": "Classic Fiction",
 "harriet-beecher-stowe_uncle-toms-cabin": "Classic Fiction", "rudyard-kipling_kim": "Adventure", "rudyard-kipling_captains-courageous": "Adventure",
 "mark-twain_the-innocents-abroad": "History & Biography", "mark-twain_the-adventures-of-tom-sawyer": "Adventure",
 "mark-twain_the-adventures-of-huckleberry-finn": "Adventure", "daniel-defoe_robinson-crusoe": "Adventure", "herman-melville_moby-dick": "Adventure",
 "aristotle_poetics": "Philosophy", "ambrose-bierce_the-devils-dictionary": "Classic Fiction", "walter-scott_ivanhoe": "Adventure", "g-k-chesterton_orthodoxy": "Philosophy",
 "jules-verne_around-the-world-in-eighty-days": "Adventure", "h-rider-haggard_she": "Adventure",
 "l-frank-baum_the-wonderful-wizard-of-oz": "Children's Classics", "lewis-carroll_alices-adventures-in-wonderland": "Children's Classics",
 "nathaniel-hawthorne_the-scarlet-letter": "Classic Fiction", "edgar-allan-poe_the-raven": "Poetry & Epics",
 "jacob-abbott_alexander-the-great": "History & Biography", "william-james_the-varieties-of-religious-experience": "Science",
}
BY_AUTHOR = {
 "Philosophy": A("plato aristotle marcus-aurelius epictetus seneca friedrich-nietzsche immanuel-kant rene-descartes baruch-spinoza david-hume augustine-of-hippo jean-jacques-rousseau thomas-hobbes john-locke henry-david-thoreau thomas-more francis-bacon john-stuart-mill"),
 "Science": A("charles-darwin albert-einstein isaac-newton michael-faraday thomas-henry-huxley alfred-russel-wallace euclid nikola-tesla sigmund-freud"),
 "Business & Politics": A("adam-smith sun-tzu niccolo-machiavelli karl-marx thomas-paine alexis-de-tocqueville thorstein-veblen walter-bagehot thomas-jefferson henry-george"),
 "Education & Society": A("john-dewey w-e-b-du-bois mary-wollstonecraft"),
 "History & Biography": A("herodotus thucydides plutarch benjamin-franklin frederick-douglass booker-t-washington harriet-jacobs"),
 "Poetry & Epics": A("walt-whitman emily-dickinson robert-frost william-butler-yeats t-s-eliot john-keats percy-bysshe-shelley lord-byron william-wordsworth samuel-taylor-coleridge alfred-lord-tennyson rainer-maria-rilke khalil-gibran omar-khayyam beowulf anonymous homer virgil dante-alighieri john-milton geoffrey-chaucer"),
 "Drama": A("william-shakespeare henrik-ibsen sophocles euripides aeschylus aristophanes"),
 "Horror & Gothic": A("bram-stoker h-p-lovecraft arthur-machen robert-w-chambers sheridan-le-fanu ambrose-bierce"),
 "Mystery": A("arthur-conan-doyle wilkie-collins gaston-leroux"),
 "Science Fiction & Fantasy": A("h-g-wells jules-verne edgar-rice-burroughs george-orwell aldous-huxley"),
 "Children's Classics": A("louisa-may-alcott l-frank-baum l-m-montgomery frances-hodgson-burnett j-m-barrie kenneth-grahame johanna-spyri kate-douglas-wiggin jean-webster e-nesbit george-macdonald carlo-collodi edmondo-de-amicis selma-lagerlof lewis-carroll"),
 "Adventure": A("alexandre-dumas robert-louis-stevenson h-rider-haggard rafael-sabatini baroness-orczy anthony-hope jack-london james-fenimore-cooper"),
}
def category(slug, subjects):
    if slug in OVERRIDE: return OVERRIDE[slug]
    author = slug.split("_")[0]
    for cat, names in BY_AUTHOR.items():
        if author in names: return cat
    return "Classic Fiction"

def clean(desc):
    t = re.sub(r"<[^>]+>", " ", desc); t = html.unescape(t); t = re.sub(r"\s+", " ", t).strip()
    if len(t) > 420:
        cut = t[:420]; i = max(cut.rfind(". "), cut.rfind("? "))
        t = cut[:i + 1] if i > 150 else cut.rstrip() + "..."
    return t

books, seen = [], set()
for r in raw:
    key = (r["title"].lower(), r["author"].lower())
    if key in seen: continue
    seen.add(key)
    books.append(dict(title=r["title"], author=r["author"], category=category(r["slug"], r["subjects"]),
                      description=clean(r["description"]), license="Public Domain (Standard Ebooks edition)",
                      download_url="https://standardebooks.org/ebooks/" + r["slug"].replace("_", "/")))
tech = [
 ("Pro Git", "Scott Chacon and Ben Straub", "The official guide to Git version control, from basic commands to internals.", "CC BY-NC-SA 3.0", "https://git-scm.com/book/en/v2"),
 ("Think Python (2nd Edition)", "Allen B. Downey", "An introduction to programming with Python, aimed at beginners.", "CC BY-NC 3.0", "https://greenteapress.com/wp/think-python-2e/"),
 ("Automate the Boring Stuff with Python", "Al Sweigart", "Practical Python programming for office workers and beginners.", "CC BY-NC-SA 3.0", "https://automatetheboringstuff.com/"),
 ("Eloquent JavaScript (4th Edition)", "Marijn Haverbeke", "A modern introduction to JavaScript and programming in general.", "CC BY-NC 3.0", "https://eloquentjavascript.net/"),
]
for t, a, d, l, u in tech:
    books.append(dict(title=t, author=a, category="Technology", description=d, license=l, download_url=u))
books.sort(key=lambda b: (b["category"], b["title"]))
json.dump(books, open("catalog.json", "w"), indent=1, ensure_ascii=False)
import collections
print(len(books), "books")
for c, n in collections.Counter(b["category"] for b in books).most_common(): print(f"{n:4d} {c}")
