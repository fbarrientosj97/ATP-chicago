# Tennis Ladder Ranking System

This project is a Flask web application to manage a tennis ladder ranking system. It allows users to add players, record matches, and view the ranking and match history.

## Installation

1. Clone the repository.
2. Create a virtual environment: `python -m venv venv`
3. Activate the environment: 
   - On Windows: `venv\Scripts\activate`
   - On macOS/Linux: `source venv/bin/activate`
4. Install the dependencies: `pip install -r requirements.txt`
5. Run the application: `python app.py`

The application will run on `http://localhost:5000/`.

## Usage

- Go to `/add_player` to add new players to the ranking.
- Go to `/add_match` to record a new match between two players.
- Go to `/ranking` to view the current ranking.
- Go to `/matches` to view the match history.

## Dependencies

- Flask
- pandas
- openpyxl# tennis-ladder-chicago
# tennis-ladder-chicago
# tennis-ladder-chicago

## Extras 

- Hay que correr el siguiente código para que funcione de no subir variables de entorno:
- export GOOGLE_APPLICATION_CREDENTIALS_JSON=$(cat credentials.json | jq -c)     

## Error handling

- In case of an error with the virtual environment: 
   1. Remove the Existing venv Completely:
Make sure you’re not just “recreating” over an existing folder. Deactivate your virtual environment (if it’s active) and then delete the entire venv folder: 
      - deactivate  # if you are in the virtual environment
      - rm -rf venv

   2.	Create a New Virtual Environment: Create a new virtual environment in a clean folder:

      - python3 -m venv venv
