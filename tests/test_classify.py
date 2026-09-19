"""Focused regressions against the reviewed commit and the replacement classifier."""
import ast
import subprocess
import unittest
from pathlib import Path

from internship_watch.classify import classify


def baseline_matcher():
    source = (Path(__file__).parent / "fixtures" / "reviewed_scrape.py.txt").read_text(encoding="utf-8")
    tree = ast.parse(source)
    nodes = [n for n in tree.body if
             isinstance(n, ast.FunctionDef) and n.name == "matches_keywords" or
             isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and
                 t.id in {"INCLUDE_KEYWORDS", "EXCLUDE_KEYWORDS"} for t in n.targets)]
    namespace = {}
    exec(compile(ast.Module(body=nodes, type_ignores=[]), "reviewed-scrape.py", "exec"), namespace)
    return namespace["matches_keywords"]


class BaselineDefects(unittest.TestCase):
    """Record the verified old behavior without importing network side effects."""
    def test_confirmed_fulltime_leak(self):
        self.assertTrue(baseline_matcher()("Software Engineer"))

    def test_confirmed_hardware_leak(self):
        self.assertTrue(baseline_matcher()("Hardware Engineering Intern"))

    def test_confirmed_product_manager_omission(self):
        self.assertFalse(baseline_matcher()("Product Manager Intern"))


