import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime, timedelta
from smart_battery import SmartBatteryManager

@pytest.fixture
def app():
    # Mock the required arguments for Hass.__init__()
    ad = MagicMock()
    name = "smart_battery"
    logging = MagicMock()
    args = {
        "soc_sensor": "sensor.battery_soc",
        "battery_capacity_kwh": 10,
        "soc_targets": [0.5] * 24,
        "energy_next_hour_sensor_1": "sensor.solar_next_hour_1",
        "energy_next_hour_sensor_2": "sensor.solar_next_hour_2",
        "energy_today_remaining_sensor_1": "sensor.solar_remaining_1",
        "energy_today_remaining_sensor_2": "sensor.solar_remaining_2",
    }
    config = MagicMock()
    app_config = MagicMock()
    global_vars = MagicMock()

    # Create an instance of SmartBatteryManager with mocked arguments
    app = SmartBatteryManager(ad, name, logging, args, config, app_config, global_vars)

    # Mock additional methods used in the tests
    app.get_state = MagicMock()
    app.log = MagicMock()
    app.run_at = MagicMock()
    app.call_service = MagicMock()
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

def test_get_current_soc(app):
    # Mock the sensor state
    app.get_state.return_value = "75"
    soc = app.get_current_soc()
    assert soc == 0.75
    app.get_state.assert_called_once_with("sensor.battery_soc")

    # Test with unavailable state
    app.get_state.return_value = "unavailable"
    soc = app.get_current_soc()
    assert soc is None

def test_get_target_soc(app):
    # Mock the target array
    next_interval = datetime.now().replace(hour=10)
    target_soc = app.get_target_soc(next_interval)
    assert target_soc == 0.5
    app.log.assert_called_with("Selected target battery SoC for hour 10: 50%")

    # Test with invalid target array
    app.args["soc_targets"] = None
    target_soc = app.get_target_soc(next_interval)
    assert target_soc == 0.9
    app.log.assert_called_with("Invalid or missing battery SoC target array, using default 90%")

def test_calculate_energy_needed(app):
    soc = 0.5
    target_soc = 0.8
    energy_needed = app.calculate_energy_needed(soc, target_soc)
    assert energy_needed == pytest.approx(3.0)  # (0.8 - 0.5) * 10

def test_get_solar_next_hour(app):
    # Mock solar sensor states
    app.get_state.side_effect = ["2.5", "1.5"]
    solar_next_hour = app.get_solar_next_hour()
    assert solar_next_hour == 4.0
    app.get_state.assert_any_call("sensor.solar_next_hour_1")
    app.get_state.assert_any_call("sensor.solar_next_hour_2")

def test_get_solar_remaining(app):
    # Mock solar remaining sensor states
    app.get_state.side_effect = ["3.0", "2.0"]
    solar_remaining = app.get_solar_remaining()
    assert solar_remaining == 5.0
    app.get_state.assert_any_call("sensor.solar_remaining_1")
    app.get_state.assert_any_call("sensor.solar_remaining_2")

# Test the check_skip_charge method
# Scenario 1: Enough solar energy available, time is after 06:00
# Expected to skip charging if solar energy is sufficient
def test_check_skip_charge_enough_energy(app):
    # Mock solar methods
    app.get_solar_next_hour = MagicMock(return_value=4.0)
    app.get_solar_remaining = MagicMock(return_value=10.0)

    # Mock datetime to simulate a time after 06:00
    with patch("smart_battery.datetime") as mock_datetime:
        mock_datetime.now.return_value = datetime(2025, 5, 1, 7, 0)  # 07:00 AM
        mock_datetime.strptime = datetime.strptime  # Ensure strptime works as expected

        # Test skipping due to solar production and time condition
        soc = 0.6
        target_soc = 0.8
        energy_needed = app.calculate_energy_needed(soc, target_soc)
        app.args["battery_capacity_kwh"] = 10
        skip = app.check_skip_charge(soc, target_soc, energy_needed)
        assert skip is True
        app.log.assert_any_call("Skipping charge: Expected remaining solar production today is more than double the energy needed")

# Scenario 2: Not enough solar energy available, time is after 06:00
# Expected to not skip charging
def test_check_skip_charge_not_enough_energy(app):
    # Mock solar methods
    app.get_solar_next_hour = MagicMock(return_value=1.0)
    app.get_solar_remaining = MagicMock(return_value=2.0)

    # Mock datetime to simulate a time after 06:00
    with patch("smart_battery.datetime") as mock_datetime:
        mock_datetime.now.return_value = datetime(2025, 5, 1, 7, 0)  # 07:00 AM
        mock_datetime.strptime = datetime.strptime  # Ensure strptime works as expected

        # Test not skipping due to insufficient solar production
        soc = 0.4
        target_soc = 0.8
        energy_needed = app.calculate_energy_needed(soc, target_soc)
        app.args["battery_capacity_kwh"] = 10
        skip = app.check_skip_charge(soc, target_soc, energy_needed)
        assert skip is False
        app.log.assert_any_call("Expected solar production next hour: 1.00 kWh")
        app.log.assert_any_call("Expected remaining solar production today: 2.00 kWh")

# Scenario 3: Time is before 06:00, expected solar remaining today is enough
# Expected to not skip charging
def test_check_skip_charge_before_time(app):
    # Mock solar methods
    app.get_solar_next_hour = MagicMock(return_value=0.0)
    app.get_solar_remaining = MagicMock(return_value=20.0)

    # Mock datetime to simulate a time before 06:00
    with patch("smart_battery.datetime") as mock_datetime:
        mock_datetime.now.return_value = datetime(2025, 5, 1, 5, 0)  # 05:00 AM
        mock_datetime.strptime = datetime.strptime  # Ensure strptime works as expected

        # Test not skipping due to time condition
        soc = 0.6
        target_soc = 0.8
        energy_needed = app.calculate_energy_needed(soc, target_soc)
        app.args["battery_capacity_kwh"] = 10
        skip = app.check_skip_charge(soc, target_soc, energy_needed)
        assert skip is False
        app.log.assert_any_call("Expected solar production next hour: 0.00 kWh")
        app.log.assert_any_call("Expected remaining solar production today: 20.00 kWh")

# Scenario 4: Projected SOC is enough to reach target SOC
# Expected to skip charging
def test_check_skip_charge_projected_soc(app):
    # Mock solar methods
    app.get_solar_next_hour = MagicMock(return_value=2.0)
    app.get_solar_remaining = MagicMock(return_value=3.0)

    # Mock datetime to simulate a time after 06:00
    with patch("smart_battery.datetime") as mock_datetime:
        mock_datetime.now.return_value = datetime(2025, 5, 1, 7, 0)  # 07:00 AM
        mock_datetime.strptime = datetime.strptime  # Ensure strptime works as expected

        # Test skipping due to projected SOC
        soc = 0.6
        target_soc = 0.8
        energy_needed = app.calculate_energy_needed(soc, target_soc)
        app.args["battery_capacity_kwh"] = 10
        skip = app.check_skip_charge(soc, target_soc, energy_needed)
        assert skip is True
        app.log.assert_any_call("Skipping charge: Expected solar next hour is enough to reach SoC target")