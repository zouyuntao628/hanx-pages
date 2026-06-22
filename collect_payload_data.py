#!/usr/bin/env python3
from __future__ import annotations

import csv
import hashlib
import html
import json
import re
import time
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode, quote
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / 'data'
DATA_DIR.mkdir(exist_ok=True)
CURRENT_YEAR = datetime.now(timezone.utc).year

PAYLOADS = [
    {
        'payload_id': 'dxd',
        'name': 'DXd',
        'display_name': 'DXd / deruxtecan',
        'aliases': ['DXd', 'deruxtecan', 'trastuzumab deruxtecan', 'datopotamab deruxtecan', 'patritumab deruxtecan', 'Dato-DXd', 'HER3-DXd'],
        'negative_aliases': [],
        'mechanism': 'TOP1 inhibitor',
        'payload_family': 'topoisomerase I inhibitor',
        'representative_adcs': ['trastuzumab deruxtecan', 'datopotamab deruxtecan', 'patritumab deruxtecan'],
    },
    {
        'payload_id': 'exatecan',
        'name': 'exatecan',
        'display_name': 'exatecan 类 payload',
        'aliases': ['exatecan', 'DX-8951', 'DX-8951f', 'exatecan mesylate'],
        'negative_aliases': [],
        'mechanism': 'TOP1 inhibitor',
        'payload_family': 'topoisomerase I inhibitor',
        'representative_adcs': ['M7437', 'CBX-12', 'ELU001'],
    },
    {
        'payload_id': 'sn38',
        'name': 'SN-38',
        'display_name': 'SN-38 / govitecan 类',
        'aliases': ['SN-38', 'SN38', 'govitecan', 'sacituzumab govitecan', 'irinotecan metabolite'],
        'negative_aliases': [],
        'mechanism': 'TOP1 inhibitor',
        'payload_family': 'topoisomerase I inhibitor',
        'representative_adcs': ['sacituzumab govitecan'],
    },
    {
        'payload_id': 'mmae',
        'name': 'MMAE',
        'display_name': 'MMAE / vedotin 类',
        'aliases': ['MMAE', 'monomethyl auristatin E', 'vedotin', 'brentuximab vedotin', 'enfortumab vedotin', 'polatuzumab vedotin'],
        'negative_aliases': [],
        'mechanism': 'microtubule inhibitor',
        'payload_family': 'auristatin microtubule inhibitor',
        'representative_adcs': ['brentuximab vedotin', 'enfortumab vedotin', 'polatuzumab vedotin'],
    },
    {
        'payload_id': 'mmaf',
        'name': 'MMAF',
        'display_name': 'MMAF / mafodotin 类',
        'aliases': ['MMAF', 'monomethyl auristatin F', 'mafodotin', 'belantamab mafodotin'],
        'negative_aliases': [],
        'mechanism': 'microtubule inhibitor',
        'payload_family': 'auristatin microtubule inhibitor',
        'representative_adcs': ['belantamab mafodotin'],
    },
    {
        'payload_id': 'dm1',
        'name': 'DM1',
        'display_name': 'DM1 / emtansine 类',
        'aliases': ['DM1', 'emtansine', 'maytansinoid DM1', 'trastuzumab emtansine', 'T-DM1'],
        'negative_aliases': ['myotonic dystrophy type 1'],
        'mechanism': 'microtubule inhibitor',
        'payload_family': 'maytansinoid microtubule inhibitor',
        'representative_adcs': ['trastuzumab emtansine'],
    },
    {
        'payload_id': 'dm4',
        'name': 'DM4',
        'display_name': 'DM4 / ravtansine 类',
        'aliases': ['DM4', 'ravtansine', 'maytansinoid DM4', 'mirvetuximab soravtansine', 'soravtansine'],
        'negative_aliases': [],
        'mechanism': 'microtubule inhibitor',
        'payload_family': 'maytansinoid microtubule inhibitor',
        'representative_adcs': ['mirvetuximab soravtansine'],
    },
    {
        'payload_id': 'pbd',
        'name': 'PBD',
        'display_name': 'PBD / pyrrolobenzodiazepine 类',
        'aliases': ['pyrrolobenzodiazepine', 'PBD dimer', 'tesirine', 'loncastuximab tesirine', 'camidanlumab tesirine'],
        'negative_aliases': ['peroxisome biogenesis disorder', 'preoperative biliary drainage', 'pre-operative biliary drainage'],
        'mechanism': 'DNA crosslinking',
        'payload_family': 'DNA crosslinking agent',
        'representative_adcs': ['loncastuximab tesirine', 'camidanlumab tesirine'],
    },
    {
        'payload_id': 'amanitin',
        'name': 'amanitin',
        'display_name': 'amanitin / alpha-amanitin 类',
        'aliases': ['amanitin', 'alpha-amanitin', 'α-amanitin', 'amanitin ADC'],
        'negative_aliases': ['mushroom poisoning', 'Amanita phalloides poisoning'],
        'mechanism': 'RNA polymerase II inhibitor',
        'payload_family': 'RNA polymerase inhibitor',
        'representative_adcs': ['HDPl-101'],
    },
]

