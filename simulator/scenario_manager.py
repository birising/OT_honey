"""
Scenario Manager - Manages test scenarios
"""

import time
import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)

class ScenarioManager:
    """Manages scenarios"""

    def __init__(self, process_model, alarm_engine, deterministic=True, seed=42):
        self.process = process_model
        self.alarms = alarm_engine
        self.deterministic = deterministic
        self.seed = seed

        self.active_scenarios = {}

        self.scenario_defs = {
            'storm': {
                'description': 'Storm event - increased influent flow',
                'duration': 1800.0,
            },
            'vfd_fault': {
                'description': 'VFD fault on blower',
                'duration': 600.0,
            },
            'ph_calibration': {
                'description': 'pH sensor calibration drift',
                'duration': 300.0,
            },
            'bypass_risk': {
                'description': 'Bypass risk - high turbidity',
                'duration': 900.0,
            },
            'screen_blockage': {
                'description': 'Screen blockage - high differential pressure',
                'duration': 600.0,
            },
            'do_sensor_failure': {
                'description': 'DO sensor failure - stuck reading, blower overdrives',
                'duration': 900.0,
            },
            'chemical_overdose': {
                'description': 'Chemical overdose - FeCl3 dosing pump stuck on high',
                'duration': 600.0,
            },
        }

    def reset_all(self):
        """Reset all scenarios"""
        for scenario_name in list(self.active_scenarios.keys()):
            self.stop_scenario(scenario_name)

    def start_scenario(self, scenario_name: str):
        """Start a scenario"""
        if scenario_name not in self.scenario_defs:
            raise ValueError(f"Unknown scenario: {scenario_name}")

        if scenario_name in self.active_scenarios:
            logger.warning(f"Scenario {scenario_name} already active")
            return

        self.active_scenarios[scenario_name] = {
            'start_time': time.time(),
            'duration': self.scenario_defs[scenario_name]['duration'],
        }

        self.process.set_scenario_effect(scenario_name, True)
        logger.info(f"Scenario started: {scenario_name}")

    def stop_scenario(self, scenario_name: str):
        """Stop a scenario"""
        if scenario_name not in self.active_scenarios:
            logger.warning(f"Scenario {scenario_name} not active")
            return

        self.process.set_scenario_effect(scenario_name, False)
        del self.active_scenarios[scenario_name]
        logger.info(f"Scenario stopped: {scenario_name}")

    def update(self):
        """Update scenarios (check for auto-stop)"""
        current_time = time.time()
        to_stop = []

        for scenario_name, scenario_data in self.active_scenarios.items():
            elapsed = current_time - scenario_data['start_time']
            if elapsed >= scenario_data['duration']:
                to_stop.append(scenario_name)

        for scenario_name in to_stop:
            self.stop_scenario(scenario_name)

    def get_scenario_list(self):
        """Get all available scenarios with status"""
        result = {}
        for name, defn in self.scenario_defs.items():
            result[name] = {
                'description': defn['description'],
                'duration': defn['duration'],
                'active': name in self.active_scenarios,
            }
        return result
