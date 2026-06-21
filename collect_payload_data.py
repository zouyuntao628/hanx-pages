#!/usr/bin/env python3
from __future__ import annotations

import csv
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode, quote
from urllib.request import Request, urlopen
from xml.etree import ElementTree as ET

ROOT = Path('/Users/Andrew/hanx-pages')
DATA_DIR = ROOT / 'data'
DATA_DIR.mkdir(exist_ok=True)

PAYLOADS = [
    {'name': 'DXd', 'aliases': ['DXd', 'deruxtecan'], 'mechanism': 'TOP1 inhibitor'},
    {'name': 'exatecan', 'aliases': ['exatecan'], 'mechanism': 'TOP1 inhibitor'},
    {'name': 'SN-38', 'aliases': ['SN-38', 'SN38'], 'mechanism': 'TOP1 inhibitor'},
    {'name': 'MMAE', 'aliases': ['MMAE', 'monomethyl auristatin E'], 'mechanism': 'microtubule inhibitor'},
    {'name': 'MMAF', 'aliases': ['MMAF', 'monomethyl auristatin F'], 'mechanism': 'microtubule inhibitor'},
    {'name': 'DM1', 'aliases': ['DM1', 'emtansine'], 'mechanism': 'microtubule inhibitor'},
    {'name': 'DM4', 'aliases': ['DM4', 'ravtansine'], 'mechanism': 'microtubule inhibitor'},
    {'name': 'PBD', 'aliases': ['PBD', 'pyrrolobenzodiazepine'], 'mechanism': 'DNA crosslinking'},
    {'name': 'amanitin', 'aliases': ['amanitin', 'alpha-amanitin'], 'mechanism': 'RNA polymerase II inhibitor'},
]

HEADERS = {'User-Agent': 'HANX-Payload-Radar/0.1 (static research prototype)'}


def fetch_json(url: str, timeout: int = 25) -> dict:
    with urlopen(Request(url, headers=HEADERS), timeout=timeout) as r:
        return json.loads(r.read().decode('utf-8', 'ignore'))


def fetch_text(url: str, timeout: int = 25) -> str:
    with urlopen(Request(url, headers=HEADERS), timeout=timeout) as r:
        return r.read().decode('utf-8', 'ignore')


def pubmed_search(payload: dict) -> list[dict]:
    term = '(' + ' OR '.join(f'"{a}"' for a in payload['aliases']) + ') AND (ADC OR antibody-drug conjugate OR payload OR cancer)'
    base = 'https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi'
    url = base + '?' + urlencode({'db': 'pubmed', 'term': term, 'retmode': 'json', 'retmax': 8, 'sort': 'pub date'})
    data = fetch_json(url)
    ids = data.get('esearchresult', {}).get('idlist', [])
    if not ids:
        return []
    time.sleep(0.35)
    summary_url = 'https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi?' + urlencode({'db': 'pubmed', 'id': ','.join(ids), 'retmode': 'json'})
    summary = fetch_json(summary_url).get('result', {})
    rows = []
    for pmid in ids[:5]:
        item = summary.get(pmid, {})
        rows.append({
            'source': 'PubMed',
            'payload': payload['name'],
            'mechanism': payload['mechanism'],
            'title': item.get('title', ''),
            'date': item.get('pubdate', ''),
            'url': f'https://pubmed.ncbi.nlm.nih.gov/{pmid}/',
            'evidence_type': 'paper',
            'status': 'auto_parsed_pending_review',
        })
    return rows


def crossref_search(payload: dict) -> list[dict]:
    query = f"{payload['name']} antibody drug conjugate payload cancer"
    url = 'https://api.crossref.org/works?' + urlencode({'query': query, 'rows': 5, 'sort': 'published', 'order': 'desc'})
    data = fetch_json(url)
    rows = []
    for item in data.get('message', {}).get('items', [])[:5]:
        title = ' '.join(item.get('title') or [])
        date_parts = item.get('published-print', item.get('published-online', item.get('created', {}))).get('date-parts', [[]])
        date = '-'.join(str(x) for x in (date_parts[0] if date_parts else []))
        rows.append({
            'source': 'Crossref',
            'payload': payload['name'],
            'mechanism': payload['mechanism'],
            'title': title,
            'date': date,
            'url': item.get('URL', ''),
            'evidence_type': 'paper_metadata',
            'status': 'auto_parsed_pending_review',
        })
    return rows


