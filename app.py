import os
import json
import joblib
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
import pytz
from flask import Flask, render_template, request, jsonify, session, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import speech_recognition as sr
from googletrans import Translator
import plotly
import plotly.graph_objs as go
import plotly.express as px
from plotly.subplots import make_subplots
from sklearn.ensemble import RandomForestClassifier
import warnings
import random
import math
import re
from gtts import gTTS
import base64
import io
import PyPDF2
import docx
warnings.filterwarnings('ignore')

# Set Indian timezone
IST = pytz.timezone('Asia/Kolkata')

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-change-this-in-production'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///triage.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024
app.config['JSON_AS_ASCII'] = False

os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

db = SQLAlchemy(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'
login_manager.login_message = 'Please log in to access this page.'

# Database Models
class Hospital(UserMixin, db.Model):
    __tablename__ = 'hospitals'
    id = db.Column(db.Integer, primary_key=True)
    hospital_id = db.Column(db.String(50), unique=True, nullable=False)
    hospital_name = db.Column(db.String(100), nullable=False)
    location = db.Column(db.String(100), nullable=False)
    area_type = db.Column(db.String(20), nullable=False)
    hospital_type = db.Column(db.String(20), nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    latitude = db.Column(db.Float, nullable=False, default=0.0)
    longitude = db.Column(db.Float, nullable=False, default=0.0)
    address = db.Column(db.String(200), default='')
    
    total_doctors = db.Column(db.Integer, default=0)
    nurses_count = db.Column(db.Integer, default=0)
    wardboys_count = db.Column(db.Integer, default=0)
    total_beds = db.Column(db.Integer, default=0)
    available_beds = db.Column(db.Integer, default=0)
    has_operation_theater = db.Column(db.Boolean, default=False)
    has_icu = db.Column(db.Boolean, default=False)
    has_emergency = db.Column(db.Boolean, default=False)
    contact_number = db.Column(db.String(20))
    ambulance_count = db.Column(db.Integer, default=1)
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class Department(db.Model):
    __tablename__ = 'departments'
    id = db.Column(db.Integer, primary_key=True)
    hospital_id = db.Column(db.Integer, db.ForeignKey('hospitals.id'), nullable=False)
    name = db.Column(db.String(50), nullable=False)
    total_doctors = db.Column(db.Integer, default=0)
    doctors_on_duty = db.Column(db.Integer, default=0)
    on_call_doctors = db.Column(db.Integer, default=0)
    next_available_time = db.Column(db.DateTime)
    emergency_contact = db.Column(db.String(20))
    is_active = db.Column(db.Boolean, default=True)
    last_updated = db.Column(db.DateTime, default=datetime.utcnow)

class Ambulance(db.Model):
    __tablename__ = 'ambulance'
    id = db.Column(db.Integer, primary_key=True)
    hospital_id = db.Column(db.Integer, db.ForeignKey('hospitals.id'), nullable=False)
    vehicle_number = db.Column(db.String(20), unique=True)
    is_available = db.Column(db.Boolean, default=True)
    current_latitude = db.Column(db.Float, default=0.0)
    current_longitude = db.Column(db.Float, default=0.0)
    estimated_return_time = db.Column(db.DateTime, nullable=True)
    paramedic_count = db.Column(db.Integer, default=2)
    has_life_support = db.Column(db.Boolean, default=True)
    driver_name = db.Column(db.String(100))
    driver_phone = db.Column(db.String(20))
    last_maintenance = db.Column(db.DateTime, default=datetime.utcnow)
    in_use_since = db.Column(db.DateTime, nullable=True)
    destination_hospital = db.Column(db.String(100), nullable=True)

class Patient(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.String(50), unique=True, nullable=False)
    hospital_id = db.Column(db.Integer, db.ForeignKey('hospitals.id'), nullable=False)
    name = db.Column(db.String(100))
    age = db.Column(db.Integer)
    gender = db.Column(db.String(10))
    symptoms = db.Column(db.Text)
    blood_pressure = db.Column(db.String(20))
    heart_rate = db.Column(db.Integer)
    temperature = db.Column(db.Float)
    pre_existing_conditions = db.Column(db.Text)
    
    risk_level = db.Column(db.String(20))
    risk_color = db.Column(db.String(20))
    confidence_score = db.Column(db.Float)
    recommended_department = db.Column(db.String(50))
    explainability = db.Column(db.Text)
    medical_explanation = db.Column(db.Text)
    future_symptoms = db.Column(db.Text)
    
    treatment_decision = db.Column(db.String(50))
    transferred_to = db.Column(db.String(100))
    transferred_to_id = db.Column(db.Integer, db.ForeignKey('hospitals.id'), nullable=True)
    outcome = db.Column(db.String(50))
    admission_date = db.Column(db.DateTime, default=datetime.utcnow)
    discharge_date = db.Column(db.DateTime, nullable=True)
    expected_discharge = db.Column(db.DateTime, nullable=True)
    bed_number = db.Column(db.Integer, nullable=True)
    is_admitted = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    ethnicity = db.Column(db.String(50), default='Not Specified')
    socioeconomic_status = db.Column(db.String(50), default='Not Specified')
    wait_time_minutes = db.Column(db.Integer, default=0)

@login_manager.user_loader
def load_user(user_id):
    return Hospital.query.get(int(user_id))

# AI Model Class
class TriageAIModel:
    def __init__(self):
        self.model = None
        self.load_or_create_model()
    
    def load_or_create_model(self):
        model_path = 'triage_model.pkl'
        if os.path.exists(model_path):
            self.model = joblib.load(model_path)
        else:
            self.create_synthetic_model()
    
    def create_synthetic_model(self):
        self.model = RandomForestClassifier(n_estimators=100, random_state=42)
        np.random.seed(42)
        n_samples = 1000
        X = np.random.randn(n_samples, 6)
        y = np.random.randint(0, 4, n_samples)
        self.model.fit(X, y)
        joblib.dump(self.model, 'triage_model.pkl')
    
    def extract_bp_values(self, bp_string):
        try:
            systolic, diastolic = map(int, bp_string.split('/'))
            return systolic, diastolic
        except:
            return 120, 80
    
    def calculate_symptom_severity(self, symptoms):
        severe_keywords = ['chest pain', 'unconscious', 'bleeding', 'stroke', 'heart attack', 
                          'seizure', 'difficulty breathing', 'severe', 'critical', 'emergency']
        symptoms_lower = symptoms.lower()
        severity = sum(2 for keyword in severe_keywords if keyword in symptoms_lower)
        return min(severity, 3)
    
    def celsius_to_fahrenheit(self, celsius):
        return (celsius * 9/5) + 32
    
    def predict_risk(self, age, heart_rate, temperature, blood_pressure, symptoms, pre_conditions):
        systolic, diastolic = self.extract_bp_values(blood_pressure)
        symptom_severity = self.calculate_symptom_severity(symptoms)
        
        if (systolic > 200 or systolic < 50 or 
            heart_rate > 160 or heart_rate < 30 or 
            temperature > 105 or temperature < 93 or
            'unconscious' in symptoms.lower() or
            'not breathing' in symptoms.lower() or
            'cardiac arrest' in symptoms.lower()):
            return 'Critical', 'Black', 0.99
        
        elif (systolic > 180 or systolic < 70 or
              heart_rate > 140 or heart_rate < 40 or
              temperature > 103.5 or
              symptom_severity >= 2 or
              'severe' in symptoms.lower() or
              any(cond in pre_conditions.lower() for cond in ['heart disease', 'diabetes', 'stroke', 'cancer'])):
            return 'High', 'Red', 0.95
        
        elif (systolic > 150 or systolic < 85 or
              heart_rate > 110 or heart_rate < 50 or
              temperature > 101.5 or
              symptom_severity >= 1 or
              age > 70 or age < 3):
            return 'Medium', 'Yellow', 0.85
        
        else:
            return 'Low', 'Green', 0.80
    
    def generate_medical_explanation(self, risk_level, age, symptoms, bp, hr, temp, pre_conditions):
        systolic, diastolic = self.extract_bp_values(bp)
        
        explanations = {
            'Critical': {
                'current': "⚠️ CRITICAL CONDITION: Life-threatening emergency requiring immediate intervention.",
                'physiology': f"Severe physiological derangement: BP {bp} (normal 120/80), HR {hr} bpm (normal 60-100), Temp {temp}°F (normal 98.6°F).",
                'risks': "High risk of cardiac arrest, respiratory failure, multi-organ dysfunction.",
                'future': "Without immediate intervention: cardiopulmonary arrest within minutes, irreversible brain damage, death."
            },
            'High': {
                'current': "🔴 HIGH RISK: Serious condition requiring urgent medical attention.",
                'physiology': f"Significant vital sign abnormalities: BP {bp} (normal 120/80), HR {hr} bpm (normal 60-100), Temp {temp}°F (normal 98.6°F).",
                'risks': "Risk of deterioration to critical condition, potential for organ damage.",
                'future': "If untreated within 1-2 hours: progression to critical state, increased morbidity."
            },
            'Medium': {
                'current': "🟡 MODERATE RISK: Medical attention needed within 2-4 hours.",
                'physiology': f"Mild to moderate vital sign abnormalities: BP {bp}, HR {hr}, Temp {temp}.",
                'risks': "Moderate risk of complications if not addressed promptly.",
                'future': "May progress to high risk if underlying condition worsens. Monitor closely."
            },
            'Low': {
                'current': "🟢 LOW RISK: Stable condition for routine care.",
                'physiology': f"Vitals within acceptable ranges: BP {bp}, HR {hr}, Temp {temp}.",
                'risks': "Minimal immediate risk of complications.",
                'future': "Expected to remain stable with routine follow-up."
            }
        }
        
        risk_data = explanations.get(risk_level, explanations['Low'])
        
        symptom_analysis = self.analyze_symptoms(symptoms, age, pre_conditions)
        
        full_explanation = f"""
{risk_data['current']}

📊 VITAL SIGNS ANALYSIS:
{risk_data['physiology']}

🩺 SYMPTOM ANALYSIS:
{symptom_analysis['analysis']}

⚠️ IMMEDIATE RISKS:
{risk_data['risks']}
{symptom_analysis['immediate_risks']}

🔮 POTENTIAL FUTURE SYMPTOMS:
{risk_data['future']}
{symptom_analysis['future_symptoms']}

💊 RECOMMENDATIONS:
• {self.get_recommendations(risk_level, symptom_analysis['likely_condition'])}
• Immediate monitoring of: {symptom_analysis['monitor']}
• Follow-up required: {symptom_analysis['follow_up']}
"""
        
        return full_explanation, symptom_analysis['future_symptoms']
    
    def analyze_symptoms(self, symptoms, age, pre_conditions):
        symptoms_lower = symptoms.lower()
        pre_conditions_lower = pre_conditions.lower()
        
        analysis = {
            'analysis': '',
            'immediate_risks': '',
            'future_symptoms': '',
            'likely_condition': '',
            'monitor': '',
            'follow_up': ''
        }
        
        if any(word in symptoms_lower for word in ['chest', 'heart', 'palpitations']):
            analysis['analysis'] = "Cardiac symptoms detected. Chest pain may indicate angina or myocardial infarction."
            analysis['immediate_risks'] = "Risk of cardiac arrhythmia, myocardial infarction, cardiac arrest."
            analysis['future_symptoms'] = "May develop: radiating arm pain, shortness of breath, diaphoresis, nausea."
            analysis['likely_condition'] = "Acute Coronary Syndrome"
            analysis['monitor'] = "ECG, cardiac enzymes, oxygen saturation"
            analysis['follow_up'] = "Cardiology review within 24 hours"
        
        elif any(word in symptoms_lower for word in ['head', 'brain', 'seizure', 'stroke', 'vertigo']):
            analysis['analysis'] = "Neurological symptoms present. May indicate cerebrovascular event."
            analysis['immediate_risks'] = "Risk of stroke progression, increased intracranial pressure."
            analysis['future_symptoms'] = "Watch for: altered consciousness, focal deficits, seizures."
            analysis['likely_condition'] = "Cerebrovascular Accident / TIA"
            analysis['monitor'] = "Neurological observations, CT/MRI imaging"
            analysis['follow_up'] = "Neurology review within 6 hours"
        
        elif any(word in symptoms_lower for word in ['breath', 'cough', 'wheezing', 'asthma']):
            analysis['analysis'] = "Respiratory symptoms indicate potential airway or lung pathology."
            analysis['immediate_risks'] = "Risk of respiratory failure, hypoxia, pneumonia."
            analysis['future_symptoms'] = "May develop: cyanosis, accessory muscle use, altered mental status."
            analysis['likely_condition'] = "Respiratory Distress / Pneumonia"
            analysis['monitor'] = "Oxygen saturation, respiratory rate, ABG"
            analysis['follow_up'] = "Pulmonology review as needed"
        
        else:
            analysis['analysis'] = "General symptoms requiring further evaluation."
            analysis['immediate_risks'] = "Risk of underlying condition progression."
            analysis['future_symptoms'] = "Monitor for worsening of presenting symptoms."
            analysis['likely_condition'] = "Undifferentiated condition"
            analysis['monitor'] = "Vital signs, symptom progression"
            analysis['follow_up'] = "Primary care follow-up within 48 hours"
        
        if age > 65:
            analysis['future_symptoms'] += " Elderly patients at higher risk for complications."
            analysis['monitor'] += ", fall risk, confusion"
        
        if 'diabetes' in pre_conditions_lower:
            analysis['future_symptoms'] += " Monitor blood glucose closely."
            analysis['monitor'] += ", blood glucose"
        
        if 'hypertension' in pre_conditions_lower:
            analysis['future_symptoms'] += " Blood pressure may become labile."
            analysis['monitor'] += ", frequent BP checks"
        
        return analysis
    
    def get_recommendations(self, risk_level, condition):
        recommendations = {
            'Critical': f"Immediate ICU admission. Emergency {condition} protocol. Prepare for resuscitation.",
            'High': f"Urgent admission to emergency. Initiate {condition} workup. Consult specialist.",
            'Medium': f"Admit to ward within 2-4 hours. Begin diagnostic workup for {condition}.",
            'Low': f"Outpatient management of {condition}. Schedule follow-up within 48 hours."
        }
        return recommendations.get(risk_level, "Follow standard clinical protocols.")
    
    def recommend_department(self, risk_level, symptoms, age, bp, heart_rate):
        symptoms_lower = symptoms.lower()
        
        if risk_level in ['Critical', 'High']:
            return 'Emergency'
        
        if any(word in symptoms_lower for word in ['chest', 'heart', 'palpitations', 'cardiac']):
            return 'Cardiology'
        elif any(word in symptoms_lower for word in ['head', 'brain', 'seizure', 'stroke', 'vertigo', 'migraine']):
            return 'Neurology'
        elif any(word in symptoms_lower for word in ['breath', 'cough', 'wheezing', 'asthma', 'pneumonia']):
            return 'Respiratory'
        elif any(word in symptoms_lower for word in ['bone', 'fracture', 'joint', 'back', 'sprain']):
            return 'Orthopedics'
        elif age < 16:
            return 'Pediatrics'
        else:
            return 'General Medicine'

# Initialize AI Model
ai_model = TriageAIModel()
translator = Translator()

# Language support
SUPPORTED_LANGUAGES = {
    'en': 'English',
    'hi': 'हिन्दी',
    'ta': 'தமிழ்',
    'te': 'తెలుగు',
    'ml': 'മലയാളം',
    'kn': 'ಕನ್ನಡ',
    'bn': 'বাংলা',
    'gu': 'ગુજરાતી',
    'mr': 'मराठी'
}

def indian_time():
    return datetime.now(IST)

def text_to_speech(text, lang='en'):
    try:
        tts = gTTS(text=text, lang=lang, slow=False)
        fp = io.BytesIO()
        tts.write_to_fp(fp)
        fp.seek(0)
        audio_base64 = base64.b64encode(fp.read()).decode('utf-8')
        return audio_base64
    except Exception as e:
        print(f"TTS Error: {e}")
        return None

# Enhanced EHR Parser Class
class EHRParser:
    @staticmethod
    def extract_text_from_pdf(filepath):
        text = ""
        try:
            with open(filepath, 'rb') as file:
                pdf_reader = PyPDF2.PdfReader(file)
                for page in pdf_reader.pages:
                    text += page.extract_text()
        except Exception as e:
            print(f"PDF extraction error: {e}")
        return text
    
    @staticmethod
    def extract_text_from_docx(filepath):
        text = ""
        try:
            doc = docx.Document(filepath)
            for para in doc.paragraphs:
                text += para.text + "\n"
        except Exception as e:
            print(f"DOCX extraction error: {e}")
        return text
    
    @staticmethod
    def extract_patient_data(text):
        data = {
            'name': '',
            'age': '',
            'gender': '',
            'symptoms': '',
            'blood_pressure': '',
            'heart_rate': '',
            'temperature': '',
            'pre_conditions': ''
        }
        
        text_lower = text.lower()
        
        # Extract name - multiple patterns
        name_patterns = [
            r'name[:\s]*([A-Za-z\s]+?)(?:\n|$)',
            r'patient[:\s]*([A-Za-z\s]+?)(?:\n|$)',
            r'patient\s+name[:\s]*([A-Za-z\s]+?)(?:\n|$)',
            r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,3})'
        ]
        for pattern in name_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match and len(match.group(1).strip()) > 2:
                data['name'] = match.group(1).strip()
                break
        
        # Extract age
        age_patterns = [
            r'age[:\s]*(\d+)',
            r'(\d+)\s*years?\s*old',
            r'(\d+)\s*yr',
            r'age:?\s*(\d+)',
            r'(\d+)[-\s]year'
        ]
        for pattern in age_patterns:
            match = re.search(pattern, text_lower)
            if match:
                data['age'] = int(match.group(1))
                break
        
        # Extract gender
        if re.search(r'\bmale\b|\bm\b(?![a-z])', text_lower):
            data['gender'] = 'Male'
        elif re.search(r'\bfemale\b|\bf\b(?![a-z])', text_lower):
            data['gender'] = 'Female'
        
        # Extract blood pressure
        bp_pattern = r'(\d{2,3})\s*[/-]\s*(\d{2,3})'
        bp_match = re.search(bp_pattern, text)
        if bp_match:
            data['blood_pressure'] = f"{bp_match.group(1)}/{bp_match.group(2)}"
        
        # Extract heart rate
        hr_patterns = [
            r'heart\s*rate[:\s]*(\d+)',
            r'pulse[:\s]*(\d+)',
            r'hr[:\s]*(\d+)',
            r'heart rate:?\s*(\d+)',
            r'pulse rate:?\s*(\d+)'
        ]
        for pattern in hr_patterns:
            match = re.search(pattern, text_lower)
            if match:
                data['heart_rate'] = int(match.group(1))
                break
        
        # Extract temperature with unit detection
        temp_patterns = [
            r'temp(?:erature)?[:\s]*(\d+\.?\d*)\s*°?([CFcf]?)',
            r'(\d+\.?\d*)\s*°([CFcf])',
            r'temp:?\s*(\d+\.?\d*)',
            r'temperature:?\s*(\d+\.?\d*)'
        ]
        for pattern in temp_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                temp_value = float(match.group(1))
                unit = match.group(2).upper() if len(match.groups()) > 1 and match.group(2) else None
                
                # Convert to Fahrenheit if Celsius
                if unit == 'C' or (not unit and 35 <= temp_value <= 42):
                    temp_value = ai_model.celsius_to_fahrenheit(temp_value)
                
                data['temperature'] = round(temp_value, 1)
                break
        
        # Extract symptoms
        symptoms_patterns = [
            r'symptoms?[:\s]*(.*?)(?:\n\n|\n[A-Z]|$)',
            r'complaints?[:\s]*(.*?)(?:\n\n|\n[A-Z]|$)',
            r'presenting\s*(?:complaints?)?[:\s]*(.*?)(?:\n\n|\n[A-Z]|$)',
            r'chief\s*complaints?[:\s]*(.*?)(?:\n\n|\n[A-Z]|$)'
        ]
        for pattern in symptoms_patterns:
            match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
            if match and len(match.group(1).strip()) > 5:
                data['symptoms'] = match.group(1).strip()
                break
        
        # Extract pre-existing conditions
        conditions = []
        condition_keywords = ['diabetes', 'hypertension', 'asthma', 'cancer', 'heart disease', 
                            'copd', 'arthritis', 'thyroid', 'epilepsy', 'stroke', 'ckd', 'cad',
                            'high blood pressure', 'diabetic', 'asthmatic']
        for keyword in condition_keywords:
            if keyword in text_lower:
                conditions.append(keyword.title())
        if conditions:
            data['pre_conditions'] = ', '.join(conditions[:3])
        
        # Debug print
        print(f"Extracted data: {data}")
        
        return data

