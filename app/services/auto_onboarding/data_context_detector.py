"""
Data Context Detector
Analyzes ACTUAL DATA CONTENT to identify organization name, type, and domain context
This is the key differentiator for multi-tenant SaaS where schema is identical but data differs

OryggiDB Problem:
- Same schema deployed to Universities, Coal Mines, Metros, Hospitals
- Schema-based analysis always returns "Access Control / HR System"
- DATA analysis reveals: "MUJ University" vs "Vedanta Coal Mine" vs "Delhi Metro"
"""

import json
import re
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime
import google.generativeai as genai
from loguru import logger
from sqlalchemy import create_engine, text

from app.config import settings


# Organization Type Patterns - learned from actual OryggiDB deployments
ORGANIZATION_PATTERNS = {
    "university": {
        "keywords": [
            "university", "college", "school", "faculty", "campus", "academic",
            "professor", "student", "dean", "hostel", "library", "examination",
            "semester", "admission", "registrar", "convocation", "phd", "research",
            "institute", "education", "lecturer", "hod", "department of"
        ],
        "department_patterns": [
            r"school of", r"faculty of", r"department of.*engineering",
            r"computer science", r"mechanical", r"electrical", r"civil",
            r"mathematics", r"physics", r"chemistry", r"biology",
            r"management", r"arts", r"commerce", r"law", r"medical"
        ],
        "designation_patterns": [
            r"professor", r"lecturer", r"dean", r"registrar", r"proctor",
            r"warden", r"librarian", r"lab.*assistant"
        ]
    },
    "coal_mine": {
        "keywords": [
            "mine", "mining", "coal", "excavation", "shaft", "underground",
            "safety", "blast", "drilling", "extraction", "conveyor", "pit",
            "vedanta", "hindalco", "coal india", "singareni", "mahanadi"
        ],
        "department_patterns": [
            r"mining", r"safety", r"excavation", r"geology", r"survey",
            r"maintenance", r"production", r"welfare", r"environment"
        ],
        "designation_patterns": [
            r"miner", r"safety.*officer", r"geologist", r"surveyor",
            r"foreman", r"blaster", r"operator"
        ]
    },
    "metro": {
        "keywords": [
            "metro", "station", "line", "train", "rail", "transit", "platform",
            "ticket", "fare", "commuter", "rapid", "underground", "elevated",
            "dmrc", "nmrc", "bmrc", "cmrl", "hmrl"
        ],
        "department_patterns": [
            r"operations", r"station", r"maintenance", r"signaling",
            r"rolling.*stock", r"civil", r"electrical", r"safety", r"security"
        ],
        "designation_patterns": [
            r"station.*master", r"train.*operator", r"controller",
            r"technician", r"engineer", r"supervisor"
        ]
    },
    "hospital": {
        "keywords": [
            "hospital", "medical", "clinic", "patient", "doctor", "nurse",
            "ward", "icu", "ot", "pharmacy", "diagnostic", "emergency",
            "apollo", "fortis", "max", "aiims", "medanta"
        ],
        "department_patterns": [
            r"cardiology", r"neurology", r"orthopedic", r"pediatric",
            r"oncology", r"radiology", r"pathology", r"surgery", r"medicine",
            r"emergency", r"icu", r"pharmacy", r"nursing"
        ],
        "designation_patterns": [
            r"doctor", r"nurse", r"surgeon", r"physician", r"technician",
            r"paramedic", r"receptionist", r"pharmacist"
        ]
    },
    "corporate": {
        "keywords": [
            "corporate", "office", "company", "enterprise", "business",
            "headquarters", "branch", "division", "subsidiary"
        ],
        "department_patterns": [
            r"human.*resource", r"finance", r"accounts", r"marketing",
            r"sales", r"it", r"admin", r"legal", r"operations"
        ],
        "designation_patterns": [
            r"manager", r"executive", r"director", r"analyst", r"officer",
            r"associate", r"coordinator", r"lead"
        ]
    },
    "manufacturing": {
        "keywords": [
            "factory", "plant", "manufacturing", "production", "assembly",
            "warehouse", "logistics", "quality", "inventory"
        ],
        "department_patterns": [
            r"production", r"quality", r"maintenance", r"stores",
            r"logistics", r"dispatch", r"assembly", r"testing"
        ],
        "designation_patterns": [
            r"operator", r"technician", r"supervisor", r"inspector",
            r"foreman", r"engineer"
        ]
    }
}


