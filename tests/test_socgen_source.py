import json
from pathlib import Path
import unittest
from unittest.mock import Mock

from internship_watch.sources import collect, SourceError
from internship_watch.socgen_source import BASE, PROFILE, identity
from internship_watch.storage import url_identity, employer_identity
from internship_watch.links import employer_compatible


def row(number, title='Office Administrator', employment='Permanent contract'):
    job='26000A'+str(number).zfill(2)
    return dict(title=title,sourcestr4=job,sourcestr12=job+'-en',sourcestr6='job',
        sourcestr7='New York, United States',sourcestr8=employment,
        url1=BASE+'/en/job-offers/role-'+job+'-en')


def page(rows,total,number):
    return dict(methodresult='ok',TotalCount=total,CurrentPage=number,PageCount=(total+9)//10,
                DocumentsThisPage=len(rows),Result={'Docs':rows})


def client(pages,details=()):
    c=Mock()
    def response(data=None,text='',url=BASE+'/en'):
        r=Mock();r.text=text;r.json.return_value=data;r.url=url;r.raise_for_status.return_value=None;return r
    settings={'csrfToken':'test-csrf','quantum':{'base_url':PROFILE.rsplit('/',1)[0]}}
    c.get.side_effect=[response(text='<script data-drupal-selector="drupal-settings-json">'+json.dumps(settings)+'</script>'),
                      response({'token':'test-anonymous'})]+[response(text=t,url=u) for t,u in details]
    c.post.side_effect=[response(p) for p in pages]
    return c


SOURCE=dict(id='socgen',type='socgen',employer='Société Générale',country_scope=['US'])


class SocGenTests(unittest.TestCase):
    def test_configured_employer_unicode_matches_real_schema(self):
        config=json.loads((Path(__file__).resolve().parents[1]/'config.example.json').read_text(encoding='utf8'))
        source=next(s for s in config['sources'] if s['id']=='socgen-us')
        self.assertTrue(employer_compatible(source['employer'],'Societe Generale',BASE+'/en'))
        self.assertTrue(any(c['company']=='Soci\u00e9t\u00e9 G\u00e9n\u00e9rale' for c in config['company_watchlist']))
        self.assertTrue(any('Moody\u2019s' in c['aliases'] for c in config['company_watchlist']))

    def test_all_pages_complete_and_no_internship_invention(self):
        c=client([page([row(n) for n in range(10)],11,1),page([row(10)],11,2)])
        jobs=collect(SOURCE,c)
        self.assertEqual(len(jobs),11)
        self.assertTrue(all(j['posting_date'] is None and j['employment_type']=='Permanent contract' for j in jobs))
        self.assertEqual(c.post.call_args_list[1].kwargs['json']['query']['skipFrom'],10)
        self.assertTrue(all(x.kwargs['respect_robots'] for x in c.post.call_args_list))
        self.assertNotIn('test-anonymous',str(jobs))

    def test_repeated_changed_and_truncated_pages_fail(self):
        for second in (page([row(0)],11,2),page([row(10)],12,2),page([],11,2)):
            with self.assertRaises(SourceError):collect(SOURCE,client([page([row(n) for n in range(10)],11,1),second]))

    def test_internship_schema_exact_requisition_and_dates(self):
        r=row(1,'Financial Engineer Internship','Internship');job=r['sourcestr4']
        app='https://socgen.taleo.net/careersection/sgcareers/jobapply.ftl?job='+job+'&lang=en'
        item={'@type':'JobPosting','identifier':{'value':job},'title':r['title']+' - New York',
            'hiringOrganization':{'name':'Societe Generale'},'employmentType':'Internship','datePosted':'2026/09/17',
            'description':'Develop quantitative trading models. Why join us Company boilerplate.'}
        html=lambda: '<script type="application/ld+json">'+json.dumps(item)+'</script><a href="'+app+'">Apply</a>'
        jobs=collect(SOURCE,client([page([r],1,1)],[(html(),r['url1'])]))
        self.assertEqual(jobs[0]['posting_date'],'2026-09-17')
        self.assertEqual(jobs[0]['application_url'],app)
        self.assertNotIn('boilerplate',jobs[0]['description'])
        item['identifier']['value']='26000ZZZ'
        with self.assertRaises(SourceError):collect(SOURCE,client([page([r],1,1)],[(html(),r['url1'])]))

    def test_exact_cross_source_aliases_and_accented_employer(self):
        r=row(1)
        app='https://socgen.taleo.net/careersection/sgcareers/jobapply.ftl?job='+r['sourcestr4']
        self.assertEqual(url_identity(r['url1']),url_identity(app))
        self.assertNotEqual(url_identity(row(2)['url1']),url_identity(app))
        self.assertIsNone(identity(app+'&job=OTHER'))
        self.assertEqual(employer_identity('Société Générale'),employer_identity('Societe Generale'))
        self.assertTrue(employer_compatible('Société Générale','Societe Generale',r['url1']))
        self.assertFalse(employer_compatible('Société Générale','Other Bank',r['url1']))


if __name__=='__main__':unittest.main()
