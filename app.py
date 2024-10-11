import os
import pandas as pd
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
import json

app = Flask(__name__)

# Define the Google Sheets ID and ranges for each sheet
SHEET_ID = '1o-RzjCAGVwmZcVg1tSmlKBs2SbUNIBsyE2VFsBwVv0c'
RANGE_NAME_RANKING = 'Ranking!A1:D'  # Adjust the range as necessary for ranking sheet
RANGE_NAME_MATCHES = 'Matches!A1:F'  # Adjust the range as necessary for matches sheet

# Set up the credentials and Google Sheets API
SCOPES = ['https://www.googleapis.com/auth/spreadsheets']
service_account_info = json.loads(os.getenv('GOOGLE_APPLICATION_CREDENTIALS_JSON'))
creds = Credentials.from_service_account_info(service_account_info, scopes=SCOPES)
service = build('sheets', 'v4', credentials=creds)
sheet = service.spreadsheets()


class Player:
    def __init__(self, name, initial_rank, age, email):
        self.name = name
        self.rank = initial_rank
        self.age = age
        self.email = email
        self.matches = []

    def __str__(self):
        return f"{self.name} (Rank: {self.rank})"


class Match:
    def __init__(self, player1, player2, result, sets, time, comment="None"):
        self.player1 = player1
        self.player2 = player2
        self.result = result
        self.sets = sets
        self.time = time
        self.comment = comment  # Add comment attribute

    def __str__(self):
        return f"{self.player1.name} vs {self.player2.name} - Winner: {self.result}, Sets: {self.sets}"

    def to_dict(self):
        return {
            "player1": self.player1.name,
            "player2": self.player2.name,
            "result": self.result,
            "sets": self.sets,
            "time": self.time,
            "comment": self.comment  # Include comment in dict
        }


class Ladder:
    def __init__(self, min_rank_difference=4):
        self.players = []
        self.matches = []
        self.min_rank_difference = min_rank_difference

    def add_player(self, player):
        self.players.append(player)

    def record_match(self, player1, player2, winner, sets, time, comment):
        if not comment:
            comment = 'None'
        match = Match(player1, player2, winner, sets, time, comment)
        self.matches.append(match)

        # Update rankings
        print(player1.rank)
        print(player2.rank)
        print(winner)

        if (player1.rank > player2.rank and winner == player1) or (player1.rank < player2.rank and winner == player2):
            print('Entré')
            self._swap_ranks(player1, player2)

    def _swap_ranks(self, winner, loser):
        winner.rank, loser.rank = loser.rank, winner.rank

    def get_player(self, name):
        """Retrieve a player by name."""
        for player in self.players:
            if player.name == name:
                return player
        return None  # In case the player is not found

    def get_ranking(self):
        return sorted(self.players, key=lambda p: p.rank)

    def get_matches(self):
        return self.matches


# Ladder system instance
ladder = Ladder()


def save_to_google_sheets():
    """Saves the ranking and matches to Google Sheets."""
    
    # Convert players to a list of lists (each player to a row of data)
    ranking_data = [['Name', 'Rank', 'Age', 'Email']] + [
        [p.name, p.rank, p.age, p.email] for p in ladder.players
    ]
    
    # Convert matches to a list of lists (each match to a row of data)
    matches_data = [['Player 1', 'Player 2', 'Winner', 'Sets', 'Time', 'Comment']] + [
        [m.player1.name, m.player2.name, m.result.name if isinstance(m.result, Player) else m.result,
         str(m.sets), str(m.time), m.comment]
        for m in ladder.matches
    ]

    # Write ranking data to the Ranking sheet
    sheet.values().update(spreadsheetId=SHEET_ID, range=RANGE_NAME_RANKING,
                          valueInputOption="RAW", body={"values": ranking_data}).execute()
    
    # Write matches data to the Matches sheet
    sheet.values().update(spreadsheetId=SHEET_ID, range=RANGE_NAME_MATCHES,
                          valueInputOption="RAW", body={"values": matches_data}).execute()