HEADERS = {'User-Agent': 'HANX-Payload-Evidence-Library/1.1 (public metadata research prototype; contact: no-reply@example.com)'}
SOURCE_POLICY = {
    'copyright_boundary': '只保存公开元数据、允许的摘要/片段、URL 和来源归属；不保存受版权保护的论文全文、新闻全文或付费数据库正文。',
    'review_boundary': '自动采集证据仅作为情报索引，必须经过人工科学/IP 审核后才能用于项目决策。',
    'patent_boundary': '专利记录只作为检索线索，不构成 FTO、可专利性或法律意见。',
}

CONTEXT_TERMS = [
    'antibody-drug conjugate', 'antibody drug conjugate', 'ADC', 'payload', 'linker', 'cancer', 'tumor',
    'oncology', 'solid tumor', 'breast cancer', 'clinical trial', 'HER2', 'TROP2', 'FRα', 'FRa', 'B7-H3'
]
COMBINATION_TERMS = ['combination', 'synergy', 'DDR', 'PARP', 'ATR', 'WEE1', 'checkpoint', 'resistance', '耐药', '联用']
RISK_TERMS = ['toxicity', 'toxic', 'DLT', 'adverse event', 'neutropenia', 'thrombocytopenia', 'ILD', 'pneumonitis', 'safety']


def fetch_json(url: str, timeout: int = 30) -> dict:
    with urlopen(Request(url, headers=HEADERS), timeout=timeout) as r:
        return json.loads(r.read().decode('utf-8', 'ignore'))


def fetch_text(url: str, timeout: int = 30) -> str:
    with urlopen(Request(url, headers=HEADERS), timeout=timeout) as r:
        return r.read().decode('utf-8', 'ignore')


def text_norm(value: str | None) -> str:
    value = value or ''
    return re.sub(r'\s+', ' ', html.unescape(str(value))).strip()


def slug_text(value: str) -> str:
    return re.sub(r'[^a-z0-9]+', ' ', (value or '').lower()).strip()


def clean_year(date_value: str | int | None) -> int | None:
    if not date_value:
        return None
    match = re.search(r'(19\d{2}|20\d{2}|21\d{2})', str(date_value))
    if not match:
        return None
    year = int(match.group(1))
    if year < 1990 or year > CURRENT_YEAR + 1:
        return year
    return year


def canonical_date(date_value: str | None) -> str:
    value = text_norm(date_value)
    if not value:
        return ''
    match = re.search(r'(19\d{2}|20\d{2}|21\d{2})(?:[-/ ](\d{1,2}))?(?:[-/ ](\d{1,2}))?', value)
    if not match:
        return value[:40]
    year = int(match.group(1))
    month = int(match.group(2) or 1)
    day = int(match.group(3) or 1)
    if not 1 <= month <= 12:
        month = 1
    if not 1 <= day <= 31:
        day = 1
    return f'{year:04d}-{month:02d}-{day:02d}'


def source_search_query(payload: dict, extra: str = '') -> str:
    aliases = ' OR '.join(f'"{a}"' for a in payload['aliases'][:5])
    context = ' OR '.join(f'"{t}"' if ' ' in t else t for t in CONTEXT_TERMS[:8])
    return f'({aliases}) AND ({context}) {extra}'.strip()


def make_record_id(source: str, payload_id: str, *parts: str) -> str:
    raw = '|'.join([source, payload_id, *[p or '' for p in parts]])
    digest = hashlib.sha1(raw.encode('utf-8', 'ignore')).hexdigest()[:14]
    return f'{source.lower().replace(".", "").replace(" ", "-")}-{payload_id}-{digest}'


