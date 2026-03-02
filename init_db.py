#!/usr/bin/env python3
"""
Initialize the database for the memory site
Run this script once to create the database and first admin user
"""

import os
import sys
from getpass import getpass
from app import app, db, User

def init_database():
    """Initialize database and create admin user"""
    with app.app_context():
        # Create tables
        print("Creating database tables...")
        db.create_all()
        
        # Check if admin user exists
        admin = User.query.filter_by(is_admin=True).first()
        
        if not admin:
            print("\n=== Create Admin User ===")
            print("This user will have full access to the system.")
            
            username = input("Username: ").strip()
            email = input("Email: ").strip()
            
            while True:
                password = getpass("Password: ")
                confirm = getpass("Confirm password: ")
                
                if password == confirm and len(password) >= 6:
                    break
                elif len(password) < 6:
                    print("Password must be at least 6 characters long.")
                else:
                    print("Passwords do not match.")
            
            # Create admin user
            admin = User(
                username=username,
                email=email,
                is_admin=True
            )
            admin.set_password(password)
            
            db.session.add(admin)
            db.session.commit()
            
            print(f"\n✅ Admin user '{username}' created successfully!")
        else:
            print(f"✅ Admin user '{admin.username}' already exists.")
        
        print("\n✅ Database initialization complete!")

if __name__ == "__main__":
    print("📸 Memory Site Database Initialization")
    print("=" * 40)
    
    # Confirm action
    response = input("This will create/overwrite the database. Continue? (y/N): ")
    
    if response.lower() == 'y':
        init_database()
    else:
        print("Operation cancelled.")
        sys.exit(0)