# ==================== ENHANCED TRANSFER DECISION ENGINE WITH HOSPITAL SELECTION ====================
class TransferDecisionEngine:
    def __init__(self):
        self.ambulance_speed_kmh = 60
        
        # Risk factors for transfer
        self.transfer_risk_factors = {
            'Critical': 0.8,  # 80% base risk for critical patients
            'High': 0.5,       # 50% base risk for high risk patients
            'Medium': 0.2,     # 20% base risk for medium risk patients
            'Low': 0.05        # 5% base risk for low risk patients
        }
    
    def calculate_distance(self, lat1, lon1, lat2, lon2):
        """Calculate distance between two coordinates using Haversine formula"""
        R = 6371  # Earth's radius in km
        dlat = math.radians(lat2 - lat1)
        dlon = math.radians(lon2 - lon1)
        a = math.sin(dlat/2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon/2)**2
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
        return R * c
    
    def calculate_eta(self, distance_km):
        """Calculate estimated time of arrival in minutes"""
        return (distance_km / self.ambulance_speed_kmh) * 60
    
    def calculate_transfer_risk(self, patient, distance_km, ambulance_available, destination_hospital):
        """
        Calculate risk of transferring patient based on multiple factors
        Returns risk score (0-1) and explanation
        """
        base_risk = self.transfer_risk_factors.get(patient.risk_level, 0.5)
        
        # Distance risk (every 10km adds 5% risk)
        distance_risk = (distance_km / 10) * 0.05
        
        # Vital instability risk
        systolic, diastolic = ai_model.extract_bp_values(patient.blood_pressure)
        vital_risk = 0
        
        if systolic > 180 or systolic < 70:
            vital_risk += 0.2
        if patient.heart_rate > 120 or patient.heart_rate < 50:
            vital_risk += 0.2
        if patient.temperature > 103 or patient.temperature < 95:
            vital_risk += 0.2
        
        # Ambulance availability risk
        ambulance_risk = 0.3 if not ambulance_available else 0
        
        # Destination hospital capability risk
        hospital_risk = 0
        if patient.risk_level == 'Critical' and not destination_hospital.get('has_icu'):
            hospital_risk = 0.5
        elif patient.risk_level == 'High' and not destination_hospital.get('has_emergency'):
            hospital_risk = 0.3
        
        # Calculate total risk (capped at 0.95)
        total_risk = min(base_risk + distance_risk + vital_risk + ambulance_risk + hospital_risk, 0.95)
        
        # Generate risk explanation
        risk_factors = []
        if distance_risk > 0.1:
            risk_factors.append(f"long distance ({distance_km:.1f}km)")
        if vital_risk > 0.2:
            risk_factors.append("unstable vitals")
        if not ambulance_available:
            risk_factors.append("no ambulance available")
        if hospital_risk > 0:
            risk_factors.append("destination lacks required facilities")
        
        if risk_factors:
            risk_explanation = f"High transfer risk due to: {', '.join(risk_factors)}"
        else:
            risk_explanation = "Moderate transfer risk - patient stable for transfer"
        
        # Survival probability
        survival_probability = 1 - total_risk
        
        return {
            'risk_score': round(total_risk, 2),
            'survival_probability': round(survival_probability, 2),
            'explanation': risk_explanation,
            'recommendation': 'TRANSFER NOT RECOMMENDED' if total_risk > 0.7 else 'Transfer feasible with precautions' if total_risk > 0.4 else 'Safe to transfer'
        }
    
    def get_ambulance_status(self, hospital_id):
        """Get real-time ambulance availability - FIXED: Returns dict, not model objects"""
        ambulances = Ambulance.query.filter_by(hospital_id=hospital_id).all()
        
        # Convert to dictionaries for JSON serialization
        available_list = []
        in_use_list = []
        
        for a in ambulances:
            amb_dict = {
                'id': a.id,
                'vehicle_number': a.vehicle_number,
                'is_available': a.is_available,
                'paramedic_count': a.paramedic_count,
                'has_life_support': a.has_life_support,
                'driver_name': a.driver_name,
                'driver_phone': a.driver_phone
            }
            
            if a.is_available:
                available_list.append(amb_dict)
            else:
                in_use_list.append(amb_dict)
        
        return {
            'available_count': len(available_list),
            'total_count': len(ambulances),
            'available': available_list,
            'in_use': in_use_list,
            'has_ambulance': len(ambulances) > 0,
            'any_available': len(available_list) > 0
        }
    
    def get_department_status(self, hospital_id, department_name):
        """Get real-time department status"""
        dept = Department.query.filter_by(
            hospital_id=hospital_id,
            name=department_name
        ).first()
        
        if dept:
            return {
                'available': dept.doctors_on_duty > 0,
                'doctors_on_duty': dept.doctors_on_duty,
                'total_doctors': dept.total_doctors,
                'is_active': dept.is_active,
                'name': dept.name
            }
        return None
    
    def find_nearby_hospitals(self, current_hospital, patient, max_distance=400):
        """Find nearby hospitals with real-time availability and capabilities"""
        nearby = []
        hospitals = Hospital.query.filter(Hospital.id != current_hospital.id).all()
        
        for hospital in hospitals:
            distance = self.calculate_distance(
                current_hospital.latitude, current_hospital.longitude,
                hospital.latitude, hospital.longitude
            )
            
            if distance <= max_distance:
                # Get real-time status
                dept_status = self.get_department_status(hospital.id, patient.recommended_department)
                amb_status = self.get_ambulance_status(hospital.id)
                
                # Calculate capability score
                capability_score = 0
                can_handle = True
                reasons = []
                capabilities = []
                
                # Check ICU for critical patients
                if patient.risk_level == 'Critical':
                    if hospital.has_icu:
                        capability_score += 40
                        capabilities.append("ICU Available")
                    else:
                        can_handle = False
                        reasons.append("No ICU")
                
                # Check Emergency for high risk
                if patient.risk_level == 'High':
                    if hospital.has_emergency:
                        capability_score += 30
                        capabilities.append("Emergency Dept")
                    else:
                        can_handle = False
                        reasons.append("No Emergency")
                
                # Check department availability
                if dept_status:
                    if dept_status['available']:
                        capability_score += dept_status['doctors_on_duty'] * 5
                        capabilities.append(f"{dept_status['doctors_on_duty']} doctors on duty")
                    else:
                        reasons.append(f"No {patient.recommended_department} doctors")
                        capability_score -= 10
                else:
                    can_handle = False
                    reasons.append(f"No {patient.recommended_department} department")
                
                # Check bed availability
                if hospital.available_beds > 0:
                    capability_score += hospital.available_beds * 3
                    capabilities.append(f"{hospital.available_beds} beds available")
                else:
                    can_handle = False
                    reasons.append("No beds")
                
                # Distance factor (closer is better)
                distance_score = max(0, 30 - distance)
                capability_score += distance_score
                
                if can_handle:
                    eta = self.calculate_eta(distance)
                    
                    # Calculate transfer risk
                    transfer_risk = self.calculate_transfer_risk(
                        patient, distance, amb_status['any_available'], 
                        {'has_icu': hospital.has_icu, 'has_emergency': hospital.has_emergency}
                    )
                    
                    nearby.append({
                        'id': hospital.id,
                        'name': hospital.hospital_name,
                        'type': hospital.hospital_type,
                        'location': hospital.location,
                        'distance': round(distance, 1),
                        'eta': round(eta, 0),
                        'available_beds': hospital.available_beds,
                        'has_icu': hospital.has_icu,
                        'has_emergency': hospital.has_emergency,
                        'contact': hospital.contact_number,
                        'doctors_available': dept_status['doctors_on_duty'] if dept_status else 0,
                        'ambulance_status': amb_status,
                        'capability_score': round(capability_score, 0),
                        'capabilities': capabilities,
                        'reasons': reasons,
                        'transfer_risk': transfer_risk,
                        'latitude': hospital.latitude,
                        'longitude': hospital.longitude,
                        'address': hospital.location
                    })
        
        # Sort by capability score (higher is better)
        nearby.sort(key=lambda x: (-x['capability_score'], x['distance']))
        return nearby
    
    def request_nearby_ambulance(self, current_hospital, patient, destination_hospital):
        """Request ambulance from nearby hospitals"""
        nearby_hospitals = Hospital.query.filter(Hospital.id != current_hospital.id).all()
        available_ambulances = []
        
        for hospital in nearby_hospitals:
            amb_status = self.get_ambulance_status(hospital.id)
            if amb_status['any_available']:
                distance = self.calculate_distance(
                    current_hospital.latitude, current_hospital.longitude,
                    hospital.latitude, hospital.longitude
                )
                if distance <= 30:  # Only within 30km
                    available_ambulances.append({
                        'hospital_name': hospital.hospital_name,
                        'hospital_id': hospital.id,
                        'available_count': amb_status['available_count'],
                        'distance': round(distance, 1),
                        'eta': round(self.calculate_eta(distance), 0),
                        'contact': hospital.contact_number
                    })
        
        return sorted(available_ambulances, key=lambda x: x['distance'])
    
    def make_transfer_decision(self, patient, current_hospital):
        """
        Make transfer decision based on resource availability and patient condition
        Includes nearby hospital selection options
        """
        # Get current status
        dept_status = self.get_department_status(current_hospital.id, patient.recommended_department)
        amb_status = self.get_ambulance_status(current_hospital.id)
        
        # Check resource availability
        beds_available = current_hospital.available_beds > 0
        doctors_available = dept_status and dept_status['available'] if dept_status else False
        appropriate_facility = True
        
        if patient.risk_level == 'Critical' and not current_hospital.has_icu:
            appropriate_facility = False
        elif patient.risk_level == 'High' and not current_hospital.has_emergency:
            appropriate_facility = False
        
        # Find nearby hospitals for potential transfer
        all_nearby = self.find_nearby_hospitals(current_hospital, patient)
        
        # Separate government and private hospitals for better display
        govt_hospitals = [h for h in all_nearby if h['type'] == 'government']
        private_hospitals = [h for h in all_nearby if h['type'] == 'private']
        
        # CASE 1: LOW RISK - always treat locally
        if patient.risk_level == 'Low':
            return {
                'should_transfer': False,
                'reason': 'Low risk patient - can be treated locally',
                'action': 'Treat in OPD',
                'department': patient.recommended_department,
                'urgency': 'Routine',
                'beds_available': beds_available,
                'doctors_available': doctors_available,
                'facility_appropriate': appropriate_facility,
                'ambulance_status': amb_status,
                'department_status': dept_status,
                'nearby_hospitals': all_nearby[:5] if all_nearby else [],
                'govt_hospitals': govt_hospitals[:5],
                'private_hospitals': private_hospitals[:5],
                'message': 'Patient can be treated at this hospital'
            }
        
        # CASE 2: Check if we have resources
        if beds_available and doctors_available and appropriate_facility:
            # We have resources, treat locally
            return {
                'should_transfer': False,
                'reason': f'Hospital has resources: {current_hospital.available_beds} beds, doctors available',
                'action': f'Admit to {"ICU" if patient.risk_level == "Critical" else "Emergency" if patient.risk_level == "High" else "Ward"}',
                'department': patient.recommended_department,
                'urgency': 'IMMEDIATE' if patient.risk_level in ['Critical', 'High'] else 'Within 2-4 hours',
                'beds_available': beds_available,
                'doctors_available': doctors_available,
                'facility_appropriate': appropriate_facility,
                'ambulance_status': amb_status,
                'department_status': dept_status,
                'nearby_hospitals': all_nearby[:5] if all_nearby else [],
                'govt_hospitals': govt_hospitals[:5],
                'private_hospitals': private_hospitals[:5],
                'message': f'Patient can be treated locally. Available beds: {current_hospital.available_beds}'
            }
        
        # CASE 3: No resources available - NEED TRANSFER
        if not beds_available or not doctors_available or not appropriate_facility:
            # Prepare resource shortage reasons
            resource_issues = []
            if not beds_available:
                resource_issues.append("no beds available")
            if not doctors_available:
                resource_issues.append(f"no {patient.recommended_department} doctors on duty")
            if not appropriate_facility:
                if patient.risk_level == 'Critical':
                    resource_issues.append("no ICU facility")
                elif patient.risk_level == 'High':
                    resource_issues.append("no emergency department")
            
            issues_text = ", ".join(resource_issues)
            
            # If no nearby hospitals, return transfer required but no options
            if not all_nearby:
                return {
                    'should_transfer': True,
                    'reason': f'Cannot treat locally: {issues_text}',
                    'action': 'TRANSFER REQUIRED - NO NEARBY HOSPITALS FOUND',
                    'nearby_hospitals': [],
                    'govt_hospitals': [],
                    'private_hospitals': [],
                    'urgency': 'CRITICAL - CONTACT EMERGENCY SERVICES',
                    'beds_available': beds_available,
                    'doctors_available': doctors_available,
                    'facility_appropriate': appropriate_facility,
                    'ambulance_status': amb_status,
                    'department_status': dept_status,
                    'resource_issues': resource_issues,
                    'message': f"⚠️ TRANSFER REQUIRED: {issues_text}. No nearby hospitals found within range!",
                    'show_selection': False
                }
            
            # Find best nearby hospital (already sorted by capability score)
            best_hospital = all_nearby[0]
            
            # Check if we have ambulance
            if amb_status['any_available']:
                ambulance_msg = f"Our ambulance (ETA: {best_hospital['eta']} mins)"
            else:
                # Need to request ambulance from nearby
                nearby_ambulances = self.request_nearby_ambulance(current_hospital, patient, best_hospital)
                if nearby_ambulances:
                    ambulance_msg = f"Request ambulance from {nearby_ambulances[0]['hospital_name']} (ETA: {nearby_ambulances[0]['eta']} mins) - Contact: {nearby_ambulances[0]['contact']}"
                else:
                    ambulance_msg = "⚠️ NO AMBULANCE AVAILABLE IN REGION - Critical situation! Patient may need private transport."
            
            # Check if transfer is safe
            transfer_risk = best_hospital['transfer_risk']
            if transfer_risk['risk_score'] > 0.7:
                survival_msg = f"⚠️ HIGH RISK: Patient has only {transfer_risk['survival_probability']*100}% chance of surviving transfer. {transfer_risk['explanation']}"
                survival_color = "danger"
            elif transfer_risk['risk_score'] > 0.4:
                survival_msg = f"⚠️ MODERATE RISK: Patient has {transfer_risk['survival_probability']*100}% chance of surviving transfer. {transfer_risk['explanation']}"
                survival_color = "warning"
            else:
                survival_msg = f"✅ LOW RISK: Patient has {transfer_risk['survival_probability']*100}% chance of surviving transfer. {transfer_risk['explanation']}"
                survival_color = "success"
            
            return {
                'should_transfer': True,
                'reason': f'Cannot treat locally: {issues_text}',
                'action': 'URGENT TRANSFER REQUIRED',
                'recommended_hospital': best_hospital,
                'nearby_hospitals': all_nearby,  # Send ALL nearby hospitals
                'govt_hospitals': govt_hospitals[:5],  # Top 5 government
                'private_hospitals': private_hospitals[:5],  # Top 5 private
                'alternative_hospitals': all_nearby[1:4] if len(all_nearby) > 1 else [],
                'urgency': 'CRITICAL - TRANSFER NOW' if patient.risk_level == 'Critical' else 'IMMEDIATE',
                'beds_available': beds_available,
                'doctors_available': doctors_available,
                'facility_appropriate': appropriate_facility,
                'ambulance_status': amb_status,
                'ambulance_arrangement': ambulance_msg,
                'transfer_risk': transfer_risk,
                'survival_message': survival_msg,
                'survival_color': survival_color,
                'department_status': dept_status,
                'resource_issues': resource_issues,
                'message': f"⚠️ TRANSFER REQUIRED: {issues_text}. Best option: {best_hospital['name']} ({best_hospital['distance']}km, {best_hospital['eta']} mins)",
                'show_selection': True  # Flag to show hospital selection UI
            }
        
        # Default fallback
        return {
            'should_transfer': False,
            'reason': 'Unable to determine - consult senior doctor',
            'action': 'Manual review required',
            'department': patient.recommended_department,
            'urgency': 'ASAP',
            'beds_available': beds_available,
            'doctors_available': doctors_available,
            'facility_appropriate': appropriate_facility,
            'ambulance_status': amb_status,
            'department_status': dept_status,
            'nearby_hospitals': all_nearby[:3] if all_nearby else [],
            'govt_hospitals': govt_hospitals[:3] if govt_hospitals else [],
            'private_hospitals': private_hospitals[:3] if private_hospitals else [],
            'message': 'Manual intervention needed',
            'show_selection': False
        }

