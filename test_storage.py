from config import LEASEWEB_CONFIG
from storage_handler import LeasewebStorageHandler

def test_storage_connection():
    """Test connection to Leaseweb storage"""
    storage = LeasewebStorageHandler(LEASEWEB_CONFIG)
    return storage.check_connection()

def test_presigned_url():
    """Test generating presigned URLs"""
    storage = LeasewebStorageHandler(LEASEWEB_CONFIG)
    if not storage.check_connection():
        return False
    
    # Try to generate a presigned URL for a test object
    test_url = storage.generate_presigned_url("test.txt")
    if test_url:
        print(f"Successfully generated presigned URL: {test_url}")
        return True
    return False

if __name__ == "__main__":
    print("Testing Leaseweb Storage connection...")
    if test_storage_connection():
        print("Storage connection test passed!")
        print("\nTesting presigned URL generation...")
        test_presigned_url()
    else:
        print("Storage connection test failed!") 