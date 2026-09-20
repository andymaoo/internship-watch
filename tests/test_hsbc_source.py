import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock

from internship_watch.classify import classify
from internship_watch.hsbc_source import identity, BASE
from internship_watch.sources import collect, SourceError
from internship_watch.storage import Store, url_identity

SOURCE = dict(id='hsbc-campus',type='hsbc',employer='HSBC',max_pages=10)
DESCRIPTION = ('Responsibilities: As an intern, you will develop software and data products with our engineering team. '
               'Qualifications: Currently pursuing a Bachelor degree and in your junior year of university. '
               'Work with product managers to evaluate customer requirements and software features.')


def url(n=1234567):
    return f'https://apply.careers.hsbc.com/emergingtalent/job/New-York-Role/{n}/?feedId=434057'


def card(n, title='Engineering - Graduate', location='USA, New York', kind='Graduate Programme'):
    return f'''<li id="programme-{n}-en_GB"><article>
    <div class="program-location">{location}</div>
    <a href="{url(n)}"><h2 class="program-text__destination">{title}<span> (opens in new window)</span></h2></a>
    <div class="program-text__short-description">Develop software and data products.</div>
    <div class="program-text__group--type"><dt>Programme type</dt><dd>{kind}</dd></div>
    <div class="program-text__group--opening"><dt>Opening Date</dt><dd>1st Sep 2026</dd></div>
    <div class="program-text__group--closing"><dt>Closing Date</dt><dd>30th Nov 2026</dd></div>
    </article></li>'''


def index(cards,total,initial=None,promo=''):
    initial = len(cards) if initial is None else initial
    return f'''<div data-component="ProgramFinder" data-props-settings="abcdef1234"
    data-props-skip="{initial}" data-props-take="2" data-props-total-count="{total}">
    <ul class="program-finder-grid">{''.join(cards)}{promo}</ul></div>'''


def response(text='', data=None, at=BASE):
    r=Mock(text=text,url=at);r.json.return_value=data;return r


def client(*responses):
    c=Mock();c.get.side_effect=list(responses);return c


def detail(title='Product Manager Internship', n=1234567, application=None):
    return (f'<span itemprop="title">{title}</span><span class="jobdescription"><p>{DESCRIPTION}</p></span>'
            f'<a href="{application or f"/talentcommunity/apply/{n}/?locale=en_GB"}">Apply now</a>')


class HsbcTests(unittest.TestCase):
    def test_complete_pagination_with_promotional_card(self):
        c=client(response(index([card(1),card(2)],3,promo='<li class="content-card">Information</li>')),
                 response(data=[card(3)]))
        jobs=collect(SOURCE,c)
        self.assertEqual(len(jobs),3)
        self.assertEqual(c.get.call_args_list[1].kwargs['params'],dict(skip=2,take=2,count=3,s='abcdef1234'))
        self.assertTrue(all(x.kwargs['respect_robots'] for x in c.get.call_args_list))
        self.assertEqual(jobs[0]['posting_date'],'2026-09-01')
        self.assertEqual(jobs[0]['evidence']['posting_date_kind'],'employer_programme_opening_date')
        self.assertTrue(all(classify(j,{})['decision']=='exclude' for j in jobs))

    def test_pagination_repetition_truncation_and_unknown_rows_fail(self):
        for following in ([card(1)],[],[card(3),card(4)],['<li>Unknown row</li>'],{'results':[]}):
            with self.subTest(following=following),self.assertRaises(SourceError):
                collect(SOURCE,client(response(index([card(1),card(2)],3)),response(data=following)))

    def test_explicit_empty_directory_and_missing_grid_differ(self):
        self.assertEqual(collect(SOURCE,client(response(index([],0,initial=20)))),[])
        with self.assertRaises(SourceError):
            collect(SOURCE,client(response('<h1>Careers</h1>')))

    def test_us_internship_details_and_product_manager_inclusion(self):
        c=client(response(index([card(1234567,'Product Manager Internship',kind='Internship Programme')],1)),
                 response(detail(),at=url()))
        job=collect(SOURCE,c)[0]
        self.assertEqual(job['description'],DESCRIPTION)
        self.assertEqual(identity(job['application_url']),'1234567')
        self.assertEqual(job['evidence']['description_kind'],'employer_public_detail')
        self.assertEqual(classify(job,{'countries':['US'],'student_years':['junior'],'degrees':['bachelor']})['decision'],'include')

    def test_conflicting_graduate_programme_and_intern_title_stays_ambiguous(self):
        job={'title':'Software Engineer Intern','employment_type':'Graduate Programme','employer':'HSBC',
             'description':DESCRIPTION,'location':'New York, USA'}
        result=classify(job,{'countries':['US']})
        self.assertEqual(result['decision'],'ambiguous')
        self.assertTrue(any('Conflicting' in r for r in result['reasons']))

    def test_details_require_matching_identity_title_application_and_availability(self):
        variants=[response(detail(),at=url(9999999)),response(detail('Office Administrator'),at=url()),
                  response(detail(application='/talentcommunity/apply/9999999/'),at=url()),
                  response(detail()+'<p>This job is closed</p>',at=url())]
        for bad in variants:
            with self.assertRaises(SourceError):
                collect(SOURCE,client(response(index([card(1234567,'Product Manager Internship',kind='Internship Programme')],1)),bad))

    def test_foreign_internship_stays_outside_us_filter(self):
        jobs=collect(SOURCE,client(response(index([card(1234567,'Software Engineer Internship','Singapore','Internship Programme')],1))))
        self.assertEqual(classify(jobs[0],{'countries':['US']})['decision'],'exclude')

    def test_url_aliases_keep_distinct_jobs_and_reject_conflicting_ids(self):
        self.assertEqual(url_identity(url()),url_identity('https://apply.careers.hsbc.com/talentcommunity/apply/1234567/?locale=en_GB'))
        self.assertNotEqual(url_identity(url()),url_identity(url(2222222)))
        for bad in [url()+'&jobId=2222222',url().replace('https:','http:'),url().replace('hsbc.com','different.example')]:
            self.assertIsNone(identity(bad))

    def test_alias_migration_and_restart_preserve_existing_job(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'jobs.sqlite3';store=Store(path)
            job=collect(SOURCE,client(response(index([card(1234567)],1))))[0]
            with store.transaction():
                jid,_=store.upsert_job('feed',dict(job,source_id='feed-1'),{'decision':'exclude'},None,baseline=True)
                saved=store.rows('SELECT id,first_seen,baseline FROM jobs')[0]
                store.db.execute("DELETE FROM identities WHERE identity LIKE 'url:hsbc:%'")
                store.db.execute("DELETE FROM meta WHERE key='hsbc_url_aliases_v1'")
            store.close();store=Store(path)
            try:
                with store.transaction():
                    other,_=store.upsert_job('hsbc-campus',job,{'decision':'exclude'},None)
                self.assertEqual(other,jid)
                self.assertEqual(store.rows('SELECT id,first_seen,baseline FROM jobs'),[saved])
            finally:
                store.close()


if __name__=='__main__':
    unittest.main()
