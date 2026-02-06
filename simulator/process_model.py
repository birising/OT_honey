"""
Process Model - WWTP Process Simulation
Simulates: screening, grit/grease, primary clarifier, aeration tank,
           secondary clarifier, chemical dosing, effluent
"""

import time
import logging
import numpy as np
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

class ProcessModel:
    """Process model for small WWTP"""

    def __init__(self, tag_generator, deterministic=True, seed=42):
        self.tag_gen = tag_generator
        self.deterministic = deterministic
        self.seed = seed
        if deterministic:
            self.rng = np.random.RandomState(seed)
        else:
            self.rng = np.random.RandomState()

        self.tags = tag_generator.generate_tags()
        self.start_time = time.time()
        self.last_update = time.time()

        # Runtime hours
        self.runtime_hours = {
            'PMP101': 12450.5,
            'BLW201': 8760.0,
            'PMP301': 6230.2,
            'PMP401': 15620.3,
            'PMP402': 3420.7,
            'PMP501': 4120.8,
        }

        # Process state
        self.state = {
            # Global operating mode
            'GLOBAL_MODE': 'AUTO',       # AUTO / MANUAL / MAINTENANCE
            'KILL_SWITCH': False,

            # Active scenario flags (set by scenario_manager)
            'SCENARIO_STORM': False,
            'SCENARIO_DO_SENSOR_FAIL': False,

            # Influent wet well
            'Q_in': 15.0,
            'LT101': 1.2,
            'PMP101_CMD': False,
            'PMP101_FB': False,
            'PMP101_AUTO': True,
            'PMP101_RUNTIME': self.runtime_hours['PMP101'],
            'PMP101_FAULT': False,

            # Screening
            'SCR101_DP': 0.15,           # bar - differential pressure
            'SCR101_CMD': False,          # auto-clean command
            'SCR101_FB': False,           # auto-clean feedback
            'SCR101_FAULT': False,
            'SCR101_AUTO': True,
            'SCR101_CLEAN_TIMER': 0.0,   # internal timer for cleaning cycle

            # Grit / Grease
            'GRT201_LEVEL': 0.5,         # m - grit chamber level
            'GRS201_SKIM': False,         # grease skimmer active

            # Primary Clarifier
            'LT301_PRI': 1.5,            # m - primary clarifier level
            'PMP301_CMD': True,
            'PMP301_FB': True,
            'PMP301_AUTO': True,
            'PMP301_FAULT': False,
            'PMP301_RUNTIME': self.runtime_hours['PMP301'],
            'COD_AFTER_PRIMARY': 180.0,  # mg/L - COD after primary settling

            # Aeration tank
            'LT201': 2.5,
            'DO301': 2.5,
            'DO301_SP': 2.5,
            'pH302': 7.2,
            'TEMP303': 18.0,
            'BLW201_CMD': True,
            'BLW201_FB': True,
            'BLW201_AUTO': True,
            'BLW201_SP': 75.0,
            'BLW201_ACTUAL': 75.0,
            'BLW201_FAULT': False,
            'BLW201_RUNTIME': self.runtime_hours['BLW201'],
            'BLW201_CURRENT': 12.5,

            # Secondary Clarifier
            'LT401': 1.8,
            'TUR501': 2.5,
            'PMP401_CMD': True,
            'PMP401_FB': True,
            'PMP401_AUTO': True,
            'PMP401_RUNTIME': self.runtime_hours['PMP401'],
            'PMP402_CMD': False,
            'PMP402_FB': False,
            'PMP402_AUTO': True,
            'PMP402_RUNTIME': self.runtime_hours['PMP402'],

            # Chemical Dosing
            'DOSE_FECL3_RATE': 2.5,      # L/h - actual dosing rate
            'DOSE_FECL3_SP': 2.5,        # L/h - dosing rate setpoint
            'PMP501_CMD': True,
            'PMP501_FB': True,
            'PMP501_AUTO': True,
            'PMP501_RUNTIME': self.runtime_hours['PMP501'],
            'DOSE_FECL3_TANK_LEVEL': 75.0,  # % - chemical tank level
            'DOSE_POLY_RATE': 0.5,        # L/h - polymer dosing rate

            # Valves
            'VLV101_POS': 100.0,          # % - inlet valve position
            'VLV101_CMD': 100.0,          # % - inlet valve command
            'VLV501_POS': 50.0,           # % - chemical valve position
            'VLV501_CMD': 50.0,           # % - chemical valve command

            # Effluent
            'Q_out': 14.5,
            'pH501': 7.1,
            'COD501': 25.0,
        }

        # Process parameters
        self.params = {
            'wet_well_volume': 50.0,
            'aeration_volume': 200.0,
            'clarifier_volume': 150.0,
            'primary_volume': 120.0,
            'pump_capacity': 20.0,
            'ras_ratio': 0.3,
            'was_ratio': 0.05,
            'influent_cod': 250.0,
        }

        # Interlocks
        self.interlocks = {
            'PMP101_LOW_LEVEL': 0.3,
            'PMP101_HIGH_LEVEL': 2.5,
            'BLW201_MIN_DO': 1.5,
        }

        # Hysteresis and delays
        self.hysteresis = {
            'PMP101': {'on': 1.5, 'off': 0.8},
            'DO301': {'low': 2.0, 'high': 3.0},
        }

        # Automation controllers
        self.controllers = {
            'DO_CONTROLLER': {
                'enabled': True,
                'mode': 'AUTO',
                'sp': 2.5,
                'kp': 15.0,
                'ki': 0.5,
                'kd': 2.0,
                'output_min': 30.0,
                'output_max': 100.0,
                'integral': 0.0,
                'last_error': 0.0,
                'last_pv': 2.5,
            },
            'LEVEL_CONTROLLER': {
                'enabled': True,
                'mode': 'AUTO',
                'sp': 2.0,
                'hysteresis_on': 1.5,
                'hysteresis_off': 0.8,
            },
        }

        self.update_history = {}

    def reset(self):
        """Reset to default state (preserves runtime hours)"""
        old_runtime = self.runtime_hours.copy()
        self.__init__(self.tag_gen, self.deterministic, self.seed)
        self.runtime_hours = old_runtime
        self.state['PMP101_RUNTIME'] = self.runtime_hours['PMP101']
        self.state['BLW201_RUNTIME'] = self.runtime_hours['BLW201']
        self.state['PMP301_RUNTIME'] = self.runtime_hours['PMP301']
        self.state['PMP401_RUNTIME'] = self.runtime_hours['PMP401']
        self.state['PMP402_RUNTIME'] = self.runtime_hours['PMP402']
        self.state['PMP501_RUNTIME'] = self.runtime_hours['PMP501']

    def _noise(self, mean=0, std=1.0):
        """Generate noise using appropriate RNG"""
        if self.deterministic:
            return self.rng.normal(mean, std)
        return np.random.normal(mean, std)

    def _is_auto_allowed(self):
        """Check if AUTO control is allowed based on global mode"""
        return self.state['GLOBAL_MODE'] == 'AUTO' and not self.state['KILL_SWITCH']

    def _is_running_allowed(self):
        """Check if equipment can run based on global mode"""
        return self.state['GLOBAL_MODE'] != 'MAINTENANCE' and not self.state['KILL_SWITCH']

    def update(self, dt: float):
        """Update process model"""
        current_time = time.time()
        self.last_update = current_time

        # Kill switch enforcement
        if self.state['KILL_SWITCH']:
            self.state['GLOBAL_MODE'] = 'MAINTENANCE'
            self._stop_all_equipment()
        elif self.state['GLOBAL_MODE'] == 'MAINTENANCE':
            self._stop_all_equipment()

        # Daily cycle
        from datetime import datetime
        hour = datetime.now().hour
        daily_factor = 1.0
        if 6 <= hour < 9:
            daily_factor = 1.4
        elif 18 <= hour < 21:
            daily_factor = 1.3
        elif 0 <= hour < 6:
            daily_factor = 0.7

        # --- INFLUENT ---
        noise = self._noise(0, 0.5)
        base_flow = 15.0 * daily_factor
        if self.state['SCENARIO_STORM']:
            base_flow = 35.0 * daily_factor  # Storm event: ~2.3x normal flow
        self.state['Q_in'] = max(8.0, base_flow + noise)

        # Inlet valve affects flow
        valve_factor = self.state['VLV101_POS'] / 100.0
        effective_inflow = self.state['Q_in'] * valve_factor

        # Wet well level dynamics
        inflow = effective_inflow / 3600.0 * dt
        outflow = 0.0

        if self._is_running_allowed():
            if self.state['PMP101_CMD'] and self.state['PMP101_AUTO'] and self._is_auto_allowed():
                if self.state['LT101'] > self.interlocks['PMP101_LOW_LEVEL']:
                    outflow = self.params['pump_capacity'] / 3600.0 * dt
                    self.state['PMP101_FB'] = True
                else:
                    self.state['PMP101_FB'] = False
                    self.state['PMP101_CMD'] = False
            elif not self.state['PMP101_AUTO']:
                self.state['PMP101_FB'] = self.state['PMP101_CMD']
                if self.state['PMP101_CMD']:
                    outflow = self.params['pump_capacity'] / 3600.0 * dt
            else:
                self.state['PMP101_FB'] = False
        else:
            self.state['PMP101_FB'] = False

        # Level update
        level_change = (inflow - outflow) / self.params['wet_well_volume']
        self.state['LT101'] = max(0.0, min(3.0, self.state['LT101'] + level_change))

        # Auto control for pump
        if self._is_auto_allowed() and self.state['PMP101_AUTO']:
            controller = self.controllers['LEVEL_CONTROLLER']
            if controller['enabled'] and controller['mode'] == 'AUTO':
                if self.state['LT101'] > controller['hysteresis_on']:
                    self.state['PMP101_CMD'] = True
                elif self.state['LT101'] < controller['hysteresis_off']:
                    self.state['PMP101_CMD'] = False

        # --- SCREENING ---
        if self._is_running_allowed():
            # DP increases slowly (fouling)
            self.state['SCR101_DP'] += 0.001 * dt + self._noise(0, 0.0002)
            self.state['SCR101_DP'] = max(0.05, self.state['SCR101_DP'])

            # Auto-clean cycle
            if self.state['SCR101_AUTO'] and self._is_auto_allowed():
                if self.state['SCR101_DP'] > 0.35 and not self.state['SCR101_CMD']:
                    self.state['SCR101_CMD'] = True
                    self.state['SCR101_CLEAN_TIMER'] = 30.0  # 30s cleaning cycle

            if self.state['SCR101_CMD']:
                self.state['SCR101_FB'] = True
                self.state['SCR101_CLEAN_TIMER'] -= dt
                # Cleaning reduces DP
                self.state['SCR101_DP'] = max(0.08, self.state['SCR101_DP'] - 0.01 * dt)
                if self.state['SCR101_CLEAN_TIMER'] <= 0:
                    self.state['SCR101_CMD'] = False
                    self.state['SCR101_FB'] = False
                    self.state['SCR101_CLEAN_TIMER'] = 0.0
            else:
                self.state['SCR101_FB'] = False

            # Fault if DP too high
            if self.state['SCR101_DP'] > 0.5:
                self.state['SCR101_FAULT'] = True
        else:
            self.state['SCR101_FB'] = False

        # --- GRIT / GREASE ---
        # Simple pass-through, grit settles
        self.state['GRT201_LEVEL'] = max(0.0, min(2.0,
            0.5 + self._noise(0, 0.05)))
        # Skimmer activates at level > 1.0m
        if self.state['GRT201_LEVEL'] > 1.0 and self._is_running_allowed():
            self.state['GRS201_SKIM'] = True
        else:
            self.state['GRS201_SKIM'] = False

        # --- PRIMARY CLARIFIER ---
        primary_inflow = outflow  # From wet well pump

        if self._is_running_allowed():
            if self.state['PMP301_AUTO'] and self._is_auto_allowed():
                if primary_inflow > 0 and self.state['LT301_PRI'] > 0.8:
                    self.state['PMP301_CMD'] = True
                else:
                    self.state['PMP301_CMD'] = False

            if self.state['PMP301_CMD'] and not self.state['PMP301_FAULT']:
                self.state['PMP301_FB'] = True
                primary_outflow = primary_inflow * 0.95
            else:
                self.state['PMP301_FB'] = False
                primary_outflow = primary_inflow * 0.3  # gravity flow
        else:
            self.state['PMP301_FB'] = False
            primary_outflow = 0.0

        # Primary settling reduces COD ~30%
        self.state['COD_AFTER_PRIMARY'] = self.params['influent_cod'] * 0.7 + self._noise(0, 5.0)
        self.state['COD_AFTER_PRIMARY'] = max(100.0, min(250.0, self.state['COD_AFTER_PRIMARY']))

        # Primary level
        pri_level_change = (primary_inflow - primary_outflow) / self.params['primary_volume']
        self.state['LT301_PRI'] = max(0.5, min(3.0, self.state['LT301_PRI'] + pri_level_change))

        # --- AERATION TANK ---
        aeration_inflow = primary_outflow

        # Aeration level
        aeration_outflow = aeration_inflow * 0.95
        level_change_aer = (aeration_inflow - aeration_outflow) / self.params['aeration_volume']
        self.state['LT201'] = max(1.0, min(3.5, self.state['LT201'] + level_change_aer))

        # DO Controller - PID (skip if blower faulted or DO sensor failed)
        do_controller = self.controllers['DO_CONTROLLER']
        if (self._is_auto_allowed() and self.state['BLW201_AUTO'] and
                do_controller['enabled'] and do_controller['mode'] == 'AUTO' and
                not self.state['BLW201_FAULT'] and not self.state['SCENARIO_DO_SENSOR_FAIL']):
            pv = self.state['DO301']
            sp = do_controller['sp']
            error = sp - pv

            p_term = do_controller['kp'] * error
            do_controller['integral'] += error * dt
            do_controller['integral'] = max(-10.0, min(10.0, do_controller['integral']))
            i_term = do_controller['ki'] * do_controller['integral']
            d_error = (error - do_controller['last_error']) / dt if dt > 0 else 0
            d_term = do_controller['kd'] * d_error
            do_controller['last_error'] = error

            pid_output = p_term + i_term + d_term
            new_speed = 50.0 + pid_output
            new_speed = max(do_controller['output_min'], min(do_controller['output_max'], new_speed))

            self.state['BLW201_SP'] = new_speed
            if new_speed > 30.0:
                self.state['BLW201_CMD'] = True
            elif new_speed < 25.0:
                self.state['BLW201_CMD'] = False

        # Blower fault forces CMD off
        if self.state['BLW201_FAULT']:
            self.state['BLW201_CMD'] = False

        # DO dynamics
        if self.state['SCENARIO_DO_SENSOR_FAIL']:
            # DO sensor stuck - reading frozen, blower overdrives
            self.state['DO301'] = 0.5
            self.state['BLW201_SP'] = 100.0
            self.state['BLW201_CMD'] = True
            self.state['BLW201_FB'] = True if self._is_running_allowed() else False
        elif self._is_running_allowed() and self.state['BLW201_CMD'] and not self.state['BLW201_FAULT']:
            do_target = 2.0 + (self.state['BLW201_ACTUAL'] / 100.0) * 2.0
            do_rate = 0.1 * dt
            if self.state['DO301'] < do_target:
                self.state['DO301'] = min(do_target, self.state['DO301'] + do_rate)
            else:
                self.state['DO301'] = max(do_target - 0.5, self.state['DO301'] - do_rate * 0.3)
            self.state['BLW201_FB'] = True
        else:
            self.state['DO301'] = max(0.0, self.state['DO301'] - 0.05 * dt)
            self.state['BLW201_FB'] = False

        # pH
        self.state['pH302'] = max(6.5, min(8.0, 7.2 + self._noise(0, 0.02)))

        # Temperature
        self.state['TEMP303'] = max(10.0, min(25.0, 18.0 + self._noise(0, 0.1)))

        # Blower speed lag (VFD inertia)
        if self.state['BLW201_SP'] != self.state['BLW201_ACTUAL']:
            diff = self.state['BLW201_SP'] - self.state['BLW201_ACTUAL']
            self.state['BLW201_ACTUAL'] += np.sign(diff) * min(abs(diff), 1.0 * dt)

        # Blower current
        if self.state['BLW201_FB']:
            speed_factor = (self.state['BLW201_ACTUAL'] / 100.0) * 8.0
            load_factor = (self.state['DO301'] / 3.0) * 2.0
            current_noise = self._noise(0, 0.3)
            self.state['BLW201_CURRENT'] = max(2.0, 4.0 + speed_factor + load_factor + current_noise)
        else:
            self.state['BLW201_CURRENT'] = 0.0

        # --- SECONDARY CLARIFIER ---
        clarifier_inflow = aeration_outflow

        if self._is_running_allowed():
            # RAS pump
            if self.state['PMP401_AUTO'] and self._is_auto_allowed():
                if self.state['PMP101_FB'] and self.state['LT401'] > 1.0:
                    self.state['PMP401_CMD'] = True
                else:
                    self.state['PMP401_CMD'] = False

            # WAS pump
            if self.state['PMP402_AUTO'] and self._is_auto_allowed():
                if self.state['LT401'] > 2.5:
                    self.state['PMP402_CMD'] = True
                elif self.state['LT401'] < 2.0:
                    self.state['PMP402_CMD'] = False

        ras_flow = clarifier_inflow * self.params['ras_ratio'] if self.state['PMP401_CMD'] else 0.0
        was_flow = clarifier_inflow * self.params['was_ratio'] if self.state['PMP402_CMD'] else 0.0
        effluent_flow = clarifier_inflow - ras_flow - was_flow

        self.state['PMP401_FB'] = self.state['PMP401_CMD'] and self._is_running_allowed()
        self.state['PMP402_FB'] = self.state['PMP402_CMD'] and self._is_running_allowed()

        # Clarifier level
        level_change_clar = (clarifier_inflow - effluent_flow - ras_flow - was_flow) / self.params['clarifier_volume']
        self.state['LT401'] = max(1.0, min(3.0, self.state['LT401'] + level_change_clar))

        # Effluent turbidity
        if self.state['DO301'] > 2.0 and self.state['LT401'] > 1.5:
            turb_noise = self._noise(0, 0.2)
            self.state['TUR501'] = max(0.5, min(5.0, 2.0 + turb_noise))
        else:
            self.state['TUR501'] = min(10.0, self.state['TUR501'] + 0.1 * dt)

        self.state['Q_out'] = effluent_flow * 3600.0

        # --- CHEMICAL DOSING ---
        if self._is_running_allowed():
            # Rate tracks setpoint with lag
            rate_diff = self.state['DOSE_FECL3_SP'] - self.state['DOSE_FECL3_RATE']
            self.state['DOSE_FECL3_RATE'] += rate_diff * 0.2 * dt  # 5s time constant
            self.state['DOSE_FECL3_RATE'] = max(0.0, min(10.0, self.state['DOSE_FECL3_RATE']))

            # Chemical valve affects rate
            valve_factor_chem = self.state['VLV501_POS'] / 100.0
            self.state['DOSE_FECL3_RATE'] *= valve_factor_chem

            if self.state['PMP501_AUTO'] and self._is_auto_allowed():
                if self.state['DOSE_FECL3_SP'] > 0.1:
                    self.state['PMP501_CMD'] = True
                else:
                    self.state['PMP501_CMD'] = False

            self.state['PMP501_FB'] = self.state['PMP501_CMD'] and self._is_running_allowed()

            # Tank level depletes
            if self.state['PMP501_FB'] and self.state['DOSE_FECL3_RATE'] > 0:
                # Assume 1000L tank, rate in L/h
                depletion = (self.state['DOSE_FECL3_RATE'] / 1000.0) * (dt / 3600.0) * 100.0
                self.state['DOSE_FECL3_TANK_LEVEL'] = max(0.0, self.state['DOSE_FECL3_TANK_LEVEL'] - depletion)

            # Polymer dosing (simplified)
            self.state['DOSE_POLY_RATE'] = max(0.0, 0.5 + self._noise(0, 0.05))
        else:
            self.state['PMP501_FB'] = False

        # --- VALVES ---
        # Position ramps to command with ~5s lag
        for vlv_prefix in ['VLV101', 'VLV501']:
            pos_key = f'{vlv_prefix}_POS'
            cmd_key = f'{vlv_prefix}_CMD'
            pos_diff = self.state[cmd_key] - self.state[pos_key]
            # ~20% per second ramp rate
            self.state[pos_key] += np.sign(pos_diff) * min(abs(pos_diff), 20.0 * dt)
            self.state[pos_key] = max(0.0, min(100.0, self.state[pos_key]))

        # --- EFFLUENT QUALITY ---
        # Chemical dosing improves effluent quality
        chem_factor = 1.0 - (self.state['DOSE_FECL3_RATE'] / 10.0) * 0.2  # up to 20% improvement
        chem_factor = max(0.7, min(1.0, chem_factor))

        if self.state['DO301'] > 2.0 and self.state['TUR501'] < 3.0:
            cod_noise = self._noise(0, 2.0)
            self.state['COD501'] = max(15.0, (25.0 + cod_noise) * chem_factor)
            self.state['pH501'] = max(6.8, min(7.5, 7.1 + self._noise(0, 0.05)))
        else:
            self.state['COD501'] = min(50.0, self.state['COD501'] + 0.5 * dt)
            self.state['pH501'] = max(6.5, min(8.0, self.state['pH501'] + self._noise(0, 0.02)))

        # --- RUNTIME HOURS ---
        if self.state['PMP101_FB']:
            self.runtime_hours['PMP101'] += dt / 3600.0
            self.state['PMP101_RUNTIME'] = self.runtime_hours['PMP101']

        if self.state['BLW201_FB']:
            self.runtime_hours['BLW201'] += dt / 3600.0
            self.state['BLW201_RUNTIME'] = self.runtime_hours['BLW201']

        if self.state['PMP301_FB']:
            self.runtime_hours['PMP301'] += dt / 3600.0
            self.state['PMP301_RUNTIME'] = self.runtime_hours['PMP301']

        if self.state['PMP401_FB']:
            self.runtime_hours['PMP401'] += dt / 3600.0
            self.state['PMP401_RUNTIME'] = self.runtime_hours['PMP401']

        if self.state['PMP402_FB']:
            self.runtime_hours['PMP402'] += dt / 3600.0
            self.state['PMP402_RUNTIME'] = self.runtime_hours['PMP402']

        if self.state['PMP501_FB']:
            self.runtime_hours['PMP501'] += dt / 3600.0
            self.state['PMP501_RUNTIME'] = self.runtime_hours['PMP501']

        # Update tag values
        self._update_tags()

    def _stop_all_equipment(self):
        """Stop all equipment (MAINTENANCE / KILL SWITCH)"""
        for key in ['PMP101_CMD', 'PMP301_CMD', 'PMP401_CMD', 'PMP402_CMD',
                     'PMP501_CMD', 'BLW201_CMD', 'SCR101_CMD']:
            self.state[key] = False

    def _update_tags(self):
        """Update tag values from state"""
        tag_map = {
            # System
            'WWTP01:SYSTEM:GLOBAL_MODE.PV': {'AUTO': 0, 'MANUAL': 1, 'MAINTENANCE': 2}.get(self.state['GLOBAL_MODE'], 0),
            'WWTP01:SYSTEM:KILL_SWITCH.PV': 1 if self.state['KILL_SWITCH'] else 0,

            # Influent
            'WWTP01:INFLUENT:Q_IN.PV': self.state['Q_in'],
            'WWTP01:INFLUENT:LT101.PV': self.state['LT101'],
            'WWTP01:INFLUENT:PMP101.CMD': 1 if self.state['PMP101_CMD'] else 0,
            'WWTP01:INFLUENT:PMP101.FB': 1 if self.state['PMP101_FB'] else 0,
            'WWTP01:INFLUENT:PMP101.AUTO': 1 if self.state['PMP101_AUTO'] else 0,
            'WWTP01:INFLUENT:PMP101.RUNTIME': self.state['PMP101_RUNTIME'],
            'WWTP01:INFLUENT:PMP101.FAULT': 1 if self.state['PMP101_FAULT'] else 0,

            # Screening
            'WWTP01:SCREENING:SCR101.DP': self.state['SCR101_DP'],
            'WWTP01:SCREENING:SCR101.CMD': 1 if self.state['SCR101_CMD'] else 0,
            'WWTP01:SCREENING:SCR101.FB': 1 if self.state['SCR101_FB'] else 0,
            'WWTP01:SCREENING:SCR101.FAULT': 1 if self.state['SCR101_FAULT'] else 0,
            'WWTP01:SCREENING:SCR101.AUTO': 1 if self.state['SCR101_AUTO'] else 0,

            # Grit/Grease
            'WWTP01:GRIT:GRT201.LEVEL': self.state['GRT201_LEVEL'],
            'WWTP01:GRIT:GRS201.SKIM': 1 if self.state['GRS201_SKIM'] else 0,

            # Primary Clarifier
            'WWTP01:PRIMARY:LT301.PV': self.state['LT301_PRI'],
            'WWTP01:PRIMARY:PMP301.CMD': 1 if self.state['PMP301_CMD'] else 0,
            'WWTP01:PRIMARY:PMP301.FB': 1 if self.state['PMP301_FB'] else 0,
            'WWTP01:PRIMARY:PMP301.AUTO': 1 if self.state['PMP301_AUTO'] else 0,
            'WWTP01:PRIMARY:PMP301.FAULT': 1 if self.state['PMP301_FAULT'] else 0,
            'WWTP01:PRIMARY:PMP301.RUNTIME': self.state['PMP301_RUNTIME'],
            'WWTP01:PRIMARY:COD_PRI.PV': self.state['COD_AFTER_PRIMARY'],

            # Aeration
            'WWTP01:AERATION:LT201.PV': self.state['LT201'],
            'WWTP01:AERATION:DO301.PV': self.state['DO301'],
            'WWTP01:AERATION:DO301.SP': self.state['DO301_SP'],
            'WWTP01:AERATION:pH302.PV': self.state['pH302'],
            'WWTP01:AERATION:TEMP303.PV': self.state['TEMP303'],
            'WWTP01:AERATION:BLW201.CMD': 1 if self.state['BLW201_CMD'] else 0,
            'WWTP01:AERATION:BLW201.FB': 1 if self.state['BLW201_FB'] else 0,
            'WWTP01:AERATION:BLW201.AUTO': 1 if self.state['BLW201_AUTO'] else 0,
            'WWTP01:AERATION:BLW201.SP': self.state['BLW201_SP'],
            'WWTP01:AERATION:BLW201.PV': self.state['BLW201_ACTUAL'],
            'WWTP01:AERATION:BLW201.FAULT': 1 if self.state['BLW201_FAULT'] else 0,
            'WWTP01:AERATION:BLW201.RUNTIME': self.state['BLW201_RUNTIME'],
            'WWTP01:AERATION:BLW201.CURRENT': self.state['BLW201_CURRENT'],

            # Clarifier
            'WWTP01:CLARIFIER:LT401.PV': self.state['LT401'],
            'WWTP01:CLARIFIER:TUR501.PV': self.state['TUR501'],
            'WWTP01:CLARIFIER:PMP401.CMD': 1 if self.state['PMP401_CMD'] else 0,
            'WWTP01:CLARIFIER:PMP401.FB': 1 if self.state['PMP401_FB'] else 0,
            'WWTP01:CLARIFIER:PMP401.AUTO': 1 if self.state['PMP401_AUTO'] else 0,
            'WWTP01:CLARIFIER:PMP401.RUNTIME': self.state['PMP401_RUNTIME'],
            'WWTP01:CLARIFIER:PMP402.CMD': 1 if self.state['PMP402_CMD'] else 0,
            'WWTP01:CLARIFIER:PMP402.FB': 1 if self.state['PMP402_FB'] else 0,
            'WWTP01:CLARIFIER:PMP402.AUTO': 1 if self.state['PMP402_AUTO'] else 0,
            'WWTP01:CLARIFIER:PMP402.RUNTIME': self.state['PMP402_RUNTIME'],

            # Chemical Dosing
            'WWTP01:CHEMICAL:DOSE_FECL3.PV': self.state['DOSE_FECL3_RATE'],
            'WWTP01:CHEMICAL:DOSE_FECL3.SP': self.state['DOSE_FECL3_SP'],
            'WWTP01:CHEMICAL:PMP501.CMD': 1 if self.state['PMP501_CMD'] else 0,
            'WWTP01:CHEMICAL:PMP501.FB': 1 if self.state['PMP501_FB'] else 0,
            'WWTP01:CHEMICAL:PMP501.AUTO': 1 if self.state['PMP501_AUTO'] else 0,
            'WWTP01:CHEMICAL:PMP501.RUNTIME': self.state['PMP501_RUNTIME'],
            'WWTP01:CHEMICAL:TANK501.LEVEL': self.state['DOSE_FECL3_TANK_LEVEL'],
            'WWTP01:CHEMICAL:DOSE_POLY.PV': self.state['DOSE_POLY_RATE'],

            # Valves
            'WWTP01:INFLUENT:VLV101.POS': self.state['VLV101_POS'],
            'WWTP01:INFLUENT:VLV101.CMD': self.state['VLV101_CMD'],
            'WWTP01:CHEMICAL:VLV501.POS': self.state['VLV501_POS'],
            'WWTP01:CHEMICAL:VLV501.CMD': self.state['VLV501_CMD'],

            # Effluent
            'WWTP01:EFFLUENT:Q_OUT.PV': self.state['Q_out'],
            'WWTP01:EFFLUENT:pH501.PV': self.state['pH501'],
            'WWTP01:EFFLUENT:COD501.PV': self.state['COD501'],

            # Controller status
            'WWTP01:AERATION:DO301.CTRL_EN': 1 if self.controllers['DO_CONTROLLER']['enabled'] else 0,
            'WWTP01:AERATION:DO301.CTRL_MODE': 1 if self.controllers['DO_CONTROLLER']['mode'] == 'AUTO' else 0,
            'WWTP01:AERATION:DO301.CTRL_ACTIVE': 1 if (self.state['BLW201_AUTO'] and self.controllers['DO_CONTROLLER']['enabled']) else 0,
            'WWTP01:INFLUENT:LT101.CTRL_EN': 1 if self.controllers['LEVEL_CONTROLLER']['enabled'] else 0,
            'WWTP01:INFLUENT:LT101.CTRL_ACTIVE': 1 if (self.state['PMP101_AUTO'] and self.controllers['LEVEL_CONTROLLER']['enabled']) else 0,
        }

        for tag_name, tag_obj in self.tags.items():
            if tag_name in tag_map:
                tag_obj['value'] = tag_map[tag_name]

    def write_tag(self, tag: str, value: Any) -> Any:
        """Write to tag"""
        if tag not in self.tags:
            raise ValueError(f"Tag {tag} not found")

        # Map tag writes to state
        if tag == 'WWTP01:INFLUENT:PMP101.CMD':
            self.state['PMP101_CMD'] = bool(value)
        elif tag == 'WWTP01:INFLUENT:PMP101.AUTO':
            self.state['PMP101_AUTO'] = bool(value)
        elif tag == 'WWTP01:AERATION:BLW201.CMD':
            self.state['BLW201_CMD'] = bool(value)
        elif tag == 'WWTP01:AERATION:BLW201.AUTO':
            self.state['BLW201_AUTO'] = bool(value)
        elif tag == 'WWTP01:AERATION:BLW201.SP':
            if not self.state['BLW201_AUTO'] or not self.controllers['DO_CONTROLLER']['enabled']:
                self.state['BLW201_SP'] = max(0.0, min(100.0, float(value)))
        elif tag == 'WWTP01:AERATION:DO301.SP':
            self.controllers['DO_CONTROLLER']['sp'] = max(1.0, min(5.0, float(value)))
            self.state['DO301_SP'] = self.controllers['DO_CONTROLLER']['sp']
        elif tag == 'WWTP01:AERATION:DO301.CTRL_EN':
            self.controllers['DO_CONTROLLER']['enabled'] = bool(value)
        elif tag == 'WWTP01:AERATION:DO301.CTRL_MODE':
            self.controllers['DO_CONTROLLER']['mode'] = 'AUTO' if bool(value) else 'MANUAL'
            if self.controllers['DO_CONTROLLER']['mode'] == 'MANUAL':
                self.state['BLW201_SP'] = max(0.0, min(100.0, self.state['BLW201_SP']))
        elif tag == 'WWTP01:CLARIFIER:PMP401.CMD':
            self.state['PMP401_CMD'] = bool(value)
        elif tag == 'WWTP01:CLARIFIER:PMP401.AUTO':
            self.state['PMP401_AUTO'] = bool(value)
        elif tag == 'WWTP01:CLARIFIER:PMP402.CMD':
            self.state['PMP402_CMD'] = bool(value)
        elif tag == 'WWTP01:CLARIFIER:PMP402.AUTO':
            self.state['PMP402_AUTO'] = bool(value)
        # New tag writes
        elif tag == 'WWTP01:SCREENING:SCR101.CMD':
            self.state['SCR101_CMD'] = bool(value)
        elif tag == 'WWTP01:SCREENING:SCR101.AUTO':
            self.state['SCR101_AUTO'] = bool(value)
        elif tag == 'WWTP01:PRIMARY:PMP301.CMD':
            self.state['PMP301_CMD'] = bool(value)
        elif tag == 'WWTP01:PRIMARY:PMP301.AUTO':
            self.state['PMP301_AUTO'] = bool(value)
        elif tag == 'WWTP01:CHEMICAL:PMP501.CMD':
            self.state['PMP501_CMD'] = bool(value)
        elif tag == 'WWTP01:CHEMICAL:PMP501.AUTO':
            self.state['PMP501_AUTO'] = bool(value)
        elif tag == 'WWTP01:CHEMICAL:DOSE_FECL3.SP':
            self.state['DOSE_FECL3_SP'] = max(0.0, min(10.0, float(value)))
        elif tag == 'WWTP01:INFLUENT:VLV101.CMD':
            self.state['VLV101_CMD'] = max(0.0, min(100.0, float(value)))
        elif tag == 'WWTP01:CHEMICAL:VLV501.CMD':
            self.state['VLV501_CMD'] = max(0.0, min(100.0, float(value)))
        elif tag == 'WWTP01:SYSTEM:GLOBAL_MODE.PV':
            mode_map = {0: 'AUTO', 1: 'MANUAL', 2: 'MAINTENANCE'}
            self.state['GLOBAL_MODE'] = mode_map.get(int(value), 'AUTO')
        elif tag == 'WWTP01:SYSTEM:KILL_SWITCH.PV':
            self.state['KILL_SWITCH'] = bool(value)

        self.tags[tag]['value'] = value
        return value

    def set_mode(self, mode: str):
        """Set global operating mode"""
        if mode in ('AUTO', 'MANUAL', 'MAINTENANCE'):
            self.state['GLOBAL_MODE'] = mode

    def set_kill_switch(self, active: bool):
        """Activate/deactivate kill switch"""
        self.state['KILL_SWITCH'] = active
        if active:
            self.state['GLOBAL_MODE'] = 'MAINTENANCE'
            self._stop_all_equipment()

    def get_snapshot(self) -> Dict[str, Any]:
        """Get current snapshot of all tags"""
        snapshot = {}
        for tag_name, tag_obj in self.tags.items():
            snapshot[tag_name] = {
                'value': tag_obj.get('value', 0),
                'type': tag_obj.get('type', 'analog'),
                'unit': tag_obj.get('unit', ''),
                'description': tag_obj.get('description', ''),
            }
        return snapshot

    def set_scenario_effect(self, scenario_name: str, active: bool):
        """Apply scenario effects"""
        if scenario_name == 'storm':
            self.state['SCENARIO_STORM'] = active
            if not active:
                self.state['Q_in'] = 15.0
        elif scenario_name == 'vfd_fault':
            if active:
                self.state['BLW201_FAULT'] = True
                self.state['BLW201_CMD'] = False
            else:
                self.state['BLW201_FAULT'] = False
        elif scenario_name == 'ph_calibration':
            if active:
                self.state['pH302'] = 8.5
            else:
                self.state['pH302'] = 7.2
        elif scenario_name == 'bypass_risk':
            if active:
                self.state['TUR501'] = 15.0
            else:
                self.state['TUR501'] = 2.5
        elif scenario_name == 'screen_blockage':
            if active:
                self.state['SCR101_DP'] = 0.55
                self.state['SCR101_FAULT'] = True
            else:
                self.state['SCR101_DP'] = 0.15
                self.state['SCR101_FAULT'] = False
        elif scenario_name == 'do_sensor_failure':
            self.state['SCENARIO_DO_SENSOR_FAIL'] = active
            if not active:
                self.state['DO301'] = 2.5
                self.state['BLW201_SP'] = 75.0
        elif scenario_name == 'chemical_overdose':
            if active:
                self.state['DOSE_FECL3_RATE'] = 9.5
                self.state['DOSE_FECL3_SP'] = 9.5
                # PMP501 stuck on
                self.state['PMP501_CMD'] = True
                self.state['PMP501_AUTO'] = False
            else:
                self.state['DOSE_FECL3_RATE'] = 2.5
                self.state['DOSE_FECL3_SP'] = 2.5
                self.state['PMP501_AUTO'] = True