def classify_and_score(payload: dict, title: str, snippet: str, source_family: str, source: str, date: str, url: str) -> tuple[dict, dict, dict]:
    text = slug_text(f'{title} {snippet}')
    flags: list[str] = []
    alias_hits = [a for a in payload['aliases'] if slug_text(a) and slug_text(a) in text]
    negative_hits = [a for a in payload.get('negative_aliases', []) if slug_text(a) and slug_text(a) in text]
    context_hits = [t for t in CONTEXT_TERMS if slug_text(t) and slug_text(t) in text]
    combination_hits = [t for t in COMBINATION_TERMS if slug_text(t) and slug_text(t) in text]
    risk_hits = [t for t in RISK_TERMS if slug_text(t) and slug_text(t) in text]
    year = clean_year(date)

    if negative_hits:
        flags.append('negative_alias_match')
    if not title:
        flags.append('missing_title')
    if not url:
        flags.append('missing_url')
    if year and (year < 1990 or year > CURRENT_YEAR + 1):
        flags.append('future_or_bad_date_suspicious')
    if source == 'Crossref' and not alias_hits:
        flags.append('crossref_low_relevance')
    if source_family == 'patent':
        flags.append('patent_needs_ip_review')
    if source_family == 'news':
        flags.append('news_metadata_only')

    if negative_hits:
        relevance = 'flagged_irrelevant'
    elif alias_hits and context_hits:
        relevance = 'direct'
    elif alias_hits:
        relevance = 'adjacent'
    elif context_hits and payload['payload_id'] in {'dxd', 'pbd', 'dm1', 'dm4'}:
        relevance = 'weak'
    else:
        relevance = 'weak'

    base_by_source = {'paper': 72, 'clinical_trial': 84, 'patent': 70, 'news': 56, 'paper_metadata': 46}
    relevance_bonus = {'direct': 18, 'adjacent': 8, 'weak': -10, 'flagged_irrelevant': -55}[relevance]
    recency = 0
    if year and 1990 <= year <= CURRENT_YEAR + 1:
        recency = max(0, min(18, (year - (CURRENT_YEAR - 8)) * 2))
    penalty = 0
    if 'future_or_bad_date_suspicious' in flags:
        penalty += 35
    if 'crossref_low_relevance' in flags:
        penalty += 18
    if 'missing_url' in flags:
        penalty += 8
    score = max(0, min(100, base_by_source.get(source_family, 50) + relevance_bonus + recency + min(8, len(combination_hits) * 3) - penalty))

    classification = {
        'topic_tags': sorted(set(alias_hits[:4] + context_hits[:5] + combination_hits[:4] + risk_hits[:4])),
        'evidence_class': 'safety_signal' if risk_hits else 'combination_signal' if combination_hits else source_family,
        'use_case': ['opportunity_radar'] + (['safety_review'] if risk_hits else []) + (['combination_recommendation'] if combination_hits else []),
        'payload_relevance': relevance,
        'decision_relevance': 'high' if score >= 80 else 'medium' if score >= 55 else 'low',
    }
    scores = {
        'relevance_score': score,
        'recency_score': recency,
        'source_weight': base_by_source.get(source_family, 50),
        'evidence_strength': max(0, min(100, score - (15 if flags else 0))),
    }
    quality = {
        'status': 'flagged_needs_review' if flags else 'auto_parsed_pending_review',
        'needs_scientific_review': True,
        'needs_ip_review': source_family == 'patent',
        'flags': flags,
    }
    return classification, scores, quality


def make_record(payload: dict, *, source: str, source_family: str, evidence_type: str, title: str, url: str = '', date: str = '', snippet: str = '', doi: str = '', pmid: str = '', nct_id: str = '', patent_id: str = '', journal_or_source: str = '', authors_or_assignee=None) -> dict:
    title = text_norm(title)
    snippet = text_norm(snippet)[:900]
    date = canonical_date(date)
    classification, scores, quality = classify_and_score(payload, title, snippet, source_family, source, date, url)
    record = {
        'record_id': make_record_id(source, payload['payload_id'], doi, pmid, nct_id, patent_id, url, title),
        'payload_id': payload['payload_id'],
        'payload': payload['name'],
        'display_name': payload['display_name'],
        'mechanism': payload['mechanism'],
        'source': source,
        'source_family': source_family,
        'evidence_type': evidence_type,
        'title': title,
        'abstract_or_snippet': snippet,
        'date': date,
        'year': clean_year(date),
        'url': url,
        'doi': doi or '',
        'pmid': pmid or '',
        'nct_id': nct_id or '',
        'patent_id': patent_id or '',
        'journal_or_source': journal_or_source or '',
        'authors_or_assignee': authors_or_assignee or [],
        'classification': classification,
        'scores': scores,
        'quality': quality,
        'rights': {
            'stored_content_level': 'metadata_and_allowed_snippet' if snippet else 'metadata_only',
            'license_note': 'No full text stored. Follow source URL for authoritative publisher/news/patent content.',
        },
    }
    return record


def pubmed_search(payload: dict) -> list[dict]:
    term = source_search_query(payload, 'AND ("antibody-drug conjugates"[MeSH Terms] OR antibody-drug conjugate[Title/Abstract] OR ADC[Title/Abstract] OR cancer[Title/Abstract])')
    url = 'https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi?' + urlencode({'db': 'pubmed', 'term': term, 'retmode': 'json', 'retmax': 12, 'sort': 'pub date'})
    ids = fetch_json(url).get('esearchresult', {}).get('idlist', [])
    if not ids:
        return []
    time.sleep(0.34)
    summary_url = 'https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi?' + urlencode({'db': 'pubmed', 'id': ','.join(ids), 'retmode': 'json'})
    summary = fetch_json(summary_url).get('result', {})
    rows = []
    for pmid in ids[:10]:
        item = summary.get(pmid, {})
        rows.append(make_record(
            payload,
            source='PubMed', source_family='paper', evidence_type='paper',
            title=item.get('title', ''), date=item.get('pubdate', ''), pmid=pmid,
            url=f'https://pubmed.ncbi.nlm.nih.gov/{pmid}/',
            journal_or_source=item.get('source', ''),
            authors_or_assignee=[a.get('name', '') for a in item.get('authors', [])[:6]],
        ))
    return rows


