"""
Pytest configuration and fixtures for CNC tests.

Provides common fixtures and configuration for all test modules.
"""

import pytest
from spindrift.cnc import CNC


@pytest.fixture
def fresh_cnc():
    """
    Provide a fresh CNC instance for each test.
    
    This fixture ensures each test gets a clean CNC instance
    with default initialization values.
    """
    return CNC()


@pytest.fixture
def cnc_with_sample_data():
    """
    Provide a CNC instance with sample data loaded.
    
    This fixture provides a CNC instance that has been populated
    with realistic sample data for testing scenarios that need
    pre-existing state.
    """
    cnc = CNC()
    
    # Parse sample status response
    status_response = "<Run|MPos:10.5000,20.2500,-5.0000,45.0000,0.0000|WPos:0.0000,0.0000,0.0000,0.0000,0.0000|F:1500.0,2000.0,75.0|S:8000.0,10000.0,80.0,1,25.5,26.0|T:1,-5.123,2|W:12.34|L:1,1,0,50.0,75.0>"
    cnc.parse_status_response(status_response)
    
    # Parse sample diagnose response
    diagnose_response = "{S:1,8000|L:0,0|F:1,75|V:1,50|G:1|T:1|R:0|C:1|E:0,1,0,1,1,0|P:1,0|A:1,1|I:0}"
    cnc.parse_diagnose_response(diagnose_response)
    
    # Parse sample state response
    state_response = "[G0 G54 G17 G21 G90 G94 M0 M5 M9 T1 F2000.0000 S10000.0000]"
    cnc.parse_state_response(state_response)
    
    return cnc


@pytest.fixture(scope="session")
def sample_responses():
    """
    Provide sample CNC response strings for testing.
    
    This fixture provides a collection of realistic CNC response
    strings that can be used across multiple test modules.
    """
    return {
        'status_responses': {
            'idle': "<Idle|MPos:-1.0000,-1.0000,-1.0000,0.0000,0.0000|WPos:287.6600,201.0800,78.1109,nan,0.0000|F:0.0,3000.0,100.0|S:0.0,12000.0,100.0,0,23.2,24.2|T:2,-7.208,-1|W:0.00|L:0,0,0,0.0,100.0>",
            'run': "<Run|MPos:10.5000,20.2500,-5.0000,45.0000,0.0000|WPos:0.0000,0.0000,0.0000,0.0000,0.0000|F:1500.0,2000.0,75.0|S:8000.0,10000.0,80.0,1,25.5,26.0|T:1,-5.123,2|W:12.34|L:1,1,0,50.0,75.0>",
            'alarm': "<Alarm|MPos:0.0000,0.0000,0.0000,0.0000,0.0000|WPos:0.0000,0.0000,0.0000,0.0000,0.0000|F:0.0,0.0,100.0|S:0.0,0.0,100.0,0,22.0,22.0|T:-1,0.0,-1|W:0.0|L:0,0,0,0.0,100.0>",
            'home': "<Home|MPos:0.0000,0.0000,0.0000,0.0000,0.0000|WPos:0.0000,0.0000,0.0000,0.0000,0.0000|F:0.0,0.0,100.0|S:0.0,0.0,100.0,0,22.0,22.0|T:0,0.0,0|W:0.0|L:0,0,0,0.0,100.0>",
            'hold': "<Hold|MPos:5.0000,5.0000,5.0000,0.0000,0.0000|WPos:5.0000,5.0000,5.0000,0.0000,0.0000|F:1000.0,1000.0,100.0|S:5000.0,5000.0,100.0,0,24.0,24.0|T:1,0.0,1|W:0.0|L:0,0,0,0.0,100.0>",
            'with_playback': "<Run|MPos:5.0,5.0,5.0,0.0,0.0|WPos:5.0,5.0,5.0,0.0,0.0|F:1000.0,1000.0,100.0|S:5000.0,5000.0,100.0,0,24.0,24.0|T:1,0.0,1|W:0.0|L:0,0,0,0.0,100.0|P:150,75,300>",
            'with_extras': "<Idle|MPos:0.0,0.0,0.0,0.0,0.0|WPos:0.0,0.0,0.0,0.0,0.0|F:0.0,0.0,100.0|S:0.0,0.0,100.0,0,22.0,22.0|T:0,0.0,0|W:0.0|L:0,0,0,0.0,100.0|A:2|O:1.5|H:3|R:45.0|G:1>",
        },
        'diagnose_responses': {
            'all_on': "{S:1,8000|L:1,50|F:1,75|V:1,50|G:1|T:1|R:1|C:1|E:1,1,1,1,1,1|P:1,1|A:1,1|I:0}",
            'all_off': "{S:0,0|L:0,0|F:0,0|V:0,0|G:0|T:0|R:0|C:0|E:0,0,0,0,0,0|P:0,0|A:0,0|I:0}",
            'mixed': "{S:1,5000|L:0,0|F:1,75|V:1,50|G:1|T:1|R:0|C:1|E:0,1,0,1,1,0|P:1,0|A:1,1|I:0}",
            'emergency_stop': "{S:0,0|L:0,0|F:0,0|V:0,0|G:0|T:0|R:0|C:0|E:0,0,0,0,0,0|P:0,0|A:0,0|I:1}",
        },
        'state_responses': {
            'basic': "[G0 G54 G17 G21 G90 G94 M0 M5 M9 T0 F3000.0000 S1.0000]",
            'g55': "[G0 G55 G17 G21 G90 G94 M5 M9 T1 F2000.0 S5000.0]",
            'g56': "[G0 G56 G17 G21 G90 G94 M5 M9 T2 F1500.0 S8000.0]",
            'high_speed': "[G0 G54 G17 G21 G90 G94 M5 M9 T5 F5000.0 S24000.0]",
            'tool_change': "[G0 G54 G17 G21 G90 G94 M5 M9 T10 F1000.0 S12000.0]",
        },
        'malformed_responses': {
            'no_brackets': "Idle|MPos:0.0,0.0,0.0",
            'only_opening': "<Idle|MPos:0.0,0.0,0.0",
            'only_closing': "Idle|MPos:0.0,0.0,0.0>",
            'empty': "",
            'whitespace': "   ",
            'just_brackets': "<>",
            'just_braces': "{}",
            'just_square_brackets': "[]",
            'invalid_data': "<Idle|MPos:abc,def,ghi>",
        }
    }


