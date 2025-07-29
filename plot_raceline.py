#!/usr/bin/env python3
"""
Script to plot the Marina raceline trajectories from the generated map data.

This script visualizes the three trajectory types:
- Centerline (blue): Conservative path through track center
- IQP (red): Aggressive racing line for minimum lap time
- SP (green): Moderate racing line balancing speed and safety
"""

import json
import matplotlib.pyplot as plt
import numpy as np
import os

def load_waypoints_data(json_file):
    """Load waypoints data from the global_waypoints.json file."""
    with open(json_file, 'r') as f:
        data = json.load(f)
    
    # Extract waypoints for each trajectory type
    centerline_waypoints = data['centerline_waypoints']['wpnts']
    iqp_waypoints = data['global_traj_wpnts_iqp']['wpnts']
    sp_waypoints = data['global_traj_wpnts_sp']['wpnts']
    
    # Extract trackbounds markers
    trackbounds_markers = data.get('trackbounds_markers', {}).get('markers', [])
    
    return centerline_waypoints, iqp_waypoints, sp_waypoints, trackbounds_markers

def extract_trackbounds_coordinates(trackbounds_markers):
    """Extract trackbounds coordinates from markers with robust error handling."""
    left_bounds_x, left_bounds_y = [], []
    right_bounds_x, right_bounds_y = [], []
    
    print(f"Processing {len(trackbounds_markers)} trackbounds markers...")
    
    valid_markers = 0
    for i, marker in enumerate(trackbounds_markers):
        try:
            # Check if marker has proper structure and position data
            if (isinstance(marker, dict) and 
                'ns' in marker and 
                marker.get('ns') in ['trackbounds_left', 'trackbounds_right'] and
                'pose' in marker and 
                isinstance(marker['pose'], dict) and
                'position' in marker['pose'] and
                isinstance(marker['pose']['position'], dict) and
                'x' in marker['pose']['position'] and
                'y' in marker['pose']['position']):
                
                x = float(marker['pose']['position']['x'])
                y = float(marker['pose']['position']['y'])
                
                if marker['ns'] == 'trackbounds_left':
                    left_bounds_x.append(x)
                    left_bounds_y.append(y)
                elif marker['ns'] == 'trackbounds_right':
                    right_bounds_x.append(x)
                    right_bounds_y.append(y)
                
                valid_markers += 1
                
        except (KeyError, TypeError, ValueError) as e:
            # Skip invalid markers silently
            continue
    
    print(f"Successfully extracted {valid_markers} valid trackbounds markers")
    print(f"Left boundary points: {len(left_bounds_x)}, Right boundary points: {len(right_bounds_x)}")
    
    return left_bounds_x, left_bounds_y, right_bounds_x, right_bounds_y

def extract_coordinates_and_speeds(waypoints):
    """Extract x, y coordinates and speeds from waypoints."""
    x_coords = [wp['x_m'] for wp in waypoints]
    y_coords = [wp['y_m'] for wp in waypoints]
    speeds = [wp['vx_mps'] for wp in waypoints]
    return x_coords, y_coords, speeds

