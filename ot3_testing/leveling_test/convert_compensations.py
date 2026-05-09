#!/usr/bin/env python3
"""
Compensation Data Converter

This script reads compensation data from Templete.xlsx, 
updates the leveling_config.json, and shows differences.
"""

import os
import json
import shutil
import datetime
import re
from typing import Dict, Any, Tuple, Optional

try:
    import pandas as pd
except ImportError:
    raise ImportError("Please install pandas: pip install pandas openpyxl")


def load_json_config(filepath: str) -> Dict[str, Any]:
    """Load JSON configuration file"""
    with open(filepath, 'r', encoding='utf-8') as f:
        return json.load(f)


def save_json_config(filepath: str, data: Dict[str, Any]):
    """Save JSON configuration file with pretty indentation"""
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4, ensure_ascii=False)


def backup_file(src_path: str) -> str:
    """Create a backup of the file with timestamp"""
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = f"{src_path}.backup_{timestamp}"
    shutil.copy2(src_path, backup_path)
    print(f"Created backup: {backup_path}")
    return backup_path


def parse_position_name(name: str) -> Tuple[str, str, str, str, str]:
    """
    Parse position name like 'zstage_left-z-c2-rear'
    
    Returns: (test_type, mount, direction, slot, field)
    """
    name = str(name).strip().lower()
    
    # Pattern 1: zstage_left-z-c2-rear
    pattern1 = r'^(\w+)_(\w+)-(\w)-(\w+)-(\w+)$'
    match = re.match(pattern1, name)
    if match:
        return match.groups()
    
    # Pattern 2: ch8_left-y-c1-rear
    pattern2 = r'^(\w+)_(\w+)-(\w)-(\w+)-(\w+)$'
    match = re.match(pattern2, name)
    if match:
        return match.groups()
    
    # Pattern 3: ch96_c1-y-rear
    pattern3 = r'^(\w+)_(\w+)-(\w)-(\w+)$'
    match = re.match(pattern3, name)
    if match:
        test_type, slot, direction, field = match.groups()
        return (test_type, 'left', direction, slot, field)
    
    # Pattern 4: ch96_d1-z-rear_left
    pattern4 = r'^(\w+)_(\w+)-(\w)-(\w+_\w+)$'
    match = re.match(pattern4, name)
    if match:
        test_type, slot, direction, field = match.groups()
        return (test_type, 'left', direction, slot, field)
    
    return (None, None, None, None, None)


def normalize_compensation_field(field: str, direction: str, mount: str) -> str:
    """Normalize compensation field names based on direction and mount"""
    field = field.lower()
    mount = mount.lower()
    
    if direction.lower() == 'x':
        if field in ['left', 'rear_left']:
            return 'rear_left'
        elif field in ['right', 'rear_right']:
            return 'rear_right'
        return field
    
    elif direction.lower() == 'y':
        if mount == 'left':
            if 'rear' in field:
                return 'left_rear'
            elif 'front' in field:
                return 'left_front'
            elif field == 'rear':
                return 'left_rear'
            elif field == 'front':
                return 'left_front'
        else:
            if 'rear' in field:
                return 'right_rear'
            elif 'front' in field:
                return 'right_front'
            elif field == 'rear':
                return 'right_rear'
            elif field == 'front':
                return 'right_front'
        return field
    
    elif direction.lower() == 'z':
        if field == 'rear_left':
            return 'below_rear_left'
        elif field == 'rear_right':
            return 'below_rear_right'
        elif field == 'front_left':
            return 'below_front_left'
        elif field == 'front_right':
            return 'below_front_right'
        elif field == 'rear':
            return 'rear'
        elif field == 'front':
            return 'front'
        return field
    
    return field


