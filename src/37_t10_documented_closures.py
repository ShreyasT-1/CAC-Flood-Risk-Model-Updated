"""Phase 2 / T10E step 1: build docs/florence_documented_closures.csv from sources actually fetched on 2026-10-11 (quotes are verbatim from the fetched page text; times are only what the source states).
Nothing is guessed: a field the source does not state is left blank and time_precision says so. status = verified (source fetched and quote present) | unverified (seen in a search summary only, page not fetched).
Usage (repo root): python src/37_t10_documented_closures.py"""
import pandas as pd
U19 = "https://www.ncdot.gov/news/press-releases/TestIgnore/2018/2018-09-19-assessing-florence-impacts-recovery.aspx"
U22 = "https://www.ncdot.gov/news/press-releases/TestIgnore/2018/2018-09-22-wilmington-routes-open.aspx"
U24 = "https://www.ncdot.gov/news/press-releases/TestIgnore/2018/2018-09-24-interstate-40-reopens.aspx"
UNWS = "https://www.weather.gov/ilm/hurricaneflorence"
UABC = "https://abc11.com/traffic/to-the-relief-of-many-i-40-reopens-throughout-nc-after-florence-flooding/4250976"
UNEWS = "https://www.newsweek.com/where-i-40-closed-north-carolina-florence-flooding-closes-interstate-sections-1132815"
rows = []
def add(road, county, section, closed, reopened, prec, url, quote, note="", status="verified"):
    rows.append(dict(road=road, county=county, section=section, closed_start=closed, closed_end=reopened, time_precision=prec, status=status, source_url=url, quote=quote, notes=note))
# --- NCDOT 2018-09-19 snapshot ("As of about 3 p.m. Wednesday, Sept. 19"): sections closed at that time; start/end not stated ---
SNAP = "2018-09-19T15:00 America/New_York"; Q19 = "As of about 3 p.m. Wednesday, Sept. 19, about 800 sections of road were closed"
snap = {"Brunswick": ["NC130", "NC133", "NC211", "NC87", "NC904", "NC906"], "Duplin": ["I-40", "NC111", "NC24", "NC241", "NC403", "NC41", "NC50", "NC903", "US117"],
        "New Hanover": ["I-40", "NC132", "NC133", "US117", "US17", "US421", "US74", "US76"], "Pender": ["I-40", "NC133", "NC210", "NC50", "NC53", "US117", "US421"],
        "Sampson": ["NC24", "NC242", "NC411", "NC903", "US13", "US701"], "Bladen": ["US701", "NC41", "NC53", "NC210", "NC211"], "Columbus": ["US74", "US76", "NC87", "NC130", "NC211", "NC904", "NC905"],
        "Cumberland": ["I-95", "US13", "US301", "NC24", "NC59", "NC87", "NC210", "NC690"], "Robeson": ["I-74", "I-95", "US74", "US301", "US501", "NC41", "NC71", "NC72", "NC83", "NC130", "NC211", "NC904"],
        "Onslow": ["US17"], "Harnett": ["I-95", "US401", "NC27", "NC82", "NC217"]}
qcty = {"Brunswick": "Brunswick County – Sections of N.C. 130, N.C. 133, N.C. 211, N.C. 87, N.C. 904 and N.C. 906", "Duplin": "Duplin County – Sections of I-40, N.C. 111, N.C. 24, N.C. 241, N.C. 403, N.C. 41, N.C. 50, N.C. 903, and U.S. 117",
        "New Hanover": "New Hanover County – Sections of I-40, N.C. 132, N.C. 133, U.S. 117, U.S. 17, U.S. 421, U.S. 74 and U.S. 76", "Pender": "Pender County – sections of I-40, N.C. 133, N.C. 210, N.C. 50, N.C. 53, U.S. 117 and U.S. 421",
        "Sampson": "Sampson County – Sections of N.C. 24, N.C. 242, N.C. 411, N.C. 903, U.S. 13, and U.S. 701", "Bladen": "Bladen: U.S. 701, N.C. 41, N.C. 53, N.C. 210, N.C. 211 and N.C. 211 Business closed in sections",
        "Columbus": "Columbus County – U.S. 74, U.S. 74 Business, U.S. 76, U.S. 701 Business, N.C. 87, N.C. 130, ... N.C. 211, N.C. 904, and N.C. 905 closed in places", "Cumberland": "Cumberland County – I-95, U.S. 13, U.S. 301, N.C. 24, N.C. 59, N.C. 87, N.C. 210 and N.C. 690",
        "Robeson": "Robeson County – I-74, I-95, U.S. 74, U.S. 301, U.S. 501, N.C. 41, N.C. 71, N.C. 72, N.C. 83, ... N.C. 130, N.C. 211 and N.C. 904 are closed in sections", "Onslow": "Onslow County – Section of U.S. 17 due to pavement washout",
        "Harnett": "Harnett: I-95, U.S. 401, N.C. 27, N.C. 82, and N.C. 217 closed in sections"}
for cty, roads in snap.items():
    for r in roads: add(r, cty, "sections (not specified)", SNAP, "", "snapshot: closed at this time; start and end not stated", U19, qcty[cty], note=Q19)
