"""Private, explicit company coverage report; empty matches do not imply coverage."""
import html
import re

from .storage import dump, now


def export_coverage(store, output, config):
    normalize = lambda value: re.sub(r'[^a-z0-9]', '', str(value).casefold())
    states = {row['source']: row for row in store.rows('SELECT * FROM source_state')}
    counts = store.rows("SELECT employer,classification,posting_status,COUNT(*) count FROM jobs GROUP BY employer,classification,posting_status")
    records, body = [], []
    esc = lambda value: html.escape(str(value or ''), quote=True)
    for company in config.get('company_watchlist', []):
        names = {normalize(name) for name in company.get('aliases', [company['company']])}
        matches = [row for row in counts if normalize(row['employer']) in names and row['classification'] == 'include']
        sources = company['direct_sources'] + company['feed_sources']
        health = [{'source': source, 'last_success': states.get(source, {}).get('last_success'),
                   'failures': states.get(source, {}).get('failures'), 'last_error': states.get(source, {}).get('last_error')}
                  for source in sources]
        record = dict(company, source_health=health, qualifying_records=sum(row['count'] for row in matches),
                      verified_records=sum(row['count'] for row in matches if row['posting_status'] == 'open'))
        records.append(record)
        status = 'Direct + public feed' if company['direct_sources'] else 'Incomplete — public feed only'
        latest = '; '.join(h['source'] + ': ' + ('never checked' if not h['last_success'] else 'FAILED' if h['failures'] else h['last_success']) for h in health)
        body.append('<tr><td>'+esc(company['company'])+'</td><td>'+esc(status)+'</td><td>'+esc(latest)+
                    '</td><td>'+str(record['verified_records'])+' / '+str(record['qualifying_records'])+
                    '</td><td>'+esc(company.get('note'))+'</td></tr>')
    (output/'coverage.json').write_text(dump({'exported_at':now(),'companies':records}),encoding='utf-8')
    page='''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Company coverage — Internship Watch</title><style>body{font:16px system-ui;margin:2rem;max-width:1400px;background:#f6f7fb;color:#17243a}table{border-collapse:collapse;width:100%;background:white}th,td{text-align:left;padding:1rem;border:1px solid #dce1eb;vertical-align:top}td:nth-child(3){font-size:.8rem;overflow-wrap:anywhere}a{color:#315ac5}</style>
<h1>Company coverage</h1><p><a href="jobs.html">Back to jobs</a> · <a href="coverage.json">Coverage data</a></p>
<p>Last export: DATE. Counts are verified / qualifying stored records, not all employer vacancies. Zero matches can be normal.</p>
<p>Five-minute polling measures our checks, not upstream publication speed. Simplify's public GitHub feed is a subset of its website and may receive daily database exports. Sources, schemas and access policies can change; failures are monitored.</p>
<table><thead><tr><th>Company</th><th>Discovery coverage</th><th>Source last success (UTC)</th><th>Stored matches</th><th>Scope and limitations</th></tr></thead><tbody>ROWS</tbody></table></html>'''
    (output/'coverage.html').write_text(page.replace('DATE',esc(now())).replace('ROWS',''.join(body)),encoding='utf-8')
