"""
Tag Generator - Generates realistic WWTP tags
Naming: WWTP01:<AREA>:<DEVICE><ID>.<ATTR>
"""

import logging
import numpy as np
from typing import Dict, Any

logger = logging.getLogger(__name__)

class TagGenerator:
    """Generates WWTP tags"""

    def __init__(self, deterministic=True, seed=42):
        self.deterministic = deterministic
        self.seed = seed
        if deterministic:
            self.rng = np.random.RandomState(seed)
        else:
            self.rng = np.random.RandomState()

    def generate_tags(self, count=200) -> Dict[str, Dict[str, Any]]:
        """Generate tags for small WWTP"""
        tags = {}

        core_tags = [
            # System
            ('WWTP01:SYSTEM:GLOBAL_MODE.PV', 'analog', '', 'Operating mode (0=AUTO, 1=MANUAL, 2=MAINTENANCE)'),
            ('WWTP01:SYSTEM:KILL_SWITCH.PV', 'digital', '', 'Emergency kill switch'),

            # Influent
            ('WWTP01:INFLUENT:Q_IN.PV', 'analog', 'm3/h', 'Influent flow rate'),
            ('WWTP01:INFLUENT:LT101.PV', 'analog', 'm', 'Wet well level - Last service: 15.3.2024'),
            ('WWTP01:INFLUENT:PMP101.CMD', 'digital', '', 'Pump 101 - command'),
            ('WWTP01:INFLUENT:PMP101.FB', 'digital', '', 'Pump 101 - feedback'),
            ('WWTP01:INFLUENT:PMP101.AUTO', 'digital', '', 'Pump 101 - auto mode'),
            ('WWTP01:INFLUENT:PMP101.RUNTIME', 'analog', 'h', 'Pump 101 runtime hours - Next service: 15000h'),
            ('WWTP01:INFLUENT:PMP101.FAULT', 'digital', '', 'Pump 101 fault'),
            ('WWTP01:INFLUENT:VLV101.POS', 'analog', '%', 'Inlet valve position'),
            ('WWTP01:INFLUENT:VLV101.CMD', 'analog', '%', 'Inlet valve command'),

            # Screening
            ('WWTP01:SCREENING:SCR101.DP', 'analog', 'bar', 'Screen differential pressure'),
            ('WWTP01:SCREENING:SCR101.CMD', 'digital', '', 'Screen auto-clean command'),
            ('WWTP01:SCREENING:SCR101.FB', 'digital', '', 'Screen auto-clean feedback'),
            ('WWTP01:SCREENING:SCR101.FAULT', 'digital', '', 'Screen fault'),
            ('WWTP01:SCREENING:SCR101.AUTO', 'digital', '', 'Screen auto mode'),

            # Grit/Grease
            ('WWTP01:GRIT:GRT201.LEVEL', 'analog', 'm', 'Grit chamber level'),
            ('WWTP01:GRIT:GRS201.SKIM', 'digital', '', 'Grease skimmer active'),

            # Primary Clarifier
            ('WWTP01:PRIMARY:LT301.PV', 'analog', 'm', 'Primary clarifier level'),
            ('WWTP01:PRIMARY:PMP301.CMD', 'digital', '', 'Primary pump 301 - command'),
            ('WWTP01:PRIMARY:PMP301.FB', 'digital', '', 'Primary pump 301 - feedback'),
            ('WWTP01:PRIMARY:PMP301.AUTO', 'digital', '', 'Primary pump 301 - auto mode'),
            ('WWTP01:PRIMARY:PMP301.FAULT', 'digital', '', 'Primary pump 301 fault'),
            ('WWTP01:PRIMARY:PMP301.RUNTIME', 'analog', 'h', 'Primary pump 301 runtime hours'),
            ('WWTP01:PRIMARY:COD_PRI.PV', 'analog', 'mg/L', 'COD after primary settling'),

            # Aeration
            ('WWTP01:AERATION:LT201.PV', 'analog', 'm', 'Aeration tank level'),
            ('WWTP01:AERATION:DO301.PV', 'analog', 'mg/L', 'Dissolved oxygen'),
            ('WWTP01:AERATION:DO301.SP', 'analog', 'mg/L', 'DO setpoint'),
            ('WWTP01:AERATION:pH302.PV', 'analog', '', 'pH value'),
            ('WWTP01:AERATION:TEMP303.PV', 'analog', '°C', 'Temperature'),
            ('WWTP01:AERATION:BLW201.CMD', 'digital', '', 'Blower 201 - command'),
            ('WWTP01:AERATION:BLW201.FB', 'digital', '', 'Blower 201 - feedback'),
            ('WWTP01:AERATION:BLW201.AUTO', 'digital', '', 'Blower 201 - auto mode'),
            ('WWTP01:AERATION:BLW201.SP', 'analog', '%', 'Blower speed setpoint'),
            ('WWTP01:AERATION:BLW201.PV', 'analog', '%', 'Blower actual speed'),
            ('WWTP01:AERATION:BLW201.FAULT', 'digital', '', 'Blower VFD fault'),
            ('WWTP01:AERATION:BLW201.RUNTIME', 'analog', 'h', 'Blower runtime hours'),
            ('WWTP01:AERATION:BLW201.CURRENT', 'analog', 'A', 'Blower current - Rated: 15A'),

            # Secondary Clarifier
            ('WWTP01:CLARIFIER:LT401.PV', 'analog', 'm', 'Secondary clarifier level'),
            ('WWTP01:CLARIFIER:TUR501.PV', 'analog', 'NTU', 'Effluent turbidity'),
            ('WWTP01:CLARIFIER:PMP401.CMD', 'digital', '', 'RAS pump 401 - command'),
            ('WWTP01:CLARIFIER:PMP401.FB', 'digital', '', 'RAS pump 401 - feedback'),
            ('WWTP01:CLARIFIER:PMP401.AUTO', 'digital', '', 'RAS pump 401 - auto mode'),
            ('WWTP01:CLARIFIER:PMP401.RUNTIME', 'analog', 'h', 'RAS pump runtime hours - Last maintenance: 20.1.2024'),
            ('WWTP01:CLARIFIER:PMP402.CMD', 'digital', '', 'WAS pump 402 - command'),
            ('WWTP01:CLARIFIER:PMP402.FB', 'digital', '', 'WAS pump 402 - feedback'),
            ('WWTP01:CLARIFIER:PMP402.AUTO', 'digital', '', 'WAS pump 402 - auto mode'),
            ('WWTP01:CLARIFIER:PMP402.RUNTIME', 'analog', 'h', 'WAS pump runtime hours - New pump installed: 10.8.2024'),

            # Chemical Dosing
            ('WWTP01:CHEMICAL:DOSE_FECL3.PV', 'analog', 'L/h', 'FeCl3 dosing rate'),
            ('WWTP01:CHEMICAL:DOSE_FECL3.SP', 'analog', 'L/h', 'FeCl3 dosing setpoint'),
            ('WWTP01:CHEMICAL:PMP501.CMD', 'digital', '', 'Chemical pump 501 - command'),
            ('WWTP01:CHEMICAL:PMP501.FB', 'digital', '', 'Chemical pump 501 - feedback'),
            ('WWTP01:CHEMICAL:PMP501.AUTO', 'digital', '', 'Chemical pump 501 - auto mode'),
            ('WWTP01:CHEMICAL:PMP501.RUNTIME', 'analog', 'h', 'Chemical pump 501 runtime hours'),
            ('WWTP01:CHEMICAL:TANK501.LEVEL', 'analog', '%', 'FeCl3 tank level'),
            ('WWTP01:CHEMICAL:DOSE_POLY.PV', 'analog', 'L/h', 'Polymer dosing rate'),
            ('WWTP01:CHEMICAL:VLV501.POS', 'analog', '%', 'Chemical valve position'),
            ('WWTP01:CHEMICAL:VLV501.CMD', 'analog', '%', 'Chemical valve command'),

            # Effluent
            ('WWTP01:EFFLUENT:Q_OUT.PV', 'analog', 'm3/h', 'Effluent flow rate'),
            ('WWTP01:EFFLUENT:pH501.PV', 'analog', '', 'Effluent pH'),
            ('WWTP01:EFFLUENT:COD501.PV', 'analog', 'mg/L', 'Effluent COD'),

            # Automation controllers
            ('WWTP01:AERATION:DO301.CTRL_EN', 'digital', '', 'DO controller - enabled'),
            ('WWTP01:AERATION:DO301.CTRL_MODE', 'digital', '', 'DO controller - mode (1=AUTO, 0=MANUAL)'),
            ('WWTP01:AERATION:DO301.CTRL_ACTIVE', 'digital', '', 'DO controller - active'),
            ('WWTP01:INFLUENT:LT101.CTRL_EN', 'digital', '', 'Level controller - enabled'),
            ('WWTP01:INFLUENT:LT101.CTRL_ACTIVE', 'digital', '', 'Level controller - active'),
        ]

        # Add core tags
        for tag_name, tag_type, unit, desc in core_tags:
            tags[tag_name] = {
                'type': tag_type,
                'unit': unit,
                'description': desc,
                'value': 0,
            }

        # Generate additional tags for realism
        areas = ['INFLUENT', 'SCREENING', 'GRIT', 'PRIMARY', 'AERATION',
                 'CLARIFIER', 'CHEMICAL', 'EFFLUENT', 'SLUDGE']
        devices = ['PMP', 'BLW', 'VALV', 'LT', 'FT', 'PT', 'TT', 'AT', 'DO', 'pH']

        generated_count = len(core_tags)
        device_id = 102

        while generated_count < count:
            area = self.rng.choice(areas)
            device = self.rng.choice(devices)
            attr = self.rng.choice(['PV', 'SP', 'CMD', 'FB', 'AUTO', 'FAULT', 'RUNTIME', 'CURRENT'])

            tag_name = f'WWTP01:{area}:{device}{device_id}.{attr}'

            if tag_name not in tags:
                tag_type = 'digital' if attr in ['CMD', 'FB', 'AUTO', 'FAULT'] else 'analog'
                unit = self._get_unit(device, attr)
                desc = f'{device} {device_id} {attr}'

                tags[tag_name] = {
                    'type': tag_type,
                    'unit': unit,
                    'description': desc,
                    'value': 0,
                }
                generated_count += 1
                device_id += 1
                if device_id > 999:
                    device_id = 102

        logger.info(f"Generated {len(tags)} tags")
        return tags

    def _get_unit(self, device: str, attr: str) -> str:
        """Get unit for device/attribute"""
        if attr in ['CMD', 'FB', 'AUTO', 'FAULT']:
            return ''
        if device == 'LT':
            return 'm'
        if device == 'FT':
            return 'm3/h'
        if device == 'PT':
            return 'bar'
        if device == 'TT':
            return '°C'
        if device == 'DO':
            return 'mg/L'
        if device == 'pH':
            return ''
        if device == 'PMP':
            if attr == 'CURRENT':
                return 'A'
            if attr == 'RUNTIME':
                return 'h'
        if device == 'BLW':
            if attr in ['SP', 'PV']:
                return '%'
            if attr == 'CURRENT':
                return 'A'
        return ''