def load_from_google_sheets():
    """Loads the ranking and matches from Google Sheets."""
    
    # Load ranking data from the Ranking sheet
    ranking_result = sheet.values().get(spreadsheetId=SHEET_ID, range=RANGE_NAME_RANKING).execute()
    ranking_values = ranking_result.get('values', [])
    print("--------")
    print(ranking_values)
    print("--------")
    # Load matches data from the Matches sheet
    matches_result = sheet.values().get(spreadsheetId=SHEET_ID, range=RANGE_NAME_MATCHES).execute()
    matches_values = matches_result.get('values', [])

    # Restore players
    ladder.players = []
    for row in ranking_values[1:]:
        player = Player(row[0], int(row[1]), int(row[2]), row[3])
        ladder.add_player(player)

    # Restore matches
    ladder.matches = []
    for row in matches_values[1:]:
        player1 = next(p for p in ladder.players if p.name == row[0])
        player2 = next(p for p in ladder.players if p.name == row[1])
        winner = row[2]
        sets = row[3]  # Convert the string of sets to a list of tuples
        time = row[4]
        comment = row[5]  # Get comment from the row
        match = Match(player1, player2, winner, sets, time, comment)
        ladder.matches.append(match)
        


@app.route('/')
def index():
    load_from_google_sheets()
    players = ladder.get_ranking()
    return render_template('index.html', players=players)


@app.route('/ranking')
def ranking():
    load_from_google_sheets()
    players = ladder.get_ranking()
    return render_template('ranking.html', players=players)


@app.route('/matches')
def matches():
    load_from_google_sheets()
    matches = ladder.get_matches()

    # Convert time string to datetime object and format the date in Python
    for match in matches:
        match.time_obj = datetime.strptime(match.time, '%Y-%m-%d %H:%M:%S')  # Parse the datetime object
        match.formatted_time = match.time_obj.strftime('%Y-%m-%d')  # Create a formatted date string

    # Sort matches by time (most recent first)
    matches.sort(key=lambda x: x.time_obj, reverse=True)

    # Group matches by month and year
    grouped_matches = {}
    for match in matches:
        print(match.result)
        # Create a key based on month and year

        match_month_year = match.time_obj.strftime('%B %Y')
        if match_month_year not in grouped_matches:
            grouped_matches[match_month_year] = []
        grouped_matches[match_month_year].append(match)

    return render_template('matches.html', grouped_matches=grouped_matches)




@app.route('/add_match', methods=['GET', 'POST'])
def add_match():
    error_message = None  # Variable para el mensaje de error
    
    # Verificar cambios más recientes en Google Sheets antes de registrar el partido
    load_from_google_sheets()

    if request.method == 'POST':
        player1_name = request.form['player1']
        player2_name = request.form['player2']
        winner = request.form['winner']
        sets = request.form['sets']
        comment = request.form['comment']  # Get the comment from the form

        player1 = ladder.get_player(player1_name)
        player2 = ladder.get_player(player2_name)

        # Validar la diferencia de rango (debería ser <= 2)
        if abs(player1.rank - player2.rank) > ladder.min_rank_difference:
            error_message = f"{player1.name} y {player2.name} están separados por más de {ladder.min_rank_difference} rangos."
            return render_template('add_match.html', players=ladder.players, error=error_message)

        match_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        # Si no hay error, proceder a registrar el partido
        try:
            if winner == 'player1':
                ladder.record_match(player1, player2, player1, sets, match_time, comment)
            else:
                ladder.record_match(player1, player2, player2, sets, match_time, comment)

            save_to_google_sheets()  # Guardar cambios en Google Sheets
            return redirect(url_for('index'))
        except ValueError as e:
            error_message = str(e)
    
    # Si es una solicitud GET o hay un error, renderizar el formulario con los jugadores y el mensaje de error
    return render_template('add_match.html', players=ladder.players, error=error_message)


@app.route('/filter_players', methods=['POST'])
def filter_players():
    """Handle AJAX request to filter players based on rank difference."""
    player1_name = request.json.get('player1')
    player1 = ladder.get_player(player1_name)
    
    if not player1:
        return {"error": "Player not found"}, 400

    # Filter players within 2 ranks of player1
    eligible_players = [player.name for player in ladder.players if abs(player.rank - player1.rank) <= ladder.min_rank_difference and player != player1]

    return {"players": eligible_players}


@app.route('/add_player')
def add_player_form():
    return render_template('add_player.html')


@app.route('/add_player', methods=['POST'])
def add_player():
    # Verificar los cambios más recientes en Google Sheets antes de hacer cualquier operación
    load_from_google_sheets()

    name = request.form['name']
    age = int(request.form['age'])
    email = request.form['email']

    # The new player gets the last rank position
    new_rank = len(ladder.players) + 1
    new_player = Player(name, new_rank, age, email)
    ladder.add_player(new_player)

    save_to_google_sheets()  # Guardar cambios en Google Sheets después de agregar al jugador

    return redirect(url_for('index'))


if __name__ == '__main__':
    # Inicialmente, cargar los datos desde Google Sheets
    load_from_google_sheets()
    app.run(debug=True)