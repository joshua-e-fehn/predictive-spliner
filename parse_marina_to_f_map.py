#!/usr/bin/env python3
"""
Parser to convert Marina map CSV format to F1Tenth Race Stack format.

This script converts the Marina raceline CSV data into the F1Tenth race stack 
map format, specifically generating the global_waypoints.json file and 
configuration files for the "marina" map.

Author: Assistant
Date: 2025
"""

import json
import math
import os
import shutil
import yaml
from typing import Dict, List, Any
import argparse
import math

class MarinaMapParser:
    def __init__(self, csv_file: str, output_map_name: str = "marina"):
        """
        Initialize the Marina map parser.
        
        Args:
            csv_file: Path to the Marina CSV file
            output_map_name: Name for the output map directory
        """
        self.csv_file = csv_file
        self.output_map_name = output_map_name
        
        # Define column mapping based on CSV header analysis
        # Marina CSV columns: x_rl_m, y_rl_m, z_rl_m, v_rl_mps, n_rl_m, chi_rl_rad, ax_rl_mps2, ay_rl_mps2, jx_rl_mps3, jy_rl_mps3, tire_util_rl, s_ref_rl_m, x_ref_rl_m, y_ref_rl_m, z_ref_rl_m, theta_ref_rl_rad, mu_ref_rl_rad, phi_ref_rl_rad, dtheta_ref_rl_radpm, dmu_ref_rl_radpm, dphi_ref_rl_radpm, w_tr_right_ref_rl_m, w_tr_left_ref_rl_m, omega_x_ref_rl_radpm, omega_y_ref_rl_radpm, omega_z_ref_rl_radpm, s_ref_cl_m, x_ref_cl_m, y_ref_cl_m, z_ref_cl_m, theta_ref_cl_rad, mu_ref_cl_rad, phi_ref_cl_rad, dtheta_ref_cl_radpm, dmu_ref_cl_radpm, dphi_ref_cl_radpm, w_tr_right_ref_cl_m, w_tr_left_ref_cl_m, omega_x_ref_cl_radpm, omega_y_ref_cl_radpm, omega_z_ref_cl_radpm, tb_left_x_ref_rl_m, tb_left_y_ref_rl_m, tb_left_z_ref_rl_m, tb_right_x_ref_rl_m, tb_right_y_ref_rl_m, tb_right_z_ref_rl_m
        # Column mapping for Marina CSV format - corrected based on actual data structure
        self.column_mapping = {
            # Raw racing line data (most aggressive - use for IQP)
            'rl_x_m': 0,        # x_rl_m
            'rl_y_m': 1,        # y_rl_m
            'rl_vx_mps': 3,     # v_rl_mps
            'rl_psi_rad': 5,    # chi_rl_rad
            'rl_ax_mps2': 6,    # ax_rl_mps2
            'rl_n_m': 4,        # n_rl_m (lateral offset)
            
            # Reference racing line data (refined - use for SP)
            'ref_rl_s_m': 11,       # s_ref_rl_m
            'ref_rl_x_m': 12,       # x_ref_rl_m
            'ref_rl_y_m': 13,       # y_ref_rl_m
            'ref_rl_psi_rad': 15,   # theta_ref_rl_rad
            'ref_rl_kappa_radpm': 18, # dtheta_ref_rl_radpm (curvature)
            'ref_rl_d_right': 21,   # w_tr_right_ref_rl_m
            'ref_rl_d_left': 22,    # w_tr_left_ref_rl_m
            
            # Reference centerline data (conservative - use for centerline)
            'ref_cl_s_m': 26,       # s_ref_cl_m
            'ref_cl_x_m': 27,       # x_ref_cl_m
            'ref_cl_y_m': 28,       # y_ref_cl_m
            'ref_cl_psi_rad': 30,   # theta_ref_cl_rad
            'ref_cl_kappa_radpm': 33, # dtheta_ref_cl_radpm
            'ref_cl_d_right': 36,   # w_tr_right_ref_cl_m
            'ref_cl_d_left': 37,    # w_tr_left_ref_cl_m
            
            # Track boundary data
            'tb_left_x': 41,        # tb_left_x_ref_rl_m
            'tb_left_y': 42,        # tb_left_y_ref_rl_m
            'tb_right_x': 44,       # tb_right_x_ref_rl_m
            'tb_right_y': 45,       # tb_right_y_ref_rl_m
        }
        
    def load_marina_csv(self) -> Dict[str, List[Dict]]:
        """Load and parse the Marina CSV file into different trajectory types."""
        print(f"Loading Marina CSV: {self.csv_file}")
        
        # Read CSV, skip header lines (comments start with #)
        data_lines = []
        with open(self.csv_file, 'r') as f:
            for line_num, line in enumerate(f):
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                # Skip empty or nan-only lines
                if line.startswith('nan') or not any(c.isdigit() for c in line):
                    continue
                data_lines.append(line)
        
        print(f"Found {len(data_lines)} data lines")
        
        # Parse the CSV data into different trajectory types
        centerline_waypoints = []
        iqp_waypoints = []
        sp_waypoints = []
        
        for i, line in enumerate(data_lines):
            try:
                # Split by comma and clean values
                values = [v.strip() for v in line.split(',')]
                
                # Create centerline waypoints (conservative, based on track centerline)
                cl_waypoint = self.create_centerline_waypoint(values, len(centerline_waypoints))
                centerline_waypoints.append(cl_waypoint)
                
                # Create IQP waypoints (aggressive racing line)
                iqp_waypoint = self.create_iqp_waypoint(values, len(iqp_waypoints))
                iqp_waypoints.append(iqp_waypoint)
                
                # Create SP waypoints (moderate racing line)
                sp_waypoint = self.create_sp_waypoint(values, len(sp_waypoints))
                sp_waypoints.append(sp_waypoint)
                
            except (ValueError, IndexError) as e:
                print(f"Warning: Could not parse line {i}: {e}")
                continue
                
        print(f"Successfully parsed {len(centerline_waypoints)} waypoints for each trajectory type")
        return {
            'centerline': centerline_waypoints,
            'iqp': iqp_waypoints,
            'sp': sp_waypoints
        }
        
    def create_centerline_waypoint(self, values: List[str], waypoint_id: int) -> Dict:
        """Create a centerline waypoint using reference centerline data."""
        # Use reference centerline data (most conservative)
        x_m = float(values[self.column_mapping['ref_cl_x_m']])
        y_m = float(values[self.column_mapping['ref_cl_y_m']])
        s_m = float(values[self.column_mapping['ref_cl_s_m']])
        psi_rad = float(values[self.column_mapping['ref_cl_psi_rad']])
        kappa_radpm = float(values[self.column_mapping['ref_cl_kappa_radpm']])
        d_right = float(values[self.column_mapping['ref_cl_d_right']])
        d_left = float(values[self.column_mapping['ref_cl_d_left']])
        
        # Conservative speed and acceleration (use raw racing line but reduce significantly)
        rl_vx_mps = float(values[self.column_mapping['rl_vx_mps']])
        rl_ax_mps2 = float(values[self.column_mapping['rl_ax_mps2']])
        
        vx_mps = rl_vx_mps * 0.7  # 30% speed reduction for safety
        ax_mps2 = rl_ax_mps2 * 0.5  # 50% acceleration reduction
        
        return {
            'id': waypoint_id,
            's_m': s_m,
            'd_m': 0.0,
            'x_m': x_m,
            'y_m': y_m,
            'd_right': d_right,
            'd_left': d_left,
            'psi_rad': psi_rad,
            'kappa_radpm': kappa_radpm,
            'vx_mps': vx_mps,
            'ax_mps2': ax_mps2
        }
    
    def create_iqp_waypoint(self, values: List[str], waypoint_id: int, speed_factor: float = 1.0) -> Dict:
        """Create an IQP waypoint using raw racing line data (most aggressive)."""
        # Use raw racing line data directly (most aggressive)
        x_m = float(values[self.column_mapping['rl_x_m']])  
        y_m = float(values[self.column_mapping['rl_y_m']])
        psi_rad = float(values[self.column_mapping['rl_psi_rad']])
        vx_mps = float(values[self.column_mapping['rl_vx_mps']]) * speed_factor
        ax_mps2 = float(values[self.column_mapping['rl_ax_mps2']])
        
        # Use reference racing line for s_m, curvature and track bounds (more stable)
        s_m = float(values[self.column_mapping['ref_rl_s_m']])
        kappa_radpm = float(values[self.column_mapping['ref_rl_kappa_radpm']])
        d_right = float(values[self.column_mapping['ref_rl_d_right']])
        d_left = float(values[self.column_mapping['ref_rl_d_left']])
        
        return {
            'id': waypoint_id,
            's_m': s_m,
            'd_m': 0.0,
            'x_m': x_m,
            'y_m': y_m,
            'd_right': d_right,
            'd_left': d_left,
            'psi_rad': psi_rad,
            'kappa_radpm': kappa_radpm,
            'vx_mps': vx_mps,
            'ax_mps2': ax_mps2
        }
    
    def create_sp_waypoint(self, values: List[str], waypoint_id: int) -> Dict:
        """Create an SP waypoint using reference racing line data (refined/moderate)."""
        # Use reference racing line data (refined, balanced approach)
        s_m = float(values[self.column_mapping['ref_rl_s_m']])
        x_m = float(values[self.column_mapping['ref_rl_x_m']])  
        y_m = float(values[self.column_mapping['ref_rl_y_m']])
        psi_rad = float(values[self.column_mapping['ref_rl_psi_rad']])
        kappa_radpm = float(values[self.column_mapping['ref_rl_kappa_radpm']])
        d_right = float(values[self.column_mapping['ref_rl_d_right']])
        d_left = float(values[self.column_mapping['ref_rl_d_left']])
        
        # Moderate speed and acceleration (use raw racing line but reduce moderately)
        rl_vx_mps = float(values[self.column_mapping['rl_vx_mps']])
        rl_ax_mps2 = float(values[self.column_mapping['rl_ax_mps2']])
        
        vx_mps = rl_vx_mps * 0.85  # 15% speed reduction
        ax_mps2 = rl_ax_mps2 * 0.8  # 20% acceleration reduction
        
        return {
            'id': waypoint_id,
            's_m': s_m,
            'd_m': 0.0,
            'x_m': x_m,
            'y_m': y_m,
            'd_right': d_right,
            'd_left': d_left,
            'psi_rad': psi_rad,
            'kappa_radpm': kappa_radpm,
            'vx_mps': vx_mps,
            'ax_mps2': ax_mps2
        }
    
    def create_global_waypoints_json(self, trajectory_data: Dict[str, List[Dict]]) -> Dict[str, Any]:
        """Create the global_waypoints.json structure."""
        
        centerline_waypoints = trajectory_data['centerline']
        iqp_waypoints = trajectory_data['iqp'] 
        sp_waypoints = trajectory_data['sp']
        
        # Create waypoint arrays with proper ROS headers
        centerline_array = self.create_waypoint_array(centerline_waypoints)
        iqp_array = self.create_waypoint_array(iqp_waypoints)
        sp_array = self.create_waypoint_array(sp_waypoints)
        
        # Calculate lap statistics from IQP (most aggressive) trajectory
        lap_time = 108.68526373056437  # From CSV header
        iqp_max_speed = max(wp['vx_mps'] for wp in iqp_waypoints)
        sp_max_speed = max(wp['vx_mps'] for wp in sp_waypoints)
        
        # Estimate different lap times based on speed profiles
        iqp_lap_time = lap_time  # Original optimized time
        sp_lap_time = lap_time * 1.08  # ~8% slower due to conservative speeds
        
        # Create visualization markers for different trajectories
        centerline_markers = self.create_waypoint_markers(centerline_waypoints, "centerline", color={'r': 0, 'g': 0, 'b': 1, 'a': 1})  # Blue
        iqp_markers = self.create_waypoint_markers(iqp_waypoints, "iqp", color={'r': 1, 'g': 0, 'b': 0, 'a': 1})  # Red  
        sp_markers = self.create_waypoint_markers(sp_waypoints, "sp", color={'r': 0, 'g': 1, 'b': 0, 'a': 1})  # Green
        trackbounds_markers = self.create_trackbounds_markers(iqp_waypoints)  # Use IQP for bounds
        
        # Create full global waypoints structure in the correct order
        global_waypoints = {
            'map_info_str': {
                'data': f'IQP estimated lap time: {iqp_lap_time:.4f}s; IQP maximum speed: {iqp_max_speed:.4f}m/s; SP estimated lap time: {sp_lap_time:.4f}s; SP maximum speed: {sp_max_speed:.4f}m/s; '
            },
            'est_lap_time': {
                'data': sp_lap_time  # Use SP (more conservative) as default estimate
            },
            'centerline_markers': centerline_markers,
            'centerline_waypoints': centerline_array,
            'global_traj_markers_iqp': iqp_markers,
            'global_traj_wpnts_iqp': iqp_array,
            'global_traj_markers_sp': sp_markers,
            'global_traj_wpnts_sp': sp_array,
            'trackbounds_markers': trackbounds_markers
        }
        
        return global_waypoints
    
    def create_waypoint_array(self, waypoints: List[Dict]) -> Dict[str, Any]:
        """Create a waypoint array with proper ROS header."""
        wpnt_list = []
        
        for wp in waypoints:
            wpnt_msg = {
                'id': wp['id'],
                's_m': wp['s_m'],
                'd_m': wp['d_m'],
                'x_m': wp['x_m'],
                'y_m': wp['y_m'],
                'd_right': wp['d_right'],
                'd_left': wp['d_left'],
                'psi_rad': wp['psi_rad'],
                'kappa_radpm': wp['kappa_radpm'],
                'vx_mps': wp['vx_mps'],
                'ax_mps2': wp['ax_mps2']
            }
            wpnt_list.append(wpnt_msg)
        
        return {
            'header': {
                'seq': 1,
                'stamp': {
                    'secs': 0,
                    'nsecs': 0
                },
                'frame_id': ""
            },
            'wpnts': wpnt_list
        }
    
    def create_map_yaml(self, waypoints: List[Dict]) -> Dict[str, Any]:
        """Create the map YAML configuration."""
        
        # Calculate map bounds from waypoints
        x_coords = [wp['x_m'] for wp in waypoints]
        y_coords = [wp['y_m'] for wp in waypoints]
        
        min_x, max_x = min(x_coords), max(x_coords)
        min_y, max_y = min(y_coords), max(y_coords)
        
        # Set origin (bottom-left corner with some padding)
        padding = 5.0  # meters
        origin_x = min_x - padding
        origin_y = min_y - padding
        
        map_config = {
            'free_thresh': 0.196,
            'image': f'{self.output_map_name}.png',
            'negate': 0,
            'occupied_thresh': 0.65,
            'origin': [origin_x, origin_y, 0],
            'resolution': 0.05000000074505806  # 5cm resolution like other maps
        }
        
        return map_config
    
    def create_ot_sectors_yaml(self, waypoints: List[Dict]) -> Dict[str, Any]:
        """Create overtaking sectors configuration."""
        
        total_waypoints = len(waypoints)
        
        # Create two sectors covering the whole track
        ot_sectors = {
            'n_sectors': 2,
            'yeet_factor': 1.25,
            'spline_len': 30,
            'ot_sector_begin': 0.5,
            'Overtaking_sector0': {
                'start': 0,
                'end': total_waypoints // 2,
                'ot_flag': False
            },
            'Overtaking_sector1': {
                'start': total_waypoints // 2 + 1,
                'end': total_waypoints - 1,
                'ot_flag': False
            }
        }
        
        return ot_sectors
    
    def create_speed_scaling_yaml(self, waypoints: List[Dict]) -> Dict[str, Any]:
        """Create speed scaling configuration."""
        
        total_waypoints = len(waypoints)
        
        speed_scaling = {
            'global_limit': 0.5,
            'n_sectors': 1,
            'Sector0': {
                'start': 0,
                'end': total_waypoints - 1,
                'scaling': 0.5,
                'only_FTG': False,
                'no_FTG': False
            }
        }
        
        return speed_scaling
    
    def create_output_directory(self) -> str:
        """Create output directory structure."""
        base_path = "/home/atlas.linux/Documents/BA/ETH/race_stack/stack_master/maps"
        output_dir = os.path.join(base_path, self.output_map_name)
        
        # Create directory if it doesn't exist
        os.makedirs(output_dir, exist_ok=True)
        print(f"Created output directory: {output_dir}")
        
        return output_dir
    
    def write_yaml_file(self, data: Dict, filepath: str):
        """Write YAML file."""
        with open(filepath, 'w') as f:
            yaml.dump(data, f, default_flow_style=False)
        print(f"Written: {filepath}")
    
    def write_json_file(self, data: Dict, filepath: str):
        """Write JSON file."""
        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2)
        print(f"Written: {filepath}")
    
    def copy_placeholder_image(self, output_dir: str):
        """Copy a placeholder image file."""
        # Try to copy from existing map
        source_image = "/home/atlas.linux/Documents/BA/ETH/race_stack/stack_master/maps/f/f.png"
        target_image = os.path.join(output_dir, f"{self.output_map_name}.png")
        
        if os.path.exists(source_image):
            shutil.copy2(source_image, target_image)
            print(f"Copied placeholder image: {target_image}")
        else:
            print(f"Warning: Could not find source image {source_image}")
            print("You will need to provide a track image manually.")
    
    def create_waypoint_markers(self, waypoints: List[Dict], marker_type: str, color: Dict) -> Dict:
        """Create visualization markers for waypoints."""
        markers = []
        
        # Sample every 10th waypoint to avoid too many markers
        sample_rate = max(1, len(waypoints) // 500)  # Limit to ~500 markers max
        
        for i, wp in enumerate(waypoints[::sample_rate]):
            marker = {
                'header': {
                    'seq': 0,
                    'stamp': {
                        'secs': 0,
                        'nsecs': 0
                    },
                    'frame_id': 'map'
                },
                'ns': '',
                'id': i,
                'type': 2,  # SPHERE marker type
                'action': 0,  # ADD action
                'pose': {
                    'position': {
                        'x': wp['x_m'],
                        'y': wp['y_m'],
                        'z': 0
                    },
                    'orientation': {
                        'x': 0,
                        'y': 0,
                        'z': 0,
                        'w': 1
                    }
                },
                'scale': {
                    'x': 0.05,
                    'y': 0.05,
                    'z': 0.05
                },
                'color': color,
                'lifetime': {
                    'secs': 0,
                    'nsecs': 0
                },
                'frame_locked': False,
                'points': [],
                'colors': [],
                'text': '',
                'mesh_resource': '',
                'mesh_use_embedded_materials': False
            }
            markers.append(marker)
        
        return {'markers': markers}
    
    def create_trackbounds_markers(self, waypoints: List[Dict]) -> Dict:
        """Create visualization markers for track boundaries."""
        markers = []
        
        # Create left and right boundary markers
        sample_rate = max(1, len(waypoints) // 200)  # Even less dense for boundaries
        
        for boundary_side, color in [('left', {'r': 1, 'g': 0.5, 'b': 0, 'a': 0.7}), 
                                   ('right', {'r': 1, 'g': 0.5, 'b': 0, 'a': 0.7})]:
            
            for i, wp in enumerate(waypoints[::sample_rate]):
                # Calculate boundary position
                if boundary_side == 'left':
                    # Left boundary position
                    boundary_x = wp['x_m'] + wp['d_left'] * (-1) * math.sin(wp['psi_rad'])
                    boundary_y = wp['y_m'] + wp['d_left'] * math.cos(wp['psi_rad'])
                else:
                    # Right boundary position  
                    boundary_x = wp['x_m'] + wp['d_right'] * math.sin(wp['psi_rad']) 
                    boundary_y = wp['y_m'] + wp['d_right'] * (-1) * math.cos(wp['psi_rad'])
                
                marker_id = i if boundary_side == 'left' else i + 1000
                
                marker = {
                    'header': {
                        'seq': 0,
                        'stamp': {
                            'secs': 0,
                            'nsecs': 0
                        },
                        'frame_id': 'map'
                    },
                    'ns': f'trackbounds_{boundary_side}',
                    'id': marker_id,
                    'type': 1,  # CUBE marker type for boundaries
                    'action': 0,
                    'pose': {
                        'position': {
                            'x': boundary_x,
                            'y': boundary_y,
                            'z': 0
                        },
                        'orientation': {
                            'x': 0,
                            'y': 0,
                            'z': 0,
                            'w': 1
                        }
                    },
                    'scale': {
                        'x': 0.1,
                        'y': 0.1,
                        'z': 0.1
                    },
                    'color': color,
                    'lifetime': {
                        'secs': 0,
                        'nsecs': 0
                    },
                    'frame_locked': False,
                    'points': [],
                    'colors': [],
                    'text': '',
                    'mesh_resource': '',
                    'mesh_use_embedded_materials': False
                }
                markers.append(marker)
        
        return {'markers': markers}
    
    def parse(self):
        """Main parsing function."""
        print("=== Marina Map CSV to F1Tenth Format Parser ===")
        
        # Load and parse trajectories
        trajectory_data = self.load_marina_csv()
        
        if not trajectory_data or not trajectory_data['centerline']:
            print("Error: No waypoints could be parsed from CSV")
            return False
        
        # Create output directory
        output_dir = self.create_output_directory()
        
        # Create and write all files
        print("\nCreating output files...")
        
        # 1. global_waypoints.json
        global_waypoints = self.create_global_waypoints_json(trajectory_data)
        json_path = os.path.join(output_dir, 'global_waypoints.json')
        self.write_json_file(global_waypoints, json_path)
        
        # 2. map.yaml (use centerline for map bounds)
        map_config = self.create_map_yaml(trajectory_data['centerline'])
        yaml_path = os.path.join(output_dir, f'{self.output_map_name}.yaml')
        self.write_yaml_file(map_config, yaml_path)
        
        # 3. ot_sectors.yaml
        ot_sectors = self.create_ot_sectors_yaml(trajectory_data['centerline'])
        ot_path = os.path.join(output_dir, 'ot_sectors.yaml')
        self.write_yaml_file(ot_sectors, ot_path)
        
        # 4. speed_scaling.yaml
        speed_scaling = self.create_speed_scaling_yaml(trajectory_data['centerline'])
        speed_path = os.path.join(output_dir, 'speed_scaling.yaml')
        self.write_yaml_file(speed_scaling, speed_path)
        
        # 5. Copy placeholder image
        self.copy_placeholder_image(output_dir)
        
        print(f"\n=== Conversion Complete ===")
        print(f"Output directory: {output_dir}")
        print(f"Total waypoints per trajectory: {len(trajectory_data['centerline'])}")
        print("\nTrajectory types generated:")
        print(f"  - Centerline: {len(trajectory_data['centerline'])} waypoints (conservative)")
        print(f"  - IQP: {len(trajectory_data['iqp'])} waypoints (aggressive racing line)")
        print(f"  - SP: {len(trajectory_data['sp'])} waypoints (moderate racing line)")
        print("\nGenerated files:")
        print(f"  - {self.output_map_name}.yaml (map configuration)")
        print(f"  - global_waypoints.json (waypoint data with 3 trajectory types)")
        print(f"  - ot_sectors.yaml (overtaking sectors)")
        print(f"  - speed_scaling.yaml (speed limits)")
        print(f"  - {self.output_map_name}.png (track image - placeholder)")
        
        print("\nNext steps:")
        print("1. Replace the placeholder .png with your actual track image")
        print("2. Adjust the origin and resolution in the .yaml file if needed")
        print("3. Configure overtaking sectors and speed scaling as desired")
        print(f"4. Test with: roslaunch stack_master base_system.launch map_name:={self.output_map_name}")
        
        return True

def main():
    parser = argparse.ArgumentParser(description='Convert Marina CSV to F1Tenth map format')
    parser.add_argument('csv_file', help='Path to Marina CSV file')
    parser.add_argument('--output-name', default='marina', help='Output map name (default: marina)')
    
    args = parser.parse_args()
    
    if not os.path.exists(args.csv_file):
        print(f"Error: CSV file not found: {args.csv_file}")
        return 1
    
    try:
        converter = MarinaMapParser(args.csv_file, args.output_name)
        success = converter.parse()
        return 0 if success else 1
        
    except ImportError as e:
        print(f"Error: Missing required package: {e}")
        print("Please install: pip install pyyaml pandas numpy")
        return 1
    except Exception as e:
        print(f"Error: {e}")
        return 1

if __name__ == "__main__":
    exit(main())