def plot_trajectories(centerline_waypoints, iqp_waypoints, sp_waypoints, trackbounds_markers):
    """Plot all three trajectory types with track boundaries."""
    
    # Extract coordinates and speeds
    cl_x, cl_y, cl_speeds = extract_coordinates_and_speeds(centerline_waypoints)
    iqp_x, iqp_y, iqp_speeds = extract_coordinates_and_speeds(iqp_waypoints)
    sp_x, sp_y, sp_speeds = extract_coordinates_and_speeds(sp_waypoints)
    
    # Extract track boundaries
    left_bounds_x, left_bounds_y, right_bounds_x, right_bounds_y = extract_trackbounds_coordinates(trackbounds_markers)
    
    # Create figure with subplots
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(20, 10))
    
    # Plot 1: Track layout with all trajectories and boundaries
    # Plot track boundaries first (so they appear behind trajectories)
    if left_bounds_x and left_bounds_y:
        ax1.plot(left_bounds_x, left_bounds_y, 'black', linewidth=2, alpha=0.8, label=f'Left Track Boundary ({len(left_bounds_x)} points)')
    if right_bounds_x and right_bounds_y:
        ax1.plot(right_bounds_x, right_bounds_y, 'black', linewidth=2, alpha=0.8, label=f'Right Track Boundary ({len(right_bounds_x)} points)')
    
    # Plot trajectories
    ax1.plot(cl_x, cl_y, 'b-', linewidth=2, label=f'Centerline (avg: {np.mean(cl_speeds):.1f} m/s)', alpha=0.8)
    ax1.plot(iqp_x, iqp_y, 'r-', linewidth=2, label=f'IQP - Aggressive (avg: {np.mean(iqp_speeds):.1f} m/s)', alpha=0.8)
    ax1.plot(sp_x, sp_y, 'g-', linewidth=2, label=f'SP - Moderate (avg: {np.mean(sp_speeds):.1f} m/s)', alpha=0.8)
    
    ax1.set_xlabel('X Position (m)')
    ax1.set_ylabel('Y Position (m)')
    ax1.set_title('Marina Race Track - All Trajectories with Track Boundaries')
    ax1.legend()
    ax1.grid(True, alpha=0.3)
    ax1.axis('equal')
    
    # Add start/finish markers
    ax1.plot(iqp_x[0], iqp_y[0], 'ko', markersize=10, label='Start/Finish')
    ax1.text(iqp_x[0], iqp_y[0], '  Start/Finish', fontsize=10, ha='left')
    
    # Plot 2: Speed profile comparison
    # Use arc length for x-axis (approximate)
    cl_s = [wp['s_m'] for wp in centerline_waypoints]
    iqp_s = [wp['s_m'] for wp in iqp_waypoints]
    sp_s = [wp['s_m'] for wp in sp_waypoints]
    
    ax2.plot(cl_s, cl_speeds, 'b-', linewidth=2, label=f'Centerline (max: {max(cl_speeds):.1f} m/s)')
    ax2.plot(iqp_s, iqp_speeds, 'r-', linewidth=2, label=f'IQP (max: {max(iqp_speeds):.1f} m/s)')
    ax2.plot(sp_s, sp_speeds, 'g-', linewidth=2, label=f'SP (max: {max(sp_speeds):.1f} m/s)')
    
    ax2.set_xlabel('Track Distance (m)')
    ax2.set_ylabel('Speed (m/s)')
    ax2.set_title('Speed Profiles Along Track')
    ax2.legend()
    ax2.grid(True, alpha=0.3)
    
    plt.tight_layout()
    return fig

def plot_speed_heatmap(waypoints, trajectory_name, trackbounds_markers=None):
    """Create a speed heatmap for a single trajectory with optional track boundaries."""
    x_coords, y_coords, speeds = extract_coordinates_and_speeds(waypoints)
    
    fig, ax = plt.subplots(figsize=(12, 10))
    
    # Plot track boundaries first if available
    if trackbounds_markers:
        left_bounds_x, left_bounds_y, right_bounds_x, right_bounds_y = extract_trackbounds_coordinates(trackbounds_markers)
        if left_bounds_x and left_bounds_y:
            ax.plot(left_bounds_x, left_bounds_y, 'gray', linewidth=2, alpha=0.6, label='Left Boundary')
        if right_bounds_x and right_bounds_y:
            ax.plot(right_bounds_x, right_bounds_y, 'gray', linewidth=2, alpha=0.6, label='Right Boundary')
    
    # Create scatter plot with speed as color
    scatter = ax.scatter(x_coords, y_coords, c=speeds, cmap='viridis', s=20, alpha=0.8)
    
    # Add colorbar
    cbar = plt.colorbar(scatter, ax=ax)
    cbar.set_label('Speed (m/s)')
    
    ax.set_xlabel('X Position (m)')
    ax.set_ylabel('Y Position (m)')
    ax.set_title(f'{trajectory_name} - Speed Heatmap with Track Boundaries')
    ax.grid(True, alpha=0.3)
    ax.axis('equal')
    
    if trackbounds_markers:
        ax.legend()
    
    return fig

def plot_track_boundaries_only(trackbounds_markers):
    """Create a plot showing only the track boundaries for detailed view."""
    left_bounds_x, left_bounds_y, right_bounds_x, right_bounds_y = extract_trackbounds_coordinates(trackbounds_markers)
    
    fig, ax = plt.subplots(figsize=(15, 12))
    
    if left_bounds_x and left_bounds_y:
        ax.plot(left_bounds_x, left_bounds_y, 'red', linewidth=2, alpha=0.8, label=f'Left Track Boundary ({len(left_bounds_x)} points)')
    if right_bounds_x and right_bounds_y:
        ax.plot(right_bounds_x, right_bounds_y, 'blue', linewidth=2, alpha=0.8, label=f'Right Track Boundary ({len(right_bounds_x)} points)')
    
    ax.set_xlabel('X Position (m)')
    ax.set_ylabel('Y Position (m)')
    ax.set_title('Marina Track Boundaries')
    ax.legend()
    ax.grid(True, alpha=0.3)
    ax.axis('equal')
    
    return fig

