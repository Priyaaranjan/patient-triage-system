from app import app, db, Hospital, Department, Ambulance
import random
from datetime import datetime

def add_sample_hospitals():
    with app.app_context():
        # Check if we already have hospitals
        existing = Hospital.query.count()
        if existing > 1:
            print(f"✅ Found {existing} hospitals already in database")
            return
        
        print("Adding sample hospitals for testing...")
        
        # Sample hospitals in different locations
        sample_hospitals = [
            {
                'hospital_id': 'GOV001',
                'hospital_name': 'City Government Hospital',
                'location': 'Central District',
                'area_type': 'urban',
                'hospital_type': 'government',
                'latitude': 28.6139,
                'longitude': 77.2090,
                'total_beds': 50,
                'available_beds': 25,
                'has_icu': True,
                'has_emergency': True,
                'contact_number': '011-12345678',
                'ambulance_count': 3
            },
            {
                'hospital_id': 'PRI001',
                'hospital_name': 'Apollo Medical Center',
                'location': 'South Extension',
                'area_type': 'urban',
                'hospital_type': 'private',
                'latitude': 28.5678,
                'longitude': 77.2198,
                'total_beds': 30,
                'available_beds': 12,
                'has_icu': True,
                'has_emergency': True,
                'contact_number': '011-87654321',
                'ambulance_count': 2
            },
            {
                'hospital_id': 'GOV002',
                'hospital_name': 'Rural Community Health Center',
                'location': 'North Village',
                'area_type': 'rural',
                'hospital_type': 'government',
                'latitude': 28.7123,
                'longitude': 77.1987,
                'total_beds': 20,
                'available_beds': 8,
                'has_icu': False,
                'has_emergency': True,
                'contact_number': '011-11223344',
                'ambulance_count': 1
            },
            {
                'hospital_id': 'PRI002',
                'hospital_name': 'Fortis Hospital',
                'location': 'West District',
                'area_type': 'urban',
                'hospital_type': 'private',
                'latitude': 28.6345,
                'longitude': 77.1876,
                'total_beds': 40,
                'available_beds': 18,
                'has_icu': True,
                'has_emergency': True,
                'contact_number': '011-99887766',
                'ambulance_count': 2
            },
            {
                'hospital_id': 'GOV003',
                'hospital_name': 'District General Hospital',
                'location': 'East Township',
                'area_type': 'rural',
                'hospital_type': 'government',
                'latitude': 28.6890,
                'longitude': 77.2345,
                'total_beds': 35,
                'available_beds': 15,
                'has_icu': True,
                'has_emergency': True,
                'contact_number': '011-55667788',
                'ambulance_count': 2
            }
        ]
        
        for data in sample_hospitals:
            # Check if hospital already exists
            existing = Hospital.query.filter_by(hospital_id=data['hospital_id']).first()
            if existing:
                continue
                
            # Create hospital
            hospital = Hospital(
                hospital_id=data['hospital_id'],
                hospital_name=data['hospital_name'],
                location=data['location'],
                area_type=data['area_type'],
                hospital_type=data['hospital_type'],
                latitude=data['latitude'],
                longitude=data['longitude'],
                total_doctors=random.randint(10, 30),
                nurses_count=random.randint(20, 50),
                wardboys_count=random.randint(5, 15),
                total_beds=data['total_beds'],
                available_beds=data['available_beds'],
                has_icu=data['has_icu'],
                has_emergency=data['has_emergency'],
                contact_number=data['contact_number'],
                ambulance_count=data['ambulance_count']
            )
            hospital.set_password('password123')  # Default password
            db.session.add(hospital)
            db.session.flush()  # Get the hospital ID
            
            # Add default departments
            departments = ['General Medicine', 'Cardiology', 'Emergency', 'Pediatrics', 'Orthopedics']
            for dept_name in departments:
                dept = Department(
                    hospital_id=hospital.id,
                    name=dept_name,
                    total_doctors=random.randint(3, 8),
                    doctors_on_duty=random.randint(1, 4),
                    on_call_doctors=random.randint(0, 2),
                    is_active=True
                )
                db.session.add(dept)
            
            # Add ambulances
            for i in range(data['ambulance_count']):
                ambulance = Ambulance(
                    hospital_id=hospital.id,
                    vehicle_number=f"AMB{data['hospital_id']}-{i+1}",
                    is_available=True,
                    current_latitude=data['latitude'],
                    current_longitude=data['longitude'],
                    paramedic_count=random.randint(1, 3),
                    has_life_support=True,
                    driver_name=f"Driver {i+1}",
                    driver_phone=data['contact_number']
                )
                db.session.add(ambulance)
            
            print(f"✅ Added hospital: {data['hospital_name']}")
        
        db.session.commit()
        print("\n✅ Sample hospitals added successfully!")
        print("\nYou can now test transfers between these hospitals.")

if __name__ == '__main__':
    add_sample_hospitals()