# Initialize Transfer Engine
transfer_engine = TransferDecisionEngine()

@app.route('/')
def index():
    return render_template('index.html', languages=SUPPORTED_LANGUAGES)

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        existing_hospital = Hospital.query.filter_by(hospital_id=request.form['hospital_id']).first()
        if existing_hospital:
            flash('Hospital ID already exists. Please choose a different ID.', 'danger')
            return render_template('signup.html')
        
        try:
            latitude = float(request.form.get('latitude', 0))
            longitude = float(request.form.get('longitude', 0))
            
            ambulance_count = int(request.form.get('ambulance_count', 1))
            
            # Calculate total doctors from departments
            department_names = request.form.getlist('departments[]')
            total_doctors = 0
            for dept_name in department_names:
                if dept_name:
                    dept_doctors = int(request.form.get(f'doctors_{dept_name}', 0))
                    total_doctors += dept_doctors
            
            hospital = Hospital(
                hospital_id=request.form['hospital_id'],
                hospital_name=request.form['hospital_name'],
                location=request.form['location'],
                area_type=request.form['area_type'],
                hospital_type=request.form['hospital_type'],
                latitude=latitude,
                longitude=longitude,
                address=request.form.get('address', ''),
                total_doctors=total_doctors,
                nurses_count=int(request.form.get('nurses_count', 0)),
                wardboys_count=int(request.form.get('wardboys_count', 0)),
                total_beds=int(request.form.get('total_beds', 0)),
                available_beds=int(request.form.get('total_beds', 0)),
                has_operation_theater='has_operation' in request.form,
                has_icu='has_icu' in request.form,
                has_emergency='has_emergency' in request.form,
                contact_number=request.form['contact_number'],
                ambulance_count=ambulance_count
            )
            hospital.set_password(request.form['password'])
            
            db.session.add(hospital)
            db.session.commit()
            
            # Add departments
            for dept_name in department_names:
                if dept_name:
                    dept = Department(
                        hospital_id=hospital.id,
                        name=dept_name,
                        total_doctors=int(request.form.get(f'doctors_{dept_name}', 2)),
                        doctors_on_duty=int(request.form.get(f'duty_{dept_name}', 1)),
                        on_call_doctors=int(request.form.get(f'oncall_{dept_name}', 0)),
                        emergency_contact=hospital.contact_number,
                        is_active=True
                    )
                    db.session.add(dept)
            
            # Create ambulances
            for i in range(ambulance_count):
                ambulance = Ambulance(
                    hospital_id=hospital.id,
                    vehicle_number=f"AMB{random.randint(100, 999)}-{i+1}",
                    is_available=True,
                    current_latitude=latitude,
                    current_longitude=longitude,
                    paramedic_count=random.randint(1, 3),
                    has_life_support=True,
                    driver_name=f"Driver {random.randint(1, 10)}",
                    driver_phone=hospital.contact_number
                )
                db.session.add(ambulance)
            
            db.session.commit()
            
            flash('Hospital registered successfully! Please login.', 'success')
            return redirect(url_for('login'))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Registration failed: {str(e)}', 'danger')
            return render_template('signup.html')
    
    return render_template('signup.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        hospital_id = request.form['hospital_id']
        password = request.form['password']
        
        hospital = Hospital.query.filter_by(hospital_id=hospital_id).first()
        
        if hospital and hospital.check_password(password):
            login_user(hospital)
            session['language'] = 'en'
            flash('Logged in successfully!', 'success')
            return redirect(url_for('dashboard'))
        elif hospital:
            flash('Invalid password. Please try again.', 'danger')
        else:
            flash(f'Hospital ID "{hospital_id}" not found. Please register first.', 'danger')
    
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('index'))

