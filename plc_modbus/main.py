#!/usr/bin/env python3
"""
Modbus TCP Server - Maps to WWTP Simulator
"""

import os
import json
import time
import logging
import requests
from datetime import datetime
from pymodbus.server import StartTcpServer
from pymodbus.device import ModbusDeviceIdentification
from pymodbus.datastore import ModbusSlaveContext, ModbusServerContext
from pymodbus.datastore import ModbusSequentialDataBlock
from pymodbus.transaction import ModbusRtuFramer, ModbusSocketFramer

logging.basicConfig(
    level=os.getenv('LOG_LEVEL', 'INFO'),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

SIMULATOR_URL = os.getenv('SIMULATOR_URL', 'http://simulator:8080')

# Tag to Modbus mapping
TAG_MAPPING = {
    # Holding registers (analog PV/SP) - scaled by 10 or 100
    'WWTP01:INFLUENT:Q_IN.PV': {'type': 'holding', 'address': 1000, 'scale': 10},
    'WWTP01:INFLUENT:LT101.PV': {'type': 'holding', 'address': 1001, 'scale': 10},
    'WWTP01:AERATION:LT201.PV': {'type': 'holding', 'address': 1002, 'scale': 10},
    'WWTP01:AERATION:DO301.PV': {'type': 'holding', 'address': 1003, 'scale': 10},
    'WWTP01:AERATION:DO301.SP': {'type': 'holding', 'address': 1004, 'scale': 10},
    'WWTP01:AERATION:pH302.PV': {'type': 'holding', 'address': 1005, 'scale': 100},
    'WWTP01:AERATION:TEMP303.PV': {'type': 'holding', 'address': 1006, 'scale': 10},
    'WWTP01:AERATION:BLW201.SP': {'type': 'holding', 'address': 1007, 'scale': 10},
    'WWTP01:AERATION:BLW201.PV': {'type': 'holding', 'address': 1008, 'scale': 10},
    'WWTP01:CLARIFIER:LT401.PV': {'type': 'holding', 'address': 1009, 'scale': 10},
    'WWTP01:CLARIFIER:TUR501.PV': {'type': 'holding', 'address': 1010, 'scale': 10},
    'WWTP01:EFFLUENT:Q_OUT.PV': {'type': 'holding', 'address': 1011, 'scale': 10},
    'WWTP01:AERATION:BLW201.CURRENT': {'type': 'holding', 'address': 1012, 'scale': 10},
    'WWTP01:AERATION:BLW201.RUNTIME': {'type': 'holding', 'address': 1013, 'scale': 1},
    'WWTP01:INFLUENT:PMP101.RUNTIME': {'type': 'holding', 'address': 1014, 'scale': 1},
    'WWTP01:CLARIFIER:PMP401.RUNTIME': {'type': 'holding', 'address': 1015, 'scale': 1},
    'WWTP01:CLARIFIER:PMP402.RUNTIME': {'type': 'holding', 'address': 1016, 'scale': 1},
    'WWTP01:EFFLUENT:pH501.PV': {'type': 'holding', 'address': 1017, 'scale': 100},
    'WWTP01:EFFLUENT:COD501.PV': {'type': 'holding', 'address': 1018, 'scale': 10},
    # New holding registers
    'WWTP01:SCREENING:SCR101.DP': {'type': 'holding', 'address': 1019, 'scale': 100},
    'WWTP01:GRIT:GRT201.LEVEL': {'type': 'holding', 'address': 1020, 'scale': 10},
    'WWTP01:PRIMARY:LT301.PV': {'type': 'holding', 'address': 1021, 'scale': 10},
    'WWTP01:PRIMARY:PMP301.RUNTIME': {'type': 'holding', 'address': 1022, 'scale': 1},
    'WWTP01:CHEMICAL:DOSE_FECL3.PV': {'type': 'holding', 'address': 1023, 'scale': 10},
    'WWTP01:CHEMICAL:DOSE_FECL3.SP': {'type': 'holding', 'address': 1024, 'scale': 10},
    'WWTP01:CHEMICAL:TANK501.LEVEL': {'type': 'holding', 'address': 1025, 'scale': 10},
    'WWTP01:CHEMICAL:PMP501.RUNTIME': {'type': 'holding', 'address': 1026, 'scale': 1},
    'WWTP01:INFLUENT:VLV101.POS': {'type': 'holding', 'address': 1027, 'scale': 10},
    'WWTP01:CHEMICAL:VLV501.POS': {'type': 'holding', 'address': 1028, 'scale': 10},
    'WWTP01:PRIMARY:COD_PRI.PV': {'type': 'holding', 'address': 1029, 'scale': 10},
    'WWTP01:CHEMICAL:DOSE_POLY.PV': {'type': 'holding', 'address': 1030, 'scale': 10},
    'WWTP01:SYSTEM:GLOBAL_MODE.PV': {'type': 'holding', 'address': 1031, 'scale': 1},

    # Coils (CMD/AUTO)
    'WWTP01:INFLUENT:PMP101.CMD': {'type': 'coil', 'address': 2000},
    'WWTP01:INFLUENT:PMP101.AUTO': {'type': 'coil', 'address': 2001},
    'WWTP01:AERATION:BLW201.CMD': {'type': 'coil', 'address': 2002},
    'WWTP01:AERATION:BLW201.AUTO': {'type': 'coil', 'address': 2003},
    'WWTP01:CLARIFIER:PMP401.CMD': {'type': 'coil', 'address': 2004},
    'WWTP01:CLARIFIER:PMP401.AUTO': {'type': 'coil', 'address': 2005},
    'WWTP01:CLARIFIER:PMP402.CMD': {'type': 'coil', 'address': 2006},
    'WWTP01:CLARIFIER:PMP402.AUTO': {'type': 'coil', 'address': 2007},
    'WWTP01:AERATION:DO301.CTRL_EN': {'type': 'coil', 'address': 2008},
    'WWTP01:AERATION:DO301.CTRL_MODE': {'type': 'coil', 'address': 2009},
    # New coils
    'WWTP01:SCREENING:SCR101.CMD': {'type': 'coil', 'address': 2010},
    'WWTP01:SCREENING:SCR101.AUTO': {'type': 'coil', 'address': 2011},
    'WWTP01:PRIMARY:PMP301.CMD': {'type': 'coil', 'address': 2012},
    'WWTP01:PRIMARY:PMP301.AUTO': {'type': 'coil', 'address': 2013},
    'WWTP01:CHEMICAL:PMP501.CMD': {'type': 'coil', 'address': 2014},
    'WWTP01:CHEMICAL:PMP501.AUTO': {'type': 'coil', 'address': 2015},
    'WWTP01:SYSTEM:KILL_SWITCH.PV': {'type': 'coil', 'address': 2016},

    # Discrete inputs (FB/status/alarms - read-only)
    'WWTP01:INFLUENT:PMP101.FB': {'type': 'discrete', 'address': 3000},
    'WWTP01:INFLUENT:PMP101.FAULT': {'type': 'discrete', 'address': 3001},
    'WWTP01:AERATION:BLW201.FB': {'type': 'discrete', 'address': 3002},
    'WWTP01:AERATION:BLW201.FAULT': {'type': 'discrete', 'address': 3003},
    'WWTP01:CLARIFIER:PMP401.FB': {'type': 'discrete', 'address': 3004},
    'WWTP01:CLARIFIER:PMP402.FB': {'type': 'discrete', 'address': 3005},
    'WWTP01:AERATION:DO301.CTRL_ACTIVE': {'type': 'discrete', 'address': 3006},
    'WWTP01:INFLUENT:LT101.CTRL_ACTIVE': {'type': 'discrete', 'address': 3007},
    # New discrete inputs
    'WWTP01:SCREENING:SCR101.FB': {'type': 'discrete', 'address': 3008},
    'WWTP01:SCREENING:SCR101.FAULT': {'type': 'discrete', 'address': 3009},
    'WWTP01:PRIMARY:PMP301.FB': {'type': 'discrete', 'address': 3010},
    'WWTP01:PRIMARY:PMP301.FAULT': {'type': 'discrete', 'address': 3011},
    'WWTP01:CHEMICAL:PMP501.FB': {'type': 'discrete', 'address': 3012},
    'WWTP01:GRIT:GRS201.SKIM': {'type': 'discrete', 'address': 3013},
}

# Whitelist for write operations
WRITE_WHITELIST = {
    'WWTP01:INFLUENT:PMP101.CMD',
    'WWTP01:INFLUENT:PMP101.AUTO',
    'WWTP01:AERATION:BLW201.CMD',
    'WWTP01:AERATION:BLW201.AUTO',
    'WWTP01:AERATION:BLW201.SP',
    'WWTP01:AERATION:DO301.SP',
    'WWTP01:AERATION:DO301.CTRL_EN',
    'WWTP01:AERATION:DO301.CTRL_MODE',
    'WWTP01:CLARIFIER:PMP401.CMD',
    'WWTP01:CLARIFIER:PMP401.AUTO',
    'WWTP01:CLARIFIER:PMP402.CMD',
    'WWTP01:CLARIFIER:PMP402.AUTO',
    'WWTP01:SCREENING:SCR101.CMD',
    'WWTP01:SCREENING:SCR101.AUTO',
    'WWTP01:PRIMARY:PMP301.CMD',
    'WWTP01:PRIMARY:PMP301.AUTO',
    'WWTP01:CHEMICAL:PMP501.CMD',
    'WWTP01:CHEMICAL:PMP501.AUTO',
    'WWTP01:CHEMICAL:DOSE_FECL3.SP',
    'WWTP01:INFLUENT:VLV101.CMD',
    'WWTP01:CHEMICAL:VLV501.CMD',
    'WWTP01:SYSTEM:GLOBAL_MODE.PV',
    'WWTP01:SYSTEM:KILL_SWITCH.PV',
}

def log_modbus_operation(fc, address, count, values=None, src_ip='unknown', result='success'):
    """Log Modbus operation"""
    log_entry = {
        'timestamp': datetime.utcnow().isoformat(),
        'src_ip': src_ip,
        'function_code': fc,
        'address': address,
        'count': count,
        'values': values,
        'result': result,
    }

    log_dir = "/data/logs"
    os.makedirs(log_dir, exist_ok=True)
    log_file = f"{log_dir}/modbus_{datetime.utcnow().strftime('%Y%m%d')}.jsonl"
    try:
        with open(log_file, 'a') as f:
            f.write(json.dumps(log_entry) + '\n')
    except Exception as e:
        logger.error(f"Failed to write log: {e}")

def get_simulator_snapshot():
    """Get snapshot from simulator"""
    try:
        response = requests.get(f"{SIMULATOR_URL}/api/snapshot", timeout=2)
        if response.status_code == 200:
            return response.json()
    except Exception as e:
        logger.error(f"Failed to get snapshot: {e}")
    return {}

def write_to_simulator(tag, value):
    """Write to simulator"""
    try:
        response = requests.post(
            f"{SIMULATOR_URL}/api/write",
            json={'tag': tag, 'value': value},
            timeout=2
        )
        return response.status_code == 200
    except Exception as e:
        logger.error(f"Failed to write to simulator: {e}")
        return False

def find_tag_by_address(fc, address):
    """Find tag by Modbus address"""
    for tag, mapping in TAG_MAPPING.items():
        if mapping['address'] == address:
            if fc in [1, 5, 15] and mapping['type'] == 'coil':
                return tag, mapping
            if fc == 2 and mapping['type'] == 'discrete':
                return tag, mapping
            if fc in [3, 6, 16] and mapping['type'] == 'holding':
                return tag, mapping
            if fc == 4 and mapping['type'] == 'input':
                return tag, mapping
    return None, None

class CustomDataBlock(ModbusSequentialDataBlock):
    """Custom data block that syncs with simulator"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.last_sync = 0

    def sync_from_simulator(self):
        """Sync data from simulator"""
        current_time = time.time()
        if current_time - self.last_sync < 1.0:
            return
        self.last_sync = current_time

        # Add 5-15ms jitter
        import random
        jitter = random.uniform(0.005, 0.015)
        time.sleep(jitter)

        snapshot = get_simulator_snapshot()

        for tag, mapping in TAG_MAPPING.items():
            if tag not in snapshot:
                continue

            value = snapshot[tag]['value']
            addr = mapping['address']

            if mapping['type'] == 'holding':
                scale = mapping.get('scale', 1)
                scaled_value = int(value * scale)
                self.setValues(addr, [scaled_value])
            elif mapping['type'] == 'coil':
                self.setValues(addr, [1 if value else 0])
            elif mapping['type'] == 'discrete':
                self.setValues(addr, [1 if value else 0])

def run_modbus_server():
    """Run Modbus TCP server"""
    import threading

    # Initialize data blocks
    coils = CustomDataBlock(0, [0] * 10000)
    discrete_inputs = CustomDataBlock(0, [0] * 10000)
    holding_registers = CustomDataBlock(0, [0] * 10000)
    input_registers = ModbusSequentialDataBlock(0, [0] * 10000)

    slave_context = ModbusSlaveContext(
        di=discrete_inputs,
        co=coils,
        hr=holding_registers,
        ir=input_registers
    )

    context = ModbusServerContext(slaves=slave_context, single=True)

    # Sync thread
    def sync_loop():
        while True:
            try:
                coils.sync_from_simulator()
                discrete_inputs.sync_from_simulator()
                holding_registers.sync_from_simulator()
            except Exception as e:
                logger.error(f"Sync error: {e}")
            time.sleep(1.0)

    sync_thread = threading.Thread(target=sync_loop, daemon=True)
    sync_thread.start()

    # Device identification
    identity = ModbusDeviceIdentification()
    identity.VendorName = 'AquaTech Control Systems s.r.o.'
    identity.ProductCode = 'ATC-PLC-2000'
    identity.VendorUrl = 'http://www.aquatech-control.cz'
    identity.ProductName = 'WWTP PLC Controller'
    identity.ModelName = 'PLC-2000'
    identity.MajorMinorRevision = '3.0.0'

    # Custom server callback for logging
    def server_callback(slave_id, function_code, address, values):
        """Callback for logging"""
        src_ip = 'unknown'
        fc = function_code

        if fc in [5, 6, 15, 16]:  # Write operations
            tag, mapping = find_tag_by_address(fc, address)

            if tag and tag in WRITE_WHITELIST:
                if mapping and mapping['type'] == 'holding':
                    scale = mapping.get('scale', 1)
                    value = values[0] / scale if values else 0
                else:
                    value = bool(values[0]) if values else False

                write_to_simulator(tag, value)
                log_modbus_operation(fc, address, len(values), values, src_ip, 'write_success')
            elif tag:
                log_modbus_operation(fc, address, len(values), values, src_ip, 'denied_not_whitelisted')
            else:
                log_modbus_operation(fc, address, len(values), values, src_ip, 'error_tag_not_found')
        else:
            log_modbus_operation(fc, address, len(values) if values else 1, None, src_ip, 'read')

    # Start server
    logger.info("Starting Modbus TCP server on port 502")
    try:
        StartTcpServer(
            context=context,
            identity=identity,
            address=("0.0.0.0", 502),
            framer=ModbusSocketFramer,
        )
    except KeyboardInterrupt:
        logger.info("Modbus server stopped")

if __name__ == '__main__':
    run_modbus_server()
