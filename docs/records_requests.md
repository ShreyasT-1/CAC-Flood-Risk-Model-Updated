# Records requests (drafts, not sent)

Contacts and process were looked up on 2026-10-11. Verify on the agency page before sending; I could not confirm an email address for either agency, so both go through web forms.

## 1. NCDOT: closure/reopening records, Hurricane Florence, Sept-Oct 2018

**How to send:** NCDOT online public-records form, https://www.ncdot.gov/news/public-records/Pages/public-records-request.aspx (status checkable there). Mail alternative: N.C. Department of Transportation, Attn: Public Records Manager (page names Jamie Kritzer or Meredith Vick), 1501 Mail Service Center, Raleigh NC 27699-1501 (the page's contact block says 1503; confirm), phone (919) 707-2663. Per the page: acknowledgement within 3 business days; electronic delivery and review are free; copies 5 cents/page; the manager may ask to clarify and a vague request may be denied. Policy: https://www.ncdot.gov/news/public-records/Documents/public-records-policy.pdf

**Note:** I found no public documentation of a historical TIMS/DriveNC incident archive (DriveNC shows current events; NCDOT GIS publishes a live incident layer). The request therefore asks whether an archive exists and, if so, for it; it also asks for the Traffic Management Center / division logs as fallback.

**Draft text**

> Subject: Public records request: road closure and reopening records, Hurricane Florence (Sept 10 - Oct 31, 2018), Brunswick, New Hanover and Pender Counties
>
> Under N.C. Gen. Stat. Chapter 132, I request, in electronic format, the following records for Brunswick, New Hanover and Pender Counties for 2018-09-10 through 2018-10-31:
> 1. The TIMS / DriveNC incident and road-condition records (closures, reopenings, flooding, detours), including the fields start time, end time/clear time, road/route, location or milepost, county, latitude/longitude if recorded, incident type and cause, and last-updated time. If TIMS does not retain history, please tell me what archive does (Traffic Management Center logs, Division 3 and Division 6 maintenance or emergency-operations logs, or ESRI/GIS snapshots) and provide those instead.
> 2. Any Division 3 / Division 6 or statewide summary or after-action table listing roads closed by flooding during Florence, with closure and reopening times.
> 3. Records for the following routes if available separately: I-40, I-140, US-17, US-74/76, US-117, US-421, NC-11, NC-53, NC-87, NC-133, NC-210, NC-211, NC-906.
>
> I am a student building a flood-awareness tool for the Congressional App Challenge (non-commercial). A CSV, spreadsheet or GIS export is ideal; I do not need personal information. If any part is unavailable or exempt, please release the rest and cite the exemption. Please contact me before incurring any fee above $20.
>
> [Name], [email], [phone], [mailing address]

## 2. NC Emergency Management (NC Dept. of Public Safety) / FEMA Public Assistance: Florence road damage sites

**Try first (no request needed):** FEMA's OpenFEMA dataset *Public Assistance Funded Projects Details* (https://fema.gov/openfema-dataset-public-assistance-funded-projects-details-v1; API `https://www.fema.gov/api/open/v1/PublicAssistanceFundedProjectsDetails`, filter disaster 4393, state NC; verify the live endpoint version). It lists obligated project worksheets by applicant and damage category (C = roads and bridges) but, as far as I could confirm, not site coordinates, hence the request below. Disaster page: fema.gov/disaster/4393 and ncdps.gov/Florence.

**How to send:** NCDPS public-records form (preferred by the agency), https://www.ncdps.gov/public-records-requests ; Emergency Management requests go through the same department process. Mail: NCDPS, 4201 Mail Service Center, Raleigh NC 27699-4201, phone (919) 733-5027 (NCEM main line on its pages: 919-710-8885). Acknowledgement within 3 business days; the agency need not create records that do not exist.

**Draft text**

> Subject: Public records request: FEMA-4393-DR (Hurricane Florence) Public Assistance Category C road and bridge damage sites, Brunswick, New Hanover and Pender Counties
>
> Under N.C. Gen. Stat. Chapter 132, I request, electronically, for FEMA-4393-DR applicants in Brunswick, New Hanover and Pender Counties (including NCDOT Divisions 3 and 6 and the three counties and municipalities):
> 1. The list of Category C (roads, bridges, culverts) damage sites or project worksheet site lists, with site name or road, location (address, coordinates or GIS), damage description, date of damage if recorded, and facility type (bridge, culvert, road).
> 2. Any GIS layer or spreadsheet of damaged-road/damage-site locations compiled for the Florence Public Assistance program.
>
> I am a student building a non-commercial flood-awareness tool (Congressional App Challenge). I do not need financial or personal information; a site list alone is fine. If any part is exempt, please release the rest and cite the exemption.
>
> [Name], [email], [phone], [mailing address]

## What these would and would not give us
Closure/reopen times would allow a real validation test (they would turn positives-only storm reports into dated closure intervals). Damage sites show where roads failed, not when they closed. Neither is available yet; no claim in `docs/claims.md` depends on them.
