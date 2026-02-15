from app import app, db
from add_sample_hospitals import add_sample_hospitals

def init_database():
    with app.app_context():
        print("=" * 60)
        print("🗄️  DATABASE INITIALIZATION")
        print("=" * 60)
        
        # Create tables
        db.create_all()
        print("✅ Database tables created")
        
        # Add sample hospitals
        add_sample_hospitals()
        
        print("\n" + "=" * 60)
        print("✅ Database initialization complete!")
        print("📊 Tables created and sample data loaded")
        print("=" * 60)

if __name__ == '__main__':
    init_database()