@app.route('/set_language/<lang>')
def set_language(lang):
    if lang in SUPPORTED_LANGUAGES:
        session['language'] = lang
    return redirect(request.referrer or url_for('index'))

@app.route('/dashboard')
@login_required
def dashboard():
    # FIX: Validate bed counts before displaying
    hospital = Hospital.query.get(current_user.id)
    
    # Count currently admitted patients (not discharged, not transferred)
    admitted_patients = Patient.query.filter(
        Patient.hospital_id == current_user.id,
        Patient.discharge_date.is_(None),
        Patient.treatment_decision != 'Transfer Required',
        Patient.outcome.notin_(['OPD Consultation', 'Discharged'])
    ).count()
    
    # Fix bed inconsistency
    expected_available = hospital.total_beds - admitted_patients
    if hospital.available_beds != expected_available:
        print(f"⚠️ Fixing bed inconsistency: {hospital.available_beds} → {expected_available}")
        hospital.available_beds = max(0, expected_available)
        db.session.commit()
    
    # Get recent patients
    recent_patients = Patient.query.filter_by(hospital_id=current_user.id)\
        .order_by(Patient.created_at.desc()).limit(10).all()
    
    # Calculate statistics
    total_patients = Patient.query.filter_by(hospital_id=current_user.id).count()
    critical_patients = Patient.query.filter_by(hospital_id=current_user.id, risk_level='Critical').count()
    high_risk = Patient.query.filter_by(hospital_id=current_user.id, risk_level='High').count()
    medium_risk = Patient.query.filter_by(hospital_id=current_user.id, risk_level='Medium').count()
    low_risk = Patient.query.filter_by(hospital_id=current_user.id, risk_level='Low').count()
    
    transferred = Patient.query.filter(
        Patient.hospital_id == current_user.id,
        Patient.treatment_decision.like('%Transfer%')
    ).count()
    
    # Get ambulance data
    ambulances = Ambulance.query.filter_by(hospital_id=current_user.id).all()
    available_ambulances = sum(1 for a in ambulances if a.is_available)
    total_ambulances = len(ambulances)
    
    # Get departments
    departments = Department.query.filter_by(hospital_id=current_user.id, is_active=True).all()
    
    # Calculate ambulance status
    if total_ambulances > 0:
        if available_ambulances > 0:
            ambulance_status = f"{available_ambulances}/{total_ambulances} Available"
        else:
            ambulance_status = "All Ambulances In Use"
    else:
        ambulance_status = "No Ambulances"
    
    # Calculate bed occupancy
    bed_occupancy = 0
    if hospital.total_beds and hospital.total_beds > 0:
        bed_occupancy = ((hospital.total_beds - hospital.available_beds) / hospital.total_beds) * 100
    
    # Create stats dictionary
    stats = {
        'total': total_patients,
        'critical': critical_patients,
        'high': high_risk,
        'medium': medium_risk,
        'low': low_risk,
        'transferred': transferred
    }
    
    # ============= RISK CHART (Pie Chart) =============
    if total_patients > 0:
        fig_risk = go.Figure(data=[go.Pie(
            labels=['Critical', 'High', 'Medium', 'Low'],
            values=[critical_patients, high_risk, medium_risk, low_risk],
            marker=dict(
                colors=['black', '#ff4444', '#ffbb33', '#00C851'],
                line=dict(color='white', width=2)
            ),
            textinfo='label+percent',
            textposition='inside',
            hole=0.4,
            pull=[0.1 if v > 0 else 0 for v in [critical_patients, high_risk, medium_risk, low_risk]]
        )])
        fig_risk.update_layout(
            title="Patient Risk Distribution",
            annotations=[dict(text='Risk Levels', x=0.5, y=0.5, font_size=20, showarrow=False)],
            height=400,
            template='plotly_white',
            showlegend=False
        )
        risk_chart = json.dumps(fig_risk, cls=plotly.utils.PlotlyJSONEncoder)
    else:
        # Create empty chart with message
        fig_risk = go.Figure()
        fig_risk.add_annotation(
            text="No patient data available",
            xref="paper", yref="paper",
            x=0.5, y=0.5, showarrow=False,
            font=dict(size=20)
        )
        fig_risk.update_layout(height=400, template='plotly_white')
        risk_chart = json.dumps(fig_risk, cls=plotly.utils.PlotlyJSONEncoder)
    
    # ============= DEPARTMENT CHART =============
    dept_data = db.session.query(
        Patient.recommended_department, 
        db.func.count(Patient.id)
    ).filter_by(hospital_id=current_user.id).group_by(Patient.recommended_department).all()
    
    if dept_data and len(dept_data) > 0:
        dept_names = [d[0] for d in dept_data if d[0]]
        dept_counts = [d[1] for d in dept_data if d[0]]
        
        fig_dept = go.Figure(data=[go.Bar(
            x=dept_names,
            y=dept_counts,
            marker=dict(
                color=dept_counts,
                colorscale='Viridis',
                showscale=True,
                colorbar=dict(title="Patient Count")
            ),
            text=dept_counts,
            textposition='outside',
            hovertemplate='<b>%{x}</b><br>Patients: %{y}<extra></extra>'
        )])
        fig_dept.update_layout(
            title="Department-wise Patient Distribution",
            xaxis_title="Department",
            yaxis_title="Number of Patients",
            height=400,
            template='plotly_white'
        )
        dept_chart = json.dumps(fig_dept, cls=plotly.utils.PlotlyJSONEncoder)
    else:
        # Create empty chart with message
        fig_dept = go.Figure()
        fig_dept.add_annotation(
            text="No department data available",
            xref="paper", yref="paper",
            x=0.5, y=0.5, showarrow=False,
            font=dict(size=20)
        )
        fig_dept.update_layout(height=400, template='plotly_white')
        dept_chart = json.dumps(fig_dept, cls=plotly.utils.PlotlyJSONEncoder)
    
    return render_template('dashboard.html', 
                         hospital=hospital,
                         patients=recent_patients,
                         now=datetime.now(IST),
                         bed_occupancy=bed_occupancy,
                         ambulances=ambulances,
                         available_ambulances=available_ambulances,
                         total_ambulances=total_ambulances,
                         departments=departments,
                         ambulance_status=ambulance_status,
                         risk_chart=risk_chart,
                         dept_chart=dept_chart,
                         languages=SUPPORTED_LANGUAGES,
                         current_lang=session.get('language', 'en'),
                         stats=stats)