class ClassificationTests(unittest.TestCase):
    def classify(self, title, description="", filters=None, **kwargs):
        return classify(dict(title=title, description=description, employer="Example", **kwargs), filters or {})

    def test_no_internship_evidence(self):
        self.assertEqual(self.classify("Software Engineer", employment_type="FullTime")["decision"], "exclude")

    def test_ambiguous_without_employment_evidence(self):
        self.assertEqual(self.classify("Software Engineer")["decision"], "ambiguous")

    def test_product_manager_included(self):
        self.assertEqual(self.classify("Product Manager Intern")["category"], "product_management")
        self.assertEqual(self.classify("Product Manager Intern")["decision"], "include")

    def test_hardware_excluded(self):
        self.assertEqual(self.classify("Hardware Engineering Intern")["decision"], "exclude")
        self.assertEqual(self.classify("Engineering Intern", "Responsibilities: Design analog circuits and PCB layouts.")["decision"], "exclude")

    def test_software_at_hardware_company_retained(self):
        result = classify(dict(title="AI Engineering Intern", employer="NVIDIA", description="We make GPUs and hardware. Responsibilities: Train machine learning models and develop Python software."), {})
        self.assertEqual(result["decision"], "include")
        self.assertEqual(self.classify("Software Intern", "Responsibilities: Develop Python software to test analog circuits.")["decision"], "include")

    def test_fulltime_hours_not_fulltime_career(self):
        self.assertEqual(self.classify("Software Engineering Intern", "This is a full-time internship, 40 hours per week.", employment_type="FullTime")["decision"], "include")

    def test_new_grad_is_not_internship(self):
        self.assertEqual(self.classify("Software Engineer New Graduate", "Previous internship experience desired.")["decision"], "exclude")

    def test_international_is_not_intern(self):
        self.assertNotEqual(self.classify("International Software Engineer")["decision"], "include")

    def test_experience_mention_is_not_internship_evidence(self):
        self.assertNotEqual(self.classify("Data Scientist", "Prior internship experience is preferred.")["decision"], "include")

    def test_negated_internship(self):
        self.assertEqual(self.classify("Software Engineer", "This is not an internship.")["decision"], "exclude")

    def test_structured_internship_and_research_description(self):
        self.assertEqual(self.classify("Student Researcher", "Research machine learning models and artificial intelligence.", employment_type="Intern")["category"], "ml_ai")

    def test_all_role_families(self):
        cases = {"Backend Intern":"software_engineering", "Full-Stack Intern":"software_engineering", "Data Analyst Intern":"data_analysis", "Data Engineer Intern":"data_engineering", "Data Scientist Intern":"data_science", "Machine Learning Research Intern":"ml_ai", "Quantitative Trading Intern":"quantitative", "Quant Developer Intern":"quantitative", "Quantitative Research Intern":"quantitative", "Algorithmic Trading Intern":"quantitative", "Product Management Internship":"product_management"}
        for title, category in cases.items():
            with self.subTest(title=title):
                result = self.classify(title)
                self.assertEqual(result["decision"], "include")
                self.assertEqual(result["category"], category)

    def test_geography_remote_season_and_eligibility(self):
        self.assertEqual(self.classify("Software Intern Summer 2027", location="Toronto, Canada", filters={"countries":["US"]})["decision"], "exclude")
        self.assertEqual(self.classify("Software Intern", location="Remote", filters={"countries":["US"]})["decision"], "ambiguous")
        self.assertEqual(self.classify("Software Intern", location="United States", filters={"remote_policy":"only"})["decision"], "ambiguous")
        self.assertEqual(self.classify("Software Intern Summer 2027", filters={"seasons":["summer2027"]})["decision"], "include")
        self.assertEqual(self.classify("Software Intern Summer 2026", filters={"seasons":["summer2027"]})["decision"], "exclude")
        self.assertEqual(self.classify("Software Intern", "Must be pursuing a PhD, graduating in 2028.", filters={"degrees":["bachelor"]})["decision"], "exclude")
        result = self.classify("Software Intern", "Must be pursuing a Bachelor's degree, graduating between 2027 and 2029.", filters={"graduation_years":[2028]})
        self.assertEqual(result["decision"], "include")
        self.assertEqual(result["eligibility"]["graduation_years"], [2027,2028,2029])

    def test_coop_explicit(self):
        self.assertEqual(self.classify("Software Engineering Co-op", filters={"include_coop":False})["decision"], "exclude")
        self.assertEqual(self.classify("Software Engineering Co-op", filters={"include_coop":True})["decision"], "include")

    def test_category_filter(self):
        self.assertEqual(self.classify("Quantitative Research Intern", filters={"categories":["software_engineering"]})["decision"], "exclude")

    def test_unknown_policy_cannot_invent_internship(self):
        self.assertEqual(self.classify("Software Engineer", filters={"unknown_policy":"include"})["decision"], "ambiguous")

    def test_junior_program_restrictions(self):
        filters = {"student_years":["junior"], "allow_unstated_eligibility":True}
        self.assertEqual(self.classify("Software Intern", "This program is open to freshman and sophomore students only.", filters)["decision"], "exclude")
        self.assertEqual(self.classify("Software Intern", "Open to sophomore and junior students.", filters)["decision"], "include")
        self.assertEqual(self.classify("Software Intern", filters=filters)["decision"], "include")

    def test_research_program_explicit_opt_in(self):
        job = {"title":"Anthropic AI Safety Fellow", "description":"This fellowship offers a research program in AI safety.", "employment_type":"FullTime"}
        self.assertEqual(classify(job,{})["decision"], "exclude")
        result = classify(job,{"include_research_programs":True})
        self.assertEqual(result["decision"], "include")
        self.assertEqual(result["opportunity_kind"], "research_program")
        self.assertEqual(classify(dict(job,title="AI Research Scientist"),{"include_research_programs":True})["decision"], "exclude")
        self.assertEqual(classify(dict(job,title="Research Program Manager"),{"include_research_programs":True})["decision"], "exclude")
        self.assertNotEqual(classify(dict(job,title="Legal Fellow"),{"include_research_programs":True})["decision"], "include")
        self.assertEqual(classify(dict(job,title="Anthropic Fellows Program"),{"include_research_programs":True})["decision"], "include")
        self.assertNotEqual(self.classify("User Research Intern", "Research user experiences for our AI and machine learning software.")["decision"], "include")

    def test_us_cities_states_and_remote(self):
        for location in ["San Francisco, CA", "San Francisco", "NYC", "Chicago, IL", "Remote - United States", "Seattle, WA"]:
            with self.subTest(location=location):
                self.assertEqual(self.classify("Software Intern", location=location,filters={"countries":["US"]})["decision"], "include")
        self.assertEqual(self.classify("Software Intern", location="London, United Kingdom",filters={"countries":["US"]})["decision"], "exclude")

    def test_degree_title_and_source_evidence(self):
        filters = {"degrees":["bachelor"], "allow_unstated_eligibility":True}
        self.assertEqual(self.classify("Machine Learning PhD Intern", filters=filters)["decision"], "exclude")
        self.assertEqual(self.classify("Machine Learning Intern", filters=filters,evidence={"degrees":["PhD"]})["decision"], "exclude")
        self.assertEqual(self.classify("Machine Learning Intern", filters=filters)["decision"], "include")

    def test_no_sponsorship_needed_is_eligible(self):
        self.assertEqual(self.classify("Software Intern", "We cannot provide visa sponsorship.",filters={"requires_sponsorship":False})["decision"], "include")
        self.assertEqual(self.classify("Software Intern", "We cannot provide visa sponsorship.",filters={"requires_sponsorship":True})["decision"], "exclude")

    def test_live_program_false_positives(self):
        filters = {"include_research_programs":True,"degrees":["bachelor"],"allow_unstated_eligibility":True}
        self.assertEqual(self.classify("STEM Fellow", "Research advanced AI models. Education: PhDs and postdoctoral researchers.",filters)["decision"], "exclude")
        self.assertEqual(self.classify("Neurosurgeon Resident", "Perform surgery and work with software engineering and research teams.",filters)["decision"], "exclude")
        self.assertEqual(self.classify("Neurodivergent Fellowship", "Build AI and software. You'll join as a full-time employee with career progression.",filters)["decision"], "exclude")
        self.assertEqual(self.classify("AI Research Fellowship", "You'll join as a full-time employee for 4 months to research AI safety.",filters)["decision"], "include")

    def test_company_filters(self):
        self.assertEqual(self.classify("Software Intern",filters={"companies":["Example"]})["decision"],"include")
        self.assertEqual(self.classify("Software Intern",filters={"companies":["Another"]})["decision"],"exclude")
        self.assertEqual(self.classify("Software Intern",filters={"exclude_companies":["example"]})["decision"],"exclude")

    def test_feed_context_requires_job_evidence(self):
        result = self.classify("Software Engineer",evidence={"feed_internship_context":True})
        self.assertEqual(result["decision"],"ambiguous")
        self.assertTrue(result["positive_opportunity_evidence"])

    def test_citizenship_is_not_work_authorization(self):
        description = "Must be a U.S. citizen. No visa sponsorship is available."
        self.assertEqual(self.classify("Software Intern",description,filters={"requires_sponsorship":False})["decision"],"ambiguous")
        self.assertEqual(self.classify("Software Intern",description,filters={"citizenships":["US"]})["decision"],"include")
        self.assertEqual(self.classify("Software Intern",description,filters={"citizenships":["Canada"]})["decision"],"exclude")
        self.assertEqual(self.classify("Software Intern","US citizenship is required.")["decision"],"ambiguous")
        self.assertEqual(self.classify("Software Intern","US citizens or permanent residents only.")["decision"],"ambiguous")
        self.assertEqual(self.classify("Software Intern","Must be a US citizen or permanent resident.")["decision"],"ambiguous")

    def test_clearance_requirement_and_boilerplate(self):
        self.assertEqual(self.classify("Software Intern","An active security clearance is required.")["decision"],"ambiguous")
        self.assertEqual(self.classify("Software Intern","Must hold an active Secret clearance.",filters={"has_security_clearance":True})["decision"],"include")
        self.assertEqual(self.classify("Software Intern","An active security clearance is required.",filters={"has_security_clearance":False})["decision"],"exclude")
        self.assertEqual(self.classify("Software Intern","Ability to obtain a security clearance is preferred.")["decision"],"include")
        self.assertEqual(self.classify("Software Intern","Must be able to obtain a security clearance.")["decision"],"ambiguous")
        self.assertEqual(self.classify("Software Intern","Must be authorized to work in the US. We do not discriminate based on citizenship or national origin. No sponsorship required.")["decision"],"include")

    def test_trading_needs_quantitative_responsibilities(self):
        result = self.classify("Trading Intern", "You will build analytics dashboards and back-test new trading strategies.")
        self.assertEqual(result["decision"],"include")
        self.assertEqual(result["category"],"quantitative")
        self.assertNotEqual(self.classify("Trading Intern","Handle customer calls and prepare sales presentations.")["decision"],"include")

    def test_negated_and_optional_degrees_are_not_requirements(self):
        filters = {"degrees":["bachelor"],"allow_unstated_eligibility":True,"include_research_programs":True}
        for description in ["No PhD required.","You do not need a PhD.","A PhD is not required.","PhD preferred.","Master's or PhD preferred.","Preferred Qualifications\nPhD in Computer Science."]:
            with self.subTest(description=description):
                result = self.classify("AI Research Fellow",description,filters)
                self.assertEqual(result["decision"],"include")
                self.assertEqual(result["eligibility"]["degrees"],[])
        for description in ["Must be pursuing a PhD.","Required Qualifications\nPhD in computer science."]:
            self.assertEqual(self.classify("AI Research Fellow",description,filters)["decision"],"exclude")
        self.assertEqual(self.classify("AI Research Fellow","Bachelor's OR PhD candidates are eligible.",filters)["decision"],"include")
        self.assertEqual(self.classify("AI Research Fellow","PhD preferred but a Bachelor's degree is required.",filters)["decision"],"include")
        self.assertEqual(self.classify("AI Research Fellow","No PhD required.",filters,evidence={"degrees":["PhD"]})["decision"],"exclude")

    def test_live_hardware_responsibilities_not_company_name(self):
        self.assertEqual(self.classify("Device Engineering Intern","Responsibilities: Assist engineers in DC/RF test, measurement, and data analysis. Developing and improving semiconductor fabrication flows and processes.")["decision"],"exclude")
        self.assertEqual(self.classify("RFIC Design Engineer Intern","Design RF and analog/mixed-signal electronic integrated circuits. Knowledge of Python software preferred.")["decision"],"exclude")
        self.assertEqual(self.classify("Test Lab Engineer Co-op","Duties: Support hardware testing on development programs. Interface with software and hardware design engineers. Assemble and modify electronic controls for testing.")["decision"],"exclude")
        self.assertEqual(self.classify("Mechatronics Engineering Co-op","Conduct hands-on hardware debugging of ADAS ECU prototypes. Assist software engineering teams.")["decision"],"exclude")
        self.assertEqual(self.classify("Component Engineering Intern","Perform component evaluations and qualifications. Demonstrate working knowledge of electronic component types. Software degree accepted.")["decision"],"exclude")
        self.assertEqual(self.classify("Mixed Signal Engineer Intern","Develop and validate machine learning models for analog design automation. Perform analog and mixed-signal circuit analysis, design, simulation, and verification.")["decision"],"ambiguous")
        self.assertEqual(self.classify("Device Software Engineering Intern","Develop Python software for device telemetry. Analyze data from semiconductor devices.")["decision"],"include")
        self.assertEqual(self.classify("AI Engineering Intern","Develop and validate machine learning models to optimize semiconductor fabrication.")["decision"],"include")

    def test_student_year_vs_senior_colleagues_and_rising_seniors(self):
        filters = {"student_years":["junior"],"allow_unstated_eligibility":True}
        self.assertEqual(self.classify("Software Intern","Students will work alongside senior engineers and senior research scientists.",filters)["decision"],"include")
        self.assertEqual(self.classify("Software Intern","Eligible applicants must be senior students.",filters)["decision"],"exclude")
        result = self.classify("Software Intern","Open to students who are rising seniors.",filters)
        self.assertEqual(result["decision"],"include")
        self.assertEqual(result["eligibility"]["student_years"],["junior"])
        self.assertEqual(result["eligibility"]["student_year_context"][0]["current_student_year"],"junior")

    def test_degree_dropdown_is_not_job_eligibility(self):
        filters = {"degrees":["bachelor"],"allow_unstated_eligibility":True}
        description = "Robotics Research Intern. Submit your application Resume/CV ATTACH RESUME/CV. Level of Education What degree are you currently enrolled in? PhD Master's Bachelor's Other Work Eligibility."
        result = self.classify("AI Research Intern",description,filters,evidence={"degrees":["PhD"]})
        self.assertEqual(result["decision"],"exclude")
        self.assertEqual(result["eligibility"]["degrees"],["phd"])
        result = self.classify("Software Intern","Responsibilities: build software. Voluntary Self-Identification of Disability. Nervous system condition, for example multiple sclerosis (MS).",filters)
        self.assertEqual(result["decision"],"include")
        self.assertEqual(result["eligibility"]["degrees"],[])

    def test_graduate_title_can_explicitly_allow_current_students(self):
        result = self.classify("Software Graduate Intern - Autonomous Lab","Preferred Qualifications: Recent graduate (BS/MS) or current student in Computer Science. Develop Python software.",{"degrees":["bachelor"],"student_years":["junior"],"allow_unstated_eligibility":True})
        self.assertEqual(result["decision"],"include")