def read_excel_compensations(excel_path: str) -> Dict[str, Dict[str, Dict[str, Dict[str, float]]]]:
    """
    Read compensation data from Templete.xlsx
    
    Returns:
        Dictionary with structure:
        {
            "config_key": {
                "slot_location_key": {
                    "position_key": {"compensation_field": value, ...}
                }
            }
        }
    """
    compensations = {
        'pipette_leveling_config': {},
        'zstage_leveling_config': {}
    }
    
    try:
        df = pd.read_excel(excel_path, engine='openpyxl', header=None)
        
        print(f"Excel shape: {df.shape}")
        print(f"\n=== Excel 内容预览 ===")
        print(df.to_string())
        
        for row_idx in range(df.shape[0]):
            for col_idx in range(0, df.shape[1], 2):
                if col_idx + 1 >= df.shape[1]:
                    break
                
                position_name = df.iloc[row_idx, col_idx]
                compensation_value = df.iloc[row_idx, col_idx + 1]
                
                if pd.isna(position_name) or str(position_name).strip() == '':
                    continue
                
                if pd.isna(compensation_value):
                    continue
                
                try:
                    value = float(compensation_value)
                except (ValueError, TypeError):
                    continue
                
                test_type, mount, direction, slot, field = parse_position_name(position_name)
                
                if None in (test_type, mount, direction, slot, field):
                    print(f"Warning: Could not parse position name: {position_name}")
                    continue
                
                slot_name = slot.upper()
                final_field = normalize_compensation_field(field, direction, mount)
                
                if test_type == 'zstage':
                    config_key = 'zstage_leveling_config'
                    slot_location_key = 'ZStagePoint'
                    position_key = mount
                    inner_key = f"Z-{slot_name}"
                    
                    if slot_location_key not in compensations[config_key]:
                        compensations[config_key][slot_location_key] = {}
                    if position_key not in compensations[config_key][slot_location_key]:
                        compensations[config_key][slot_location_key][position_key] = {}
                    if inner_key not in compensations[config_key][slot_location_key][position_key]:
                        compensations[config_key][slot_location_key][position_key][inner_key] = {}
                    compensations[config_key][slot_location_key][position_key][inner_key][final_field] = value
                    
                elif test_type == 'ch8':
                    config_key = 'pipette_leveling_config'
                    slot_location_key = 'SlotLocationCH8'
                    position_key = f"Y-{slot_name}-{mount.capitalize()}"
                    
                    if slot_location_key not in compensations[config_key]:
                        compensations[config_key][slot_location_key] = {}
                    if position_key not in compensations[config_key][slot_location_key]:
                        compensations[config_key][slot_location_key][position_key] = {}
                    compensations[config_key][slot_location_key][position_key][final_field] = value
                
                elif test_type == 'ch96':
                    config_key = 'pipette_leveling_config'
                    slot_location_key = 'SlotLocationCH96'
                    position_key = f"{slot_name}-{direction.upper()}"
                    
                    if slot_location_key not in compensations[config_key]:
                        compensations[config_key][slot_location_key] = {}
                    if position_key not in compensations[config_key][slot_location_key]:
                        compensations[config_key][slot_location_key][position_key] = {}
                    compensations[config_key][slot_location_key][position_key][final_field] = value
        
        print(f"\n=== 解析结果 ===")
        for config_key, slots in compensations.items():
            if slots:
                print(f"{config_key}:")
                for slot_key, positions in slots.items():
                    print(f"  {slot_key}: {positions}")
        
        return compensations
    
    except Exception as e:
        print(f"Error reading Excel file: {e}")
        import traceback
        traceback.print_exc()
        return {}