def europe_pmc_search(payload: dict) -> list[dict]:
    query = source_search_query(payload)
    url = 'https://www.ebi.ac.uk/europepmc/webservices/rest/search?' + urlencode({'query': query, 'format': 'json', 'pageSize': 10, 'sort': 'DATE'})
    data = fetch_json(url)
    rows = []
    for item in data.get('resultList', {}).get('result', [])[:10]:
        pmid = item.get('pmid', '')
        doi = item.get('doi', '')
        rows.append(make_record(
            payload,
            source='Europe PMC', source_family='paper', evidence_type='paper',
            title=item.get('title', ''), snippet=item.get('abstractText', ''),
            date=item.get('firstPublicationDate') or item.get('pubYear', ''),
            url=item.get('fullTextUrlList', {}).get('fullTextUrl', [{}])[0].get('url', '') if item.get('fullTextUrlList') else (f'https://europepmc.org/article/MED/{pmid}' if pmid else ''),
            doi=doi, pmid=pmid, journal_or_source=item.get('journalTitle', ''),
            authors_or_assignee=[a.strip() for a in text_norm(item.get('authorString', '')).split(',')[:6] if a.strip()],
        ))
    return rows


def openalex_search(payload: dict) -> list[dict]:
    query = f"{payload['name']} antibody drug conjugate payload cancer"
    url = 'https://api.openalex.org/works?' + urlencode({'search': query, 'per-page': 8, 'sort': 'publication_date:desc'})
    data = fetch_json(url)
    rows = []
    for item in data.get('results', [])[:8]:
        doi_url = item.get('doi') or ''
        doi = doi_url.replace('https://doi.org/', '')
        primary_location = item.get('primary_location') or {}
        source_info = primary_location.get('source') or {}
        rows.append(make_record(
            payload,
            source='OpenAlex', source_family='paper_metadata', evidence_type='paper_metadata',
            title=item.get('title', ''), date=item.get('publication_date') or str(item.get('publication_year', '') or ''),
            url=primary_location.get('landing_page_url') or doi_url or item.get('id', ''),
            doi=doi, journal_or_source=source_info.get('display_name', ''),
            authors_or_assignee=[a.get('author', {}).get('display_name', '') for a in item.get('authorships', [])[:6]],
        ))
    return rows


def crossref_search(payload: dict) -> list[dict]:
    query = f"{payload['name']} antibody drug conjugate payload cancer"
    url = 'https://api.crossref.org/works?' + urlencode({'query.bibliographic': query, 'rows': 8, 'sort': 'published', 'order': 'desc', 'filter': f'from-pub-date:1990-01-01,until-pub-date:{CURRENT_YEAR + 1}-12-31'})
    data = fetch_json(url)
    rows = []
    for item in data.get('message', {}).get('items', [])[:8]:
        title = ' '.join(item.get('title') or [])
        date_parts = item.get('published-print', item.get('published-online', item.get('created', {}))).get('date-parts', [[]])
        date = '-'.join(str(x) for x in (date_parts[0] if date_parts else []))
        rec = make_record(
            payload,
            source='Crossref', source_family='paper_metadata', evidence_type='paper_metadata',
            title=title, date=date, url=item.get('URL', ''), doi=item.get('DOI', ''),
            journal_or_source='; '.join(item.get('container-title') or []),
            authors_or_assignee=[f"{a.get('given','')} {a.get('family','')}".strip() for a in item.get('author', [])[:6]],
        )
        if rec['classification']['payload_relevance'] != 'flagged_irrelevant':
            rows.append(rec)
    return rows


def clinical_trials_search(payload: dict) -> list[dict]:
    query = f"({payload['name']} OR {' OR '.join(payload['aliases'][:5])}) antibody drug conjugate cancer"
    url = 'https://clinicaltrials.gov/api/v2/studies?' + urlencode({'query.term': query, 'pageSize': 10, 'format': 'json'})
    data = fetch_json(url)
    rows = []
    for study in data.get('studies', [])[:10]:
        protocol = study.get('protocolSection', {})
        ident = protocol.get('identificationModule', {})
        status = protocol.get('statusModule', {})
        descr = protocol.get('descriptionModule', {})
        design = protocol.get('designModule', {})
        arms = protocol.get('armsInterventionsModule', {})
        title = ident.get('briefTitle', '') or ident.get('officialTitle', '')
        nct = ident.get('nctId', '')
        interventions = '; '.join(i.get('name', '') for i in arms.get('interventions', [])[:8])
        snippet = ' '.join([descr.get('briefSummary', ''), interventions, design.get('phases', [''])[0] if design.get('phases') else ''])
        rows.append(make_record(
            payload,
            source='ClinicalTrials.gov', source_family='clinical_trial', evidence_type='clinical_trial',
            title=title, snippet=snippet,
            date=status.get('lastUpdateSubmitDate', '') or status.get('startDateStruct', {}).get('date', ''),
            url=f'https://clinicaltrials.gov/study/{nct}' if nct else '', nct_id=nct,
            journal_or_source='ClinicalTrials.gov', authors_or_assignee=[protocol.get('sponsorCollaboratorsModule', {}).get('leadSponsor', {}).get('name', '')],
        ))
    return rows


