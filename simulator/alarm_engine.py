"""
Alarm Engine - Handles alarms with delay, hysteresis, severity
"""

import time
import logging
import numpy as np
from typing import Dict, Any, List
from enum import Enum

logger = logging.getLogger(__name__)

class AlarmSeverity(Enum):
    LOW = 1
    MEDIUM = 2
    HIGH = 3
    CRITICAL = 4

class AlarmEngine:
    """Alarm engine with delay and hysteresis"""

    def __init__(self, tag_generator, deterministic=True, seed=42):
        self.tag_gen = tag_generator
        self.deterministic = deterministic
        self.seed = seed
        if deterministic:
            self.rng = np.random.RandomState(seed)
        else:
            self.rng = np.random.RandomState()

        self.active_alarms = {}
        self.alarm_history = []

        # Alarm definitions
        self.alarm_defs = {
            'HH_WET_WELL': {
                'tag': 'WWTP01:INFLUENT:LT101.PV',
                'condition': lambda v: v > 2.5,
                'clear_condition': lambda v: v < 2.2,
                'delay': 5.0,
                'severity': AlarmSeverity.HIGH,
                'text': 'HH Wet Well Level',
                'description': 'Critically high wet well level - overflow risk',
            },
            'LL_WET_WELL': {
                'tag': 'WWTP01:INFLUENT:LT101.PV',
                'condition': lambda v: v < 0.3,
                'clear_condition': lambda v: v > 0.5,
                'delay': 3.0,
                'severity': AlarmSeverity.MEDIUM,
                'text': 'LL Wet Well Level',
                'description': 'Critically low wet well level - pump dry run protection',
            },
            'LOW_DO': {
                'tag': 'WWTP01:AERATION:DO301.PV',
                'condition': lambda v: v < 1.5,
                'clear_condition': lambda v: v > 2.0,
                'delay': 10.0,
                'severity': AlarmSeverity.MEDIUM,
                'text': 'Low Dissolved Oxygen',
                'description': 'DO below minimum threshold - reduced process efficiency',
            },
            'HIGH_DO': {
                'tag': 'WWTP01:AERATION:DO301.PV',
                'condition': lambda v: v > 5.0,
                'clear_condition': lambda v: v < 4.5,
                'delay': 30.0,
                'severity': AlarmSeverity.LOW,
                'text': 'High Dissolved Oxygen',
                'description': 'DO above optimal range - energy waste',
            },
            'VFD_FAULT': {
                'tag': 'WWTP01:AERATION:BLW201.FAULT',
                'condition': lambda v: v > 0,
                'clear_condition': lambda v: v == 0,
                'delay': 0.0,
                'severity': AlarmSeverity.HIGH,
                'text': 'Blower 201 VFD Fault',
                'description': 'Blower VFD fault detected - check drive unit',
            },
            'BLOWER_OVERLOAD': {
                'tag': 'WWTP01:AERATION:BLW201.CURRENT',
                'condition': lambda v: v > 18.0,
                'clear_condition': lambda v: v < 16.0,
                'delay': 5.0,
                'severity': AlarmSeverity.HIGH,
                'text': 'Blower Overload',
                'description': 'Blower current above rated value - possible mechanical fault',
            },
            'HIGH_TURBIDITY': {
                'tag': 'WWTP01:CLARIFIER:TUR501.PV',
                'condition': lambda v: v > 5.0,
                'clear_condition': lambda v: v < 4.0,
                'delay': 15.0,
                'severity': AlarmSeverity.MEDIUM,
                'text': 'High Effluent Turbidity',
                'description': 'Effluent turbidity above discharge limit',
            },
            'pH_OUT_RANGE': {
                'tag': 'WWTP01:AERATION:pH302.PV',
                'condition': lambda v: v < 6.5 or v > 8.0,
                'clear_condition': lambda v: 6.8 <= v <= 7.8,
                'delay': 20.0,
                'severity': AlarmSeverity.LOW,
                'text': 'pH Out of Range',
                'description': 'pH value outside optimal range',
            },
            'HIGH_COD': {
                'tag': 'WWTP01:EFFLUENT:COD501.PV',
                'condition': lambda v: v > 40.0,
                'clear_condition': lambda v: v < 35.0,
                'delay': 60.0,
                'severity': AlarmSeverity.MEDIUM,
                'text': 'High Effluent COD',
                'description': 'Effluent COD above discharge limit',
            },
            'PUMP_FAULT': {
                'tag': 'WWTP01:INFLUENT:PMP101.FAULT',
                'condition': lambda v: v > 0,
                'clear_condition': lambda v: v == 0,
                'delay': 0.0,
                'severity': AlarmSeverity.HIGH,
                'text': 'Pump 101 Fault',
                'description': 'Influent pump fault detected',
            },
            # New alarms
            'SCREEN_BLOCKAGE': {
                'tag': 'WWTP01:SCREENING:SCR101.DP',
                'condition': lambda v: v > 0.45,
                'clear_condition': lambda v: v < 0.35,
                'delay': 10.0,
                'severity': AlarmSeverity.MEDIUM,
                'text': 'Screen Blockage',
                'description': 'Screen differential pressure high - possible blockage',
            },
            'SCREEN_FAULT': {
                'tag': 'WWTP01:SCREENING:SCR101.FAULT',
                'condition': lambda v: v > 0,
                'clear_condition': lambda v: v == 0,
                'delay': 0.0,
                'severity': AlarmSeverity.HIGH,
                'text': 'Screen Fault',
                'description': 'Screen mechanism fault - manual intervention required',
            },
            'LOW_CHEMICAL_TANK': {
                'tag': 'WWTP01:CHEMICAL:TANK501.LEVEL',
                'condition': lambda v: v < 10.0,
                'clear_condition': lambda v: v > 15.0,
                'delay': 30.0,
                'severity': AlarmSeverity.MEDIUM,
                'text': 'Low Chemical Tank Level',
                'description': 'FeCl3 tank level below 10% - refill required',
            },
            'CHEMICAL_OVERDOSE': {
                'tag': 'WWTP01:CHEMICAL:DOSE_FECL3.PV',
                'condition': lambda v: v > 8.0,
                'clear_condition': lambda v: v < 6.0,
                'delay': 15.0,
                'severity': AlarmSeverity.HIGH,
                'text': 'Chemical Overdose',
                'description': 'FeCl3 dosing rate dangerously high',
            },
            'KILL_SWITCH_ACTIVE': {
                'tag': 'WWTP01:SYSTEM:KILL_SWITCH.PV',
                'condition': lambda v: v > 0,
                'clear_condition': lambda v: v == 0,
                'delay': 0.0,
                'severity': AlarmSeverity.CRITICAL,
                'text': 'EMERGENCY STOP ACTIVE',
                'description': 'Emergency kill switch activated - all equipment stopped',
            },
        }

        # Alarm state tracking
        self.alarm_states = {}
        for alarm_id in self.alarm_defs:
            self.alarm_states[alarm_id] = {
                'triggered_time': None,
                'active': False,
                'acknowledged': False,
            }

    def reset(self):
        """Reset alarm engine"""
        self.active_alarms = {}
        self.alarm_history = []
        for alarm_id in self.alarm_states:
            self.alarm_states[alarm_id] = {
                'triggered_time': None,
                'active': False,
                'acknowledged': False,
            }

    def update(self, snapshot: Dict[str, Any]):
        """Update alarm engine"""
        current_time = time.time()

        for alarm_id, alarm_def in self.alarm_defs.items():
            tag_name = alarm_def['tag']
            if tag_name not in snapshot:
                continue

            tag_value = snapshot[tag_name]['value']
            state = self.alarm_states[alarm_id]

            # Check alarm condition
            if alarm_def['condition'](tag_value):
                if state['triggered_time'] is None:
                    state['triggered_time'] = current_time

                # Check if delay has passed
                if current_time - state['triggered_time'] >= alarm_def['delay']:
                    if not state['active']:
                        state['active'] = True
                        alarm = {
                            'id': alarm_id,
                            'tag': tag_name,
                            'value': tag_value,
                            'severity': alarm_def['severity'].value,
                            'severity_text': alarm_def['severity'].name,
                            'text': alarm_def['text'],
                            'description': alarm_def['description'],
                            'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
                            'acknowledged': False,
                        }
                        self.active_alarms[alarm_id] = alarm
                        self.alarm_history.append(alarm.copy())
                        logger.info(f"Alarm activated: {alarm_def['text']}")
            else:
                # Check clear condition
                if alarm_def['clear_condition'](tag_value):
                    if state['active']:
                        state['active'] = False
                        state['triggered_time'] = None
                        if alarm_id in self.active_alarms:
                            del self.active_alarms[alarm_id]
                        logger.info(f"Alarm cleared: {alarm_def['text']}")
                else:
                    if state['triggered_time'] is not None and not state['active']:
                        state['triggered_time'] = None

    def get_active_alarms(self) -> List[Dict[str, Any]]:
        """Get list of active alarms"""
        return list(self.active_alarms.values())

    def acknowledge_alarm(self, alarm_id: str) -> bool:
        """Acknowledge an alarm"""
        if alarm_id in self.active_alarms:
            self.active_alarms[alarm_id]['acknowledged'] = True
            self.alarm_states[alarm_id]['acknowledged'] = True
            return True
        return False