def find_and_update_compensation(config: Dict[str, Any], 
                                 excel_compensations: Dict[str, Dict[str, Dict[str, float]]]) -> Dict[str, Dict[str, Any]]:
    """
    Update compensation data in config with data from Excel
    
    Returns:
        Dictionary of changes made
    """
    changes = {}
    
    for config_key, slot_locations in excel_compensations.items():
        if config_key not in config:
            print(f"Warning: Config key '{config_key}' not found in config")
            continue
        
        parent_config = config[config_key]
        
        for slot_location_key, positions in slot_locations.items():
            if slot_location_key not in parent_config:
                print(f"Warning: Slot location '{slot_location_key}' not found in {config_key}")
                continue
            
            slot_data = parent_config[slot_location_key]
            
            if config_key == 'zstage_leveling_config' and slot_location_key == 'ZStagePoint':
                for mount_key, inner_positions in positions.items():
                    if mount_key not in slot_data:
                        print(f"Warning: Mount '{mount_key}' not found in {config_key}.{slot_location_key}")
                        continue
                    
                    mount_data = slot_data[mount_key]
                    
                    for position_key, new_compensation in inner_positions.items():
                        if position_key not in mount_data:
                            print(f"Warning: Position '{position_key}' not found in {config_key}.{slot_location_key}.{mount_key}")
                            continue
                        
                        position_data = mount_data[position_key]
                        
                        if 'compensation' not in position_data:
                            print(f"Warning: No compensation field in {config_key}.{slot_location_key}.{mount_key}.{position_key}")
                            continue
                        
                        old_compensation = position_data['compensation']
                        
                        if old_compensation != new_compensation:
                            full_key = f"{config_key}.{slot_location_key}.{mount_key}.{position_key}"
                            changes[full_key] = {
                                'old': old_compensation.copy(),
                                'new': new_compensation.copy()
                            }
                            position_data['compensation'] = new_compensation
            else:
                for position_key, new_compensation in positions.items():
                    if position_key not in slot_data:
                        print(f"Warning: Position '{position_key}' not found in {config_key}.{slot_location_key}")
                        continue
                    
                    position_data = slot_data[position_key]
                    
                    if 'compensation' not in position_data:
                        print(f"Warning: No compensation field in {config_key}.{slot_location_key}.{position_key}")
                        continue
                    
                    old_compensation = position_data['compensation']
                    
                    if old_compensation != new_compensation:
                        full_key = f"{config_key}.{slot_location_key}.{position_key}"
                        changes[full_key] = {
                            'old': old_compensation.copy(),
                            'new': new_compensation.copy()
                        }
                        position_data['compensation'] = new_compensation
    
    return changes


def print_changes(changes: Dict[str, Dict[str, Any]]):
    """Print the differences between old and new compensation data"""
    if not changes:
        print("\nNo changes found - compensation data is the same.")
        return
    
    print("\n" + "="*80)
    print("COMPENSATION DATA CHANGES")
    print("="*80)
    
    for key, values in changes.items():
        old = values['old']
        new = values['new']
        
        print(f"\n{key}:")
        print(f"  Old compensation: {old}")
        print(f"  New compensation: {new}")
        
        all_keys = set(old.keys()) | set(new.keys())
        for field in all_keys:
            old_val = old.get(field, None)
            new_val = new.get(field, None)
            if old_val != new_val:
                diff = None
                if old_val is not None and new_val is not None:
                    diff = round(new_val - old_val, 6)
                print(f"    {field}: {old_val} -> {new_val} (diff: {diff})")


def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    config_path = os.path.join(script_dir, 'leveling_config.json')
    excel_path = os.path.join(script_dir, 'Templete.xlsx')
    
    if not os.path.exists(config_path):
        print(f"Error: Config file not found - {config_path}")
        return
    
    if not os.path.exists(excel_path):
        print(f"Error: Excel file not found - {excel_path}")
        return
    
    print(f"Loading config from: {config_path}")
    config = load_json_config(config_path)
    
    backup_path = backup_file(config_path)
    
    print(f"\nReading Excel from: {excel_path}")
    excel_compensations = read_excel_compensations(excel_path)
    
    if not excel_compensations or all(not v for v in excel_compensations.values()):
        print("No compensation data found in Excel")
        return
    
    print("\n" + "="*80)
    print("Updating compensation data...")
    print("="*80)
    changes = find_and_update_compensation(config, excel_compensations)
    
    save_json_config(config_path, config)
    print(f"\nUpdated config saved to: {config_path}")
    
    print_changes(changes)
    
    print("\n" + "="*80)
    print("Conversion completed!")
    print("="*80)
    print(f"\nBackup file: {backup_path}")


if __name__ == '__main__':
    main()
