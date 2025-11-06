#!/usr/bin/env python3
"""
Systematic Evaluation of OSS Governance Chatbot
Tests queries across all categories and verifies accuracy
"""
import requests
import json
import pandas as pd
from typing import Dict, List, Tuple
import time

API_BASE = "http://localhost:8000"
PROJECT_ID = "keras-team-keras-io"

class ChatbotEvaluator:
    def __init__(self):
        self.results = []
        self.issues_df = None
        self.commits_df = None
        self.load_ground_truth()

    def load_ground_truth(self):
        """Load actual CSV data for verification"""
        try:
            self.issues_df = pd.read_csv('../data/scraped/keras-io/keras-io_issues.csv')
            print(f"✓ Loaded {len(self.issues_df)} issues for verification")
        except Exception as e:
            print(f"⚠ Could not load issues CSV: {e}")

        try:
            self.commits_df = pd.read_csv('../data/scraped/keras-io/keras-io_commits.csv')
            print(f"✓ Loaded {len(self.commits_df)} commits for verification")
        except Exception as e:
            print(f"⚠ Could not load commits CSV: {e}")

    def query_chatbot(self, question: str) -> Dict:
        """Send query to chatbot and get response"""
        try:
            response = requests.post(
                f"{API_BASE}/api/query",
                json={"query": question, "project_id": PROJECT_ID},
                timeout=30
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            return {"error": str(e)}

    def verify_issue_count(self, response: Dict, expected_key: str = None) -> Tuple[bool, str]:
        """Verify issue count against ground truth"""
        if self.issues_df is None:
            return False, "No ground truth data"

        response_text = response.get('response', '').lower()

        # Extract counts from response
        if expected_key == "open":
            actual_count = len(self.issues_df[self.issues_df['issue_state'].str.lower() == 'open'])
            if str(actual_count) in response_text or f"{actual_count} open" in response_text:
                return True, f"Correct: {actual_count} open issues"
            else:
                return False, f"Expected {actual_count} open issues"

        elif expected_key == "closed":
            actual_count = len(self.issues_df[self.issues_df['issue_state'].str.lower() == 'closed'])
            if str(actual_count) in response_text:
                return True, f"Correct: {actual_count} closed issues"
            else:
                return False, f"Expected {actual_count} closed issues"

        elif expected_key == "total":
            actual_count = len(self.issues_df)
            if str(actual_count) in response_text:
                return True, f"Correct: {actual_count} total issues"
            else:
                return False, f"Expected {actual_count} total issues"

        return None, "Manual verification needed"

    def verify_commit_count(self, response: Dict) -> Tuple[bool, str]:
        """Verify commit count against ground truth"""
        if self.commits_df is None:
            return False, "No ground truth data"

        response_text = response.get('response', '').lower()
        actual_count = len(self.commits_df)

        if str(actual_count) in response_text:
            return True, f"Correct: {actual_count} total commits"
        else:
            return False, f"Expected {actual_count} total commits"

    def verify_top_contributors(self, response: Dict, top_n: int = 5) -> Tuple[bool, str]:
        """Verify top contributors list"""
        if self.commits_df is None:
            return False, "No ground truth data"

        # Get actual top contributors
        top_contributors = self.commits_df['name'].value_counts().head(top_n)
        response_text = response.get('response', '')

        # Check if top contributor is mentioned
        top_contributor = top_contributors.index[0]
        if top_contributor.lower() in response_text.lower():
            return True, f"Contains top contributor: {top_contributor}"
        else:
            return False, f"Expected to see {top_contributor}"

    def evaluate_query(self, category: str, question: str, verification_type: str = None, **verify_kwargs):
        """Evaluate a single query"""
        print(f"\n{'='*80}")
        print(f"Category: {category}")
        print(f"Question: {question}")
        print(f"{'='*80}")

        start_time = time.time()
        response = self.query_chatbot(question)
        elapsed_time = time.time() - start_time

        if "error" in response:
            print(f"❌ ERROR: {response['error']}")
            self.results.append({
                'category': category,
                'question': question,
                'status': 'ERROR',
                'response': response['error'],
                'verified': False,
                'time_ms': elapsed_time * 1000
            })
            return

        intent = response.get('metadata', {}).get('intent', 'UNKNOWN')
        answer = response.get('response', '')
        sources = len(response.get('sources', []))

        print(f"Intent: {intent}")
        print(f"Response: {answer[:300]}...")
        print(f"Sources: {sources} documents")
        print(f"Time: {elapsed_time:.2f}s")

        # Verification
        verified = None
        verification_msg = "Not verified"

        if verification_type == "issue_count":
            verified, verification_msg = self.verify_issue_count(response, **verify_kwargs)
        elif verification_type == "commit_count":
            verified, verification_msg = self.verify_commit_count(response)
        elif verification_type == "top_contributors":
            verified, verification_msg = self.verify_top_contributors(response, **verify_kwargs)

        if verified is not None:
            status = "✅ PASS" if verified else "❌ FAIL"
            print(f"\nVerification: {status} - {verification_msg}")
        else:
            status = "⚠ MANUAL"
            print(f"\nVerification: {status} - {verification_msg}")

        self.results.append({
            'category': category,
            'question': question,
            'intent': intent,
            'status': status,
            'response': answer,
            'sources': sources,
            'verified': verified,
            'verification_msg': verification_msg,
            'time_ms': elapsed_time * 1000
        })

    def run_evaluation(self):
        """Run complete evaluation suite"""
        print("\n" + "="*80)
        print("SYSTEMATIC CHATBOT EVALUATION - Keras-io Project")
        print("="*80)

        # ============================================================
        # CATEGORY 1: GOVERNANCE DOCUMENTATION
        # ============================================================
        print("\n\n### CATEGORY 1: GOVERNANCE DOCUMENTATION ###\n")

        self.evaluate_query(
            "Governance",
            "Who maintains the Keras-io project?"
        )

        self.evaluate_query(
            "Governance",
            "What is a tutobook?"
        )

        self.evaluate_query(
            "Governance",
            "How do I contribute to Keras-io?"
        )

        self.evaluate_query(
            "Governance",
            "What kinds of examples does Keras-io emphasize?"
        )

        self.evaluate_query(
            "Governance",
            "How do I submit a new code example?"
        )

        # ============================================================
        # CATEGORY 2: ISSUES QUERIES
        # ============================================================
        print("\n\n### CATEGORY 2: ISSUES QUERIES ###\n")

        self.evaluate_query(
            "Issues",
            "How many issues are open?",
            verification_type="issue_count",
            expected_key="open"
        )

        self.evaluate_query(
            "Issues",
            "How many issues are closed?",
            verification_type="issue_count",
            expected_key="closed"
        )

        self.evaluate_query(
            "Issues",
            "What is the total number of issues?",
            verification_type="issue_count",
            expected_key="total"
        )

        self.evaluate_query(
            "Issues",
            "Show me the latest issues"
        )

        self.evaluate_query(
            "Issues",
            "Who opened the most issues?"
        )

        # ============================================================
        # CATEGORY 3: COMMITS QUERIES
        # ============================================================
        print("\n\n### CATEGORY 3: COMMITS QUERIES ###\n")

        self.evaluate_query(
            "Commits",
            "How many commits are there in total?",
            verification_type="commit_count"
        )

        self.evaluate_query(
            "Commits",
            "Who are the top contributors?",
            verification_type="top_contributors",
            top_n=5
        )

        self.evaluate_query(
            "Commits",
            "Show me the latest commits"
        )

        self.evaluate_query(
            "Commits",
            "Who is the most active contributor?"
        )

        # ============================================================
        # CATEGORY 4: GENERAL QUERIES
        # ============================================================
        print("\n\n### CATEGORY 4: GENERAL QUERIES ###\n")

        self.evaluate_query(
            "General",
            "What is Keras?"
        )

        self.evaluate_query(
            "General",
            "How do I install Keras?"
        )

        # ============================================================
        # GENERATE REPORT
        # ============================================================
        self.generate_report()

    def generate_report(self):
        """Generate evaluation summary report"""
        print("\n\n" + "="*80)
        print("EVALUATION SUMMARY REPORT")
        print("="*80)

        df = pd.DataFrame(self.results)

        # Overall statistics
        total_queries = len(df)
        passed = len(df[df['status'] == '✅ PASS'])
        failed = len(df[df['status'] == '❌ FAIL'])
        manual = len(df[df['status'] == '⚠ MANUAL'])
        errors = len(df[df['status'] == 'ERROR'])

        print(f"\nTotal Queries: {total_queries}")
        print(f"✅ Passed (Verified): {passed} ({passed/total_queries*100:.1f}%)")
        print(f"❌ Failed (Incorrect): {failed} ({failed/total_queries*100:.1f}%)")
        print(f"⚠  Manual Review: {manual} ({manual/total_queries*100:.1f}%)")
        print(f"🔴 Errors: {errors} ({errors/total_queries*100:.1f}%)")

        # By category
        print("\n### Results by Category ###")
        for category in df['category'].unique():
            cat_df = df[df['category'] == category]
            cat_passed = len(cat_df[cat_df['status'] == '✅ PASS'])
            cat_total = len(cat_df)
            print(f"{category}: {cat_passed}/{cat_total} verified correct")

        # Intent classification accuracy
        print("\n### Intent Classification ###")
        for intent in df['intent'].unique():
            count = len(df[df['intent'] == intent])
            print(f"{intent}: {count} queries")

        # Performance
        avg_time = df['time_ms'].mean()
        max_time = df['time_ms'].max()
        print(f"\n### Performance ###")
        print(f"Average Response Time: {avg_time:.0f}ms")
        print(f"Max Response Time: {max_time:.0f}ms")

        # Failed queries
        failed_df = df[df['status'] == '❌ FAIL']
        if len(failed_df) > 0:
            print("\n### Failed Queries (Need Attention) ###")
            for idx, row in failed_df.iterrows():
                print(f"\n- {row['question']}")
                print(f"  Reason: {row['verification_msg']}")

        # Save detailed results
        df.to_csv('chatbot_evaluation_results.csv', index=False)
        print(f"\n✓ Detailed results saved to: chatbot_evaluation_results.csv")


if __name__ == "__main__":
    evaluator = ChatbotEvaluator()
    evaluator.run_evaluation()
