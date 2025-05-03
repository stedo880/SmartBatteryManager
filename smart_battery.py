import appdaemon.plugins.hass.hassapi as hass
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from dateutil import parser

class SmartBatteryManager(hass.Hass):

    def initialize(self) -> None:
        self.log("Smart battery manager initializing...")
        now = datetime.now()
        first_run = now.replace(second=0, microsecond=0)
        if now.minute % 15 == 14:
            first_run = first_run.replace(minute=now.minute)
        else:
            first_run = first_run.replace(minute=(now.minute // 15) * 15 + 14)
        if first_run < now:
            first_run += timedelta(minutes=15)
        self.run_every(self.plan_charging, first_run, 900)  # 900 seconds = 15 minutes
        self.run_in(self.plan_charging, 5)  # Initial run after 5 seconds

    def plan_charging(self, kwargs: Dict[str, Any]) -> None:
        try:
            now = datetime.now()
            next_interval = now.replace(second=0, microsecond=0) + timedelta(minutes=15 - now.minute % 15)

            soc = self.get_current_soc()
            if soc is None:
                return

            # Charge if price is below always charge threshold
            always_charge_threshold = self.args.get("always_charge_threshold", 0.0)
            energy_needed = self.calculate_energy_needed(soc, 1.0) # 100% SoC
            next_interval_price = self.get_price_for_interval(next_interval)
            if next_interval_price is not None and energy_needed > 0 and next_interval_price < always_charge_threshold:
                self.log(f"Next interval price: {next_interval_price:.2f} is below always charge threshold of {always_charge_threshold}")
                self.schedule_charge(next_interval)
                return
            else:
                self.log(f"Next interval price: {next_interval_price:.2f} is above always charge threshold of {always_charge_threshold}")
  
            target_soc = self.get_target_soc(next_interval)
            energy_needed = self.calculate_energy_needed(soc, target_soc)
            self.log(f"Current battery SoC: {soc*100:.0f}%, energy needed from grid: {energy_needed:.2f} kWh")         
            if self.check_skip_charge(soc, target_soc, energy_needed):
                return

            candidate_hours = self.get_candidate_hours()
            if self.is_next_interval_candidate(next_interval, candidate_hours):
                self.schedule_charge(next_interval)
            else:
                self.log("Skipping charge: Next interval is not a candidate for charging")

        except Exception as e:
            self.log(f"Error during planning: {str(e)}")

    def get_current_soc(self) -> Optional[float]:
        soc_raw = self.get_state(self.args["soc_sensor"])
        if soc_raw is None or soc_raw in ["unknown", "unavailable"]:
            self.log("Battery SoC sensor returned no data.")
            return None
        return float(soc_raw) / 100

    def get_target_soc(self, next_interval: datetime) -> float:
        soc_targets = self.args.get("soc_targets")
        if not soc_targets or len(soc_targets) != 24:
            self.log("Invalid or missing battery SoC target array, using default 90%")
            return 0.9
        target_soc = soc_targets[next_interval.hour]
        self.log(f"Selected target battery SoC for hour {next_interval.hour}: {target_soc * 100:.0f}%")
        return target_soc

    def calculate_energy_needed(self, soc: float, target_soc: float) -> float:
        battery_capacity = self.args.get("battery_capacity_kwh", 10)
        energy_needed = max(0, (target_soc - soc) * battery_capacity)
        return energy_needed

    def get_solar_next_hour(self) -> float:
        solar_next_hour_1 = self.get_state(self.args["energy_next_hour_sensor_1"])
        solar_next_hour_2 = self.get_state(self.args["energy_next_hour_sensor_2"])
        try:
            return float(solar_next_hour_1 or 0) + float(solar_next_hour_2 or 0)
        except ValueError:
            self.log("Could not parse solar forecast data, assuming 0 kWh")
            return 0

    def get_solar_remaining(self) -> float:
        solar_remaining_1 = self.get_state(self.args["energy_today_remaining_sensor_1"])
        solar_remaining_2 = self.get_state(self.args["energy_today_remaining_sensor_2"])
        try:
            return float(solar_remaining_1 or 0) + float(solar_remaining_2 or 0)
        except ValueError:
            self.log("Could not parse remaining solar production data, assuming 0 kWh")
            return 0

    def check_skip_charge(self, soc: float, target_soc: float, energy_needed: float) -> bool:
        if energy_needed <= 0:
           self.log("Skipping charge: No additional energy needed")
           return True

        solar_next_hour = self.get_solar_next_hour()
        solar_remaining = self.get_solar_remaining()

        self.log(f"Expected solar production next hour: {solar_next_hour:.2f} kWh")
        self.log(f"Expected remaining solar production today: {solar_remaining:.2f} kWh")
   
        now = datetime.now()
        if solar_remaining > 2 * energy_needed and now.time() > datetime.strptime("06:00", "%H:%M").time():
            self.log("Skipping charge: Expected remaining solar production today is more than double the energy needed")
            return True

        projected_soc = soc + (solar_next_hour / self.args.get("battery_capacity_kwh", 10))
        if projected_soc >= target_soc:
            self.log(f"Skipping charge: Expected solar next hour is enough to reach SoC target")
            return True

        return False

    def get_all_prices(self) -> List[tuple]:
        price_data_full = self.get_state(self.args["tibber_sensor"], attribute="all")
        if not price_data_full or "attributes" not in price_data_full:
            self.log("No price data attributes found")
            return []

        price_data = price_data_full["attributes"]
        tibber_prices = price_data.get("today", []) + price_data.get("tomorrow", [])
        if not tibber_prices:
            self.log("No price data available")
            return []

        return [
            (parser.isoparse(e["startsAt"]).replace(tzinfo=None), float(e["total"]))
            for e in tibber_prices
        ]

    def get_price_for_interval(self, interval: datetime) -> Optional[float]:
        all_prices = self.get_all_prices()
        for start_time, price in all_prices:
            # Match only the date and hour, ignoring the minutes
            if start_time.date() == interval.date() and start_time.hour == interval.hour:
                return price

        self.log(f"No price found for interval: {interval}")
        return None
    
    def get_candidate_hours(self) -> List[datetime]:
        all_prices = self.get_all_prices()
        if not all_prices:
            self.log("No prices available to calculate candidate hours")
            return []
        
        all_prices.sort(key=lambda x: x[0])

        smoothed = self.smooth_prices([p for (_, p) in all_prices])
        local_minima = self.find_local_minima(smoothed, all_prices)
        return self.build_candidate_hours(local_minima, all_prices)

    def smooth_prices(self, prices: List[float]) -> List[float]:
        smoothed = []
        window = 3  # 3×1 hour smoothing
        for i in range(len(prices)):
            lo = max(0, i - window // 2)
            hi = min(len(prices), i + window // 2 + 1)
            smoothed.append(sum(prices[lo:hi]) / (hi - lo))
        return smoothed

    def find_local_minima(self, smoothed: List[float], all_prices: List[tuple]) -> List[datetime]:
        local_minima = []
        for i in range(1, len(smoothed) - 1):
            if smoothed[i] < smoothed[i - 1] and smoothed[i] < smoothed[i + 1]:
                local_minima.append(all_prices[i][0])
        self.log(f"Detected local minima: {', '.join(t.strftime('%Y-%m-%d %H:%M') for t in local_minima)}")
        return local_minima

    def build_candidate_hours(self, local_minima: List[datetime], all_prices: List[tuple]) -> List[datetime]:
        candidate_hours = set()
        
        # Find mean price from all_prices
        mean_price = sum(p[1] for p in all_prices) / len(all_prices)
        self.log(f"Mean price: {mean_price:.2f}")
        
        for minimum in local_minima:
            min_price = next((p for (t, p) in all_prices if t == minimum), None)
            if min_price is None:
                continue

            window = [tp for tp in all_prices if abs((tp[0] - minimum).total_seconds()) / 3600 <= 2]
            cheapest_three = sorted(window, key=lambda x: x[1])[:3]
            candidate_hours.update(t[0] for t in cheapest_three)

            i = next((idx for idx, (t, _) in enumerate(all_prices) if t == minimum), None)
            if i is None:
                continue

            # Find future hours with prices below the minimum price + 0.10 and below the mean price
            j = i + 1
            while j < len(all_prices) and all_prices[j][1] <= min_price + 0.10 and all_prices[j][1] < mean_price:
                candidate_hours.add(all_prices[j][0])
                j += 1

            # Find past hours with prices below the minimum price + 0.10 and below the mean price
            j = i - 1
            while j >= 0 and all_prices[j][1] <= min_price + 0.10 and all_prices[j][1] < mean_price:
                candidate_hours.add(all_prices[j][0])
                j -= 1

        candidate_hours = sorted(candidate_hours)
        self.log(f"Candidate hours: {', '.join(t.strftime('%Y-%m-%d %H:%M') for t in candidate_hours)}")
        return candidate_hours

    def is_next_interval_candidate(self, next_interval: datetime, candidate_hours: List[datetime]) -> bool:
        return any(t.date() == next_interval.date() and t.hour == next_interval.hour for t in candidate_hours)

    def schedule_charge(self, target_time: datetime) -> None:
        now = datetime.now()
        target = target_time.replace(second=0, microsecond=0)
        if target < now:
            return
        self.log(f"Next charging scheduled: {target.strftime('%Y-%m-%d %H:%M')}")
        self.run_at(self.start_charging, target, hour=target.hour, minute=target.minute)

    def start_charging(self, kwargs: Dict[str, Any]) -> None:
        hour = kwargs.get("hour")
        minute = kwargs.get("minute")
        duration = self.args.get("charge_duration_minutes", 15)  # Default to 15 minutes if not specified
        power = self.args.get("charge_power_w", 3000)

        self.log(f"Starting CHARGE at {hour:02d}:{minute:02d} for {duration} minutes at {power}W")

        self.call_service("script/turn_on", entity_id="script.force_battery_charge", variables={
            "duration": duration,
            "power": power
        })
