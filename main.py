import os
import uuid
import base64
import json
from flask import Flask, request, redirect, url_for, render_template, send_from_directory
from google import generativeai as genai

# Initialize Flask app and Gemini client
app = Flask(__name__)
client = genai.GenerativeModel(
    'gemini-2.0-flash-lite',
    generation_config={"response_mime_type": "application/json"}
)
recipes = {}  # In-memory storage for recipe data

# Ensure the images directory exists
os.makedirs('images', exist_ok=True)

# Configure Gemini API key from environment variables
os.environ['GOOGLE_API_KEY'] = os.environ.get('GOOGLE_API_KEY', 'your-default-key-here')  # Fallback for local testing
genai.configure(api_key=os.environ['GOOGLE_API_KEY'])

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload():
    # Log the incoming request for debugging
    print("Upload Request Files:", request.files)
    files = request.files.getlist('photo')
    if not files or all(file.filename == '' for file in files):
        print("No files provided or empty filenames")
        return "No files uploaded", 400

    # Generate a unique key for this recipe
    unique_key = str(uuid.uuid4())
    image_filenames = []
    image_datas = []

    # Process each uploaded file
    for i, file in enumerate(files):
        image_path = f'images/{unique_key}_{i}.jpg'
        file.save(image_path)
        print(f"File saved to {image_path}")
        with open(image_path, "rb") as image_file:
            image_data = base64.b64encode(image_file.read()).decode('utf-8')
        image_datas.append({"inline_data": {"mime_type": "image/jpeg", "data": image_data}})
        image_filenames.append(f'{unique_key}_{i}.jpg')

    # Prompt adjusted for multiple images
    prompt = """
    The following images are all part of the same recipe. Please convert the recipe text from these images into a structured JSON object with the following keys:
    - title: string
    - description: string (short summary)
    - servings: string or integer
    - prep_time: string
    - cook_time: string
    - total_time: string
    - ingredients: list of strings
    - directions: list of strings (numbered steps)
    - nutrition_info: string (estimate using ingredient list and quantities if not provided, e.g., "Approximately 300 calories")
    Output only the JSON object, without any additional text or explanations.
    """

    try:
        # Send request to Gemini API with all images
        response = client.generate_content([prompt] + image_datas)
        print("API Response Text:", response.text)

        # Parse the response
        recipe_data = json.loads(response.text)
        print("Parsed Recipe Data:", recipe_data)

        # Ensure recipe_data is a dictionary
        if not isinstance(recipe_data, dict):
            print(f"Warning: API returned non-dictionary data: {recipe_data}")
            recipe_data = {}

        # Store the recipe data with image filenames
        recipes[unique_key] = {'data': recipe_data, 'images': image_filenames}

        # Redirect to the recipe page
        return redirect(url_for('recipe', key=unique_key))

    except json.decoder.JSONDecodeError as e:
        print(f"Error parsing JSON: {response.text}, Error: {e}")
        recipes[unique_key] = {'data': {}, 'images': image_filenames}
        return redirect(url_for('recipe', key=unique_key))
    except Exception as e:
        print(f"Unexpected error: {e}")
        return "Error processing images", 500

@app.route('/recipe/<key>')
def recipe(key):
    recipe_info = recipes.get(key)
    if not recipe_info:
        print(f"Recipe key {key} not found")
        return "Recipe not found", 404

    recipe_data = recipe_info.get('data', {})
    image_filenames = recipe_info.get('images', [])
    image_urls = [url_for('serve_image', filename=filename) for filename in image_filenames]

    # Provide default values if recipe_data is incomplete
    default_data = {
        'title': 'Untitled Recipe',
        'description': 'No description available',
        'servings': '',
        'prep_time': '',
        'cook_time': '',
        'total_time': '',
        'ingredients': [],
        'directions': [],
        'nutrition_info': 'Not available'
    }
    recipe_data = {**default_data, **recipe_data}

    print(f"Rendering recipe page for key {key} with data: {recipe_data} and images: {image_urls}")
    return render_template('recipe.html', data=recipe_data, image_urls=image_urls)

@app.route('/images/<filename>')
def serve_image(filename):
    return send_from_directory('images', filename)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)
