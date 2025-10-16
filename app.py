# app.py - Final version with missing ID detection

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
    for line in lines:
        long_id_match = re.match(r'^(I-KO-KLKT-ENB-([\w\d]+))$', line.strip())
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

        short_id_match = re.match(r'^\b([A-Z]?\d{3,4})\b', cleaned_line)
        if short_id_match:
            current_short_id = short_id_match.group(1)
            continue

        if not current_short_id:
            continue

        lat_long_match = re.search(r'(\d{2}\.\d+)\s*°?\s*(\d{2,3}\.\d+)', cleaned_line)
        angle_distance_match = re.search(r'\b(\d{1,3})\b(?:[\s,]*deg)?(?:[\s,]+)(\d+)\s*m', cleaned_line, re.IGNORECASE)
        building_match = re.search(r'(B\d)', cleaned_line, re.IGNORECASE)

        if lat_long_match and angle_distance_match:
            full_site_id = site_id_map.get(current_short_id, current_short_id)
            grouped_data[full_site_id].append({
                "lat": lat_long_match.group(1),
                "long": lat_long_match.group(2).lstrip('0'),
                "angle": int(angle_distance_match.group(1)),
                "distance": angle_distance_match.group(2),
                "building": building_match.group(1).upper() if building_match else 'N/A'
            })
    
    # --- New Step: Identify Site IDs that were listed but had no data ---
    all_listed_full_ids = set(site_id_map.values())
    ids_with_data = set(grouped_data.keys())
    missing_ids = sorted(list(all_listed_full_ids - ids_with_data))

    # --- Final Step: Flatten the data and sort it as requested ---
    final_result = []
    for site_id in sorted(grouped_data.keys()):
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
            "missingIds": missing_ids
        })

if __name__ == '__main__':
    app.run(debug=True)

