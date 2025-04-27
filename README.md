# Smart Battery Manager

The `SmartBatteryManager` is an AppDaemon app for Home Assistant, designed to optimize battery charging by leveraging solar production forecasts, electricity price data, and user-defined parameters. It schedules charging tasks to minimize costs and maximize the use of renewable energy.

## Features

- **Battery SoC Monitoring**: Tracks the current battery state of charge (SoC) to determine energy needs.
- **Solar Production Forecast Integration**: Uses solar production forecasts to avoid unnecessary grid charging.
- **Electricity Price Optimization**: Analyzes electricity price data to schedule charging during low-cost periods.
- **Dynamic Scheduling**: Adjusts charging plans every 15 minutes based on updated forecasts and price data.
- **Customizable Parameters**: Allows users to configure battery capacity, target SoC per hour, charging power, and duration.
- **15-Minute Updates**: The app recalculates the charging plan every 15 minutes, ensuring timely adjustments to the schedule.

## How it works

The `SmartBatteryManager` operates by continuously monitoring and analyzing data from various sources to optimize battery charging. Here's a step-by-step breakdown of its functionality:

1. **State of Charge (SoC) Monitoring**: The app retrieves the current battery SoC from the configured sensor (`soc_sensor`). This value is used to determine how much energy is needed to reach the target SoC.

2. **Hourly SoC Targets**: Users can define a 24-hour array of target SoC values (`soc_targets`) in the configuration. The app uses the target for the next hour to determine the desired SoC level. If no valid `soc_targets` array is provided, a default target of 90% is used.

3. **Solar Production Forecast**: Using data from the `Forecast.Solar` service, the app predicts the amount of solar energy expected to be available in the coming hours. This helps prioritize charging during periods of high solar production.

4. **Electricity Price Analysis**: The app fetches electricity price data from the `Tibber` integration (`tibber_sensor`). It identifies low-cost periods to schedule grid charging when solar energy is insufficient.

5. **Smoothing and Local Minima Detection**: The app applies a 3-hour smoothing window to electricity price data to reduce noise and identify trends. Local minima in the smoothed price data are detected to pinpoint the most cost-effective charging times.

6. **Left-Right Seek for Adjacent Low Prices**: After identifying local minima, the app extends the candidate charging hours by seeking adjacent time periods where the price is within a threshold (`+0.10`) of the minimum price. This ensures that slightly higher but still cost-effective periods are included in the charging plan.

7. **Dynamic Scheduling**: Based on the SoC, solar forecast, and electricity prices, the app dynamically adjusts the charging schedule. It ensures that charging occurs during optimal times to minimize costs and maximize renewable energy usage.

8. **15-Minute Updates**: The app recalculates the charging plan every 15 minutes at `HH:59`, `HH:14`, `HH:29`, and `HH:44`. This ensures that the schedule remains efficient and up-to-date.

9. **Charging Duration**: Charging sessions are scheduled to start at the next 15-minute interval (`HH:00`, `HH:15`, `HH:30`, `HH:45`) and last for 15 minutes.

## Dependencies

To use this app, ensure the following dependencies are installed and configured:

1. **[HomeAssistant](https://www.home-assistant.io/)**: Open-source home automation solution.
2. **[AppDaemon](https://appdaemon.readthedocs.io/en/latest/)**: A Python-based automation framework for Home Assistant.
3. **[HACS (Home Assistant Community Store)](https://hacs.xyz/)**: A custom component manager for Home Assistant.
4. **[Huawei Solar (HACS)](https://github.com/wlcrs/huawei_solar)**: Integration for Huawei solar inverters to retrieve solar production data.
5. **[Forecast.Solar](https://forecast.solar/)**: A solar production forecasting service.
6. **[Tibber](https://developer.tibber.com/)**: Integration for electricity price data.
7. **[RESTful Integration](https://www.home-assistant.io/integrations/rest/)**: Used to retrieve additional data if needed.

## Installation

1. Install the required dependencies listed above.
2. Place the `smart_battery.py` file in your AppDaemon `apps` directory.
3. Add the following configuration to your `apps.yaml` file, change any values to match your own setup:

```yaml
smart_battery:
  module: smart_battery
  class: SmartBatteryManager
  soc_sensor: sensor.batteries_state_of_capacity
  tibber_sensor: sensor.tibber_electricity_prices
  battery_capacity_kwh: 10
  charge_duration_minutes: 15
  charge_power_w: 3000
  soc_targets:
    - 0.50  # 00:00
    - 0.50  # 01:00
    - 0.50  # 02:00
    - 0.50  # 03:00
    - 0.50  # 04:00
    - 0.50  # 05:00
    - 0.50  # 06:00
    - 1.00  # 07:00
    - 1.00  # 08:00
    - 1.00  # 09:00
    - 1.00  # 10:00
    - 1.00  # 11:00
    - 1.00  # 12:00
    - 1.00  # 13:00
    - 1.00  # 14:00
    - 1.00  # 15:00
    - 1.00  # 16:00
    - 1.00  # 17:00
    - 0.50  # 18:00
    - 0.50  # 19:00
    - 0.50  # 20:00
    - 0.50  # 21:00
    - 0.50  # 22:00
    - 0.50  # 23:00
```