@app.route('/new_patient', methods=['GET', 'POST'])
@login_required
def new_patient():
    if request.method == 'POST':
        # CRITICAL FIX: Check bed availability BEFORE processing
        hospital = Hospital.query.get(current_user.id)
        
        # Count currently admitted patients
        admitted_count = Patient.query.filter(
            Patient.hospital_id == current_user.id,
            Patient.discharge_date.is_(None),
            Patient.treatment_decision != 'Transfer Required',
            Patient.outcome.notin_(['OPD Consultation', 'Discharged'])
        ).count()
        
        # Calculate ACTUAL available beds
        actual_available = hospital.total_beds - admitted_count
        if hospital.available_beds != actual_available:
            # Fix inconsistency
            print(f"⚠️ Fixing bed inconsistency in new_patient: {hospital.available_beds} → {actual_available}")
            hospital.available_beds = actual_available
            db.session.commit()
        
        patient_id = f"P{datetime.now(IST).strftime('%Y%m%d%H%M%S')}"
        
        patient = Patient(
            patient_id=patient_id,
            hospital_id=current_user.id,
            name=request.form.get('name', 'Unknown'),
            age=int(request.form['age']),
            gender=request.form['gender'],
            symptoms=request.form['symptoms'],
            blood_pressure=request.form['blood_pressure'],
            heart_rate=int(request.form['heart_rate']),
            temperature=float(request.form['temperature']),
            pre_existing_conditions=request.form.get('pre_conditions', 'None'),
            is_admitted=False,
            admission_date=datetime.now(IST)
        )
        
        risk_level, risk_color, confidence = ai_model.predict_risk(
            patient.age,
            patient.heart_rate,
            patient.temperature,
            patient.blood_pressure,
            patient.symptoms,
            patient.pre_existing_conditions
        )
        
        department = ai_model.recommend_department(
            risk_level, 
            patient.symptoms, 
            patient.age,
            patient.blood_pressure,
            patient.heart_rate
        )
        
        medical_explanation, future_symptoms = ai_model.generate_medical_explanation(
            risk_level,
            patient.age,
            patient.symptoms,
            patient.blood_pressure,
            patient.heart_rate,
            patient.temperature,
            patient.pre_existing_conditions
        )
        
        patient.risk_level = risk_level
        patient.risk_color = risk_color
        patient.confidence_score = confidence
        patient.recommended_department = department
        patient.explainability = medical_explanation
        patient.medical_explanation = medical_explanation
        patient.future_symptoms = future_symptoms
        
        # Make transfer decision using updated engine
        transfer_decision = transfer_engine.make_transfer_decision(patient, hospital)
        
        if transfer_decision['should_transfer']:
            patient.treatment_decision = 'Transfer Required'
            patient.outcome = 'Transfer Initiated'
            patient.is_admitted = False
            
            # Don't set transferred_to yet - will be set when user selects hospital
            if 'recommended_hospital' in transfer_decision:
                # Store recommended hospital but don't commit transfer yet
                patient.transferred_to = None
                patient.transferred_to_id = None
        else:
            # Treat locally
            patient.treatment_decision = 'Treat Local'
            
            # Set outcome and expected discharge based on risk
            if risk_level == 'Critical':
                patient.outcome = 'ICU Admission'
                patient.expected_discharge = datetime.now(IST) + timedelta(days=3)
                patient.is_admitted = True
            elif risk_level == 'High':
                patient.outcome = 'Emergency Admission'
                patient.expected_discharge = datetime.now(IST) + timedelta(days=1)
                patient.is_admitted = True
            elif risk_level == 'Medium':
                patient.outcome = 'Ward Admission'
                patient.expected_discharge = datetime.now(IST) + timedelta(hours=12)
                patient.is_admitted = True
            else:
                patient.outcome = 'OPD Consultation'
                patient.expected_discharge = datetime.now(IST) + timedelta(hours=2)
                patient.is_admitted = False  # OPD doesn't use bed
            
            # Allocate bed only if admitted AND bed available
            if patient.is_admitted:
                if hospital.available_beds > 0:
                    # Find first available bed number
                    used_beds = [p.bed_number for p in Patient.query.filter_by(
                        hospital_id=current_user.id,
                        is_admitted=True
                    ).all() if p.bed_number]
                    
                    for bed_num in range(1, hospital.total_beds + 1):
                        if bed_num not in used_beds:
                            patient.bed_number = bed_num
                            break
                    
                    # Decrease available beds
                    hospital.available_beds = hospital.available_beds - 1
                    print(f"✅ Bed allocated: {patient.bed_number}. Remaining beds: {hospital.available_beds}")
                else:
                    # This should not happen due to transfer decision, but just in case
                    patient.treatment_decision = 'Transfer Required'
                    patient.outcome = 'Transfer Initiated - No Beds'
                    patient.is_admitted = False
        
        patient.wait_time_minutes = random.randint(5, 30)
        
        db.session.add(patient)
        db.session.commit()
        
        audio_data = text_to_speech(medical_explanation[:500], session.get('language', 'en'))
        
        return jsonify({
            'success': True,
            'patient_id': patient_id,
            'risk_level': risk_level,
            'risk_color': risk_color,
            'confidence': float(confidence),
            'department': department,
            'explanation': medical_explanation,
            'future_symptoms': future_symptoms,
            'decision': patient.treatment_decision,
            'outcome': patient.outcome,
            'transfer_details': transfer_decision if transfer_decision['should_transfer'] else None,
            'urgency': transfer_decision.get('urgency', 'Normal'),
            'audio': audio_data,
            'message': transfer_decision.get('message', '')
        })
    
    departments = Department.query.filter_by(
        hospital_id=current_user.id, 
        is_active=True
    ).all()
    
    return render_template('new_patient.html', 
                         departments=departments,
                         languages=SUPPORTED_LANGUAGES,
                         current_lang=session.get('language', 'en'))

