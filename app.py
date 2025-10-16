# app.py - Final version with a more robust regex

import re
from flask import Flask, request, jsonify
from flask_cors import CORS
from collections import defaultdict

# Initialize the Flask app
app = Flask(__name__)
CORS(app)  # Enable Cross-Origin Resource Sharing

# The intelligent, rule-based parsing function
def parse_data_content(data):
    lines = data.split('\n')
    site_id_map = {}
    grouped_data = defaultdict(list)
    current_short_id = None
    
    # --- PASS 1: Find all long-form IDs and create a map ---
    # This regex is made more lenient to handle potential trailing space/non-content text.
    for line in lines:
        long_id_match = re.match(r'.*(I-KO-KLKT-ENB-([\w\d]+)).*', line.strip())
        if long_id_match:
            full_id = long_id_match.group(1)
            short_id = long_id_match.group(2)
            site_id_map[short_id] = full_id
    
    # --- PASS 2: Extract all data and associate it with the correct ID ---
    for line in lines:
        # 1. Clean up: Remove chat metadata (timestamp/name)
        temp_line = re.sub(r'.*:\s*', '', line).strip()
        # 2. Clean up: Remove brackets/parentheses and media tags
        cleaned_line = re.sub(r'\(.*?\)|\s*\[.*?\]', '', temp_line).strip()

        if not cleaned_line or cleaned_line.startswith('<Media omitted>'):
            continue

        # Check for Short ID (e.g., '0116', '0187') to set context
        short_id_match = re.match(r'^\b([A-Z]?\d{3,4})\b$', cleaned_line)
        if short_id_match and short_id_match.group(1) in site_id_map:
            current_short_id = short_id_match.group(1)
            continue

        if not current_short_id:
            continue
        
        # --- ROBUST REGEX FOR DATA EXTRACTION ---
        
        # LAT/LONG: Handles space, comma, and degree symbol separation for Lat and Long.
        lat_long_match = re.search(r'(\d{2}\.\d+)\s*°?\s*[,\s]\s*(\d{2,3}\.\d+)\s*°?', cleaned_line)
        
        # ANGLE/DISTANCE: This flexible regex captures Angle and Distance regardless of order or text.
        # It looks for: (NUMBER) followed by 'deg/deeg' AND (NUMBER) followed by 'm'.
        # We search for two distinct patterns and sort them later if necessary.
        angle_match = re.search(r'(\d{1,3})\s*(?:DEG|DEEG|deg)\b', cleaned_line, re.IGNORECASE)
        distance_match = re.search(r'(\d+)\s*M\b', cleaned_line, re.IGNORECASE)
        
        # BUILDING: Looks for 'B' followed by a single digit, regardless of case.
        building_match = re.search(r'\b(B\d)\b', cleaned_line, re.IGNORECASE)

        # Only process if we have the critical Lat/Long and Angle/Distance components
        if lat_long_match and angle_match and distance_match:
            full_site_id = site_id_map.get(current_short_id, current_short_id)
            
            # Extract and clean values
            lat = lat_long_match.group(1)
            # Remove leading zero if present in Long (e.g., '088.42655')
            long = lat_long_match.group(2).lstrip('0') 
            angle = int(angle_match.group(1))
            distance = distance_match.group(1)
            building = building_match.group(1).upper() if building_match else 'N/A'
            
            grouped_data[full_site_id].append({
                "lat": lat,
                "long": long,
                "angle": angle,
                "distance": distance,
                "building": building
            })
    
    # --- New Step: Identify Site IDs that were listed but had no data ---
    all_listed_full_ids = set(site_id_map.values())
    ids_with_data = set(grouped_data.keys())
    missing_ids = sorted(list(all_listed_full_ids - ids_with_data))

    # --- Final Step: Flatten the data and sort it as requested ---
    final_result = []
    for site_id in sorted(grouped_data.keys()):
        # Sort each site's entries by the 'angle' column
        sorted_entries = sorted(grouped_data[site_id], key=lambda x: x['angle'])
        for entry in sorted_entries:
            final_result.append({
                "siteId": site_id,
                "lat": entry["lat"],
                "long": entry["long"],
                "angle": str(entry["angle"]),
                "distance": entry["distance"],
                "building": entry["building"]
            })

    # Return both the parsed data and the list of IDs with missing data
    return final_result, missing_ids

# The main upload endpoint that your frontend calls
@app.route('/upload', methods=['POST'])
def upload_file():
    if 'dataFile' not in request.files:
        return jsonify({"error": "No file part"}), 400
    
    file = request.files['dataFile']
    
    if file.filename == '':
        return jsonify({"error": "No selected file"}), 400

    if file:
        content = file.read().decode('utf-8')
        # Get both pieces of information from the parser
        parsed_data, missing_ids = parse_data_content(content)
        # Send a structured response back to the frontend
        return jsonify({
            "parsedData": parsed_data,
            # It's helpful to also return the missing IDs for display/debugging
            "missingIds": missing_ids 
        })

if __name__ == '__main__':
    # When deployed to Render, use the host and port recommended by the platform
    # For local development:
    app.run(debug=True, host='0.0.0.0', port=5000)
