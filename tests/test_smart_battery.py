import pytest
from unittest.mock import MagicMock
from datetime import datetime, timedelta
from smart_battery import SmartBatteryManager

@pytest.fixture
def app():
    # Mock the required arguments for Hass.__init__()
    ad = MagicMock()
    name = "smart_battery"
    logging = MagicMock()
    args = {"duration_minutes": 15, "charge_power_w": 3000}
    config = MagicMock()
    app_config = MagicMock()
    global_vars = MagicMock()

    # Create an instance of SmartBatteryManager with mocked arguments
    app = SmartBatteryManager(ad, name, logging, args, config, app_config, global_vars)

    # Mock additional methods used in the tests
    app.run_at = MagicMock()
    app.call_service = MagicMock()
    app.log = MagicMock()
    return app

def test_schedule_charge(app):
    # Test schedule_charge with a valid future time
    target_time = datetime.now() + timedelta(minutes=10)
    app.schedule_charge(target_time)

    # Assert that run_at was called with the correct arguments
    app.run_at.assert_called_once()
    args, kwargs = app.run_at.call_args
    assert args[0] == app.start_charging
    assert args[1] == target_time.replace(second=0, microsecond=0)
    assert kwargs["hour"] == target_time.hour
    assert kwargs["minute"] == target_time.minute

def test_schedule_charge_past_time(app):
    # Test schedule_charge with a past time
    target_time = datetime.now() - timedelta(minutes=10)
    app.schedule_charge(target_time)

    # Assert that run_at was not called
    app.run_at.assert_not_called()

def test_start_charging(app):
    # Test start_charging with valid kwargs
    kwargs = {"hour": 14, "minute": 30}
    app.start_charging(kwargs)

    # Assert that call_service was called with the correct arguments
    app.call_service.assert_called_once_with(
        "script/turn_on",
        entity_id="script.force_battery_charge",
        variables={"duration": 15, "power": 3000}
    )

    # Assert that log was called with the correct message
    app.log.assert_called_once_with("Starting CHARGE at 14:30 for 15 minutes at 3000W")