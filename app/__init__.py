#===========================================================
# App Creation and Launch
#===========================================================

from flask import Flask, render_template, request, flash, redirect, session
from werkzeug.security import generate_password_hash, check_password_hash
import html

from app.helpers.session import init_session
from app.helpers.db      import connect_db
from app.helpers.errors  import init_error, not_found_error
from app.helpers.logging import init_logging
from app.helpers.auth    import login_required
from app.helpers.time    import init_datetime, utc_timestamp, utc_timestamp_now


# Create the app
app = Flask(__name__)

# Configure app
init_session(app)   # Setup a session for messages, etc.
init_logging(app)   # Log requests
init_error(app)     # Handle errors and exceptions
init_datetime(app)  # Handle UTC dates in timestamps


#-----------------------------------------------------------
# Home page route
#-----------------------------------------------------------

@app.get("/")
def show_all_teams():
    with connect_db() as client:
        # Get all the things from the DB
        sql = "SELECT * FROM teams"
        params=[]
        result = client.execute(sql, params)
        teams = result.rows

        # And show them on the page
        return render_template("pages/home.jinja", teams=teams)


#-----------------------------------------------------------
# Thing page route - Show details of a single thing
#-----------------------------------------------------------
@app.get("/team/<string:code>")
def show_one_team(code):
    with connect_db() as client:
        # Get the thing details from the DB, including the owner info
        sql = """
            SELECT teams.code,
                   teams.name,
                   teams.description,
                   teams.website,
                   teams.manager,
                   users.id,
                   users.username

            FROM teams
            JOIN users ON teams.manager = users.id

            WHERE teams.code=?
        """
        params = [code]
        result = client.execute(sql, params)

        # Did we get a result?
        if not result.rows:
            # No, so show error
            return not_found_error()
        
        # yes, so show it on the page
        team = result.rows[0]

        # Get the thing details from the DB, including the owner info
        sql = "SELECT * FROM players WHERE team=?"
        params = [code]
        result = client.execute(sql, params)

        players = result.rows
        
        return render_template("pages/team.jinja", team=team, players=players)
        


#-----------------------------------------------------------
# Route for adding a team, using data posted from a form
# - Restricted to logged in users
#-----------------------------------------------------------
@app.post("/add-team")
@login_required
def add_a_team():
    # Get the data from the form
    name = request.form.get("name")
    code = request.form.get("code")
    desc = request.form.get("description")
    site = request.form.get("website")

    # Sanitise the text inputs
    name = html.escape(name)
    code = html.escape(code)
    desc = html.escape(desc)
    site = html.escape(site)

    #Format the text capitalization
    name = name.title()
    code = code.upper()

    # Get the user id from the session
    user_id = session["user_id"]

    with connect_db() as client:
        # Add the thing to the DB
        sql = "INSERT INTO teams (code, name, description, website, manager) VALUES (?, ?, ?, ?, ?)"
        params = [code, name, desc, site, user_id]
        client.execute(sql, params)

        # Go back to the home page
        flash(f"Team '{name}' added", "success")
        return redirect("/")


#-----------------------------------------------------------
# Route for deleting a team, Code given in the route
# - Restricted to logged in users
#-----------------------------------------------------------
@app.get("/delete-team/<string:code>")
@login_required
def delete_a_team(code):
    # Get the user id from the session
    user_id = session["user_id"]

    with connect_db() as client:
        # Delete the thing from the DB only if we own it
        sql = "DELETE FROM teams WHERE code=? AND manager=?"
        params = [code, user_id]
        client.execute(sql, params)

        # Go back to the home page
        flash(f"Team {code} deleted", "success")
        return redirect("/")

