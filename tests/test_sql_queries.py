"""
Comprehensive Test Suite for SQL Query Generation
Tests query success rate with RAG + Few-Shot Learning
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.agents.sql_agent import sql_agent
from app.rag.faiss_manager import faiss_manager
from app.rag.few_shot_manager import few_shot_manager
from app.database import init_database
from loguru import logger
import time

# Test cases covering diverse SQL patterns
TEST_CASES = [
    # Simple Counts
    {
        "id": "test_001",
        "category": "simple_count",
        "question": "How many total employees are in the database?",
        "expected_pattern": "COUNT",
        "expected_tables": ["EmployeeMaster"]
    },
    {
        "id": "test_002",
        "category": "simple_count_filter",
        "question": "How many active employees are there?",
        "expected_pattern": "Active = 1",
        "expected_tables": ["EmployeeMaster"]
    },
    {
        "id": "test_003",
        "category": "simple_count_filter",
        "question": "How many male employees do we have?",
        "expected_pattern": "Sex",
        "expected_tables": ["EmployeeMaster"]
    },

    # Date Operations
    {
        "id": "test_004",
        "category": "date_filter",
        "question": "How many employees joined in the last 30 days?",
        "expected_pattern": "DATEADD",
        "expected_tables": ["EmployeeMaster"]
    },
    {
        "id": "test_005",
        "category": "date_filter",
        "question": "How many employees joined in the last 7 days?",
        "expected_pattern": "DATEADD",
        "expected_tables": ["EmployeeMaster"]
    },
    {
        "id": "test_006",
        "category": "date_range",
        "question": "List employees who joined in 2024",
        "expected_pattern": "2024",
        "expected_tables": ["EmployeeMaster"]
    },
    {
        "id": "test_007",
        "category": "date_extraction",
        "question": "Count employees hired per year",
        "expected_pattern": "YEAR",
        "expected_tables": ["EmployeeMaster"]
    },

    # Simple JOINs
    {
        "id": "test_008",
        "category": "simple_join",
        "question": "Show employee names with their department names",
        "expected_pattern": "JOIN",
        "expected_tables": ["EmployeeMaster", "DeptMaster"]
    },
    {
        "id": "test_009",
        "category": "simple_join",
        "question": "List employees with their section names",
        "expected_pattern": "JOIN",
        "expected_tables": ["EmployeeMaster", "SectionMaster"]
    },
    {
        "id": "test_010",
        "category": "simple_join",
        "question": "Show employees with their designation titles",
        "expected_pattern": "JOIN",
        "expected_tables": ["EmployeeMaster", "DesignationMaster"]
    },

    # GROUP BY and Aggregations
    {
        "id": "test_011",
        "category": "groupby_count",
        "question": "Show top 5 departments with most employees",
        "expected_pattern": "GROUP BY",
        "expected_tables": ["EmployeeMaster"]
    },
    {
        "id": "test_012",
        "category": "groupby_count",
        "question": "Count employees by department",
        "expected_pattern": "GROUP BY",
        "expected_tables": ["EmployeeMaster"]
    },
    {
        "id": "test_013",
        "category": "groupby_count",
        "question": "How many employees in each section?",
        "expected_pattern": "GROUP BY",
        "expected_tables": ["EmployeeMaster"]
    },
    {
        "id": "test_014",
        "category": "having_clause",
        "question": "Which departments have more than 50 employees?",
        "expected_pattern": "HAVING",
        "expected_tables": ["EmployeeMaster"]
    },

    # Multiple JOINs
    {
        "id": "test_015",
        "category": "multiple_joins",
        "question": "Show employees with department, section and designation",
        "expected_pattern": "JOIN",
        "expected_tables": ["EmployeeMaster", "DeptMaster", "SectionMaster", "DesignationMaster"]
    },

    # LIKE pattern matching
    {
        "id": "test_016",
        "category": "like_pattern",
        "question": "Find employees whose name contains 'kumar'",
        "expected_pattern": "LIKE",
        "expected_tables": ["EmployeeMaster"]
    },
    {
        "id": "test_017",
        "category": "like_pattern",
        "question": "Find employees whose name starts with 'A'",
        "expected_pattern": "LIKE",
        "expected_tables": ["EmployeeMaster"]
    },

    # IN clause
    {
        "id": "test_018",
        "category": "in_clause",
        "question": "Show employees in IT, HR and Finance departments",
        "expected_pattern": "IN",
        "expected_tables": ["EmployeeMaster", "DeptMaster"]
    },

    # DISTINCT
    {
        "id": "test_019",
        "category": "distinct",
        "question": "List all unique department codes",
        "expected_pattern": "DISTINCT",
        "expected_tables": ["EmployeeMaster"]
    },
    {
        "id": "test_020",
        "category": "distinct",
        "question": "What are all the unique designations?",
        "expected_pattern": "DISTINCT",
        "expected_tables": ["EmployeeMaster"]
    },

    # ORDER BY
    {
        "id": "test_021",
        "category": "order_by",
        "question": "List employees ordered by join date (newest first)",
        "expected_pattern": "ORDER BY",
        "expected_tables": ["EmployeeMaster"]
    },
    {
        "id": "test_022",
        "category": "order_by",
        "question": "Show employees sorted by name alphabetically",
        "expected_pattern": "ORDER BY",
        "expected_tables": ["EmployeeMaster"]
    },

    # MIN/MAX
    {
        "id": "test_023",
        "category": "min_max",
        "question": "What is the earliest employee join date?",
        "expected_pattern": "MIN",
        "expected_tables": ["EmployeeMaster"]
    },
    {
        "id": "test_024",
        "category": "min_max",
        "question": "What is the latest employee join date?",
        "expected_pattern": "MAX",
        "expected_tables": ["EmployeeMaster"]
    },

    # Complex queries
    {
        "id": "test_025",
        "category": "complex_aggregation",
        "question": "What is the average number of employees per department?",
        "expected_pattern": "AVG",
        "expected_tables": ["EmployeeMaster"]
    },
    {
        "id": "test_026",
        "category": "complex_date",
        "question": "Show employees who joined more than 1 year ago",
        "expected_pattern": "DATEADD",
        "expected_tables": ["EmployeeMaster"]
    },
    {
        "id": "test_027",
        "category": "null_check",
        "question": "Find employees with no email address",
        "expected_pattern": "IS NULL",
        "expected_tables": ["EmployeeMaster"]
    },
    {
        "id": "test_028",
        "category": "case_when",
        "question": "Categorize employees by experience (junior, mid, senior)",
        "expected_pattern": "CASE",
        "expected_tables": ["EmployeeMaster"]
    },
    {
        "id": "test_029",
        "category": "left_join",
        "question": "List all departments including those with no employees",
        "expected_pattern": "LEFT JOIN",
        "expected_tables": ["DeptMaster", "EmployeeMaster"]
    },
    {
        "id": "test_030",
        "category": "not_in",
        "question": "Find employees who are not in the IT department",
        "expected_pattern": "NOT IN",
        "expected_tables": ["EmployeeMaster"]
    },

    # String operations
    {
        "id": "test_031",
        "category": "string_function",
        "question": "Show employee names in uppercase",
        "expected_pattern": "UPPER",
        "expected_tables": ["EmployeeMaster"]
    },
    {
        "id": "test_032",
        "category": "string_function",
        "question": "Show employee names in lowercase",
        "expected_pattern": "LOWER",
        "expected_tables": ["EmployeeMaster"]
    },

    # TOP clause
    {
        "id": "test_033",
        "category": "top_clause",
        "question": "Show first 10 employees",
        "expected_pattern": "TOP",
        "expected_tables": ["EmployeeMaster"]
    },
    {
        "id": "test_034",
        "category": "top_clause",
        "question": "Show 5 most recent hires",
        "expected_pattern": "TOP",
        "expected_tables": ["EmployeeMaster"]
    },

    # Pagination
    {
        "id": "test_035",
        "category": "pagination",
        "question": "Show employees 11-20 when sorted by name",
        "expected_pattern": "OFFSET",
        "expected_tables": ["EmployeeMaster"]
    },

    # Multiple conditions
    {
        "id": "test_036",
        "category": "multiple_conditions",
        "question": "Find active male employees in IT department",
        "expected_pattern": "AND",
        "expected_tables": ["EmployeeMaster"]
    },
    {
        "id": "test_037",
        "category": "multiple_conditions",
        "question": "Show active employees who joined after 2023",
        "expected_pattern": "AND",
        "expected_tables": ["EmployeeMaster"]
    },

    # Gender analysis
    {
        "id": "test_038",
        "category": "gender_analysis",
        "question": "What is the ratio of male to female employees?",
        "expected_pattern": "CASE",
        "expected_tables": ["EmployeeMaster"]
    },
    {
        "id": "test_039",
        "category": "gender_count",
        "question": "Count male and female employees separately",
        "expected_pattern": "CASE",
        "expected_tables": ["EmployeeMaster"]
    },

    # Department-specific queries
    {
        "id": "test_040",
        "category": "dept_specific",
        "question": "How many employees are in HR department?",
        "expected_pattern": "JOIN",
        "expected_tables": ["EmployeeMaster", "DeptMaster"]
    },
    {
        "id": "test_041",
        "category": "dept_specific",
        "question": "List all employees in Finance department",
        "expected_pattern": "JOIN",
        "expected_tables": ["EmployeeMaster", "DeptMaster"]
    },

    # Audit log queries
    {
        "id": "test_042",
        "category": "audit_log",
        "question": "Show last 10 audit logs",
        "expected_pattern": "TOP",
        "expected_tables": ["AuditLog"]
    },
    {
        "id": "test_043",
        "category": "audit_log",
        "question": "Which employee has most audit logs in last 10 days?",
        "expected_pattern": "GROUP BY",
        "expected_tables": ["AuditLog"]
    },
    {
        "id": "test_044",
        "category": "audit_log",
        "question": "Count audit logs per day for last week",
        "expected_pattern": "GROUP BY",
        "expected_tables": ["AuditLog"]
    },

    # Error log queries
    {
        "id": "test_045",
        "category": "error_log",
        "question": "Show last 10 error logs",
        "expected_pattern": "TOP",
        "expected_tables": ["OryggiErrorLog"]
    },
    {
        "id": "test_046",
        "category": "error_log",
        "question": "Count errors by type",
        "expected_pattern": "GROUP BY",
        "expected_tables": ["OryggiErrorLog"]
    },

    # EXISTS subquery
    {
        "id": "test_047",
        "category": "exists",
        "question": "Find departments that have at least one active employee",
        "expected_pattern": "EXISTS",
        "expected_tables": ["DeptMaster", "EmployeeMaster"]
    },

    # Between operator
    {
        "id": "test_048",
        "category": "between",
        "question": "Show employees who joined between Jan 2023 and Dec 2023",
        "expected_pattern": "BETWEEN",
        "expected_tables": ["EmployeeMaster"]
    },

    # Complex COUNT variations
    {
        "id": "test_049",
        "category": "count_variations",
        "question": "How many unique departments have employees?",
        "expected_pattern": "DISTINCT",
        "expected_tables": ["EmployeeMaster"]
    },
    {
        "id": "test_050",
        "category": "count_variations",
        "question": "Count total, active and inactive employees",
        "expected_pattern": "CASE",
        "expected_tables": ["EmployeeMaster"]
    },
]


class SQLQueryTester:
    """Test suite for SQL query generation"""

    def __init__(self):
        self.results = []
        self.passed = 0
        self.failed = 0
        self.total_time = 0

    def initialize(self):
        """Initialize required services"""
        logger.info("Initializing test suite...")

        # Initialize database
        init_database()

        # Initialize FAISS
        faiss_manager.initialize()

        # Initialize few-shot manager
        few_shot_manager.initialize()

        logger.info("✓ Test suite initialized")

    def run_test(self, test_case):
        """Run a single test case"""
        test_id = test_case["id"]
        question = test_case["question"]
        category = test_case["category"]

        logger.info(f"Running {test_id}: {question}")

        start_time = time.time()

        try:
            # Generate and execute query
            result = sql_agent.query_and_answer(question)

            execution_time = time.time() - start_time

            # Check if query was generated
            if not result.get("sql_query"):
                raise Exception("No SQL query generated")

            sql_query = result["sql_query"]

            # Check for expected pattern
            expected_pattern = test_case.get("expected_pattern", "")
            pattern_found = expected_pattern.upper() in sql_query.upper() if expected_pattern else True

            # Check if query executed successfully
            has_results = result.get("result_count", 0) >= 0
            no_error = "error" not in result

            # Determine success
            success = pattern_found and no_error

            test_result = {
                "id": test_id,
                "category": category,
                "question": question,
                "sql_query": sql_query,
                "success": success,
                "execution_time": execution_time,
                "result_count": result.get("result_count", 0),
                "pattern_found": pattern_found,
                "expected_pattern": expected_pattern,
                "error": result.get("error", None)
            }

            if success:
                self.passed += 1
                logger.info(f"✓ {test_id} PASSED ({execution_time:.2f}s)")
            else:
                self.failed += 1
                logger.warning(f"✗ {test_id} FAILED: Pattern '{expected_pattern}' not found")

            self.results.append(test_result)
            self.total_time += execution_time

        except Exception as e:
            execution_time = time.time() - start_time
            self.failed += 1
            logger.error(f"✗ {test_id} ERROR: {str(e)}")

            self.results.append({
                "id": test_id,
                "category": category,
                "question": question,
                "sql_query": None,
                "success": False,
                "execution_time": execution_time,
                "result_count": 0,
                "pattern_found": False,
                "expected_pattern": test_case.get("expected_pattern", ""),
                "error": str(e)
            })

            self.total_time += execution_time

    def run_all_tests(self):
        """Run all test cases"""
        logger.info("=" * 80)
        logger.info(f"Running {len(TEST_CASES)} test cases...")
        logger.info("=" * 80)

        for test_case in TEST_CASES:
            self.run_test(test_case)
            time.sleep(0.5)  # Small delay between tests

        return self.print_summary()

    def print_summary(self):
        """Print test results summary"""
        total = len(TEST_CASES)
        success_rate = (self.passed / total * 100) if total > 0 else 0
        avg_time = self.total_time / total if total > 0 else 0

        logger.info("=" * 80)
        logger.info("TEST SUMMARY")
        logger.info("=" * 80)
        logger.info(f"Total Tests: {total}")
        logger.info(f"Passed: {self.passed}")
        logger.info(f"Failed: {self.failed}")
        logger.info(f"Success Rate: {success_rate:.1f}%")
        logger.info(f"Total Time: {self.total_time:.2f}s")
        logger.info(f"Average Time per Query: {avg_time:.2f}s")
        logger.info("=" * 80)

        # Print failures
        if self.failed > 0:
            logger.info("\nFAILED TESTS:")
            for result in self.results:
                if not result["success"]:
                    logger.info(f"\n{result['id']}: {result['question']}")
                    if result.get("error"):
                        logger.info(f"  Error: {result['error']}")
                    elif not result["pattern_found"]:
                        logger.info(f"  Expected pattern '{result['expected_pattern']}' not found")
                        logger.info(f"  Generated SQL: {result.get('sql_query', 'N/A')}")

        # Category breakdown
        logger.info("\nRESULTS BY CATEGORY:")
        categories = {}
        for result in self.results:
            cat = result["category"]
            if cat not in categories:
                categories[cat] = {"passed": 0, "failed": 0}
            if result["success"]:
                categories[cat]["passed"] += 1
            else:
                categories[cat]["failed"] += 1

        for cat, stats in sorted(categories.items()):
            total_cat = stats["passed"] + stats["failed"]
            rate = (stats["passed"] / total_cat * 100) if total_cat > 0 else 0
            logger.info(f"  {cat}: {stats['passed']}/{total_cat} ({rate:.0f}%)")

        return success_rate


if __name__ == "__main__":
    logger.info("Starting SQL Query Test Suite")

    tester = SQLQueryTester()
    tester.initialize()
    success_rate = tester.run_all_tests()

    # Exit with appropriate code
    exit(0 if success_rate >= 90 else 1)
