"""
Gemini chat agent with MongoDB function calling.
Gemini decides which collection to query based on the user's question.
"""
import os
import json
import pandas as pd
from pymongo import MongoClient
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
MONGODB_URI = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
DB_NAME = os.getenv("MONGODB_DB", "agenticpharma")

# Available collections Gemini can query
COLLECTION_DESCRIPTIONS = {
    "demographics": "Patient demographics: age, sex, race, BMI, treatment arm (A=Zibotentan, B=Placebo)",
    "adverse_events": "Adverse events: MedDRA code, severity (CTC grade 1-4), duration, causality, body system",
    "laboratory": "Lab results: CBC, chemistry, PSA, liver function, kidney function per visit",
    "vital_signs": "Vital signs per visit: blood pressure, pulse, weight, temperature",
    "dosing": "Drug dosing: dose amount, administration time, study period, compliance",
    "serious_adverse_events": "Serious adverse events: hospitalization, death, life-threatening events",
    "survival": "Survival data: overall survival, censoring dates, death flags",
    "ecg": "ECG / cardiac data: heart rate, QT interval, QTc, ECG findings",
    "randomization": "Randomization: treatment allocation, date, stratification factors",
    "subject_summary": "One row per patient: full trial summary, enrollment, demographics, outcomes",
    "psa_biomarker": "PSA biomarker over time: PSA levels, % change, response flag",
    "protocol_deviations": "Protocol deviations: deviation codes, major/minor, reasons",
    "recist_derived": "RECIST tumor response: CR/PR/SD/PD classifications, target lesions",
    "who_performance_status": "WHO/ECOG performance status per visit",
    "medications": "Concomitant medications throughout trial",
    "medical_history": "Pre-existing medical conditions and history",
    "discontinuation": "Study discontinuation: reason, date, last dose",
    "visits": "Visit schedule: planned vs actual dates, visit types",
    "death": "Death records: cause of death, date, relationship to study drug",
    "physical_exam": "Physical examination findings per visit",
    "patient_reported_outcomes": "Patient-reported outcomes questionnaire results",
}


def query_mongodb(collection: str, filter_json: str, limit: int = 100) -> str:
    """
    Query a MongoDB collection and return results as JSON.
    Called by Gemini via function calling.
    """
    try:
        client = MongoClient(MONGODB_URI, serverSelectionTimeoutMS=3000)
        db = client[DB_NAME]

        filter_dict = json.loads(filter_json) if filter_json else {}
        results = list(db[collection].find(filter_dict, {"_id": 0}).limit(limit))

        if not results:
            return json.dumps({"count": 0, "data": [], "message": "No records found."})

        # Return first 20 rows + summary stats
        df = pd.DataFrame(results)
        summary = {
            "count": len(results),
            "columns": list(df.columns),
            "data": results[:20],
        }

        # Add numeric stats for key columns
        numeric_cols = df.select_dtypes(include="number").columns.tolist()
        if numeric_cols:
            stats = df[numeric_cols].describe().round(2).to_dict()
            summary["numeric_summary"] = stats

        return json.dumps(summary, default=str)

    except Exception as e:
        return json.dumps({"error": str(e)})


def aggregate_mongodb(collection: str, pipeline_json: str) -> str:
    """
    Run a MongoDB aggregation pipeline. For counts, group-bys, averages.
    Called by Gemini via function calling.
    """
    try:
        client = MongoClient(MONGODB_URI, serverSelectionTimeoutMS=3000)
        db = client[DB_NAME]

        pipeline = json.loads(pipeline_json)
        results = list(db[collection].aggregate(pipeline))

        return json.dumps({"count": len(results), "data": results[:50]}, default=str)

    except Exception as e:
        return json.dumps({"error": str(e)})


def list_collections() -> str:
    """Return available collections with descriptions."""
    return json.dumps(COLLECTION_DESCRIPTIONS)


