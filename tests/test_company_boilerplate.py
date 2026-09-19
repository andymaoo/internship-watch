import unittest
from internship_watch.classify import classify


class CompanyBoilerplateTests(unittest.TestCase):
    intro = 'Our company builds an AI-powered operating system and uses computer vision and machine learning. '
    def role(self,title,duties):
        return {'title':title,'description':self.intro+' ABOUT THE JOB '+duties,'employer':'Anduril Industries',
                'employment_type':'Intern','location':'Costa Mesa, CA, United States'}

    def test_warhead_coop_is_hardware_not_company_ai(self):
        result=classify(self.role('Winter 2027 Warhead Engineer Co-op',
            'Design warheads and complex ordnance systems. Create prototype parts and assemble explosive test articles. '),{'include_coop':True})
        self.assertEqual(result['decision'],'exclude')
        self.assertTrue(any('Hardware' in reason for reason in result['reasons']))

    def test_generic_engineer_is_not_ai_just_because_company_mentions_it(self):
        result=classify(self.role('Test and Evaluation Engineer Intern',
            'Conduct flight tests at the range. Prepare equipment and plan experimental procedures.'),{})
        self.assertNotEqual(result['decision'],'include')
        self.assertNotEqual(result['category'],'ml_ai')

    def test_software_and_ai_roles_at_hardware_employer_survive(self):
        for title,duties in [('Software Engineering Intern','Build software and backend services.'),
                             ('Research Intern','You will train machine learning models for computer vision research.')]:
            with self.subTest(title=title):
                self.assertEqual(classify(self.role(title,duties),{})['decision'],'include')

    def test_amazon_industrial_coop_does_not_inherit_robotics_ai_intro(self):
        job=self.role('Industrial Development Engineer Intern/Co-op, ROBOTICS', '')
        job['description']=self.intro+' Key job responsibilities Design process path layouts and space utilization using AutoCAD and SolidWorks.'
        result=classify(job,{})
        self.assertNotEqual(result['decision'],'include')
        self.assertNotEqual(result['category'],'ml_ai')

    def test_regular_graduate_job_with_copied_intern_sentence_is_not_included(self):
        job=self.role('Applied Machine Learning Production Engineer Graduate - 2027 Start','')
        job.update(employment_type='Regular',description='As a production engineer intern, you will work on software. As a graduate, you will join the team. Individuals completing or recently completed a bachelor degree.')
        self.assertEqual(classify(job,{})['decision'],'exclude')
        job.update(title='Graduate Research Intern',employment_type='Intern',description='You will build software and research machine learning models.')
        self.assertEqual(classify(job,{})['decision'],'include')

    def test_colleagues_and_mixed_systems_are_not_software_duties(self):
        for title,duties in [
            ('EWIS Harness Engineer Co-op','Design and fabricate wiring harnesses. Work with product managers and software engineers.'),
            ('Test & Evaluation Engineer Co-op','Conduct ground and flight testing. Work with software engineers and product managers.'),
            ('Systems Engineer Co-op','Prepare system design reviews and requirements. Coordinate hardware and software integration.'),
            ('Technical Program Management Co-op','Manage projects across hardware and software teams.')]:
            with self.subTest(title=title):
                self.assertNotEqual(classify(self.role(title,duties),{})['decision'],'include')

    def test_explicit_title_degree_is_not_overridden_by_prior_bachelor(self):
        for title in ['AI Research Intern (PhD)','Product Management MBA Intern']:
            job=self.role(title,'Must have completed a bachelor degree and be enrolled in a graduate program.')
            self.assertEqual(classify(job,{'degrees':['bachelor']})['decision'],'exclude')
