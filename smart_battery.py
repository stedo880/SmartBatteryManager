import appdaemon.plugins.hass.hassapi as hass
from datetime import datetime, timedelta
from dateutil import parser
import math

class SmartBatteryManager(hass.Hass):

    def initialize(self):
        self.log("Smart battery manager initializing...")
        run_time = datetime.now().replace(minute=55, second=0, microsecond=0)
        if run_time < datetime.now():
            run_time += timedelta(hours=1)
        self.run_every(self.plan_charging_strategy, run_time, 3600)  # Run every hour at HH:55
        self.run_in(self.plan_charging_strategy, 5)

    def plan_charging_strategy(self, kwargs):
        try:
            # Get the next hour for planning
            now = datetime.now()
            next_hour = now.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)

            # Get the current state of the battery SoC
            soc_raw = self.get_state(self.args["soc_sensor"])
            if soc_raw is None or soc_raw in ["unknown", "unavailable"]:
                self.log("Battery SoC sensor returned no data.")
                return
            soc = float(soc_raw) / 100

            # Get battery capacity and target SoC from arguments
            battery_capacity = self.args.get("battery_capacity_kwh", 10)
            soc_targets = self.args.get("soc_targets")
            if not soc_targets or len(soc_targets) != 24:
                self.log("Invalid or missing battery SoC target array, using default 90%")
                target_soc = 0.9
            else:
                target_soc = soc_targets[next_hour.hour]
                self.log(f"Selected target battery SoC for hour {next_hour.hour}: {target_soc * 100:.0f}%")
                           
            # Estimate solar production for next hour
            solar_1 = self.get_state("sensor.energy_next_hour")
            solar_2 = self.get_state("sensor.energy_next_hour_2")

            # Check if the battery is already full
            energy_needed = max(0, (target_soc - soc) * battery_capacity)
            if energy_needed <= 0:
                self.log("No additional energy needed, skipping charging plan.")
                return
            
            self.log(f"Current battery SoC: {soc*100:.0f}%, energy needed from grid: {energy_needed:.2f} kWh")

            # Check if solar production data is available
            try:
                solar_next_hour = float(solar_1 or 0) + float(solar_2 or 0)
            except ValueError:
                self.log("Could not parse solar forecast data, assuming 0 kWh")
                solar_next_hour = 0

            self.log(f"Expected solar production next hour: {solar_next_hour:.2f} kWh")

            # Check if the expected solar production is enough to reach the target SoC
            projected_soc = soc + (solar_next_hour / battery_capacity)
            if projected_soc >= target_soc:
                self.log(f"Skipping charge at {next_hour.strftime('%H:%M')} - expected solar enough to reach SoC target.")
                return

            # Check price data from Tibber
            price_data_full = self.get_state(self.args["tibber_sensor"], attribute="all")
            if not price_data_full or "attributes" not in price_data_full:
                self.log("No price data attributes found.")
                return

            price_data = price_data_full["attributes"]
            tibber_prices = price_data.get("today", []) + price_data.get("tomorrow", [])
            if not tibber_prices:
                self.log("No price data available.")
                return

            all_prices = [
                (parser.isoparse(e["startsAt"]).replace(tzinfo=None), float(e["total"]))
                for e in tibber_prices
            ]
            all_prices.sort(key=lambda x: x[0])

            # Identify price data local minimas
            local_minima = []
            for i in range(1, len(all_prices) - 1):
                prev_price = all_prices[i - 1][1]
                curr_price = all_prices[i][1]
                next_price = all_prices[i + 1][1]
                if curr_price < prev_price and curr_price < next_price:
                    local_minima.append(all_prices[i][0])

            self.log(f"Detected local minima: {', '.join(t.strftime('%Y-%m-%d %H:%M') for t in local_minima)}")

            # Build candidate hours from local minima
            candidate_hours = set()
            for minimum in local_minima:
                min_price = next((p for (t, p) in all_prices if t == minimum), None)
                if min_price is None:
                    continue

                # Get ±2h window around minimum
                window = [tp for tp in all_prices if abs((tp[0] - minimum).total_seconds()) / 3600 <= 2]
                cheapest_three = sorted(window, key=lambda x: x[1])[:3]
                candidate_hours.update(t[0] for t in cheapest_three)

                # Extend to all adjacent within 10% and 20% of the minimum price
                i = next((idx for idx, (t, _) in enumerate(all_prices) if t == minimum), None)
                if i is None:
                    continue

                # Look left
                j = i - 1
                while j >= 0 and all_prices[j][1] <= min_price * 1.10:
                    candidate_hours.add(all_prices[j][0])
                    j -= 1

                # Look right
                j = i + 1
                while j < len(all_prices) and all_prices[j][1] <= min_price * 1.20:
                    candidate_hours.add(all_prices[j][0])
                    j += 1

            candidate_hours = sorted(candidate_hours)
            self.log(f"Candidate hours: {', '.join(t.strftime('%Y-%m-%d %H:%M') for t in candidate_hours)}")

            # Check if the next hour is a candidate for charging
            if next_hour in [t for t in candidate_hours if t >= now]:
                self.log(f"Next charging hour scheduled: {next_hour.strftime('%Y-%m-%d %H:%M')}")
                self.schedule_charge(next_hour)
            else:
                self.log("Next hour is not a candidate for charging.")

        except Exception as e:
            self.log(f"Error during planning: {str(e)}")

    def schedule_charge(self, target_time):
        now = datetime.now()
        target = target_time.replace(second=0, microsecond=0)
        if target < now:
            return
        self.run_at(self.start_charging, target, hour=target.hour)

    def start_charging(self, kwargs):
        hour = kwargs.get("hour")
        duration = self.args.get("charge_duration_minutes", 60)
        power = self.args.get("charge_power_w", 3000)

        self.log(f"Starting CHARGE at hour {hour:02d}:00 for {duration} minutes at {power}W")

        self.call_service("script/turn_on", entity_id="script.force_battery_charge", variables={
            "duration": duration,
            "power": power
        })