# Gemini function declarations
TOOLS = [
    {
        "function_declarations": [
            {
                "name": "query_mongodb",
                "description": (
                    "Query a MongoDB collection from the Zibotentan clinical trial database. "
                    "Use this to fetch patient records and answer specific questions about trial data. "
                    "Available collections: " + ", ".join(COLLECTION_DESCRIPTIONS.keys())
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "collection": {
                            "type": "string",
                            "description": "Collection name to query",
                            "enum": list(COLLECTION_DESCRIPTIONS.keys()),
                        },
                        "filter_json": {
                            "type": "string",
                            "description": (
                                "MongoDB filter as JSON string. Examples: "
                                '"{}" for all records, '
                                '{"TRTCODE": "A"} for Zibotentan arm, '
                                '{"TRTCODE": "B"} for Placebo arm, '
                                '{"SEX": "M"} for male patients. '
                                "Always use double quotes inside the JSON string."
                            ),
                        },
                        "limit": {
                            "type": "integer",
                            "description": "Max records to return (default 100, max 500)",
                        },
                    },
                    "required": ["collection", "filter_json"],
                },
            },
            {
                "name": "aggregate_mongodb",
                "description": (
                    "Run a MongoDB aggregation pipeline for counts, group-bys, averages, and summaries. "
                    "Use this for: 'how many patients', 'average age by arm', 'count AEs by grade', etc."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "collection": {
                            "type": "string",
                            "description": "Collection name",
                            "enum": list(COLLECTION_DESCRIPTIONS.keys()),
                        },
                        "pipeline_json": {
                            "type": "string",
                            "description": (
                                "MongoDB aggregation pipeline as JSON array string. "
                                'Example: [{"$group": {"_id": "$TRTCODE", "count": {"$sum": 1}}}]'
                            ),
                        },
                    },
                    "required": ["collection", "pipeline_json"],
                },
            },
            {
                "name": "list_collections",
                "description": "List all available data collections in the trial database with descriptions.",
                "parameters": {"type": "object", "properties": {}},
            },
        ]
    }
]

SYSTEM_PROMPT = """You are an AI clinical data analyst for the Zibotentan Phase 3 oncology trial (NCT00617669, AstraZeneca).

Trial context:
- Drug: Zibotentan (endothelin receptor antagonist) for castration-resistant prostate cancer
- Arms: A = Zibotentan (treatment), B = Placebo
- Studies: D4320C00015 (primary) and D4320C00033 (extended follow-up)
- ~500,000 patient records across 40+ clinical domains
- Key fields: SUBJ (patient ID), CENT (site), STUDY, TRTCODE (A/B), VISIT

Your job:
1. Answer questions about the trial data using the MongoDB query tools
2. Always query the database before answering — don't guess numbers
3. Present findings clearly with counts, percentages, and clinical context
4. Flag any safety signals or clinically relevant patterns
5. Use proper clinical terminology (AE, SAE, CTC grade, RECIST, PSA, etc.)

Available tools: query_mongodb, aggregate_mongodb, list_collections"""


class ClinicalAgent:
    def __init__(self):
        genai.configure(api_key=GEMINI_API_KEY)
        self.model = genai.GenerativeModel(
            model_name="gemini-2.0-flash",
            tools=TOOLS,
            system_instruction=SYSTEM_PROMPT,
        )
        self.history = []

    def chat(self, user_message: str) -> str:
        self.history.append({"role": "user", "parts": [user_message]})

        response = self.model.generate_content(self.history)

        # Handle function calling loop
        while response.candidates[0].content.parts[0].function_call.name if (
            response.candidates and
            response.candidates[0].content.parts and
            hasattr(response.candidates[0].content.parts[0], "function_call") and
            response.candidates[0].content.parts[0].function_call.name
        ) else False:
            fc = response.candidates[0].content.parts[0].function_call
            fn_name = fc.name
            fn_args = dict(fc.args)

            # Execute function
            if fn_name == "query_mongodb":
                result = query_mongodb(
                    fn_args.get("collection", ""),
                    fn_args.get("filter_json", "{}"),
                    fn_args.get("limit", 100),
                )
            elif fn_name == "aggregate_mongodb":
                result = aggregate_mongodb(
                    fn_args.get("collection", ""),
                    fn_args.get("pipeline_json", "[]"),
                )
            elif fn_name == "list_collections":
                result = list_collections()
            else:
                result = json.dumps({"error": f"Unknown function: {fn_name}"})

            # Add function call + result to history
            self.history.append({"role": "model", "parts": response.candidates[0].content.parts})
            self.history.append({
                "role": "user",
                "parts": [{
                    "function_response": {
                        "name": fn_name,
                        "response": {"result": result},
                    }
                }],
            })

            response = self.model.generate_content(self.history)

        # Extract text response
        text = response.text if hasattr(response, "text") else str(response)
        self.history.append({"role": "model", "parts": [text]})
        return text

    def reset(self):
        self.history = []
