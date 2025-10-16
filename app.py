# app.py - Revised to produce a single, concatenated string output

import re
from flask import Flask, request, jsonify
from flask_cors import CORS
from collections import defaultdict

# Initialize the Flask app
app = Flask(__name__)
CORS(app)  # Enable Cross-Origin Resource Sharing

# The intelligent, rule-based parsing function (remains unchanged from previous step)
def parse_data_content(data):
    lines = data.split('\n')
    site_id_map = {}
    grouped_data = defaultdict(list)
    current_short_id = None
    
    # --- PASS 1: Find all long-form IDs and create a map ---
    for line in lines:
        long_id_match = re.match(r'.*(I-KO-KLKT-ENB-([\w\d]+)).*', line.strip())
        if long_id_match:
            full_id = long_id_match.group(1)
            short_id = long_id_match.group(2)
            site_id_map[short_id] = full_id
    
    # --- PASS 2: Extract all data and associate it with the correct ID ---
    for line in lines:
        temp_line = re.sub(r'.*:\s*', '', line).strip()
        cleaned_line = re.sub(r'\(.*?\)|\s*\[.*?\]', '', temp_line).strip()

        if not cleaned_line or cleaned_line.startswith('<Media omitted>'):
            continue

        short_id_match = re.match(r'^\b([A-Z]?\d{3,4})\b$', cleaned_line)
        if short_id_match and short_id_match.group(1) in site_id_map:
            current_short_id = short_id_match.group(1)
            continue

        if not current_short_id:
            continue
        
        # --- ROBUST REGEX FOR DATA EXTRACTION ---
        lat_long_match = re.search(r'(\d{2}\.\d+)\s*°?\s*[,\s]\s*(\d{2,3}\.\d+)\s*°?', cleaned_line)
        angle_match = re.search(r'(\d{1,3})\s*(?:DEG|DEEG|deg)\b', cleaned_line, re.IGNORECASE)
        distance_match = re.search(r'(\d+)\s*M\b', cleaned_line, re.IGNORECASE)
        building_match = re.search(r'\b(B\d)\b', cleaned_line, re.IGNORECASE)

        if lat_long_match and angle_match and distance_match:
            full_site_id = site_id_map.get(current_short_id, current_short_id)
            
            lat = lat_long_match.group(1)
            long = lat_long_match.group(2).lstrip('0') 
            angle = int(angle_match.group(1))
            distance = distance_match.group(1)
            building = building_match.group(1).upper() if building_match else 'N/A'
            
            # Store data in a structured way first
            grouped_data[full_site_id].append({
                "lat": lat,
                "long": long,
                "angle": angle,
                "distance": distance,
                "building": building
            })
    
    # --- Identify Site IDs that were listed but had no data ---
    all_listed_full_ids = set(site_id_map.values())
    ids_with_data = set(grouped_data.keys())
    missing_ids = sorted(list(all_listed_full_ids - ids_with_data))

    # --- Final Step: Flatten the data and prepare for concatenation ---
    final_result_list = []
    for site_id in sorted(grouped_data.keys()):
        sorted_entries = sorted(grouped_data[site_id], key=lambda x: x['angle'])
        for entry in sorted_entries:
            # Create a list of all 6 field values for easy concatenation later
            final_result_list.append([
                site_id,
                entry["lat"],
                entry["long"],
                str(entry["angle"]),
                entry["distance"],
                entry["building"]
            ])

    # Return the list of structured entries and missing IDs
    return final_result_list, missing_ids

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
        # Get the structured list of entries and missing IDs
        structured_data, missing_ids = parse_data_content(content)
        
        # --- NEW LOGIC: Concatenate all fields into one continuous string ---
        concatenated_string = ""
        for entry in structured_data:
            # Join all six fields for the current entry
            concatenated_string += "".join(entry) 
            
        # The output is now the single continuous string you requested
        return jsonify({
            "parsedDataString": concatenated_string,
            "missingIds": missing_ids
        })

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
