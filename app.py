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
RANGE_NAME_RANKING = 'Ranking!A1:D'
RANGE_NAME_MATCHES = 'Matches!A1:F'

# Set up the credentials and Google Sheets API
SCOPES = ['https://www.googleapis.com/auth/spreadsheets']
service_account_info = json.loads(os.getenv('GOOGLE_APPLICATION_CREDENTIALS_JSON'))
creds = Credentials.from_service_account_info(service_account_info, scopes=SCOPES)
service = build('sheets', 'v4', credentials=creds)
sheet = service.spreadsheets()


class Player:
    def __init__(self, name, initial_rank, age, email):
        self.name = name
        self.rank = initial_rank  # Rank is stored as an attribute
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
        self.comment = comment

    def __str__(self):
        return f"{self.player1.name} vs {self.player2.name} - Winner: {self.result}, Sets: {self.sets}"

    def to_dict(self):
        return {
            "player1": self.player1.name,
            "player2": self.player2.name,
            "result": self.result,
            "sets": self.sets,
            "time": self.time,
            "comment": self.comment
        }


class Ladder:
    def __init__(self, min_rank_difference=6, downrank_rank_difference=3, uprank_rank_difference=3):
        self.players = []  # The players list is not assumed to be in ranking order.
        self.matches = []
        self.min_rank_difference = min_rank_difference
        self.downrank_rank_difference = downrank_rank_difference
        self.uprank_rank_difference = uprank_rank_difference

    def add_player(self, player):
        self.players.append(player)

    def record_match(self, player1, player2, winner, sets, time, comment):
        if not comment:
            comment = 'None'
        match = Match(player1, player2, winner, sets, time, comment)
        self.matches.append(match)

        # Create a sorted list of players based on their rank attribute (rank 1 is best)
        sorted_players = sorted(self.players, key=lambda p: p.rank)
        # Find the indices in the sorted order
        idx1 = next(i for i, p in enumerate(sorted_players) if p.name == player1.name)
        idx2 = next(i for i, p in enumerate(sorted_players) if p.name == player2.name)

        # Determine the better ranked (lower rank number) and the worse ranked player.
        if idx1 < idx2:
            better = player1
            worse = player2
            better_index, worse_index = idx1, idx2
        else:
            better = player2
            worse = player1
            better_index, worse_index = idx2, idx1

        # If the better ranked player wins, no ranking change is needed.
        if winner == better:
            return

        # Upset occurred: the better ranked player lost.
        rank_diff = worse_index - better_index

        if rank_diff <= self.min_rank_difference:
            # For a small difference, simply swap the players’ rank values.
            better.rank, worse.rank = worse.rank, better.rank
        else:
            # For a significant upset, adjust rankings:
            # 1. Determine new positions in the sorted order.
            #    - The upset winner moves up by uprank_rank_difference positions.
            #    - The better (losing) player moves down by downrank_rank_difference positions.
            winner_index = next(i for i, p in enumerate(sorted_players) if p.name == winner.name)
            new_winner_index = max(0, winner_index - self.uprank_rank_difference)
            # Remove and reinsert the upset winner.
            sorted_players.pop(winner_index)
            sorted_players.insert(new_winner_index, winner)

            # Now, adjust the loser (the originally better player).
            loser_index = next(i for i, p in enumerate(sorted_players) if p.name == better.name)
            new_loser_index = min(len(sorted_players) - 1, loser_index + self.downrank_rank_difference)
            sorted_players.pop(loser_index)
            sorted_players.insert(new_loser_index, better)

            # Reassign sequential rank numbers (starting at 1) based on new sorted order.
            for i, player in enumerate(sorted_players):
                player.rank = i + 1

        # Optionally, update self.players to match the new order.
        # (This is not strictly necessary since ranking is stored in each player's attribute.)
        # self.players = sorted_players

    def get_player(self, name):
        for player in self.players:
            if player.name == name:
                return player
        return None

    def get_ranking(self):
        # Return players sorted by their rank attribute (lowest rank number first)
        return sorted(self.players, key=lambda p: p.rank)

    def get_matches(self):
        return self.matches


# Ladder system instance
ladder = Ladder()