# Add confirm transfer endpoint
@app.route('/api/confirm_transfer', methods=['POST'])
@login_required
def confirm_transfer():
    """Confirm transfer to selected hospital"""
    data = request.json
    patient_id = data.get('patient_id')
    hospital_id = data.get('hospital_id')
    
    patient = Patient.query.filter_by(
        patient_id=patient_id,
        hospital_id=current_user.id
    ).first()
    
    if not patient:
        return jsonify({'error': 'Patient not found'}), 404
    
    destination = Hospital.query.get(hospital_id)
    if not destination:
        return jsonify({'error': 'Destination hospital not found'}), 404
    
    # Update patient record
    patient.transferred_to = destination.hospital_name
    patient.transferred_to_id = destination.id
    patient.treatment_decision = 'Transfer Confirmed'
    patient.outcome = f'Transferred to {destination.hospital_name}'
    
    # Calculate distance and ETA for ambulance
    distance = transfer_engine.calculate_distance(
        current_user.latitude, current_user.longitude,
        destination.latitude, destination.longitude
    )
    eta = transfer_engine.calculate_eta(distance)
    
    # Dispatch ambulance
    ambulance = Ambulance.query.filter_by(
        hospital_id=current_user.id,
        is_available=True
    ).first()
    
    if ambulance:
        ambulance.is_available = False
        ambulance.in_use_since = datetime.now(IST)
        ambulance.estimated_return_time = datetime.now(IST) + timedelta(minutes=int(eta * 2 + 30))
        ambulance.destination_hospital = destination.hospital_name
    
    db.session.commit()
    
    return jsonify({
        'success': True,
        'message': f'Transfer confirmed to {destination.hospital_name}',
        'eta': round(eta, 0)
    })