def patentsview_search(payload: dict) -> list[dict]:
    terms = ' '.join(payload['aliases'][:4] + ['antibody drug conjugate', 'payload'])
    q = {
        '_and': [
            {'_text_any': {'patent_abstract': terms}},
            {'_text_any': {'patent_abstract': 'antibody drug conjugate ADC payload linker cancer oncology'}},
        ]
    }
    fields = ['patent_number', 'patent_title', 'patent_abstract', 'patent_date', 'assignees.assignee_organization']
    opts = {'per_page': 8}
    url = 'https://api.patentsview.org/patents/query?' + urlencode({'q': json.dumps(q), 'f': json.dumps(fields), 'o': json.dumps(opts)})
    rows = []
    try:
        data = fetch_json(url)
        for item in data.get('patents', [])[:8]:
            patent_id = item.get('patent_number', '')
            rows.append(make_record(
                payload,
                source='PatentsView', source_family='patent', evidence_type='patent',
                title=item.get('patent_title', ''), snippet=item.get('patent_abstract', ''),
                date=item.get('patent_date', ''), patent_id=patent_id,
                url=f'https://patents.google.com/patent/US{patent_id}' if patent_id else '',
                journal_or_source='PatentsView',
                authors_or_assignee=[a.get('assignee_organization', '') for a in item.get('assignees', [])[:6] if a.get('assignee_organization')],
            ))
    except Exception:
        rows = []
    if rows:
        return rows
    seed_query = f"{payload['display_name']} antibody drug conjugate payload linker patent"
    return [make_record(
        payload,
        source='Google Patents Search', source_family='patent', evidence_type='patent_search_seed',
        title=f"{payload['display_name']} 专利检索入口（待 IP 人工复核）",
        snippet=f"PatentsView 当前不可用或无稳定返回。该记录是人工 IP 复核入口：请用 payload 别名、ADC、linker-payload、combination、biomarker 等关键词检索。关键词：{seed_query}",
        date=str(CURRENT_YEAR),
        url='https://patents.google.com/?' + urlencode({'q': seed_query}),
        journal_or_source='Google Patents Search',
    )]


def gdelt_news_search(payload: dict) -> list[dict]:
    query = f'("{payload["name"]}" OR "{payload["aliases"][0]}") ("antibody drug conjugate" OR ADC OR oncology OR cancer)'
    url = 'https://api.gdeltproject.org/api/v2/doc/doc?' + urlencode({'query': query, 'mode': 'ArtList', 'format': 'json', 'maxrecords': 8, 'sort': 'HybridRel', 'timespan': '24months'})
    rows = []
    try:
        data = fetch_json(url)
        for item in data.get('articles', [])[:8]:
            rows.append(make_record(
                payload,
                source='GDELT', source_family='news', evidence_type='news_metadata',
                title=item.get('title', ''), snippet=item.get('seendate', '') + ' ' + item.get('sourcecountry', ''),
                date=item.get('seendate', '')[:8], url=item.get('url', ''),
                journal_or_source=item.get('domain', '') or item.get('source', ''),
                authors_or_assignee=[item.get('domain', '')] if item.get('domain') else [],
            ))
    except Exception:
        rows = []
    if rows:
        return rows
    news_query = f"{payload['display_name']} ADC payload company news clinical update"
    return [make_record(
        payload,
        source='News Search Seed', source_family='news', evidence_type='news_search_seed',
        title=f"{payload['display_name']} 新闻/公司动态检索入口（待人工复核）",
        snippet=f"GDELT 当前限流或不可用。该记录只作为新闻和公司动态人工复核入口，不代表已确认新闻结论。关键词：{news_query}",
        date=str(CURRENT_YEAR),
        url='https://news.google.com/search?' + urlencode({'q': news_query}),
        journal_or_source='Google News Search',
    )]


def dedupe_records(records: list[dict]) -> list[dict]:
    seen = set()
    out = []
    for r in records:
        key = r.get('doi') or r.get('pmid') or r.get('nct_id') or r.get('patent_id') or r.get('url') or slug_text(r.get('title', ''))[:120]
        key = f"{r['payload_id']}|{r['source_family']}|{key}".lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(r)
    return out