@pytest.fixture
def mock_responses(sample_responses):
    """
    Provide easy access to mock responses for testing.
    
    This is a convenience fixture that provides the same data
    as sample_responses but with a shorter name for easier use.
    """
    return sample_responses


# Test markers for organizing tests
def pytest_configure(config):
    """Configure custom pytest markers"""
    config.addinivalue_line(
        "markers", "unit: mark test as a unit test"
    )
    config.addinivalue_line(
        "markers", "integration: mark test as an integration test"
    )
    config.addinivalue_line(
        "markers", "parsing: mark test as a parsing test"
    )
    config.addinivalue_line(
        "markers", "communication: mark test as a communication test"
    )
    config.addinivalue_line(
        "markers", "data_classes: mark test as a data class test"
    )
    config.addinivalue_line(
        "markers", "edge_case: mark test as an edge case test"
    )
    config.addinivalue_line(
        "markers", "slow: mark test as slow running"
    )


# Custom assertion helpers
class CNCAssertions:
    """Custom assertion helpers for CNC testing"""
    
    @staticmethod
    def assert_position_equal(pos1, pos2, tolerance=0.0001):
        """Assert that two positions are equal within tolerance"""
        assert abs(pos1.x - pos2.x) <= tolerance, f"X coordinates differ: {pos1.x} != {pos2.x}"
        assert abs(pos1.y - pos2.y) <= tolerance, f"Y coordinates differ: {pos1.y} != {pos2.y}"
        assert abs(pos1.z - pos2.z) <= tolerance, f"Z coordinates differ: {pos1.z} != {pos2.z}"
        assert abs(pos1.a - pos2.a) <= tolerance, f"A coordinates differ: {pos1.a} != {pos2.a}"
        assert abs(pos1.b - pos2.b) <= tolerance, f"B coordinates differ: {pos1.b} != {pos2.b}"
    
    @staticmethod
    def assert_cnc_state_valid(cnc):
        """Assert that CNC state is in a valid configuration"""
        # Check that all required objects exist
        assert cnc.machine_position is not None
        assert cnc.work_position is not None
        assert cnc.work_coordinate_offset is not None
        assert cnc.feed_info is not None
        assert cnc.spindle_info is not None
        assert cnc.tool_info is not None
        assert cnc.laser_info is not None
        assert cnc.wcs is not None
        assert cnc.switches is not None
        assert cnc.switch_levels is not None
        assert cnc.sensors is not None
        
        # Check that state is a valid enum value
        assert isinstance(cnc.state, type(cnc.state))
        
        # Check that numeric values are reasonable
        assert -10000 <= cnc.machine_position.x <= 10000
        assert -10000 <= cnc.machine_position.y <= 10000
        assert -10000 <= cnc.machine_position.z <= 10000
        assert 0 <= cnc.feed_info.override <= 200
        assert 0 <= cnc.spindle_info.override <= 200


@pytest.fixture
def cnc_assertions():
    """Provide CNC assertion helpers"""
    return CNCAssertions
