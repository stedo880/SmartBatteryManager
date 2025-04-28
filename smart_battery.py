import appdaemon.plugins.hass.hassapi as hass
from datetime import datetime, timedelta
from dateutil import parser

class SmartBatteryManager(hass.Hass):

    def initialize(self):
        self.log("Smart battery manager initializing...")
        # Schedule `plan_charging_strategy` to run every 15 minutes at HH:59, HH:14, HH:29, HH:44
        now = datetime.now()
        first_run = now.replace(second=0, microsecond=0)
        if now.minute % 15 == 14:
            first_run = first_run.replace(minute=now.minute)
        else:
            first_run = first_run.replace(minute=(now.minute // 15) * 15 + 14)
        if first_run < now:
            first_run += timedelta(minutes=15)
        self.run_every(self.plan_charging_strategy, first_run, 900)  # 900 seconds = 15 minutes

    def plan_charging_strategy(self, kwargs):
        try:
            # Get the next 15-minute interval for planning
            now = datetime.now()
            next_interval = now.replace(second=0, microsecond=0) + timedelta(minutes=15 - now.minute % 15)

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
                target_soc = soc_targets[next_interval.hour]
                self.log(f"Selected target battery SoC for hour {next_interval.hour}: {target_soc * 100:.0f}%")
                           
            # Estimate solar production for next hour
            solar_1 = self.get_state(self.args["energy_next_hour_sensor_1"])
            solar_2 = self.get_state(self.args["energy_next_hour_sensor_2"])

            # Check if the battery is already full
            energy_needed = max(0, (target_soc - soc) * battery_capacity)
            self.log(f"Current battery SoC: {soc*100:.0f}%, energy needed from grid: {energy_needed:.2f} kWh")
            if energy_needed <= 0:
                self.log("No additional energy needed, skipping charging plan.")
                return         

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
                self.log(f"Skipping charge at {next_interval.strftime('%H:%M')} - expected solar enough to reach SoC target.")
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

            # Smooth the price data
            prices = [p for (_, p) in all_prices]
            smoothed = []
            window = 3  # 3×1 hour smoothing
            for i in range(len(prices)):
                lo = max(0, i - window//2)
                hi = min(len(prices), i + window//2 + 1)
                smoothed.append(sum(prices[lo:hi]) / (hi - lo))

            # Identify local minima on the smoothed series
            local_minima = []
            for i in range(1, len(smoothed) - 1):
                if smoothed[i] < smoothed[i-1] and smoothed[i] < smoothed[i+1]:
                    # map back to the real timestamp
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

                # Extend to all adjacent within +0.1 the minimum price
                i = next((idx for idx, (t, _) in enumerate(all_prices) if t == minimum), None)
                if i is None:
                    continue

                # Look left
                # j = i - 1
                # while j >= 0 and all_prices[j][1] <= min_price + 0.10:
                #     candidate_hours.add(all_prices[j][0])
                #     j -= 1

                # Look right
                j = i + 1
                while j < len(all_prices) and all_prices[j][1] <= min_price + 0.10:
                    candidate_hours.add(all_prices[j][0])
                    j += 1

            candidate_hours = sorted(candidate_hours)
            self.log(f"Candidate hours: {', '.join(t.strftime('%Y-%m-%d %H:%M') for t in candidate_hours)}")

            # Check if the next interval is a candidate for charging
            if any(t.date() == next_interval.date() and t.hour == next_interval.hour for t in candidate_hours):
                self.log(f"Next charging scheduled: {next_interval.strftime('%Y-%m-%d %H:%M')}")
                self.schedule_charge(next_interval)
            else:
                self.log("Next interval is not a candidate for charging.")

        except Exception as e:
            self.log(f"Error during planning: {str(e)}")

    def schedule_charge(self, target_time):
        now = datetime.now()
        target = target_time.replace(second=0, microsecond=0)
        if target < now:
            return
        self.run_at(self.start_charging, target, hour=target.hour, minute=target.minute)

    def start_charging(self, kwargs):
        hour = kwargs.get("hour")
        minute = kwargs.get("minute")
        duration = self.args.get("charge_duration_minutes", 15)  # Default to 15 minutes if not specified
        power = self.args.get("charge_power_w", 3000)

        self.log(f"Starting CHARGE at {hour:02d}:{minute:02d} for {duration} minutes at {power}W")

        self.call_service("script/turn_on", entity_id="script.force_battery_charge", variables={
            "duration": duration,
            "power": power
        })