def clinical_trials_search(payload: dict) -> list[dict]:
    query = f"{payload['name']} OR {' OR '.join(payload['aliases'])} antibody drug conjugate"
    url = 'https://clinicaltrials.gov/api/v2/studies?' + urlencode({'query.term': query, 'pageSize': 5, 'format': 'json'})
    data = fetch_json(url)
    rows = []
    for study in data.get('studies', [])[:5]:
        protocol = study.get('protocolSection', {})
        ident = protocol.get('identificationModule', {})
        status = protocol.get('statusModule', {})
        title = ident.get('briefTitle', '') or ident.get('officialTitle', '')
        nct = ident.get('nctId', '')
        rows.append({
            'source': 'ClinicalTrials.gov',
            'payload': payload['name'],
            'mechanism': payload['mechanism'],
            'title': title,
            'date': status.get('lastUpdateSubmitDate', '') or status.get('startDateStruct', {}).get('date', ''),
            'url': f'https://clinicaltrials.gov/study/{nct}' if nct else '',
            'evidence_type': 'clinical_trial',
            'status': 'auto_parsed_pending_review',
        })
    return rows


def score_payload(payload: dict, records: list[dict]) -> dict:
    related = [r for r in records if r['payload'] == payload['name']]
    pubmed = sum(1 for r in related if r['source'] == 'PubMed')
    crossref = sum(1 for r in related if r['source'] == 'Crossref')
    clinical = sum(1 for r in related if r['source'] == 'ClinicalTrials.gov')
    external_heat = min(100, (pubmed * 10) + (crossref * 6) + (clinical * 14))
    mechanism_bonus = 18 if 'TOP1' in payload['mechanism'] else 12 if 'microtubule' in payload['mechanism'] else 10
    combination_potential = 82 if payload['name'] in {'DXd', 'exatecan', 'SN-38'} else 74 if payload['name'] in {'MMAE', 'MMAF'} else 62
    risk_penalty = 18 if payload['name'] in {'PBD', 'amanitin'} else 10 if payload['name'] in {'DXd', 'SN-38'} else 6
    opportunity = round(0.20 * external_heat + 0.15 * mechanism_bonus + 0.25 * combination_potential + 0.15 * 65 + 0.15 * (80 - risk_penalty) + 0.10 * 70)
    priority = 'P1' if opportunity >= 72 else 'P2' if opportunity >= 58 else 'P3'
    return {
        'payload': payload['name'],
        'mechanism': payload['mechanism'],
        'records': len(related),
        'pubmed_records': pubmed,
        'crossref_records': crossref,
        'clinical_records': clinical,
        'external_heat': external_heat,
        'combination_potential': combination_potential,
        'risk_penalty': risk_penalty,
        'opportunity_score': opportunity,
        'priority': priority,
        'recommended_action': '进入 0B 机会评估；若公司资源匹配，进入方案一项目定义卡' if priority == 'P1' else '继续补资料或观察',
    }


