# Smart Battery Manager

The `SmartBatteryManager` is an AppDaemon app designed to optimize battery charging by leveraging solar production forecasts, electricity price data, and user-defined parameters. It schedules charging tasks to minimize costs and maximize the use of renewable energy.

## Features

- **Battery SoC Monitoring**: Tracks the current battery state of charge (SoC) to determine energy needs.
- **Solar Production Forecast Integration**: Uses solar production forecasts to avoid unnecessary grid charging.
- **Electricity Price Optimization**: Analyzes electricity price data to schedule charging during low-cost periods.
- **Dynamic Scheduling**: Adjusts charging plans hourly based on updated forecasts and price data.
- **Customizable Parameters**: Allows users to configure battery capacity, target SoC, charging power, and duration.

## Dependencies

To use this app, ensure the following dependencies are installed and configured:

1. **[AppDaemon](https://appdaemon.readthedocs.io/en/latest/)**: A Python-based automation framework for Home Assistant.
2. **[HACS (Home Assistant Community Store)](https://hacs.xyz/)**: A custom component manager for Home Assistant.
3. **[Huawei Solar (HACS)](https://github.com/wlcrs/huawei_solar)**: Integration for Huawei solar inverters to retrieve solar production data.
4. **[Forecast.Solar](https://forecast.solar/)**: A solar production forecasting service.
5. **[Tibber](https://developer.tibber.com/)**: Integration for electricity price data.
6. **[RESTful Integration](https://www.home-assistant.io/integrations/rest/)**: Used to retrieve additional data if needed.

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