def save_to_google_sheets():
    ranking_data = [['Name', 'Rank', 'Age', 'Email']] + [
        [p.name, p.rank, p.age, p.email] for p in ladder.players
    ]
    matches_data = [['Player 1', 'Player 2', 'Winner', 'Sets', 'Time', 'Comment']] + [
        [m.player1.name, m.player2.name, m.result.name if isinstance(m.result, Player) else m.result,
         str(m.sets), str(m.time), m.comment]
        for m in ladder.matches
    ]

    sheet.values().update(
        spreadsheetId=SHEET_ID,
        range=RANGE_NAME_RANKING,
        valueInputOption="RAW",
        body={"values": ranking_data}
    ).execute()
    
    sheet.values().update(
        spreadsheetId=SHEET_ID,
        range=RANGE_NAME_MATCHES,
        valueInputOption="RAW",
        body={"values": matches_data}
    ).execute()


def load_from_google_sheets():
    ranking_result = sheet.values().get(spreadsheetId=SHEET_ID, range=RANGE_NAME_RANKING).execute()
    ranking_values = ranking_result.get('values', [])
    print("--------")
    print(ranking_values)
    print("--------")
    matches_result = sheet.values().get(spreadsheetId=SHEET_ID, range=RANGE_NAME_MATCHES).execute()
    matches_values = matches_result.get('values', [])

    ladder.players = []
    for row in ranking_values[1:]:
        player = Player(row[0], int(row[1]), int(row[2]), row[3])
        ladder.add_player(player)
    # Ensure players are sorted by their rank attribute
    ladder.players.sort(key=lambda p: p.rank)

    ladder.matches = []
    for row in matches_values[1:]:
        player1 = next(p for p in ladder.players if p.name == row[0])
        player2 = next(p for p in ladder.players if p.name == row[1])
        winner = row[2]
        sets = row[3]
        time = row[4]
        comment = row[5]
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

    for match in matches:
        match.time_obj = datetime.strptime(match.time, '%Y-%m-%d %H:%M:%S')
        match.formatted_time = match.time_obj.strftime('%Y-%m-%d')

    matches.sort(key=lambda x: x.time_obj, reverse=True)

    grouped_matches = {}
    for match in matches:
        match_month_year = match.time_obj.strftime('%B %Y')
        if match_month_year not in grouped_matches:
            grouped_matches[match_month_year] = []
        grouped_matches[match_month_year].append(match)

    return render_template('matches.html', grouped_matches=grouped_matches)


@app.route('/add_match', methods=['GET', 'POST'])
def add_match():
    error_message = None
    load_from_google_sheets()

    if request.method == 'POST':
        player1_name = request.form['player1']
        player2_name = request.form['player2']
        winner = request.form['winner']
        sets = request.form['sets']
        comment = request.form['comment']

        player1 = ladder.get_player(player1_name)
        player2 = ladder.get_player(player2_name)

        match_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        try:
            if winner == 'player1':
                ladder.record_match(player1, player2, player1, sets, match_time, comment)
            else:
                ladder.record_match(player1, player2, player2, sets, match_time, comment)

            save_to_google_sheets()
            return redirect(url_for('index'))
        except ValueError as e:
            error_message = str(e)
    
    return render_template('add_match.html', players=ladder.players, error=error_message)


@app.route('/filter_players', methods=['POST'])
def filter_players():
    player1_name = request.json.get('player1')
    player1 = ladder.get_player(player1_name)
    
    if not player1:
        return {"error": "Player not found"}, 400

    eligible_players = [
        player.name for player in ladder.players
        if abs(player.rank - player1.rank) <= ladder.min_rank_difference and player != player1
    ]

    return {"players": eligible_players}


@app.route('/add_player')
def add_player_form():
    return render_template('add_player.html')


@app.route('/add_player', methods=['POST'])
def add_player():
    load_from_google_sheets()

    name = request.form['name']
    age = int(request.form['age'])
    email = request.form['email']

    new_rank = len(ladder.players) + 1
    new_player = Player(name, new_rank, age, email)
    ladder.add_player(new_player)

    save_to_google_sheets()

    return redirect(url_for('index'))


if __name__ == '__main__':
    load_from_google_sheets()
    app.run(debug=True)