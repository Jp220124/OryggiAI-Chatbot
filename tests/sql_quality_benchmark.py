"""
SQL Quality Testing Benchmark
Tests the chatbot's SQL generation accuracy against known correct queries.

This benchmark validates:
1. Correct table/view selection (VIEW-FIRST architecture)
2. Proper column usage
3. Correct JOINs (or preferably, view usage)
4. Appropriate filters (especially Active=1 for employees)
5. SQL syntax correctness
"""

import asyncio
import json
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from datetime import datetime
from loguru import logger

from app.database import db_manager


@dataclass
class BenchmarkTestCase:
    """Single benchmark test case"""
    id: str
    category: str
    question: str
    expected_tables: List[str]  # Tables/views that SHOULD be used
    forbidden_tables: List[str]  # Tables that should NOT be used
    required_columns: List[str]  # Columns that must appear
    required_filters: List[str]  # Filter patterns that must appear
    expected_result_type: str  # 'count', 'list', 'aggregate'
    difficulty: str  # 'easy', 'medium', 'hard'
    notes: str = ""


# =============================================================================
# BENCHMARK TEST CASES
# =============================================================================

BENCHMARK_CASES: List[BenchmarkTestCase] = [

    # ==================== EMPLOYEE QUERIES (VIEW-FIRST) ====================

    BenchmarkTestCase(
        id="emp_001",
        category="employee_count",
        question="How many active employees are there?",
        expected_tables=["vw_EmployeeMaster_Vms", "AllEmployeeUnion"],
        forbidden_tables=["EmployeeMaster"],  # Should use view
        required_columns=["COUNT"],
        required_filters=["Active = 1", "Active=1"],
        expected_result_type="count",
        difficulty="easy",
        notes="Must use view, not base table. Must filter Active=1."
    ),

    BenchmarkTestCase(
        id="emp_002",
        category="employee_list",
        question="List employees in the IT department",
        expected_tables=["vw_EmployeeMaster_Vms"],
        forbidden_tables=["EmployeeMaster", "DeptMaster"],  # View has Dname
        required_columns=["EmpName", "Dname"],
        required_filters=["Active = 1", "IT", "LIKE"],
        expected_result_type="list",
        difficulty="easy",
        notes="Must use view with Dname column, not JOIN to DeptMaster."
    ),

    BenchmarkTestCase(
        id="emp_003",
        category="employee_count",
        question="How many employees are in each department?",
        expected_tables=["vw_EmployeeMaster_Vms"],
        forbidden_tables=["EmployeeMaster", "DeptMaster"],
        required_columns=["Dname", "COUNT"],
        required_filters=["Active = 1", "GROUP BY"],
        expected_result_type="aggregate",
        difficulty="easy",
        notes="Must GROUP BY Dname from view."
    ),

    BenchmarkTestCase(
        id="emp_004",
        category="employee_search",
        question="Find employee with code EMP001",
        expected_tables=["vw_EmployeeMaster_Vms"],
        forbidden_tables=[],
        required_columns=["CorpEmpCode"],
        required_filters=["EMP001"],
        expected_result_type="list",
        difficulty="easy",
        notes="Direct lookup by CorpEmpCode."
    ),

    BenchmarkTestCase(
        id="emp_005",
        category="employee_stats",
        question="Show employee count by designation",
        expected_tables=["vw_EmployeeMaster_Vms"],
        forbidden_tables=["DesignationMaster"],
        required_columns=["DesName", "COUNT"],
        required_filters=["Active = 1", "GROUP BY"],
        expected_result_type="aggregate",
        difficulty="easy",
        notes="DesName available in view."
    ),

    BenchmarkTestCase(
        id="emp_006",
        category="employee_org",
        question="How many male and female employees are there?",
        expected_tables=["vw_EmployeeMaster_Vms"],
        forbidden_tables=[],
        required_columns=["Sex", "COUNT"],
        required_filters=["Active = 1", "GROUP BY"],
        expected_result_type="aggregate",
        difficulty="medium",
        notes="Sex=1 is Male, Sex=0 is Female. May need CASE statement."
    ),

    BenchmarkTestCase(
        id="emp_007",
        category="employee_list",
        question="Show employees who joined this year",
        expected_tables=["vw_EmployeeMaster_Vms"],
        forbidden_tables=[],
        required_columns=["DateofJoin"],
        required_filters=["Active = 1", "YEAR", "GETDATE"],
        expected_result_type="list",
        difficulty="medium",
        notes="Must use YEAR(DateofJoin) = YEAR(GETDATE())."
    ),

    # ==================== ATTENDANCE QUERIES ====================

    BenchmarkTestCase(
        id="att_001",
        category="attendance",
        question="Show attendance for today",
        expected_tables=["vw_RawPunchDetail"],
        forbidden_tables=["MachineRawPunch", "EmployeeMaster"],
        required_columns=["ATDate", "EmpName"],
        required_filters=["GETDATE", "CAST"],
        expected_result_type="list",
        difficulty="easy",
        notes="Must use view. Filter by ATDate = CAST(GETDATE() AS DATE)."
    ),

    BenchmarkTestCase(
        id="att_002",
        category="attendance",
        question="Which employees came late today (after 9:30 AM)?",
        expected_tables=["vw_RawPunchDetail"],
        forbidden_tables=["MachineRawPunch"],
        required_columns=["InTime", "EmpName"],
        required_filters=["09:30", "GETDATE"],
        expected_result_type="list",
        difficulty="medium",
        notes="InTime > '09:30:00' filter required."
    ),

    BenchmarkTestCase(
        id="att_003",
        category="attendance",
        question="Show attendance summary for the last 7 days",
        expected_tables=["vw_RawPunchDetail"],
        forbidden_tables=["MachineRawPunch"],
        required_columns=["ATDate"],
        required_filters=["DATEADD", "7"],
        expected_result_type="aggregate",
        difficulty="medium",
        notes="Use DATEADD to calculate date range."
    ),

    # ==================== ACCESS CONTROL QUERIES ====================

    BenchmarkTestCase(
        id="acc_001",
        category="access_control",
        question="Which employees have access to terminal 101?",
        expected_tables=["View_Employee_Terminal_Authentication_Relation"],
        forbidden_tables=["Authentication_Terminal"],
        required_columns=["TerminalID"],
        required_filters=["101"],
        expected_result_type="list",
        difficulty="easy",
        notes="Must use access relation view."
    ),

    BenchmarkTestCase(
        id="acc_002",
        category="access_control",
        question="Show all online terminals",
        expected_tables=["Vw_TerminalDetail_VMS"],
        forbidden_tables=["MachineMaster"],
        required_columns=["Status"],
        required_filters=["Online"],
        expected_result_type="list",
        difficulty="easy",
        notes="Use terminal view for status info."
    ),

    # ==================== VISITOR QUERIES ====================

    BenchmarkTestCase(
        id="vis_001",
        category="visitor",
        question="Show all visitors enrolled today",
        expected_tables=["View_Visitor_EnrollmentDetail", "vw_VisitorBasicDetail"],
        forbidden_tables=["VisitorMaster"],
        required_columns=[],
        required_filters=["GETDATE"],
        expected_result_type="list",
        difficulty="easy",
        notes="Use visitor view."
    ),

    # ==================== COMPLEX QUERIES ====================

    BenchmarkTestCase(
        id="complex_001",
        category="complex",
        question="Show total employee count (including deleted employees)",
        expected_tables=["AllEmployeeUnion"],
        forbidden_tables=["EmployeeMaster"],
        required_columns=["COUNT"],
        required_filters=[],  # No Active filter - we want ALL
        expected_result_type="count",
        difficulty="medium",
        notes="Must use AllEmployeeUnion view for total count."
    ),

    BenchmarkTestCase(
        id="complex_002",
        category="complex",
        question="Show employees with their department and branch names",
        expected_tables=["vw_EmployeeMaster_Vms"],
        forbidden_tables=["DeptMaster", "BranchMaster"],  # Should NOT JOIN manually
        required_columns=["EmpName", "Dname", "BranchName"],
        required_filters=["Active = 1"],
        expected_result_type="list",
        difficulty="medium",
        notes="View has all hierarchy pre-joined. No manual JOINs needed."
    ),

    BenchmarkTestCase(
        id="complex_003",
        category="complex",
        question="Show attendance for IT department employees today",
        expected_tables=["vw_RawPunchDetail"],
        forbidden_tables=["MachineRawPunch", "DeptMaster"],
        required_columns=["Dname", "ATDate", "EmpName"],
        required_filters=["IT", "GETDATE"],
        expected_result_type="list",
        difficulty="hard",
        notes="vw_RawPunchDetail has Dname. No need to JOIN."
    ),
]


