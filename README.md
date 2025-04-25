# Smart Battery Manager

The `SmartBatteryManager` is an AppDaemon app for Home Assistant, designed to optimize battery charging by leveraging solar production forecasts, electricity price data, and user-defined parameters. It schedules charging tasks to minimize costs and maximize the use of renewable energy.

## Features

- **Battery SoC Monitoring**: Tracks the current battery state of charge (SoC) to determine energy needs.
- **Solar Production Forecast Integration**: Uses solar production forecasts to avoid unnecessary grid charging.
- **Electricity Price Optimization**: Analyzes electricity price data to schedule charging during low-cost periods.
- **Dynamic Scheduling**: Adjusts charging plans hourly based on updated forecasts and price data.
- **Customizable Parameters**: Allows users to configure battery capacity, target SoC, charging power, and duration.

## How it works

The `SmartBatteryManager` operates by continuously monitoring and analyzing data from various sources to optimize battery charging. Here's a step-by-step breakdown of its functionality:

1. **State of Charge (SoC) Monitoring**: The app retrieves the current battery SoC from the configured sensor (`soc_sensor`). This value is used to determine how much energy is needed to reach the target SoC.

2. **Solar Production Forecast**: Using data from the `Forecast.Solar` service, the app predicts the amount of solar energy expected to be available in the coming hours. This helps prioritize charging during periods of high solar production.

3. **Electricity Price Analysis**: The app fetches electricity price data from the `Tibber` integration (`tibber_sensor`). It identifies low-cost periods to schedule grid charging when solar energy is insufficient.

4. **Dynamic Scheduling**: Based on the SoC, solar forecast, and electricity prices, the app dynamically adjusts the charging schedule. It ensures that charging occurs during optimal times to minimize costs and maximize renewable energy usage.

5. **Customizable Parameters**: Users can configure parameters such as battery capacity, target SoC, charging power, and duration. These settings allow the app to adapt to different battery systems and user preferences.

6. **Hourly Updates**: The app recalculates the charging plan every hour, incorporating the latest data to ensure the schedule remains efficient and up-to-date.

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
3. Add the following configuration to your `apps.yaml` file:

   ```yaml
   smart_battery:
     module: smart_battery
     class: SmartBatteryManager
     soc_sensor: sensor.batteries_state_of_capacity
     tibber_sensor: sensor.tibber_electricity_prices
     battery_capacity_kwh: 10
     target_soc: 1.0
     charge_duration_minutes: 60
     charge_power_w: 3000