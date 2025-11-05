"""
Test script for Session Manager
"""

import sys
from pathlib import Path
import numpy as np
import shutil

# Add modules to path
sys.path.append(str(Path(__file__).parent))

from modules.session_manager import SessionManager
from modules.data_loader import DataLoader


def test_session_create():
    """Test session creation"""
    print("\n=== Testing Session Creation ===")

    try:
        manager = SessionManager(session_dir="test_sessions")

        # Create a new session
        session_id = manager.create_session("test_session_001")

        print(f"✅ Session created: {session_id}")

        # Verify session file exists
        session_path = Path("test_sessions") / f"{session_id}.json"
        if session_path.exists():
            print(f"✅ Session file created: {session_path}")
            return True
        else:
            print(f"❌ Session file not found: {session_path}")
            return False

    except Exception as e:
        print(f"❌ Error creating session: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_session_save_load():
    """Test session save and load"""
    print("\n=== Testing Session Save/Load ===")

    try:
        manager = SessionManager(session_dir="test_sessions")

        # Load sample data
        sample_file = Path(__file__).parent / "examples" / "sample_chromatogram.csv"
        loader = DataLoader()
        time, intensity = loader.load_file(str(sample_file))

        # Create session
        session_id = manager.create_session("test_save_load")

        # Save data to session
        data = {
            'filename': 'sample_chromatogram.csv',
            'time': time,
            'intensity': intensity,
            'plot_settings': {
                'color': '#FF0000',
                'line_width': 2.0,
                'show_grid': False,
            }
        }

        progress = {
            'status': 'paused',
            'last_action': 'Data loaded',
        }

        success = manager.save_state(session_id, data, progress)

        if not success:
            print("❌ Failed to save session state")
            return False

        print(f"✅ Session state saved")

        # Load session
        loaded_data = manager.load_state(session_id)

        if loaded_data is None:
            print("❌ Failed to load session state")
            return False

        print(f"✅ Session state loaded")

        # Verify data
        loaded_time = loaded_data['data']['time']
        loaded_intensity = loaded_data['data']['intensity']
        loaded_filename = loaded_data['data']['filename']

        if not np.array_equal(time, loaded_time):
            print("❌ Time data mismatch")
            return False

        if not np.array_equal(intensity, loaded_intensity):
            print("❌ Intensity data mismatch")
            return False

        if loaded_filename != 'sample_chromatogram.csv':
            print("❌ Filename mismatch")
            return False

        print(f"✅ All data verified successfully")
        print(f"   - Time points: {len(loaded_time)}")
        print(f"   - Intensity points: {len(loaded_intensity)}")
        print(f"   - Filename: {loaded_filename}")

        return True

    except Exception as e:
        print(f"❌ Error in save/load test: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_session_list():
    """Test session listing"""
    print("\n=== Testing Session Listing ===")

    try:
        manager = SessionManager(session_dir="test_sessions")

        # Create multiple sessions
        session_ids = []
        for i in range(3):
            session_id = manager.create_session(f"test_list_{i}")
            session_ids.append(session_id)

        # List sessions
        sessions = manager.list_sessions()

        print(f"✅ Found {len(sessions)} sessions")

        for session in sessions:
            print(f"   - {session['session_id']}: {session['status']}")

        if len(sessions) >= 3:
            return True
        else:
            print(f"❌ Expected at least 3 sessions, found {len(sessions)}")
            return False

    except Exception as e:
        print(f"❌ Error listing sessions: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_session_delete():
    """Test session deletion"""
    print("\n=== Testing Session Deletion ===")

    try:
        manager = SessionManager(session_dir="test_sessions")

        # Create a session
        session_id = manager.create_session("test_delete")

        # Verify it exists
        sessions_before = manager.list_sessions()
        session_exists = any(s['session_id'] == session_id for s in sessions_before)

        if not session_exists:
            print(f"❌ Session not found after creation")
            return False

        print(f"✅ Session exists: {session_id}")

        # Delete session
        success = manager.delete_session(session_id)

        if not success:
            print(f"❌ Failed to delete session")
            return False

        # Verify it's gone
        sessions_after = manager.list_sessions()
        session_exists = any(s['session_id'] == session_id for s in sessions_after)

        if session_exists:
            print(f"❌ Session still exists after deletion")
            return False

        print(f"✅ Session deleted successfully")
        return True

    except Exception as e:
        print(f"❌ Error deleting session: {e}")
        import traceback
        traceback.print_exc()
        return False


def cleanup():
    """Clean up test sessions"""
    print("\n=== Cleaning Up Test Sessions ===")

    test_dir = Path("test_sessions")
    if test_dir.exists():
        shutil.rmtree(test_dir)
        print(f"✅ Test sessions directory removed")


def main():
    """Run all tests"""
    print("=" * 60)
    print("Session Manager Tests")
    print("=" * 60)

    results = []

    # Test session creation
    results.append(("Session Creation", test_session_create()))

    # Test save/load
    results.append(("Session Save/Load", test_session_save_load()))

    # Test listing
    results.append(("Session Listing", test_session_list()))

    # Test deletion
    results.append(("Session Deletion", test_session_delete()))

    # Summary
    print("\n" + "=" * 60)
    print("Test Summary")
    print("=" * 60)

    for name, result in results:
        status = "✅ PASSED" if result else "❌ FAILED"
        print(f"{name}: {status}")

    all_passed = all(result for _, result in results)

    if all_passed:
        print("\n🎉 All tests passed!")
    else:
        print("\n⚠️ Some tests failed!")

    # Cleanup
    cleanup()

    return all_passed


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