#-----------------------------------------------------------
# Route for adding a player, using data posted from a form
# - Restricted to logged in users
#-----------------------------------------------------------
@app.post("/add-player")
@login_required
def add_a_player():
    # Get the data from the form
    name = request.form.get("name")
    note = request.form.get("note")
    team = request.form.get("team")

    # Sanitise the text inputs
    name = html.escape(name)
    note = html.escape(note)
    team = html.escape(team)

    #Format the text capitalisation
    name = name.title()

    # Get the user id from the session
    user_id = session["user_id"]

    with connect_db() as client:
        # Add the thing to the DB
        sql = "INSERT INTO players (name, notes, team) VALUES (?, ?, ?)"
        params = [name, note, team]
        client.execute(sql, params)

        # Go back to the home page
        flash(f"Player '{name}' added to team {team}", "success")
        return redirect(f"/team/{team}") #redirect to the page the user was on

#-----------------------------------------------------------
# Route for deleting a player, Id given in the route
# - Restricted to logged in users
#-----------------------------------------------------------
@app.get("/delete-player/<string:code>/<int:id>")
@login_required
def delete_a_player(code, id):
    
    with connect_db() as client:
        # Delete the thing from the DB only if we own it
        sql = "DELETE FROM players WHERE id=? AND team=?"
        params = [id, code]
        client.execute(sql, params)

        # Go back to the home page
        flash(f"Player {id} deleted", "success")
        return redirect(f"/team/{code}")

#-----------------------------------------------------------
# User registration form route
#-----------------------------------------------------------
@app.get("/register")
def register_form():
    return render_template("pages/register.jinja")


#-----------------------------------------------------------
# User login form route
#-----------------------------------------------------------
@app.get("/login")
def login_form():
    return render_template("pages/login.jinja")


#-----------------------------------------------------------
# Route for adding a user when registration form submitted
#-----------------------------------------------------------
@app.post("/add-user")
def add_user():
    # Get the data from the form
    name = request.form.get("name")
    username = request.form.get("username")
    password = request.form.get("password")

    #Format the text capitalisation
    name = name.title()

    with connect_db() as client:
        # Attempt to find an existing record for that user
        sql = "SELECT * FROM users WHERE username = ?"
        params = [username]
        result = client.execute(sql, params)

        # No existing record found, so safe to add the user
        if not result.rows:
            # Sanitise the name
            name = html.escape(name)

            # Salt and hash the password
            hash = generate_password_hash(password)

            # Add the user to the users table
            sql = "INSERT INTO users (name, username, password_hash) VALUES (?, ?, ?)"
            params = [name, username, hash]
            client.execute(sql, params)

            # And let them know it was successful and they can login
            flash("Registration successful", "success")
            return redirect("/login")

        # Found an existing record, so prompt to try again
        flash("Username already exists. Try again...", "error")
        return redirect("/register")


#-----------------------------------------------------------
# Route for processing a user login
#-----------------------------------------------------------
@app.post("/login-user")
def login_user():
    # Get the login form data
    username = request.form.get("username")
    password = request.form.get("password")

    with connect_db() as client:
        # Attempt to find a record for that user
        sql = "SELECT * FROM users WHERE username = ?"
        params = [username]
        result = client.execute(sql, params)

        # Did we find a record?
        if result.rows:
            # Yes, so check password
            user = result.rows[0]
            hash = user["password_hash"]

            # Hash matches?
            if check_password_hash(hash, password):
                # Yes, so save info in the session
                session["user_id"]   = user["id"]
                session["user_name"] = user["name"]
                session["logged_in"] = True

                # And head back to the home page
                flash("Login successful", "success")
                return redirect("/")

        # Either username not found, or password was wrong
        flash("Invalid credentials", "error")
        return redirect("/login")


#-----------------------------------------------------------
# Route for processing a user logout
#-----------------------------------------------------------
@app.get("/logout")
def logout():
    # Clear the details from the session
    session.pop("user_id", None)
    session.pop("user_name", None)
    session.pop("logged_in", None)

    # And head back to the home page
    flash("Logged out successfully", "success")
    return redirect("/")