def write_csv(path: Path, rows: list[dict]) -> None:
    if not rows:
        return
    fields = list(rows[0].keys())
    with path.open('w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    started = datetime.now(timezone.utc).isoformat()
    records = []
    errors = []
    for payload in PAYLOADS:
        for func in (pubmed_search, crossref_search, clinical_trials_search):
            try:
                records.extend(func(payload))
            except Exception as exc:
                errors.append({'payload': payload['name'], 'source': func.__name__, 'error': repr(exc)})
            time.sleep(0.4)
    scores = [score_payload(p, records) for p in PAYLOADS]
    scores.sort(key=lambda x: x['opportunity_score'], reverse=True)
    payload = {
        'generated_at': datetime.now(timezone.utc).isoformat(),
        'started_at': started,
        'records_count': len(records),
        'payloads_count': len(PAYLOADS),
        'sources': ['PubMed', 'Crossref', 'ClinicalTrials.gov'],
        'notes': 'Public data collection MVP. Results are automatically parsed and require human scientific/IP review before project decisions.',
        'scores': scores,
        'records': records,
        'errors': errors,
    }
    (DATA_DIR / 'payload_intelligence.json').write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')
    write_csv(DATA_DIR / 'payload_intelligence_records.csv', records)
    write_csv(DATA_DIR / 'payload_scores.csv', scores)
    render_html(payload)
    print(json.dumps({'records': len(records), 'scores': len(scores), 'errors': len(errors)}, ensure_ascii=False))


def render_html(data: dict) -> None:
    score_rows = ''.join(
        f"<tr><td>{i+1}</td><td>{s['payload']}</td><td>{s['mechanism']}</td><td>{s['opportunity_score']}</td><td>{s['records']}</td><td>{s['priority']}</td><td>{s['recommended_action']}</td></tr>"
        for i, s in enumerate(data['scores'][:9])
    )
    rec_rows = ''.join(
        f"<tr><td>{r['source']}</td><td>{r['payload']}</td><td>{r['evidence_type']}</td><td>{r['date']}</td><td><a href='{r['url']}'>来源</a></td><td>{r['title'][:160]}</td><td>{r['status']}</td></tr>"
        for r in data['records'][:80]
    )
    err_rows = ''.join(f"<tr><td>{e['payload']}</td><td>{e['source']}</td><td>{e['error']}</td></tr>" for e in data['errors']) or '<tr><td colspan="3">无采集错误</td></tr>'
    html = f'''<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"/><meta name="viewport" content="width=device-width,initial-scale=1"/><title>数据采集状态｜ADC Payload 情报雷达</title><style>
body{{margin:0;background:#07111f;color:#eef6ff;font-family:-apple-system,BlinkMacSystemFont,"Segoe UI","PingFang SC","Microsoft YaHei",sans-serif;line-height:1.68}}a{{color:#6fffe9;font-weight:700;text-decoration:none}}.wrap{{width:min(1240px,calc(100% - 40px));margin:0 auto}}nav{{position:sticky;top:0;background:rgba(7,17,31,.82);border-bottom:1px solid rgba(255,255,255,.16);backdrop-filter:blur(18px)}}nav .wrap{{display:flex;justify-content:space-between;gap:16px;padding:14px 0}}.navlinks{{display:flex;gap:14px;flex-wrap:wrap}}.navlinks a{{color:#a8b7c9}}header{{padding:64px 0 28px}}h1{{font-size:clamp(36px,6vw,64px);line-height:1.05;margin:16px 0}}.lead{{font-size:20px;color:#d7e7f7;max-width:960px}}section{{padding:30px 0}}.card,table{{background:rgba(255,255,255,.075);border:1px solid rgba(255,255,255,.16);border-radius:22px;box-shadow:0 22px 70px rgba(0,0,0,.35)}}.card{{padding:22px}}.grid{{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:16px}}strong.big{{font-size:32px;color:#68d5ff;display:block}}table{{width:100%;border-collapse:separate;border-spacing:0;overflow:hidden;font-size:14px}}th,td{{padding:12px 13px;border-bottom:1px solid rgba(255,255,255,.16);vertical-align:top;text-align:left}}th{{background:linear-gradient(135deg,#68d5ff,#8ef6a3);color:#061622}}td{{color:#e5f0fb}}tr:last-child td{{border-bottom:0}}.note{{padding:16px 18px;border-left:4px solid #8ef6a3;background:rgba(142,246,163,.08);border-radius:0 18px 18px 0}}@media(max-width:900px){{.grid{{grid-template-columns:1fr}}table{{display:block;overflow-x:auto;white-space:nowrap}}}}
</style></head><body><nav><div class="wrap"><strong>数据采集状态</strong><div class="navlinks"><a href="./index.html">首页</a><a href="./ADC毒素组合用药算法沟通网页/ADC协作型方案详情-00-Payload机会扫描与选题雷达.html">ADC 0A</a><a href="./changelog.html">更新日志</a></div></div></nav><header class="wrap"><h1>ADC Payload 数据采集状态</h1><p class="lead">这是第一版公开数据采集 MVP：围绕主要 ADC payload 从 PubMed、Crossref 和 ClinicalTrials.gov 抓取公开记录，生成 payload 机会评分草案。所有结果均需人工科学/IP 审核后才能用于项目决策。</p></header><main>
<section class="wrap"><div class="grid"><div class="card"><strong class="big">{data['records_count']}</strong>公开记录</div><div class="card"><strong class="big">{data['payloads_count']}</strong>Payload 候选</div><div class="card"><strong class="big">{len(data['sources'])}</strong>数据源</div><div class="card"><strong class="big">{len(data['errors'])}</strong>采集错误</div></div></section>
<section class="wrap"><div class="note"><strong>生成时间：</strong>{data['generated_at']}<br/><strong>数据源：</strong>{', '.join(data['sources'])}<br/><strong>边界：</strong>{data['notes']}</div></section>
<section class="wrap"><h2>Payload 机会评分草案</h2><table><thead><tr><th>排名</th><th>Payload</th><th>机制</th><th>机会分</th><th>记录数</th><th>优先级</th><th>推荐动作</th></tr></thead><tbody>{score_rows}</tbody></table></section>
<section class="wrap"><h2>采集记录样例</h2><table><thead><tr><th>来源</th><th>Payload</th><th>类型</th><th>日期</th><th>链接</th><th>标题</th><th>状态</th></tr></thead><tbody>{rec_rows}</tbody></table></section>
<section class="wrap"><h2>采集错误 / 待处理</h2><table><thead><tr><th>Payload</th><th>来源</th><th>错误</th></tr></thead><tbody>{err_rows}</tbody></table></section>
</main></body></html>'''
    (ROOT / 'data-status.html').write_text(html, encoding='utf-8')


if __name__ == '__main__':
    main()
