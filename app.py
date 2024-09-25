import os
import pandas as pd
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for

app = Flask(__name__)

APP_ROOT = os.path.dirname(os.path.abspath(__file__))
EXCEL_FILE = os.path.join(APP_ROOT, 'ladder_data.xlsx')


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
    def __init__(self, player1, player2, result, sets):
        self.player1 = player1
        self.player2 = player2
        self.result = result
        self.sets = sets

    def __str__(self):
        return f"{self.player1.name} vs {self.player2.name} - Winner: {self.result}, Sets: {self.sets}"


class Ladder:
    def __init__(self, min_rank_difference=2):
        self.players = []
        self.matches = []
        self.min_rank_difference = min_rank_difference

    def add_player(self, player):
        self.players.append(player)

    def record_match(self, player1, player2, winner, sets):
        match = Match(player1, player2, winner, sets)
        self.matches.append(match)

        # Update rankings
        if player1.rank < player2.rank:
            winner, loser = player1, player2
        else:
            winner, loser = player2, player1

        if winner == player1:
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


def save_to_excel():
    """Saves the ranking and matches to an Excel file."""
    ranking_data = [{'Name': p.name, 'Rank': p.rank, 'Age': p.age, 'Email': p.email} for p in ladder.players]
    matches_data = [{
        'Player 1': m.player1.name,
        'Player 2': m.player2.name,
        'Winner': m.result,
        'Sets': str(m.sets),
        'Time': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    } for m in ladder.matches]

    with pd.ExcelWriter(EXCEL_FILE, mode='w') as writer:
        pd.DataFrame(ranking_data).to_excel(writer, sheet_name='Ranking', index=False)
        pd.DataFrame(matches_data).to_excel(writer, sheet_name='Matches', index=False)


def load_from_excel():
    """Loads the ranking and matches from the Excel file if it exists."""
    if os.path.exists(EXCEL_FILE):
        data = pd.read_excel(EXCEL_FILE, sheet_name=None)

        ranking_df = data['Ranking']
        matches_df = data['Matches']

        # Restore players
        ladder.players = []
        for _, row in ranking_df.iterrows():
            player = Player(row['Name'], row['Rank'], row['Age'], row['Email'])
            ladder.add_player(player)

        # Restore matches
        ladder.matches = []
        for _, row in matches_df.iterrows():
            player1 = next(p for p in ladder.players if p.name == row['Player 1'])
            player2 = next(p for p in ladder.players if p.name == row['Player 2'])
            winner = row['Winner']
            sets = eval(row['Sets'])  # Convert the string of sets to a list of tuples
            match = Match(player1, player2, winner, sets)
            ladder.matches.append(match)


@app.route('/')
def index():
    players = ladder.get_ranking()
    return render_template('index.html', players=players)


@app.route('/ranking')
def ranking():
    players = ladder.get_ranking()
    return render_template('ranking.html', players=players)


@app.route('/matches')
def matches():
    matches = ladder.get_matches()
    return render_template('matches.html', matches=matches)


@app.route('/add_match', methods=['GET', 'POST'])
def add_match():
    error_message = None  # Variable to store error message
    
    if request.method == 'POST':
        player1_name = request.form['player1']
        player2_name = request.form['player2']
        winner = request.form['winner']
        sets = request.form['sets']

        player1 = ladder.get_player(player1_name)
        player2 = ladder.get_player(player2_name)

        # Validate the rank difference (should be <= 2)
        if abs(player1.rank - player2.rank) > ladder.min_rank_difference:
            error_message = f"{player1.name} and {player2.name} are more than {ladder.min_rank_difference} ranks apart."
            return render_template('add_match.html', players=ladder.players, error=error_message)

        # If no error, proceed to record the match
        try:
            if winner == 'player1':
                ladder.record_match(player1, player2, player1, sets)
            else:
                ladder.record_match(player1, player2, player2, sets)

            save_to_excel()  # Save changes to Excel
            return redirect(url_for('index'))
        except ValueError as e:
            error_message = str(e)
    
    # If GET request or there is an error, render the form with players and error message
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
    name = request.form['name']
    age = int(request.form['age'])
    email = request.form['email']

    # The new player gets the last rank position
    new_rank = len(ladder.players) + 1
    new_player = Player(name, new_rank, age, email)
    ladder.add_player(new_player)
    save_to_excel()  # Save to Excel after adding the player

    return redirect(url_for('index'))


if __name__ == '__main__':
    load_from_excel()  # Load data from Excel when the app starts
    app.run(debug=True)