def main():
    """Main plotting function."""
    # Path to the global waypoints file
    json_file = "/home/atlas.linux/Documents/BA/ETH/race_stack/stack_master/maps/marina/global_waypoints.json"
    
    if not os.path.exists(json_file):
        print(f"Error: Could not find {json_file}")
        print("Make sure you've run the Marina map parser first.")
        return
    
    print("Loading waypoints data...")
    try:
        centerline_waypoints, iqp_waypoints, sp_waypoints, trackbounds_markers = load_waypoints_data(json_file)
        print(f"Loaded {len(centerline_waypoints)} waypoints for each trajectory type")
        print(f"Loaded {len(trackbounds_markers)} trackbounds markers")
        
        # Plot all trajectories with track boundaries
        print("Creating trajectory comparison plot with track boundaries...")
        fig1 = plot_trajectories(centerline_waypoints, iqp_waypoints, sp_waypoints, trackbounds_markers)
        
        # Save the plot
        output_path = "/home/atlas.linux/Documents/BA/ETH/race_stack/marina_trajectories.png"
        fig1.savefig(output_path, dpi=300, bbox_inches='tight')
        print(f"Saved trajectory plot: {output_path}")
        
        # Create speed heatmaps for each trajectory with track boundaries
        print("Creating speed heatmaps with track boundaries...")
        
        # IQP heatmap
        fig2 = plot_speed_heatmap(iqp_waypoints, "IQP (Aggressive)", trackbounds_markers)
        iqp_heatmap_path = "/home/atlas.linux/Documents/BA/ETH/race_stack/marina_iqp_heatmap.png"
        fig2.savefig(iqp_heatmap_path, dpi=300, bbox_inches='tight')
        print(f"Saved IQP heatmap: {iqp_heatmap_path}")
        
        # SP heatmap
        fig3 = plot_speed_heatmap(sp_waypoints, "SP (Moderate)", trackbounds_markers)
        sp_heatmap_path = "/home/atlas.linux/Documents/BA/ETH/race_stack/marina_sp_heatmap.png"
        fig3.savefig(sp_heatmap_path, dpi=300, bbox_inches='tight')
        print(f"Saved SP heatmap: {sp_heatmap_path}")
        
        # Create track boundaries only plot
        print("Creating track boundaries plot...")
        fig4 = plot_track_boundaries_only(trackbounds_markers)
        boundaries_path = "/home/atlas.linux/Documents/BA/ETH/race_stack/marina_track_boundaries.png"
        fig4.savefig(boundaries_path, dpi=300, bbox_inches='tight')
        print(f"Saved track boundaries plot: {boundaries_path}")
        
        # Show statistics
        print("\n=== Trajectory and Boundary Statistics ===")
        left_bounds_x, left_bounds_y, right_bounds_x, right_bounds_y = extract_trackbounds_coordinates(trackbounds_markers)
        print(f"Track Boundaries - Left: {len(left_bounds_x)} points, Right: {len(right_bounds_x)} points")
        cl_speeds = [wp['vx_mps'] for wp in centerline_waypoints]
        iqp_speeds = [wp['vx_mps'] for wp in iqp_waypoints]
        sp_speeds = [wp['vx_mps'] for wp in sp_waypoints]
        
        print(f"Centerline - Min: {min(cl_speeds):.2f} m/s, Max: {max(cl_speeds):.2f} m/s, Avg: {np.mean(cl_speeds):.2f} m/s")
        print(f"IQP        - Min: {min(iqp_speeds):.2f} m/s, Max: {max(iqp_speeds):.2f} m/s, Avg: {np.mean(iqp_speeds):.2f} m/s")
        print(f"SP         - Min: {min(sp_speeds):.2f} m/s, Max: {max(sp_speeds):.2f} m/s, Avg: {np.mean(sp_speeds):.2f} m/s")
        
        # Track length
        track_length = max([wp['s_m'] for wp in iqp_waypoints])
        print(f"\nTrack length: {track_length:.2f} m")
        
        # Estimated lap times (rough calculation)
        def estimate_lap_time(waypoints):
            total_time = 0
            for i in range(len(waypoints)-1):
                wp1 = waypoints[i]
                wp2 = waypoints[i+1]
                distance = np.sqrt((wp2['x_m'] - wp1['x_m'])**2 + (wp2['y_m'] - wp1['y_m'])**2)
                avg_speed = (wp1['vx_mps'] + wp2['vx_mps']) / 2
                if avg_speed > 0:
                    total_time += distance / avg_speed
            return total_time
        
        cl_time = estimate_lap_time(centerline_waypoints)
        iqp_time = estimate_lap_time(iqp_waypoints)
        sp_time = estimate_lap_time(sp_waypoints)
        
        print(f"\nEstimated lap times:")
        print(f"Centerline: {cl_time:.2f} seconds")
        print(f"IQP:        {iqp_time:.2f} seconds")
        print(f"SP:         {sp_time:.2f} seconds")
        
        # Display plots
        plt.show()
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