class DataContextDetector:
    """
    Detects organization context by analyzing ACTUAL DATA, not just schema

    The Magic:
    1. Query metadata tables (CompanyMaster, BranchMaster, etc.)
    2. Analyze department names, designations, branch names
    3. Use pattern matching + LLM for classification
    4. Extract organization name and type
    5. Build domain-specific vocabulary
    """

    def __init__(self, connection_string: str):
        """Initialize with database connection"""
        self.connection_string = connection_string
        self.engine = create_engine(connection_string)

        # Initialize Gemini for complex analysis
        genai.configure(api_key=settings.gemini_api_key)
        self.model = genai.GenerativeModel(settings.gemini_model)

        logger.info("DataContextDetector initialized")

    async def detect_context(self, schema: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Main method: Detect organization context from data

        Returns:
            {
                "organization_name": "Manipal University Jaipur",
                "organization_short_name": "MUJ",
                "organization_type": "university",
                "organization_type_display": "University / Educational Institution",
                "confidence": 0.95,
                "detection_method": "data_analysis",
                "evidence": {
                    "company_name": "MUJ - Manipal University Jaipur",
                    "departments_found": ["School of Computing", "Faculty of Engineering", ...],
                    "branches_found": ["Main Campus", "Academic Block A", ...],
                    "designations_found": ["Professor", "Assistant Professor", ...]
                },
                "domain_vocabulary": {
                    "faculty": "Teaching staff member",
                    "semester": "Academic term period",
                    ...
                },
                "key_entities": ["Students", "Faculty", "Courses", "Departments"],
                "typical_queries": [
                    "How many students are enrolled?",
                    "List all faculty members in Computer Science",
                    ...
                ]
            }
        """
        logger.info("Starting data context detection...")

        result = {
            "organization_name": "Unknown Organization",
            "organization_short_name": "",
            "organization_type": "corporate",  # Default fallback
            "organization_type_display": "Corporate / Business",
            "confidence": 0.0,
            "detection_method": "data_analysis",
            "evidence": {},
            "domain_vocabulary": {},
            "key_entities": [],
            "typical_queries": []
        }

        try:
            # Step 1: Extract organization name from metadata tables
            org_info = self._extract_organization_info()
            result["evidence"]["raw_company_data"] = org_info

            if org_info.get("company_name"):
                result["organization_name"] = org_info["company_name"]
                result["organization_short_name"] = org_info.get("short_name", "")

            # Step 2: Gather data samples for classification
            data_samples = self._gather_classification_data()
            result["evidence"]["departments_found"] = data_samples.get("departments", [])[:20]
            result["evidence"]["branches_found"] = data_samples.get("branches", [])[:20]
            result["evidence"]["designations_found"] = data_samples.get("designations", [])[:20]

            # Step 3: Pattern-based classification (include company name for better detection)
            pattern_result = self._classify_by_patterns(
                data_samples,
                company_name=org_info.get("company_name", "")
            )

            # Step 4: If pattern confidence is low, use LLM
            if pattern_result["confidence"] < 0.7:
                llm_result = await self._classify_with_llm(org_info, data_samples)

                # Combine results
                if llm_result["confidence"] > pattern_result["confidence"]:
                    result["organization_type"] = llm_result["organization_type"]
                    result["confidence"] = llm_result["confidence"]
                    result["detection_method"] = "llm_analysis"
                else:
                    result["organization_type"] = pattern_result["organization_type"]
                    result["confidence"] = pattern_result["confidence"]
            else:
                result["organization_type"] = pattern_result["organization_type"]
                result["confidence"] = pattern_result["confidence"]

            # Step 5: Get display name for organization type
            result["organization_type_display"] = self._get_type_display_name(
                result["organization_type"]
            )

            # Step 6: Build domain vocabulary
            result["domain_vocabulary"] = await self._build_domain_vocabulary(
                result["organization_type"],
                data_samples
            )

            # Step 7: Identify key entities
            result["key_entities"] = self._identify_key_entities(
                result["organization_type"],
                data_samples
            )

            # Step 8: Generate typical queries for this domain
            result["typical_queries"] = self._generate_typical_queries(
                result["organization_type"],
                result["organization_name"]
            )

            logger.info(f"Context detected: {result['organization_name']} ({result['organization_type']})")
            logger.info(f"Confidence: {result['confidence']:.2%}")

        except Exception as e:
            logger.error(f"Context detection failed: {e}")
            result["evidence"]["error"] = str(e)

        return result

    def _extract_organization_info(self) -> Dict[str, Any]:
        """Extract organization name from metadata tables"""

        info = {
            "company_name": None,
            "short_name": None,
            "address": None,
            "branches": []
        }

        # OryggiDB actual schema queries (based on discovered column names)
        queries = {
            # CompanyMaster - CName is the company name column
            "company_primary": """
                SELECT TOP 1 CName, Address, PinCode, Email
                FROM CompanyMaster
                ORDER BY Ccode
            """,
            # Fallback: Try different column name variations
            "company_fallback1": """
                SELECT TOP 1 CompanyName, Address
                FROM CompanyMaster
                ORDER BY 1
            """,
            "company_fallback2": """
                SELECT TOP 1 Name, Address
                FROM CompanyMaster
                ORDER BY 1
            """,
            # BranchMaster - BranchName column
            "branches": """
                SELECT BranchName, Location
                FROM BranchMaster
                WHERE BranchName IS NOT NULL AND BranchName != ''
                ORDER BY BranchCode
            """
        }

        with self.engine.connect() as conn:
            # Try primary CompanyMaster query
            try:
                result = conn.execute(text(queries["company_primary"]))
                row = result.fetchone()
                if row and row[0]:
                    info["company_name"] = row[0]
                    info["address"] = row[1] if len(row) > 1 and row[1] else None
                    logger.info(f"Found company name: {info['company_name']}")
            except Exception as e:
                logger.debug(f"CompanyMaster primary query failed: {e}")

            # Try fallback queries if no company name yet
            if not info["company_name"]:
                for fallback in ["company_fallback1", "company_fallback2"]:
                    try:
                        result = conn.execute(text(queries[fallback]))
                        row = result.fetchone()
                        if row and row[0]:
                            info["company_name"] = row[0]
                            info["address"] = row[1] if len(row) > 1 and row[1] else None
                            break
                    except Exception:
                        pass

            # Get branches
            try:
                result = conn.execute(text(queries["branches"]))
                info["branches"] = [row[0] for row in result.fetchall() if row[0]]
            except Exception as e:
                logger.debug(f"BranchMaster query failed: {e}")

        return info

    def _gather_classification_data(self) -> Dict[str, List[str]]:
        """Gather data samples for classification"""

        data = {
            "departments": [],
            "branches": [],
            "designations": [],
            "employee_names": [],
            "custom_fields": []
        }

        # OryggiDB actual schema queries
        queries = {
            "departments": [
                # DeptMaster - Dname column (OryggiDB specific)
                "SELECT DISTINCT Dname FROM DeptMaster WHERE Dname IS NOT NULL AND Dname != 'Department Name'",
                # Fallback variations
                "SELECT DISTINCT DeptName FROM DepartmentMaster WHERE DeptName IS NOT NULL",
                "SELECT DISTINCT DivisionName FROM DivisionMaster WHERE DivisionName IS NOT NULL",
                "SELECT DISTINCT SectionName FROM SectionMaster WHERE SectionName IS NOT NULL"
            ],
            "branches": [
                # BranchMaster - BranchName column (OryggiDB specific)
                "SELECT DISTINCT BranchName FROM BranchMaster WHERE BranchName IS NOT NULL AND BranchName != 'Branch Name'",
                # Fallback variations
                "SELECT DISTINCT LocationName FROM LocationMaster WHERE LocationName IS NOT NULL"
            ],
            "designations": [
                # DesignationMaster - DesName column (OryggiDB specific)
                "SELECT DISTINCT DesName FROM DesignationMaster WHERE DesName IS NOT NULL",
                # Fallback variations
                "SELECT DISTINCT DesigName FROM DesignationMaster WHERE DesigName IS NOT NULL",
                "SELECT DISTINCT TOP 50 Designation FROM EmployeeMaster WHERE Designation IS NOT NULL"
            ]
        }

        with self.engine.connect() as conn:
            for data_type, query_list in queries.items():
                for query in query_list:
                    try:
                        result = conn.execute(text(query))
                        values = [row[0] for row in result.fetchall() if row[0]]
                        data[data_type].extend(values)
                    except Exception:
                        pass  # Table might not exist

                # Deduplicate
                data[data_type] = list(set(data[data_type]))

        return data

    def _classify_by_patterns(
        self,
        data_samples: Dict[str, List[str]],
        company_name: str = ""
    ) -> Dict[str, Any]:
        """Classify organization type using pattern matching"""

        scores = {org_type: 0.0 for org_type in ORGANIZATION_PATTERNS.keys()}

        # Combine all text for analysis - INCLUDING COMPANY NAME (most important!)
        all_text = " ".join([
            company_name,  # Company name is the strongest signal
            " ".join(data_samples.get("departments", [])),
            " ".join(data_samples.get("branches", [])),
            " ".join(data_samples.get("designations", []))
        ]).lower()

        for org_type, patterns in ORGANIZATION_PATTERNS.items():
            # Keyword matching
            keyword_score = sum(
                1 for kw in patterns["keywords"]
                if kw.lower() in all_text
            )

            # Department pattern matching
            dept_score = sum(
                1 for pattern in patterns["department_patterns"]
                if re.search(pattern, all_text, re.IGNORECASE)
            )

            # Designation pattern matching
            desig_score = sum(
                1 for pattern in patterns["designation_patterns"]
                if re.search(pattern, all_text, re.IGNORECASE)
            )

            # Weighted score
            total_possible = (
                len(patterns["keywords"]) +
                len(patterns["department_patterns"]) +
                len(patterns["designation_patterns"])
            )

            scores[org_type] = (
                keyword_score * 1.0 +
                dept_score * 2.0 +
                desig_score * 2.0
            ) / (total_possible * 1.5)  # Normalize

        # Get best match
        best_type = max(scores, key=scores.get)
        best_score = min(scores[best_type], 1.0)  # Cap at 1.0

        logger.debug(f"Pattern classification scores: {scores}")

        return {
            "organization_type": best_type,
            "confidence": best_score,
            "all_scores": scores
        }

    async def _classify_with_llm(
        self,
        org_info: Dict[str, Any],
        data_samples: Dict[str, List[str]]
    ) -> Dict[str, Any]:
        """Use LLM for complex classification when patterns are unclear"""

        prompt = f"""Analyze this data and classify the organization type.

ORGANIZATION DATA:
- Company Name: {org_info.get('company_name', 'Unknown')}
- Branches: {', '.join(org_info.get('branches', [])[:10])}

DEPARTMENT NAMES:
{', '.join(data_samples.get('departments', [])[:30])}

DESIGNATION/ROLES:
{', '.join(data_samples.get('designations', [])[:30])}

Classify this organization into ONE of these types:
1. university - Educational institution (schools, colleges, universities)
2. coal_mine - Mining operation (coal, minerals, excavation)
3. metro - Metro/Railway transit system
4. hospital - Healthcare facility (hospital, clinic, medical center)
5. corporate - General corporate office
6. manufacturing - Factory/manufacturing plant

Return ONLY a JSON object:
{{
    "organization_type": "university|coal_mine|metro|hospital|corporate|manufacturing",
    "confidence": 0.0 to 1.0,
    "reasoning": "Brief explanation"
}}

Return ONLY valid JSON, no markdown."""

        try:
            response = await self.model.generate_content_async(
                prompt,
                generation_config=genai.GenerationConfig(
                    temperature=0.1,
                    max_output_tokens=500
                )
            )

            response_text = response.text
            if "```json" in response_text:
                response_text = response_text.split("```json")[1].split("```")[0]
            elif "```" in response_text:
                response_text = response_text.split("```")[1].split("```")[0]

            result = json.loads(response_text.strip())
            return {
                "organization_type": result.get("organization_type", "corporate"),
                "confidence": float(result.get("confidence", 0.5)),
                "reasoning": result.get("reasoning", "")
            }

        except Exception as e:
            logger.warning(f"LLM classification failed: {e}")
            return {
                "organization_type": "corporate",
                "confidence": 0.3,
                "reasoning": "Fallback due to LLM error"
            }

    def _get_type_display_name(self, org_type: str) -> str:
        """Get human-readable display name for organization type"""

        display_names = {
            "university": "University / Educational Institution",
            "coal_mine": "Coal Mine / Mining Operation",
            "metro": "Metro / Transit System",
            "hospital": "Hospital / Healthcare Facility",
            "corporate": "Corporate / Business Office",
            "manufacturing": "Manufacturing / Factory"
        }

        return display_names.get(org_type, "Organization")

    async def _build_domain_vocabulary(
        self,
        org_type: str,
        data_samples: Dict[str, List[str]]
    ) -> Dict[str, str]:
        """Build domain-specific vocabulary for the organization type"""

        # Base vocabulary per type
        base_vocab = {
            "university": {
                "faculty": "Teaching staff members (professors, lecturers)",
                "semester": "Academic term period (typically 6 months)",
                "enrollment": "Process of registering students for courses",
                "credits": "Unit measuring course workload",
                "GPA": "Grade Point Average - academic performance metric",
                "hostel": "Student residential accommodation",
                "dean": "Head of a faculty or school",
                "HOD": "Head of Department",
                "convocation": "Graduation ceremony"
            },
            "coal_mine": {
                "shaft": "Vertical passage into underground mine",
                "seam": "Layer of coal in the earth",
                "pit": "Open excavation area",
                "shift": "Work period for miners",
                "safety": "Protective measures and equipment",
                "extraction": "Process of removing coal/minerals",
                "ventilation": "Air circulation system in mines"
            },
            "metro": {
                "line": "Specific metro route (e.g., Blue Line)",
                "station": "Metro stop/platform location",
                "platform": "Area where passengers board trains",
                "headway": "Time between successive trains",
                "ridership": "Number of passengers using metro",
                "fare": "Ticket price for journey"
            },
            "hospital": {
                "OPD": "Out Patient Department",
                "IPD": "In Patient Department",
                "ICU": "Intensive Care Unit",
                "OT": "Operation Theatre",
                "ward": "Hospital room/section for patients",
                "discharge": "Patient release from hospital",
                "referral": "Directing patient to specialist"
            },
            "corporate": {
                "department": "Organizational division",
                "designation": "Job title/position",
                "reporting": "Management hierarchy",
                "appraisal": "Performance evaluation"
            },
            "manufacturing": {
                "production": "Manufacturing process",
                "quality": "Product standards and testing",
                "inventory": "Stock of materials/products",
                "dispatch": "Shipping of finished goods"
            }
        }

        return base_vocab.get(org_type, base_vocab["corporate"])

    def _identify_key_entities(
        self,
        org_type: str,
        data_samples: Dict[str, List[str]]
    ) -> List[str]:
        """Identify key business entities for this organization type"""

        entities = {
            "university": [
                "Students", "Faculty", "Courses", "Departments",
                "Semesters", "Examinations", "Hostels", "Library"
            ],
            "coal_mine": [
                "Miners", "Shifts", "Safety Records", "Production",
                "Equipment", "Excavation Sites", "Departments"
            ],
            "metro": [
                "Stations", "Lines", "Staff", "Shifts",
                "Passengers", "Tickets", "Maintenance"
            ],
            "hospital": [
                "Patients", "Doctors", "Nurses", "Departments",
                "Appointments", "Wards", "Treatments"
            ],
            "corporate": [
                "Employees", "Departments", "Branches",
                "Attendance", "Leave", "Payroll"
            ],
            "manufacturing": [
                "Workers", "Production Lines", "Inventory",
                "Quality Checks", "Shifts", "Dispatch"
            ]
        }

        return entities.get(org_type, entities["corporate"])

    def _generate_typical_queries(
        self,
        org_type: str,
        org_name: str
    ) -> List[str]:
        """Generate typical queries users would ask for this organization"""

        queries = {
            "university": [
                f"How many students are enrolled at {org_name}?",
                "List all faculty members in the Computer Science department",
                "Show attendance for today",
                "Which professors are on leave this week?",
                "How many students are in each department?",
                "Show late arrivals for faculty today"
            ],
            "coal_mine": [
                f"How many workers are on shift today at {org_name}?",
                "Show safety incidents this month",
                "List all miners in the excavation department",
                "Show attendance for the morning shift",
                "Which areas have the most workers?"
            ],
            "metro": [
                f"How many staff are on duty at {org_name}?",
                "Show attendance for station masters",
                "List all technicians on Blue Line",
                "How many employees per station?",
                "Show late arrivals today"
            ],
            "hospital": [
                f"How many staff are present at {org_name} today?",
                "List all doctors in Cardiology",
                "Show nurses on night shift",
                "How many staff per department?",
                "Show attendance for emergency department"
            ],
            "corporate": [
                f"How many employees work at {org_name}?",
                "Show today's attendance summary",
                "List employees in IT department",
                "Who is on leave today?",
                "Show late arrivals this week"
            ],
            "manufacturing": [
                f"How many workers are present at {org_name}?",
                "Show production line attendance",
                "List quality inspectors on duty",
                "Show shift-wise employee count",
                "Who are the absent workers today?"
            ]
        }

        return queries.get(org_type, queries["corporate"])

    def close(self):
        """Close database connection"""
        if self.engine:
            self.engine.dispose()