@app.route('/discharge_patient/<patient_id>', methods=['POST'])
@login_required
def discharge_patient(patient_id):
    """Discharge patient and free up bed"""
    patient = Patient.query.filter_by(
        patient_id=patient_id, 
        hospital_id=current_user.id
    ).first()
    
    if not patient:
        return jsonify({'error': 'Patient not found'}), 404
    
    if patient.discharge_date:
        return jsonify({'error': 'Patient already discharged'}), 400
    
    # Free up the bed
    hospital = Hospital.query.get(current_user.id)
    if patient.is_admitted and patient.bed_number:
        hospital.available_beds = hospital.available_beds + 1
        print(f"✅ Bed {patient.bed_number} freed. Available beds now: {hospital.available_beds}")
    
    patient.discharge_date = datetime.now(IST)
    patient.is_admitted = False
    patient.outcome = 'Discharged'
    
    db.session.commit()
    
    return jsonify({
        'success': True, 
        'message': f'Patient {patient.name} discharged, bed freed'
    })

@app.route('/api/fix_beds', methods=['POST'])
@login_required
def fix_beds():
    """Fix bed count inconsistencies"""
    hospital = Hospital.query.get(current_user.id)
    
    # Count currently admitted patients
    admitted = Patient.query.filter(
        Patient.hospital_id == current_user.id,
        Patient.discharge_date.is_(None),
        Patient.treatment_decision != 'Transfer Required',
        Patient.outcome.notin_(['OPD Consultation', 'Discharged'])
    ).count()
    
    # Correct available beds
    hospital.available_beds = hospital.total_beds - admitted
    db.session.commit()
    
    return jsonify({
        'success': True,
        'message': f'Bed count fixed. Available beds: {hospital.available_beds}',
        'available_beds': hospital.available_beds,
        'admitted_patients': admitted
    })

