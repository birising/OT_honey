#!/usr/bin/env python3
"""
SNMP Agent - Read-only SNMP agent for WWTP
Simplified implementation - basic SNMP v2c responder
"""

import os
import json
import time
import logging
import socket
import struct
from datetime import datetime

logging.basicConfig(
    level=os.getenv('LOG_LEVEL', 'INFO'),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

SNMP_PORT = int(os.getenv('SNMP_PORT', '161'))

START_TIME = time.time()

# Fiktivní čistička odpadních vod
WWTP_NAME = "ČOV Belokluky"
WWTP_LOCATION = "Belokluky"
WWTP_OPERATOR = "Vodohospodářská společnost Východní Čechy, a.s."
WWTP_ADDRESS = "Čistírna odpadních vod, Belokluky"
WWTP_CONTACT = "provoz@vsch.cz"
WWTP_SYSTEM_NAME = "BEL-CZ-01"

# SNMP OID values (simplified - basic responses)
SNMP_VALUES = {
    '1.3.6.1.2.1.1.1.0': ('OctetString', f'ČOV Control System v2.1 - {WWTP_NAME} (kapacita 4.5k EO)'),
    '1.3.6.1.2.1.1.2.0': ('ObjectIdentifier', '1.3.6.1.4.1.9999.1.1'),
    '1.3.6.1.2.1.1.3.0': ('TimeTicks', lambda: int((time.time() - START_TIME) * 100)),
    '1.3.6.1.2.1.1.4.0': ('OctetString', WWTP_CONTACT),
    '1.3.6.1.2.1.1.5.0': ('OctetString', WWTP_SYSTEM_NAME),
    '1.3.6.1.2.1.1.6.0': ('OctetString', WWTP_ADDRESS),
    '1.3.6.1.2.1.1.7.0': ('Integer', 72),  # sysServices
    '1.3.6.1.4.1.9999.1.1.1.0': ('Integer', 28),  # Cabinet temp
    '1.3.6.1.4.1.9999.1.1.2.0': ('Integer', 1),  # UPS status
    '1.3.6.1.4.1.9999.1.1.3.0': ('Integer', 45),  # CPU load
}

def log_snmp_query(oid, src_ip, result='success'):
    """Log SNMP query"""
    log_entry = {
        'timestamp': datetime.utcnow().isoformat(),
        'src_ip': src_ip,
        'oid': str(oid),
        'result': result,
    }
    
    log_dir = "/data/logs"
    os.makedirs(log_dir, exist_ok=True)
    log_file = f"{log_dir}/snmp_{datetime.utcnow().strftime('%Y%m%d')}.jsonl"
    try:
        with open(log_file, 'a') as f:
            f.write(json.dumps(log_entry) + '\n')
    except Exception as e:
        logger.error(f"Failed to write log: {e}")

def get_snmp_value(oid_str):
    """Get SNMP value for OID"""
    if oid_str in SNMP_VALUES:
        value = SNMP_VALUES[oid_str]
        if callable(value):
            return value()
        return value
    return None

def encode_oid(oid_str):
    """Encode OID string to ASN.1 BER format"""
    parts = [int(x) for x in oid_str.split('.')]
    encoded = bytearray()
    
    # First two sub-identifiers encoded together
    if len(parts) >= 2:
        first = parts[0] * 40 + parts[1]
        encoded.append(first)
    
    # Remaining sub-identifiers
    for part in parts[2:]:
        if part < 128:
            encoded.append(part)
        else:
            # Multi-byte encoding
            bytes_needed = []
            val = part
            while val > 0:
                bytes_needed.insert(0, val & 0x7F)
                val >>= 7
            for i, byte_val in enumerate(bytes_needed):
                if i < len(bytes_needed) - 1:
                    encoded.append(byte_val | 0x80)
                else:
                    encoded.append(byte_val)
    
    return bytes(encoded)

def encode_value(value_type, value):
    """Encode SNMP value to ASN.1 BER format"""
    if value_type == 'OctetString':
        val_bytes = value.encode('utf-8') if isinstance(value, str) else value
        length = len(val_bytes)
        if length < 128:
            return struct.pack('BB', 0x04, length) + val_bytes
        else:
            length_bytes = struct.pack('B', length)
            return struct.pack('B', 0x04 | 0x80) + struct.pack('B', len(length_bytes)) + length_bytes + val_bytes
    elif value_type == 'Integer':
        # Simple integer encoding (for small values)
        if value < 128:
            return struct.pack('BB', 0x02, 1) + struct.pack('B', value)
        elif value < 256:
            return struct.pack('BB', 0x02, 2) + struct.pack('>H', value)
        else:
            return struct.pack('BB', 0x02, 4) + struct.pack('>I', value)
    elif value_type == 'TimeTicks':
        # TimeTicks as unsigned integer
        val_bytes = struct.pack('>I', value)
        return struct.pack('BB', 0x43, 4) + val_bytes
    elif value_type == 'ObjectIdentifier':
        oid_encoded = encode_oid(value)
        length = len(oid_encoded)
        return struct.pack('BB', 0x06, length) + oid_encoded
    return b''

def build_snmp_response(request_data, community='public_ro'):
    """Build SNMP v2c GET response"""
    try:
        # Very basic SNMP v2c response
        # This is a simplified implementation - for full SNMP, use pysnmp
        
        # Parse request (simplified - just check for GET request)
        if len(request_data) < 20:
            return None
        
        # Build response header
        response = bytearray()
        
        # SNMP Message (SEQUENCE)
        response.append(0x30)  # SEQUENCE
        msg_length_pos = len(response)
        response.append(0)  # Placeholder for length
        
        # Version (INTEGER 1 = v2c)
        response.extend([0x02, 0x01, 0x01])
        
        # Community (OCTET STRING)
        comm_bytes = community.encode('ascii')
        response.append(0x04)  # OCTET STRING
        response.append(len(comm_bytes))
        response.extend(comm_bytes)
        
        # PDU (GET Response)
        response.append(0xA2)  # GET Response PDU
        pdu_length_pos = len(response)
        response.append(0)  # Placeholder
        
        # Request ID (copy from request or use 1)
        response.extend([0x02, 0x01, 0x01])
        
        # Error Status (noError)
        response.extend([0x02, 0x01, 0x00])
        
        # Error Index
        response.extend([0x02, 0x01, 0x00])
        
        # VarBindList
        response.append(0x30)  # SEQUENCE
        varbind_length_pos = len(response)
        response.append(0)  # Placeholder
        
        # VarBind (simplified - return sysDescr)
        response.append(0x30)  # SEQUENCE
        varbind_item_length_pos = len(response)
        response.append(0)  # Placeholder
        
        # OID (1.3.6.1.2.1.1.1.0)
        oid_encoded = encode_oid('1.3.6.1.2.1.1.1.0')
        response.append(0x06)  # OBJECT IDENTIFIER
        response.append(len(oid_encoded))
        response.extend(oid_encoded)
        
        # Value (sysDescr)
        value = get_snmp_value('1.3.6.1.2.1.1.1.0')
        if value:
            val_type, val_data = value
            val_encoded = encode_value(val_type, val_data)
            response.extend(val_encoded)
        
        # Update lengths
        varbind_item_length = len(response) - varbind_item_length_pos - 1
        response[varbind_item_length_pos] = varbind_item_length
        
        varbind_length = len(response) - varbind_length_pos - 1
        response[varbind_length_pos] = varbind_length
        
        pdu_length = len(response) - pdu_length_pos - 1
        response[pdu_length_pos] = pdu_length
        
        msg_length = len(response) - msg_length_pos - 1
        response[msg_length_pos] = msg_length
        
        return bytes(response)
    except Exception as e:
        logger.error(f"Error building SNMP response: {e}")
        return None

def run_simple_snmp_server():
    """Simple SNMP v2c server using raw UDP sockets"""
    logger.info(f"Starting SNMP agent on port {SNMP_PORT}/udp")
    logger.info("Community string: public_ro (read-only)")
    logger.info("Note: This is a simplified SNMP responder - logs all queries")
    
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    
    try:
        sock.bind(('0.0.0.0', SNMP_PORT))
    except OSError as e:
        if e.errno == 98:  # Address already in use
            logger.warning(f"Port {SNMP_PORT} already in use, waiting...")
            time.sleep(5)
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                sock.bind(('0.0.0.0', SNMP_PORT))
                logger.info("Successfully bound to port after retry")
            except Exception as e2:
                logger.error(f"Failed to bind after retry: {e2}")
                return
        else:
            logger.error(f"Socket error: {e}")
            return
    
    logger.info("SNMP server listening...")
    
    while True:
        try:
            data, addr = sock.recvfrom(1024)
            src_ip = addr[0]
            
            # Log query
            log_snmp_query('query_received', src_ip, 'received')
            logger.info(f"SNMP query from {src_ip}: {len(data)} bytes")
            
            # Try to build response (simplified)
            # For honeypot purposes, just logging is often enough
            # But we'll try to send a basic response
            response = build_snmp_response(data)
            if response:
                sock.sendto(response, addr)
                logger.debug(f"Sent SNMP response to {src_ip}")
            else:
                logger.debug(f"Could not build response for {src_ip}")
                
        except Exception as e:
            logger.error(f"SNMP server error: {e}")
            time.sleep(1)

if __name__ == '__main__':
    run_simple_snmp_server()
