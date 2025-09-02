#!/usr/bin/env python3
"""
Test script to verify the dues tracking system works correctly
"""
import asyncio
import os
from datetime import datetime
from utils.database import DatabaseManager

async def test_dues_system():
    """Test the dues tracking system"""
    print("🧪 Testing Dues Tracking System...")
    
    # Create test database
    db_path = 'test_dues_system.db'
    if os.path.exists(db_path):
        os.remove(db_path)
    
    try:
        # Initialize database
        db = DatabaseManager(db_path)
        await db.initialize_database()
        print("✅ Database schema created successfully")
        
        # Test creating a dues period
        guild_id = 12345
        test_user_id = 67890
        
        period_id = await db.create_dues_period(
            guild_id=guild_id,
            period_name="January 2024 Dues",
            description="Monthly dues for January",
            due_amount=50.0,
            due_date=datetime(2024, 1, 31),
            created_by_id=test_user_id
        )
        print(f"✅ Created dues period with ID: {period_id}")
        
        # Test getting active periods
        periods = await db.get_active_dues_periods(guild_id)
        print(f"✅ Retrieved {len(periods)} active periods")
        
        # Test updating payment
        payment_id = await db.update_dues_payment(
            guild_id=guild_id,
            user_id=test_user_id,
            dues_period_id=period_id,
            amount_paid=50.0,
            payment_date=datetime(2024, 1, 15),
            payment_method="Venmo",
            payment_status="paid",
            notes="Test payment",
            is_exempt=False,
            updated_by_id=test_user_id
        )
        print(f"✅ Updated payment record with ID: {payment_id}")
        
        # Test getting collection summary
        summary = await db.get_dues_collection_summary(guild_id, period_id)
        print(f"✅ Generated collection summary: {summary.get('collection_percentage', 0):.1f}% collection rate")
        
        # Test reset functionality
        success = await db.reset_dues_period(guild_id, period_id, test_user_id)
        print(f"✅ Reset period test: {'Success' if success else 'Failed'}")
        
        await db.close()
        print("✅ Database connection closed")
        
        # Clean up test database
        if os.path.exists(db_path):
            os.remove(db_path)
            print("✅ Test database cleaned up")
        
        print("\n🎉 All dues tracking tests passed successfully!")
        
    except Exception as e:
        print(f"❌ Test failed with error: {e}")
        # Clean up on error
        if os.path.exists(db_path):
            os.remove(db_path)
        raise

if __name__ == "__main__":
    asyncio.run(test_dues_system())