@app.route('/process_voice_text', methods=['POST'])
@login_required
def process_voice_text():
    try:
        data = request.get_json()
        text = data.get('text', '')
        target_lang = data.get('lang', 'en')
        
        if not text:
            return jsonify({'error': 'No text provided'}), 400
        
        try:
            detected_lang = translator.detect(text).lang
            if detected_lang != target_lang:
                text = translator.translate(text, dest=target_lang).text
        except:
            detected_lang = 'en'
        
        return jsonify({
            'success': True,
            'text': text,
            'detected_language': detected_lang,
            'target_language': target_lang
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/upload_ehr', methods=['POST'])
@login_required
def upload_ehr():
    if 'file' not in request.files:
        return jsonify({'error': 'No file uploaded'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400
    
    try:
        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)
        
        text = ""
        if filename.endswith('.txt'):
            with open(filepath, 'r', encoding='utf-8') as f:
                text = f.read()
        elif filename.endswith('.pdf'):
            text = EHRParser.extract_text_from_pdf(filepath)
        elif filename.endswith('.docx'):
            text = EHRParser.extract_text_from_docx(filepath)
        else:
            # For demo purposes, create sample text
            text = """
            Patient Name: John Doe
            Age: 45 years
            Gender: Male
            Blood Pressure: 130/85
            Heart Rate: 78 bpm
            Temperature: 37.2°C
            Symptoms: Chest pain and shortness of breath for the past 2 hours
            Pre-existing Conditions: Hypertension, Type 2 Diabetes
            """
        
        parser = EHRParser()
        extracted_data = parser.extract_patient_data(text)
        
        # Clean up
        try:
            os.remove(filepath)
        except:
            pass
        
        print(f"Sending extracted data: {extracted_data}")
        return jsonify(extracted_data)
        
    except Exception as e:
        print(f"Error parsing file: {str(e)}")
        return jsonify({'error': f'Error parsing file: {str(e)}'}), 500

@app.route('/api/ambulance/status', methods=['GET'])
@login_required
def get_ambulance_status():
    """Get ambulance status - FIXED: Returns dict, not model objects"""
    ambulances = Ambulance.query.filter_by(hospital_id=current_user.id).all()
    
    status = []
    for amb in ambulances:
        status.append({
            'id': amb.id,
            'vehicle_number': amb.vehicle_number,
            'is_available': amb.is_available,
            'paramedic_count': amb.paramedic_count,
            'has_life_support': amb.has_life_support,
            'destination': amb.destination_hospital,
            'estimated_return': amb.estimated_return_time.strftime('%H:%M') if amb.estimated_return_time else None,
            'driver_name': amb.driver_name,
            'driver_phone': amb.driver_phone
        })
    
    return jsonify({
        'available': sum(1 for a in ambulances if a.is_available),
        'total': len(ambulances),
        'ambulances': status
    })

@app.route('/api/ambulance/update', methods=['POST'])
@login_required
def update_ambulance():
    data = request.json
    new_count = data.get('count', 0)
    
    current_count = Ambulance.query.filter_by(hospital_id=current_user.id).count()
    
    if new_count > current_count:
        for i in range(new_count - current_count):
            ambulance = Ambulance(
                hospital_id=current_user.id,
                vehicle_number=f"AMB{random.randint(100, 999)}-{current_count + i + 1}",
                is_available=True,
                current_latitude=current_user.latitude,
                current_longitude=current_user.longitude,
                paramedic_count=2,
                has_life_support=True,
                driver_name=f"Driver {random.randint(1, 10)}",
                driver_phone=current_user.contact_number
            )
            db.session.add(ambulance)
    elif new_count < current_count:
        excess = Ambulance.query.filter_by(
            hospital_id=current_user.id,
            is_available=True
        ).limit(current_count - new_count).all()
        for amb in excess:
            db.session.delete(amb)
    
    current_user.ambulance_count = new_count
    db.session.commit()
    
    return jsonify({'success': True, 'message': 'Ambulance fleet updated'})

@app.route('/api/department/status', methods=['GET'])
@login_required
def get_department_status():
    departments = Department.query.filter_by(
        hospital_id=current_user.id,
        is_active=True
    ).all()
    
    status = []
    for dept in departments:
        status.append({
            'id': dept.id,
            'name': dept.name,
            'doctors_on_duty': dept.doctors_on_duty,
            'total_doctors': dept.total_doctors,
            'on_call': dept.on_call_doctors,
            'available': dept.doctors_on_duty > 0
        })
    
    return jsonify(status)

@app.route('/api/department/update', methods=['POST'])
@login_required
def update_department():
    data = request.json
    dept_id = data.get('department_id')
    doctors_on_duty = data.get('doctors_on_duty')
    total_doctors = data.get('total_doctors')
    
    dept = Department.query.filter_by(
        id=dept_id,
        hospital_id=current_user.id
    ).first()
    
    if not dept:
        return jsonify({'error': 'Department not found'}), 404
    
    if doctors_on_duty is not None:
        dept.doctors_on_duty = doctors_on_duty
    if total_doctors is not None:
        dept.total_doctors = total_doctors
    
    # Update hospital total doctors
    all_depts = Department.query.filter_by(hospital_id=current_user.id).all()
    current_user.total_doctors = sum(d.total_doctors for d in all_depts)
    
    dept.last_updated = datetime.now(IST)
    db.session.commit()
    
    return jsonify({
        'success': True,
        'message': f'{dept.name} department updated',
        'total_doctors': current_user.total_doctors
    })

@app.route('/api/department/add', methods=['POST'])
@login_required
def add_department():
    data = request.json
    name = data.get('name')
    
    existing = Department.query.filter_by(
        hospital_id=current_user.id,
        name=name
    ).first()
    
    if existing:
        return jsonify({'error': 'Department already exists'}), 400
    
    dept = Department(
        hospital_id=current_user.id,
        name=name,
        total_doctors=data.get('total_doctors', 2),
        doctors_on_duty=data.get('doctors_on_duty', 1),
        on_call_doctors=data.get('on_call_doctors', 0),
        emergency_contact=current_user.contact_number,
        is_active=True
    )
    
    db.session.add(dept)
    
    # Update hospital total doctors
    all_depts = Department.query.filter_by(hospital_id=current_user.id).all()
    current_user.total_doctors = sum(d.total_doctors for d in all_depts) + dept.total_doctors
    
    db.session.commit()
    
    return jsonify({'success': True, 'message': f'{name} department added'})

@app.route('/patient_history')
@login_required
def patient_history():
    three_months_ago = datetime.now(IST) - timedelta(days=90)
    
    # Get sort parameter
    sort_by = request.args.get('sort', 'date_desc')
    risk_filter = request.args.get('risk')
    status_filter = request.args.get('status')  # admitted/discharged/all
    
    query = Patient.query.filter(
        Patient.hospital_id == current_user.id,
        Patient.created_at >= three_months_ago
    )
    
    # Apply risk filter
    if risk_filter and risk_filter != 'all':
        query = query.filter(Patient.risk_level == risk_filter.capitalize())
    
    # Apply status filter
    if status_filter == 'admitted':
        query = query.filter(Patient.is_admitted == True)
    elif status_filter == 'discharged':
        query = query.filter(Patient.discharge_date.isnot(None))
    
    # Apply sorting
    if sort_by == 'date_desc':
        query = query.order_by(Patient.created_at.desc())
    elif sort_by == 'date_asc':
        query = query.order_by(Patient.created_at.asc())
    elif sort_by == 'time_desc':
        query = query.order_by(Patient.created_at.desc())
    elif sort_by == 'time_asc':
        query = query.order_by(Patient.created_at.asc())
    
    patients = query.all()
    
    return render_template('history.html', 
                         patients=patients, 
                         hospital=current_user, 
                         now=datetime.now(IST),
                         sort_by=sort_by,
                         languages=SUPPORTED_LANGUAGES,
                         current_lang=session.get('language', 'en'))

@app.route('/patient/<patient_id>')
@login_required
def patient_detail(patient_id):
    patient = Patient.query.filter_by(patient_id=patient_id, hospital_id=current_user.id).first_or_404()
    return render_template('patient_detail.html', 
                         patient=patient, 
                         now=datetime.now(IST),
                         languages=SUPPORTED_LANGUAGES,
                         current_lang=session.get('language', 'en'))

@app.route('/hospital_profile')
@login_required
def hospital_profile():
    departments = Department.query.filter_by(hospital_id=current_user.id).all()
    ambulances = Ambulance.query.filter_by(hospital_id=current_user.id).all()
    
    # Department chart
    dept_names = [d.name for d in departments]
    dept_on_duty = [d.doctors_on_duty for d in departments]
    dept_total = [d.total_doctors for d in departments]
    
    fig_dept = go.Figure()
    fig_dept.add_trace(go.Bar(
        name='On Duty',
        x=dept_names,
        y=dept_on_duty,
        marker_color='green'
    ))
    fig_dept.add_trace(go.Bar(
        name='Off Duty',
        x=dept_names,
        y=[d.total_doctors - d.doctors_on_duty for d in departments],
        marker_color='red'
    ))
    fig_dept.update_layout(
        title="Doctor Availability by Department",
        barmode='stack',
        height=400,
        template='plotly_white'
    )
    dept_chart = json.dumps(fig_dept, cls=plotly.utils.PlotlyJSONEncoder)
    
    # Ambulance chart
    amb_available = sum(1 for a in ambulances if a.is_available)
    amb_in_use = len(ambulances) - amb_available
    
    fig_amb = go.Figure(data=[go.Pie(
        labels=['Available', 'In Use'],
        values=[amb_available, amb_in_use],
        marker_colors=['green', 'red'],
        hole=0.4,
        textinfo='label+percent'
    )])
    fig_amb.update_layout(title="Ambulance Status", height=300, template='plotly_white')
    amb_chart = json.dumps(fig_amb, cls=plotly.utils.PlotlyJSONEncoder)
    
    return render_template('profile.html', 
                         hospital=current_user,
                         departments=departments,
                         ambulances=ambulances,
                         dept_chart=dept_chart,
                         amb_chart=amb_chart,
                         languages=SUPPORTED_LANGUAGES,
                         current_lang=session.get('language', 'en'))

@app.route('/api/nearby_hospitals/<patient_id>')
@login_required
def get_nearby_hospitals(patient_id):
    patient = Patient.query.filter_by(patient_id=patient_id, hospital_id=current_user.id).first()
    
    if not patient:
        return jsonify({'error': 'Patient not found'}), 404
    
    nearby = transfer_engine.find_nearby_hospitals(current_user, patient)
    
    govt_hospitals = [h for h in nearby if h['type'] == 'government']
    private_hospitals = [h for h in nearby if h['type'] == 'private']
    
    return jsonify({
        'all': nearby,
        'government': govt_hospitals[:3],
        'private': private_hospitals[:3],
        'best': nearby[0] if nearby else None
    })

@app.route('/api/text_to_speech', methods=['POST'])
@login_required
def api_text_to_speech():
    data = request.json
    text = data.get('text', '')
    lang = data.get('lang', 'en')
    
    audio_data = text_to_speech(text, lang)
    
    if audio_data:
        return jsonify({'success': True, 'audio': audio_data})
    else:
        return jsonify({'error': 'Could not generate speech'}), 500

if __name__ == '__main__':
    with app.app_context():
        # Only create tables if they don't exist
        db.create_all()
        print("=" * 80)
        print("✅ AI PATIENT TRIAGE SYSTEM - READY")
        print("=" * 80)
        print("📌 Access at: http://localhost:5000")
        print("\n📋 Database Persistence ENABLED:")
        print("   ✓ Data will now persist between restarts")
        print("   ✓ No more dropping tables on every run")
        print("=" * 80)
    
    app.run(debug=True, host='0.0.0.0', port=5000)