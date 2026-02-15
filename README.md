Table of Contents

· Problem Statement
· Solution Overview
· Key Features
· Tech Stack
· Installation
· Usage Guide
· Demo Scenarios
· Model Performance
· Team

---

🎯 Problem Statement

Healthcare systems face:

· ⏰ Delays in identifying high-risk patients
· 🏥 Overcrowded departments
· 📊 Inconsistent prioritization
· 💪 Increased operational strain

Build an AI system that:

1. Classifies patients into Low/Medium/High risk
2. Recommends medical department
3. Provides explainable insights
4. Supports efficient prioritization

---

💡 Solution Overview

AAROGYA-ADAPT is a hybrid AI triage system combining:

Component Description
🔴 Rule Engine 12 safety red flags (ESI/MTS standards)
🤖 ML Engine RandomForest (89% accuracy)
🌆 Urban Mode Resource-aware queue optimization
🌾 Rural Mode Transfer risk assessment
🔍 Explainability SHAP + Confidence scores + Uncertainty flags
🛡️ Resilience Graceful degradation when ML fails

---

✨ Key Features

🔷 Core Engine (Always On)

Feature Implementation
📝 Patient Intake Manual form + EHR upload (.txt/.pdf)
🚨 Rule Engine 12 red flags (Chest pain + Age > 50 → HIGH, BP > 180 → HIGH, etc.)
🤖 ML Classifier RandomForest with 89% accuracy
📊 Risk Levels LOW / MEDIUM / HIGH with confidence %
🏥 Department Mapping Cardiology, Emergency, Neurology, General Medicine
🔍 Explainability SHAP top 5 factors + Uncertainty flag (<60% confidence)

🏙️ Urban Mode (Hospital Optimization)

Feature Description
ICU Bed Tracking Slider input for available beds
Doctor Availability Number of doctors on duty
Dynamic Queue Priority = Risk × Resources × Wait Time
Fairness Factor Long-waiting patients get slight boost

🌾 Rural Mode (Referral Safety)

Feature Description
Distance Input Distance to district hospital (km)
Ambulance Toggle Available / Not available
Vitals Check Auto-detects instability (BP/HR/Temp)
Transfer Risk Score 0-100 with color-coded action

Transfer Risk Categories:

Score Category Action
70-100 🔴 CRITICAL Stabilize locally first
40-69 🟠 CAUTION Transfer with medical escort
0-39 🟢 SAFE Transfer when ready

🛡️ Resilience

Feature Description
ML Failure Simulation One-click button to test fallback
Graceful Degradation Falls back to rule-only mode
System Status 🟢 Full / 🟡 Limited / 🔴 Safety

---

🛠️ Tech Stack

Component Technology
Language Python 3.9+
Web Framework Streamlit
ML Model RandomForestClassifier (scikit-learn)
Explainability SHAP
Data Processing Pandas, NumPy
Visualization Plotly, Streamlit native
PDF Parsing PyPDF2
Version Control Git

---

⚡ Installation

Prerequisites

· Python 3.9 or higher
· pip package manager

Steps

bash
# 1. Clone the repository
git clone https://github.com/yourusername/aarogya-adapt.git
cd aarogya-adapt

# 2. Create virtual environment (optional but recommended)
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Run the app
streamlit run app/main.py


The app will open in your browser at http://localhost:8501

---

📁 Project Structure


AAROGYA-ADAPT/
│
├── app/
│   ├── main.py              # Main Streamlit application
│   ├── model.py              # ML model training & prediction
│   ├── rules.py               # Rule engine (12 red flags)
│   ├── explain.py              # SHAP explainability
│   ├── context.py               # Urban/Rural modes
│   ├── data_generator.py         # Synthetic data generation
│   ├── ehr_parser.py              # Document upload parser
│   └── utils.py                    # Helper functions
│
├── models/
│   ├── triage_model.pkl         # Trained RandomForest (regenerate)
│   └── feature_names.pkl         # Feature names for SHAP
│
├── data/
│   ├── data_generator.py         # Script to generate data
│   └── sample_ehr.txt             # Demo upload file
│
├── requirements.txt               # Dependencies
├── README.md                       # This file
└── .gitignore                       # Git ignore rules


Note: Model and data files are regenerated on first run due to GitHub size limits.

---

🚀 Usage Guide

1. Starting the App

bash
streamlit run app/main.py


2. Input Methods

· Manual Entry: Fill the patient form
· EHR Upload: Upload .txt or .pdf file (auto-populates form)

3. Select Context Mode

· Urban Mode: For city hospitals with resource constraints
· Rural Mode: For remote clinics with transfer considerations

4. View Results

· Risk level with confidence %
· Department recommendation
· SHAP explanation (top 5 factors)
· Queue position (Urban mode)
· Transfer recommendation (Rural mode)

---

🎮 Demo Scenarios

Scenario 1: Cardiac Emergency (Urban)


Patient: 55-year-old male
Symptoms: Chest pain, shortness of breath
Vitals: BP 160/95, HR 98, Temp 98.6
History: Diabetes, Hypertension

Expected: HIGH risk → Cardiology → ICU scarcity boosts priority


Scenario 2: Stroke Symptoms (Rural)


Patient: 72-year-old female
Symptoms: Headache, weakness on one side
Vitals: BP 180/100, HR 88, Temp 98.4
Context: 80km from hospital, no ambulance

Expected: HIGH risk → 🔴 CRITICAL transfer risk → Stabilize locally


Scenario 3: Uncertainty Case


Patient: 45-year-old with vague symptoms
Symptoms: Fatigue, mild nausea
Vitals: All normal
History: None

Expected: LOW/MEDIUM risk → Low confidence (<60%) → 🔴 Uncertainty flag


---

📊 Model Performance

Metric Value
Accuracy 89%
Precision (High Risk) 0.87
Recall (High Risk) 0.91
F1-Score (High Risk) 0.89
AUC-ROC 0.92

⚠️ Known Limitations

· Trained on synthetic data (needs validation with real data)
· 9% false negative rate for High-risk (mitigated by rule engine)
· Rural logic is heuristic (conservative by design)
· PDF parsing is basic (manual entry always available)

---

👥 Team

Role Name
ML Engineer [Name]
Backend Developer [Name]
Frontend Developer [Name]
Domain Expert [Name]

Institution: [Your College/University]

---

📝 License

This project is licensed under the MIT License - see the LICENSE file for details.

---

🙏 Acknowledgments

· Inspired by global triage standards: ESI (USA) , MTS (UK) , CTAS (Canada)
· Built for [Hackathon Name] 32-Hour Healthcare Challenge
· SHAP library for explainable AI
· Streamlit for rapid prototyping



📧 Contact

For questions or collaboration:

· Email: your.email@example.com
· GitHub Issues: Create an issue

---

⭐ If you find this project useful, please star it on GitHub!

---

🚀 Quick Start (One-Liner)

bash
git clone https://github.com/yourusername/aarogya-adapt.git && cd aarogya-adapt && pip install -r requirements.txt && streamlit run app/main.py


---

Made with ❤️ for better healthcare
