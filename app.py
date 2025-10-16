import re
from flask import Flask, request, jsonify
from flask_cors import CORS
from collections import defaultdict

# Initialize Flask
app = Flask(__name__)
CORS(app)  # Enable Cross-Origin Resource Sharing (for frontend apps)

# --------------------------------------------------------------------
# Function: Parse the uploaded raw text data into structured JSON
# --------------------------------------------------------------------
def parse_data_content(data):
    lines = data.split('\n')
    site_id_map = {}
    grouped_data = defaultdict(list)
    current_short_id = None

    # --- PASS 1: Identify all full Site IDs and map them to short IDs ---
    for line in lines:
        long_id_match = re.match(r'^(I-KO-KLKT-ENB-(\d+))$', line.strip())
        if long_id_match:
            full_id = long_id_match.group(1)
            short_id = long_id_match.group(2)
            site_id_map[short_id] = full_id

    # --- PASS 2: Extract all coordinate entries and associate with IDs ---
    for line in lines:
        cleaned_line = re.sub(r'.*:\s*', '', line).strip()
        if not cleaned_line or cleaned_line.startswith('<Media omitted>'):
            continue

        # Detect short Site ID (e.g., 0116, 0187, etc.)
        short_id_match = re.match(r'^(\d{3,4})$', cleaned_line)
        if short_id_match:
            current_short_id = short_id_match.group(1)
            continue

        if not current_short_id:
            continue  # Skip data until first Site ID is found

        # Match patterns in each line flexibly
        lat_long_match = re.search(r'(\d{2}\.\d+)[^\d]+(\d{2,3}\.\d+)', cleaned_line)
        angle_match = re.search(r'(\d{1,3})\s*(?:DEG|DEEG|DEGREE|deg)', cleaned_line, re.IGNORECASE)
        distance_match = re.search(r'(\d+)\s*M', cleaned_line, re.IGNORECASE)
        building_match = re.search(r'(B\d)', cleaned_line, re.IGNORECASE)

        # If the line has valid data points, add it to the group
        if lat_long_match and angle_match and distance_match:
            full_site_id = site_id_map.get(current_short_id, f"I-KO-KLKT-ENB-{current_short_id}")
            grouped_data[full_site_id].append({
                "lat": lat_long_match.group(1),
                "long": lat_long_match.group(2).lstrip('0'),
                "angle": int(angle_match.group(1)),
                "distance": int(distance_match.group(1)),
                "building": building_match.group(1).upper() if building_match else "N/A"
            })

    # --- PASS 3: Sort data by Site ID and then by Angle ---
    final_result = []
    for site_id in sorted(grouped_data.keys()):
        sorted_entries = sorted(grouped_data[site_id], key=lambda x: x['angle'])
        for entry in sorted_entries:
            final_result.append({
                "siteId": site_id,
                "lat": entry["lat"],
                "long": entry["long"],
                "angle": str(entry["angle"]),
                "distance": str(entry["distance"]),
                "building": entry["building"]
            })

    return final_result


# --------------------------------------------------------------------
# Flask Route: Handle file upload and parse the data
# --------------------------------------------------------------------
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


# --------------------------------------------------------------------
# Run the Flask app
# --------------------------------------------------------------------
if __name__ == '__main__':
    app.run(debug=True)