def summarize_payloads(payloads: list[dict], records: list[dict]) -> list[dict]:
    summaries = []
    for payload in payloads:
        related = [r for r in records if r['payload_id'] == payload['payload_id'] and r['classification']['payload_relevance'] != 'flagged_irrelevant']
        by_source = Counter(r['source'] for r in related)
        by_type = Counter(r['source_family'] for r in related)
        direct = sum(1 for r in related if r['classification']['payload_relevance'] == 'direct')
        adjacent = sum(1 for r in related if r['classification']['payload_relevance'] == 'adjacent')
        flagged = sum(1 for r in records if r['payload_id'] == payload['payload_id'] and r['quality']['flags'])
        scientific = min(100, by_type['paper'] * 7 + by_type['paper_metadata'] * 3 + direct * 3)
        clinical = min(100, by_type['clinical_trial'] * 12 + direct * 2)
        patent = min(100, by_type['patent'] * 10)
        news = min(100, by_type['news'] * 7)
        combo = min(100, 45 + sum(1 for r in related if 'combination_signal' == r['classification']['evidence_class']) * 9 + (20 if 'TOP1' in payload['mechanism'] else 10))
        risk_penalty = min(35, flagged * 3 + sum(1 for r in related if 'safety_review' in r['classification']['use_case']) * 3 + (10 if payload['payload_id'] in {'pbd', 'amanitin'} else 0))
        opportunity = round(0.25 * scientific + 0.25 * clinical + 0.15 * patent + 0.10 * news + 0.15 * combo + 0.10 * 65 - risk_penalty)
        opportunity = max(0, min(100, opportunity))
        priority = 'P1' if opportunity >= 72 and direct >= 4 else 'P2' if opportunity >= 52 else 'P3'
        summaries.append({
            'payload_id': payload['payload_id'],
            'payload': payload['name'],
            'display_name': payload['display_name'],
            'mechanism': payload['mechanism'],
            'records_total': len(related),
            'records_by_source': dict(by_source),
            'records_by_type': dict(by_type),
            'relevance': {'direct_records': direct, 'adjacent_records': adjacent, 'flagged_records': flagged},
            'scores': {
                'external_heat': min(100, len(related) * 5),
                'scientific_activity': scientific,
                'clinical_activity': clinical,
                'patent_activity': patent,
                'news_activity': news,
                'combination_potential': combo,
                'risk_penalty': risk_penalty,
                'opportunity_score': opportunity,
            },
            'priority': priority,
            'recommended_action': '进入 0B 机会评估；同步补 IP 和安全性复核。' if priority == 'P1' else '继续补证据、人工审核或进入观察池。',
        })
    return sorted(summaries, key=lambda x: x['scores']['opportunity_score'], reverse=True)


def source_stats(records: list[dict]) -> list[dict]:
    grouped = defaultdict(list)
    for r in records:
        grouped[r['source']].append(r)
    return [
        {
            'source': source,
            'records': len(items),
            'direct': sum(1 for r in items if r['classification']['payload_relevance'] == 'direct'),
            'flagged': sum(1 for r in items if r['quality']['flags']),
            'families': dict(Counter(r['source_family'] for r in items)),
        }
        for source, items in sorted(grouped.items())
    ]


def flatten_record_for_csv(record: dict) -> dict:
    return {
        'record_id': record['record_id'],
        'payload': record['payload'],
        'source': record['source'],
        'source_family': record['source_family'],
        'evidence_type': record['evidence_type'],
        'date': record['date'],
        'year': record['year'] or '',
        'title': record['title'],
        'url': record['url'],
        'doi': record['doi'],
        'pmid': record['pmid'],
        'nct_id': record['nct_id'],
        'patent_id': record['patent_id'],
        'journal_or_source': record['journal_or_source'],
        'payload_relevance': record['classification']['payload_relevance'],
        'decision_relevance': record['classification']['decision_relevance'],
        'relevance_score': record['scores']['relevance_score'],
        'status': record['quality']['status'],
        'flags': ';'.join(record['quality']['flags']),
        'snippet': record['abstract_or_snippet'][:500],
    }


