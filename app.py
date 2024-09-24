from flask import Flask, render_template, request, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
import os
from datetime import datetime
from flask_migrate import Migrate

app = Flask(__name__)

EXCEL_FILE = 'ladder_data.xlsx'

# Database setup
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///ladder.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

migrate = Migrate(app, db)

class Player(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    age = db.Column(db.Integer, nullable=False)
    email = db.Column(db.String(120), nullable=False, unique=True)
    rank = db.Column(db.Integer, nullable=False)

    def __init__(self, name, rank, age, email):
        self.name = name
        self.rank = rank
        self.age = age
        self.email = email


class Match(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    player1_id = db.Column(db.Integer, db.ForeignKey('player.id'), nullable=False)
    player2_id = db.Column(db.Integer, db.ForeignKey('player.id'), nullable=False)
    winner = db.Column(db.String(100), nullable=False)
    sets = db.Column(db.String(100), nullable=False)
    date = db.Column(db.DateTime, default=datetime.utcnow)
    
    player1 = db.relationship('Player', foreign_keys=[player1_id])
    player2 = db.relationship('Player', foreign_keys=[player2_id])


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

@app.route('/')
def index():
    # Fetch players ordered by their rank directly from the database
    players = Player.query.order_by(Player.rank).all()
    return render_template('index.html', players=players)


@app.route('/ranking')
def ranking():
    players = Player.query.order_by(Player.rank).all()
    print("Fetching ranking page with players:", players)  # Debugging line
    return render_template('ranking.html', players=players)


@app.route('/matches')
def matches():
    matches = Match.query.all()
    return render_template('matches.html', matches=matches)


@app.route('/add_match', methods=['GET', 'POST'])
def add_match():
    if request.method == 'POST':
        player1_name = request.form['player1']
        player2_name = request.form['player2']
        winner_name = request.form['winner']
        sets = request.form['sets']

        player1 = Player.query.filter_by(name=player1_name).first()
        player2 = Player.query.filter_by(name=player2_name).first()

        if not player1 or not player2:
            return render_template('add_match.html', players=Player.query.all(), error="One or both players not found.")

        # Record the match in the database
        new_match = Match(player1_id=player1.id, player2_id=player2.id, winner=winner_name, sets=sets)
        db.session.add(new_match)

        # Update player rankings
        if winner_name == 'player1':
            winner = player1
            loser = player2
        else:
            winner = player2
            loser = player1

        # Adjust rankings based on the winner
        if winner.rank > loser.rank:  # Ensure the winner's rank is always higher (lower number)
            winner.rank, loser.rank = loser.rank, winner.rank
        else:
            winner.rank, loser.rank = winner.rank + 1, loser.rank - 1  # Adjust ranks accordingly

        # Save changes to the players
        db.session.commit()

        return redirect(url_for('index'))

    # If it's a GET request, show the form
    players = Player.query.all()
    return render_template('add_match.html', players=players)

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


@app.route('/add_player', methods=['GET', 'POST'])
def add_player():
    if request.method == 'POST':
        name = request.form['name']
        age = int(request.form['age'])
        email = request.form['email']

        # The new player gets the last rank position
        last_rank = Player.query.order_by(Player.rank.desc()).first()
        new_rank = last_rank.rank + 1 if last_rank else 1  # If no players exist, start at rank 1
        new_player = Player(name=name, rank=new_rank, age=age, email=email)

        db.session.add(new_player)
        db.session.commit()

        return redirect(url_for('index'))

    return render_template('add_player.html')


if __name__ == '__main__':
    app.run(debug=True)