# =============================================================================
# BENCHMARK RUNNER
# =============================================================================

class SQLQualityBenchmark:
    """
    Runs SQL quality benchmark tests
    """

    def __init__(self):
        self.results: List[Dict[str, Any]] = []
        self.passed = 0
        self.failed = 0

    def evaluate_sql(self, generated_sql: str, test_case: BenchmarkTestCase) -> Dict[str, Any]:
        """
        Evaluate generated SQL against test case expectations

        Args:
            generated_sql: The SQL query generated by the chatbot
            test_case: The benchmark test case

        Returns:
            Evaluation results
        """
        sql_upper = generated_sql.upper()
        issues = []
        score = 100

        # Check 1: Correct tables/views used
        tables_found = []
        for table in test_case.expected_tables:
            if table.upper() in sql_upper:
                tables_found.append(table)

        if not tables_found:
            issues.append(f"Expected one of {test_case.expected_tables} but none found")
            score -= 30

        # Check 2: Forbidden tables not used (use word boundary matching)
        import re
        for table in test_case.forbidden_tables:
            # Use word boundary to avoid matching substrings (e.g., "EmployeeMaster" in "vw_EmployeeMaster_Vms")
            pattern = r'\b' + re.escape(table) + r'\b'
            if re.search(pattern, generated_sql, re.IGNORECASE):
                # Additional check: make sure it's not part of a view name
                view_pattern = r'vw_.*' + re.escape(table) + r'|View_.*' + re.escape(table)
                if not re.search(view_pattern, generated_sql, re.IGNORECASE):
                    issues.append(f"FORBIDDEN table used: {table} (should use view instead)")
                    score -= 25

        # Check 3: Required columns present
        for col in test_case.required_columns:
            if col.upper() not in sql_upper:
                issues.append(f"Missing required column/keyword: {col}")
                score -= 10

        # Check 4: Required filters present
        for filter_pattern in test_case.required_filters:
            if filter_pattern.upper() not in sql_upper.replace(" ", ""):
                # Try with spaces
                if filter_pattern.upper() not in sql_upper:
                    issues.append(f"Missing required filter: {filter_pattern}")
                    score -= 15

        # Check 5: Basic SQL syntax
        if "SELECT" not in sql_upper:
            issues.append("Missing SELECT keyword")
            score -= 20

        if "FROM" not in sql_upper:
            issues.append("Missing FROM keyword")
            score -= 20

        # Determine pass/fail
        # Pass if score >= 70 and no forbidden tables were actually used (no issues about forbidden tables)
        forbidden_used = any("FORBIDDEN" in issue for issue in issues)
        passed = score >= 70 and not forbidden_used

        return {
            "test_id": test_case.id,
            "category": test_case.category,
            "question": test_case.question,
            "generated_sql": generated_sql,
            "score": max(0, score),
            "passed": passed and score >= 70,
            "issues": issues,
            "tables_found": tables_found,
            "difficulty": test_case.difficulty,
            "notes": test_case.notes
        }

    def run_benchmark(self, sql_generator_func) -> Dict[str, Any]:
        """
        Run full benchmark suite

        Args:
            sql_generator_func: Function that takes a question and returns SQL

        Returns:
            Benchmark results summary
        """
        self.results = []
        self.passed = 0
        self.failed = 0

        for test_case in BENCHMARK_CASES:
            try:
                # Generate SQL for the question
                generated_sql = sql_generator_func(test_case.question)

                # Evaluate the result
                result = self.evaluate_sql(generated_sql, test_case)
                self.results.append(result)

                if result["passed"]:
                    self.passed += 1
                else:
                    self.failed += 1

            except Exception as e:
                self.results.append({
                    "test_id": test_case.id,
                    "category": test_case.category,
                    "question": test_case.question,
                    "error": str(e),
                    "passed": False,
                    "score": 0
                })
                self.failed += 1

        # Calculate summary
        total = len(BENCHMARK_CASES)
        pass_rate = (self.passed / total * 100) if total > 0 else 0
        avg_score = sum(r.get("score", 0) for r in self.results) / total if total > 0 else 0

        # Category breakdown
        category_stats = {}
        for result in self.results:
            cat = result["category"]
            if cat not in category_stats:
                category_stats[cat] = {"passed": 0, "failed": 0, "total": 0}
            category_stats[cat]["total"] += 1
            if result["passed"]:
                category_stats[cat]["passed"] += 1
            else:
                category_stats[cat]["failed"] += 1

        return {
            "total_tests": total,
            "passed": self.passed,
            "failed": self.failed,
            "pass_rate": round(pass_rate, 1),
            "average_score": round(avg_score, 1),
            "category_breakdown": category_stats,
            "results": self.results,
            "timestamp": datetime.now().isoformat()
        }

    def print_report(self, summary: Dict[str, Any]):
        """Print formatted benchmark report"""
        print("=" * 80)
        print("SQL QUALITY BENCHMARK REPORT")
        print("=" * 80)
        print()
        print(f"Total Tests: {summary['total_tests']}")
        print(f"Passed: {summary['passed']} ({summary['pass_rate']}%)")
        print(f"Failed: {summary['failed']}")
        print(f"Average Score: {summary['average_score']}/100")
        print()
        print("Category Breakdown:")
        print("-" * 40)
        for cat, stats in summary["category_breakdown"].items():
            pct = (stats["passed"] / stats["total"] * 100) if stats["total"] > 0 else 0
            print(f"  {cat}: {stats['passed']}/{stats['total']} ({pct:.0f}%)")
        print()
        print("Failed Tests:")
        print("-" * 40)
        for result in summary["results"]:
            if not result["passed"]:
                print(f"\n  [{result['test_id']}] {result['question']}")
                if "error" in result:
                    print(f"    ERROR: {result['error']}")
                else:
                    print(f"    Score: {result['score']}")
                    print(f"    Issues: {', '.join(result['issues'])}")
        print()
        print("=" * 80)