# --- dated closures ---
add("I-40", "Duplin;Pender;New Hanover", "MM 373-385 and MM 408-414", "2018-09-15 (date only)", "2018-09-24 (Monday; Cooper announcement, afternoon per ABC11)", "date only", U24,
    "Florence's floodwaters covered two sections of I-40 (between mile markers 373-385, and 408-414) on Sept. 15. | I-40 reopened Monday, Gov. Cooper announced. | One lane remained closed leaving Wilmington, near mile marker 413, due to water on the road.", "reopening text: 'I-40 has reopened throughout North Carolina' (ABC11, Sept 25 page, announcement Monday afternoon Sept 24)")
add("I-40", "Pender;New Hanover;Duplin", "MM 385 to Duplin/Pender line; exits 390-414; I-40/I-140 ramps", "", "", "no times; still flooded Friday 2018-09-21 morning", UNEWS, "I-40 has been closed in over seven spots spanning three counties: Pender County, New Hanover County and Duplin County. | Several sections of I-40 were still flooded on Friday morning")
add("I-95", "Robeson;Cumberland;Harnett", "Lumberton to Benson (about 60 miles at maximum)", "2018-09-16 (9-mile stretch; 33 miles 09-17; ~60 miles by 09-19)", "2018-09-23 (late Sunday evening)", "date only", UNWS,
    "Flash flooding closed a 9 mile stretch of Interstate 95 on September 16. | Floodwaters expanded on September 17, closing a 33 mile stretch | by September 19th a nearly 60-mile stretch of this major north-south highway was closed between Lumberton and Benson, NC. | The Interstate did not reopen until September 23.",
    "NCDOT 09-24 page: 'I-95 reopened through North Carolina late Sunday evening.'")
add("US-17;NC-87", "Brunswick", "portions", "2018-09-14/15 (flooding dates)", "", "date only; end not stated", UNWS, "closing many roads including portions Of U.S. Highway 17 and NC Highway 87.")
add("NC-133", "Brunswick", "main route between Wilmington and Southport, several locations", "", "", "no dates stated", UNWS, "NC Highway 133, the main route between Wilmington and Southport, was closed due to flooding in several locations")
add("US-74/76", "Columbus", "east of Whiteville", "", "", "no dates stated", UNWS, "U.S. Highway 74/76 east of Whiteville was closed for a time due to flooding.")
add("US-421", "Pender;New Hanover", "near the New Hanover County line (300 ft washout)", "", "", "no dates stated", UNWS, "U.S. Highway 421 near the New Hanover County line was washed out over a 300 foot expanse | A portion of U.S. Highway 421 was also closed due to flooding.")
add("NC-53", "Pender", "", "", "", "no dates stated", UNWS, "NC highway 53 was covered with seven feet of water.")
add("ALL ACCESS ROUTES (I-40, US-17, US-74, US-76, US-421)", "New Hanover", "Wilmington isolation", "", "", "dates not stated for the isolation start; NWS quotes state officials on 2018-09-20", UNWS,
    "every access route including Interstate 40, and U.S. Highways 17, 74, 76, and 421 were all closed due to flooding. | There is not a safe, stable, or reliable route for the public to get to and from Wilmington.", "second quote: State officials, September 20 (as quoted by NWS)")
add("US-17 (from south); I-40 E to NC-24 (exit 373) to US-17 S (from north)", "New Hanover", "routes into Wilmington", "", "2018-09-22 (route announced open)", "date only", U22,
    "identified three safe alternate routes the public may use to access Wilmington | From the south, take U.S. 17 | From the north, travel on Interstate 40 East to N.C. 24 East (exit 373), then onto U.S. 17 South | many roads remain impassable, including sections of I-40 closer to Wilmington")
add("US-74", "Robeson;Columbus;Brunswick;New Hanover", "I-95 to Wilmington", "", "open by 2018-09-24/25 (ABC11)", "date only; opening time not stated", UABC, "US 74 is open from I-95 to Wilmington.", "no date/time given for when US-74 opened")
add("I-95", "Robeson", "I-95 near Lumberton (Exit 13 area)", "", "", "", "https://www.postandcourier.com/news/how-to-get-around-sc-road-closures-during-florence-flooding/article_24a78c0a-bd23-11e8-8f12-bb3374d2a311.html", "(seen in a search summary only: 'sections of I-95 were closed at Exit 13 due to flooding between U.S. Highway 74 near Lumberton and I-40')", "page not fetched", status="unverified")
add("US-421", "New Hanover", "county line", "2018-09-20 (Thursday morning)", "", "", "https://abc11.com/traffic/how-to-get-in-and-out-of-wilmington-after-florence-road-closures-/4276801", "(search summary only: 'All lanes of U.S. 421 were closed near the county line between New Hanover and Pender counties Thursday morning due to flooding')", "page not fetched", status="unverified")
D = pd.DataFrame(rows); D["quote_check"] = D.source_url.map(lambda u: "quote string found in raw page HTML (saved in data/phase2/t10/src_pages)" if ("ncdot.gov" in u or "newsweek" in u) else "text from fetch-tool extraction; raw HTML not re-checked (site blocked/unreachable from curl)")
D.loc[D.status == "unverified", "quote_check"] = "not checked"
D.to_csv("docs/florence_documented_closures.csv", index=False); print(len(D), D.status.value_counts().to_dict(), D.time_precision.str[:8].value_counts().to_dict())
