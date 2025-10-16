# app.py - Final, robust version with data grouping and sorting

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
    # Use a defaultdict to easily group all data entries under a Site ID
    grouped_data = defaultdict(list)
    current_short_id = None
    
    # --- PASS 1: Find all long-form IDs and create a map ---
    # This is crucial to link short IDs (e.g., "0116") to their full names.
    for line in lines:
        long_id_match = re.match(r'^(I-KO-KLKT-ENB-([\w\d]+))$', line.strip())
        if long_id_match:
            full_id = long_id_match.group(1)
            short_id = long_id_match.group(2)
            site_id_map[short_id] = full_id

    # --- PASS 2: Extract all data and associate it with the correct ID ---
    for line in lines:
        # Clean up the line by removing timestamps or chat prefixes
        temp_line = re.sub(r'.*:\s*', '', line).strip()
        # ** NEW ** Remove bracketed and parenthesized comments to isolate data
        cleaned_line = re.sub(r'\(.*?\)|\s*\[.*?\]', '', temp_line).strip()

        if not cleaned_line or cleaned_line.startswith('<Media omitted>'):
            continue

        # Find a short Site ID and set it as the current context
        short_id_match = re.match(r'^\b([A-Z]?\d{3,4})\b', cleaned_line)
        if short_id_match:
            current_short_id = short_id_match.group(1)
            continue

        # If we haven't found a Site ID in the file yet, we can't process data
        if not current_short_id:
            continue

        # Use flexible patterns (regex) to find all the data points in any order
        lat_long_match = re.search(r'(\d{2}\.\d+)\s*°?\s*(\d{2,3}\.\d+)', cleaned_line)
        angle_distance_match = re.search(r'\b(\d{1,3})\b(?:[\s,]*deg)?(?:[\s,]+)(\d+)\s*m', cleaned_line, re.IGNORECASE)
        building_match = re.search(r'(B\d)', cleaned_line, re.IGNORECASE)

        if lat_long_match and angle_distance_match:
            # Look up the full ID from our map, or use the short ID if no full ID exists
            full_site_id = site_id_map.get(current_short_id, current_short_id)
            
            # Store the extracted data under its full Site ID
            grouped_data[full_site_id].append({
                "lat": lat_long_match.group(1),
                "long": lat_long_match.group(2).lstrip('0'),
                "angle": int(angle_distance_match.group(1)), # Convert angle to a number for sorting
                "distance": angle_distance_match.group(2),
                "building": building_match.group(1).upper() if building_match else 'N/A'
            })
    
    # --- Final Step: Flatten the data and sort it as requested ---
    final_result = []
    # First, sort the Site IDs themselves alphabetically for a consistent output
    for site_id in sorted(grouped_data.keys()):
        # Then, sort the data entries for each site by their angle (ascending)
        sorted_entries = sorted(grouped_data[site_id], key=lambda x: x['angle'])
        
        # Add the correctly sorted entries to our final result list
        for entry in sorted_entries:
            final_result.append({
                "siteId": site_id,
                "lat": entry["lat"],
                "long": entry["long"],
                "angle": str(entry["angle"]), # Convert angle back to a string for the JSON response
                "distance": entry["distance"],
                "building": entry["building"]
            })

    return final_result

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
        json_data = parse_data_content(content)
        return jsonify(json_data)

if __name__ == '__main__':
    app.run(debug=True)