# =============================================================================
# STANDALONE TEST FUNCTION
# =============================================================================

def test_sql_against_benchmark(sql: str, test_id: str) -> Dict[str, Any]:
    """
    Test a single SQL query against a specific benchmark case

    Args:
        sql: The generated SQL query
        test_id: The test case ID (e.g., 'emp_001')

    Returns:
        Evaluation result
    """
    benchmark = SQLQualityBenchmark()

    # Find the test case
    test_case = None
    for tc in BENCHMARK_CASES:
        if tc.id == test_id:
            test_case = tc
            break

    if not test_case:
        return {"error": f"Test case {test_id} not found"}

    return benchmark.evaluate_sql(sql, test_case)


def get_benchmark_questions() -> List[Dict[str, str]]:
    """Get all benchmark questions for testing"""
    return [
        {
            "id": tc.id,
            "category": tc.category,
            "question": tc.question,
            "difficulty": tc.difficulty
        }
        for tc in BENCHMARK_CASES
    ]


# =============================================================================
# MAIN (for direct testing)
# =============================================================================

if __name__ == "__main__":
    print("SQL Quality Benchmark - Test Cases")
    print("=" * 60)

    for tc in BENCHMARK_CASES:
        print(f"\n[{tc.id}] {tc.category} ({tc.difficulty})")
        print(f"  Q: {tc.question}")
        print(f"  Expected tables: {tc.expected_tables}")
        print(f"  Forbidden: {tc.forbidden_tables}")

    print(f"\nTotal test cases: {len(BENCHMARK_CASES)}")