def write_csv(path: Path, rows: list[dict]) -> None:
    if not rows:
        path.write_text('', encoding='utf-8')
        return
    fields = list(rows[0].keys())
    with path.open('w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def render_html(data: dict) -> None:
    summaries = data['payload_summaries']
    score_rows = ''.join(
        f"<tr><td>{i+1}</td><td>{html.escape(s['display_name'])}</td><td>{html.escape(s['mechanism'])}</td><td>{s['scores']['opportunity_score']}</td><td>{s['records_total']}</td><td>{s['records_by_type'].get('paper', 0) + s['records_by_type'].get('paper_metadata', 0)}</td><td>{s['records_by_type'].get('clinical_trial', 0)}</td><td>{s['records_by_type'].get('patent', 0)}</td><td>{s['records_by_type'].get('news', 0)}</td><td>{s['priority']}</td></tr>"
        for i, s in enumerate(summaries)
    )
    stat_rows = ''.join(
        f"<tr><td>{html.escape(s['source'])}</td><td>{s['records']}</td><td>{s['direct']}</td><td>{s['flagged']}</td><td>{html.escape(json.dumps(s['families'], ensure_ascii=False))}</td></tr>"
        for s in data['source_stats']
    )
    sample_records = sorted(data['records'], key=lambda r: (r['quality']['flags'] != [], -(r['scores']['relevance_score'] or 0)))[:120]
    rec_rows = ''.join(
        f"<tr><td>{html.escape(r['source'])}</td><td>{html.escape(r['payload'])}</td><td>{html.escape(r['source_family'])}</td><td>{html.escape(r['date'])}</td><td>{html.escape(r['classification']['payload_relevance'])}</td><td>{r['scores']['relevance_score']}</td><td><a href='{html.escape(r['url'])}'>来源</a></td><td>{html.escape(r['title'][:180])}</td><td>{html.escape(', '.join(r['quality']['flags']) or r['quality']['status'])}</td></tr>"
        for r in sample_records
    )
    err_rows = ''.join(f"<tr><td>{html.escape(e['payload'])}</td><td>{html.escape(e['source'])}</td><td>{html.escape(e['error'])}</td></tr>" for e in data['errors']) or '<tr><td colspan="3">无采集错误</td></tr>'
    html_doc = f'''<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"/><meta name="viewport" content="width=device-width,initial-scale=1"/><title>数据采集状态｜ADC Payload 证据资料库</title><style>
body{{margin:0;background:#07111f;color:#eef6ff;font-family:-apple-system,BlinkMacSystemFont,"Segoe UI","PingFang SC","Microsoft YaHei",sans-serif;line-height:1.68}}a{{color:#6fffe9;font-weight:700;text-decoration:none}}.wrap{{width:min(1240px,calc(100% - 40px));margin:0 auto}}nav{{position:sticky;top:0;background:rgba(7,17,31,.82);border-bottom:1px solid rgba(255,255,255,.16);backdrop-filter:blur(18px);z-index:2}}nav .wrap{{display:flex;justify-content:space-between;gap:16px;padding:14px 0}}.navlinks{{display:flex;gap:14px;flex-wrap:wrap}}.navlinks a{{color:#a8b7c9}}header{{padding:64px 0 28px}}h1{{font-size:clamp(36px,6vw,64px);line-height:1.05;margin:16px 0}}.lead{{font-size:20px;color:#d7e7f7;max-width:960px}}section{{padding:30px 0}}.card,table{{background:rgba(255,255,255,.075);border:1px solid rgba(255,255,255,.16);border-radius:22px;box-shadow:0 22px 70px rgba(0,0,0,.35)}}.card{{padding:22px}}.grid{{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:16px}}strong.big{{font-size:32px;color:#68d5ff;display:block}}table{{width:100%;border-collapse:separate;border-spacing:0;overflow:hidden;font-size:14px}}th,td{{padding:12px 13px;border-bottom:1px solid rgba(255,255,255,.16);vertical-align:top;text-align:left}}th{{background:linear-gradient(135deg,#68d5ff,#8ef6a3);color:#061622}}td{{color:#e5f0fb}}tr:last-child td{{border-bottom:0}}.note{{padding:16px 18px;border-left:4px solid #8ef6a3;background:rgba(142,246,163,.08);border-radius:0 18px 18px 0}}@media(max-width:900px){{.grid{{grid-template-columns:1fr}}table{{display:block;overflow-x:auto;white-space:nowrap}}}}
</style></head><body><nav><div class="wrap"><strong>数据采集状态</strong><div class="navlinks"><a href="./index.html">首页</a><a href="./payload-evidence-library.html">证据资料库</a><a href="./ADC毒素组合用药算法沟通网页/ADC协作型方案详情-00-Payload机会扫描与选题雷达.html">ADC 0A</a><a href="./changelog.html">更新日志</a></div></div></nav><header class="wrap"><h1>ADC Payload 数据采集与 QC 状态</h1><p class="lead">这是公开证据资料库生成状态：围绕主要 ADC payload 从论文、临床试验、专利和新闻元数据源采集记录，并进行去重、相关性评分和质量标记。所有结果都需要人工科学/IP 审核后才能用于项目决策。</p></header><main>
<section class="wrap"><div class="grid"><div class="card"><strong class="big">{len(data['records'])}</strong>证据记录</div><div class="card"><strong class="big">{len(data['payloads'])}</strong>Payload</div><div class="card"><strong class="big">{len(data['source_stats'])}</strong>数据源</div><div class="card"><strong class="big">{sum(1 for r in data['records'] if r['quality']['flags'])}</strong>质量标记</div><div class="card"><strong class="big">{len(data['errors'])}</strong>采集错误</div></div></section>
<section class="wrap"><div class="note"><strong>生成时间：</strong>{html.escape(data['generated_at'])}<br/><strong>版权边界：</strong>{html.escape(data['source_policy']['copyright_boundary'])}<br/><strong>审核边界：</strong>{html.escape(data['source_policy']['review_boundary'])}<br/><strong>下载：</strong><a href="./data/payload_evidence_library.json">JSON</a> · <a href="./data/payload_evidence_records.csv">记录 CSV</a> · <a href="./data/payload_evidence_summary.csv">汇总 CSV</a></div></section>
<section class="wrap"><h2>Payload 汇总</h2><table><thead><tr><th>排名</th><th>Payload</th><th>机制</th><th>机会分</th><th>记录数</th><th>论文</th><th>临床</th><th>专利</th><th>新闻</th><th>优先级</th></tr></thead><tbody>{score_rows}</tbody></table></section>
<section class="wrap"><h2>来源覆盖与质量标记</h2><table><thead><tr><th>来源</th><th>记录数</th><th>直接相关</th><th>有质量标记</th><th>类型分布</th></tr></thead><tbody>{stat_rows}</tbody></table></section>
<section class="wrap"><h2>高相关 / 待审核记录样例</h2><table><thead><tr><th>来源</th><th>Payload</th><th>类型</th><th>日期</th><th>相关性</th><th>分数</th><th>链接</th><th>标题</th><th>状态/标记</th></tr></thead><tbody>{rec_rows}</tbody></table></section>
<section class="wrap"><h2>采集错误 / 待处理</h2><table><thead><tr><th>Payload</th><th>来源</th><th>错误</th></tr></thead><tbody>{err_rows}</tbody></table></section>
</main></body></html>'''
    (ROOT / 'data-status.html').write_text(html_doc, encoding='utf-8')


def compatibility_exports(data: dict) -> tuple[dict, list[dict], list[dict]]:
    old_records = []
    for r in data['records']:
        old_records.append({
            'source': r['source'],
            'payload': r['payload'],
            'mechanism': r['mechanism'],
            'title': r['title'],
            'date': r['date'],
            'url': r['url'],
            'evidence_type': r['evidence_type'],
            'status': r['quality']['status'],
        })
    old_scores = []
    for s in data['payload_summaries']:
        old_scores.append({
            'payload': s['payload'],
            'mechanism': s['mechanism'],
            'records': s['records_total'],
            'pubmed_records': s['records_by_source'].get('PubMed', 0),
            'crossref_records': s['records_by_source'].get('Crossref', 0),
            'clinical_records': s['records_by_source'].get('ClinicalTrials.gov', 0),
            'external_heat': s['scores']['external_heat'],
            'combination_potential': s['scores']['combination_potential'],
            'risk_penalty': s['scores']['risk_penalty'],
            'opportunity_score': s['scores']['opportunity_score'],
            'priority': s['priority'],
            'recommended_action': s['recommended_action'],
        })
    old_payload = {
        'generated_at': data['generated_at'],
        'started_at': data['started_at'],
        'records_count': len(old_records),
        'payloads_count': len(data['payloads']),
        'sources': [s['source'] for s in data['source_stats']],
        'notes': data['source_policy']['review_boundary'],
        'scores': old_scores,
        'records': old_records,
        'errors': data['errors'],
    }
    return old_payload, old_records, old_scores


def main() -> None:
    started = datetime.now(timezone.utc).isoformat()
    records: list[dict] = []
    errors: list[dict] = []
    fetchers = [pubmed_search, europe_pmc_search, openalex_search, crossref_search, clinical_trials_search, patentsview_search, gdelt_news_search]
    for payload in PAYLOADS:
        for func in fetchers:
            try:
                records.extend(func(payload))
            except Exception as exc:
                errors.append({'payload': payload['name'], 'source': func.__name__.replace('_search', ''), 'error': repr(exc)[:500]})
            time.sleep(0.28)
    records = dedupe_records(records)
    records.sort(key=lambda r: (r['payload_id'], -(r['scores']['relevance_score'] or 0), r['date']), reverse=False)
    summaries = summarize_payloads(PAYLOADS, records)
    data = {
        'schema_version': '1.1',
        'generated_at': datetime.now(timezone.utc).isoformat(),
        'started_at': started,
        'source_policy': SOURCE_POLICY,
        'payloads': PAYLOADS,
        'payload_summaries': summaries,
        'records': records,
        'source_stats': source_stats(records),
        'quality_flags': sorted(set(flag for r in records for flag in r['quality']['flags'])),
        'errors': errors,
    }
    (DATA_DIR / 'payload_evidence_library.json').write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
    write_csv(DATA_DIR / 'payload_evidence_records.csv', [flatten_record_for_csv(r) for r in records])
    write_csv(DATA_DIR / 'payload_evidence_summary.csv', [
        {
            'payload': s['payload'],
            'display_name': s['display_name'],
            'mechanism': s['mechanism'],
            'records_total': s['records_total'],
            'papers': s['records_by_type'].get('paper', 0) + s['records_by_type'].get('paper_metadata', 0),
            'clinical_trials': s['records_by_type'].get('clinical_trial', 0),
            'patents': s['records_by_type'].get('patent', 0),
            'news': s['records_by_type'].get('news', 0),
            'direct_records': s['relevance']['direct_records'],
            'flagged_records': s['relevance']['flagged_records'],
            'opportunity_score': s['scores']['opportunity_score'],
            'priority': s['priority'],
            'recommended_action': s['recommended_action'],
        }
        for s in summaries
    ])
    schema = {
        'schema_version': '1.1',
        'description': 'Payload evidence library schema for HANX static GitHub Pages site.',
        'top_level_fields': list(data.keys()),
        'record_fields': list(records[0].keys()) if records else [],
        'summary_fields': list(summaries[0].keys()) if summaries else [],
    }
    (DATA_DIR / 'payload_evidence_schema.json').write_text(json.dumps(schema, ensure_ascii=False, indent=2), encoding='utf-8')
    old_payload, old_records, old_scores = compatibility_exports(data)
    (DATA_DIR / 'payload_intelligence.json').write_text(json.dumps(old_payload, ensure_ascii=False, indent=2), encoding='utf-8')
    write_csv(DATA_DIR / 'payload_intelligence_records.csv', old_records)
    write_csv(DATA_DIR / 'payload_scores.csv', old_scores)
    render_html(data)
    print(json.dumps({'records': len(records), 'payloads': len(PAYLOADS), 'sources': len(data['source_stats']), 'quality_flags': len(data['quality_flags']), 'errors': len(errors)}, ensure_ascii=False))


if __name__ == '__main__':
    main()
