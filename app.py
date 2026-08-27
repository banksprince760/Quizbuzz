import os
import json
import sqlite3
from pathlib import Path
from functools import wraps

from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    session,
    abort,
)

from werkzeug.security import (
    generate_password_hash,
    check_password_hash,
)


# ============================================================
# APP
# ============================================================

app = Flask(__name__)

app.secret_key = os.environ.get(
    "SECRET_KEY",
    "quizbuzz-change-this-secret-key"
)


# ============================================================
# PATHS
# ============================================================

BASE_DIR = Path(__file__).resolve().parent

QUESTIONS_FILE = BASE_DIR / "questions.json"

DATABASE_FILE = BASE_DIR / "quizbuzz.db"


# ============================================================
# QUIZ SETTINGS
# ============================================================

TIME_PER_QUESTION = 3

QUIZ_LENGTH = 10


# ============================================================
# CATEGORIES
# ============================================================

CATEGORY_LABELS = {
    "teaching": "Teaching",
    "music": "Music",
    "sports": "Sports",
    "physical": "Physical",
}

CATEGORY_ICONS = {
    "teaching": "📚",
    "music": "🎵",
    "sports": "🏆",
    "physical": "💪",
}


# ============================================================
# QUESTIONS
# ============================================================

QUESTION_DATA = {}


def load_questions():

    global QUESTION_DATA

    if not QUESTIONS_FILE.exists():

        print(
            f"WARNING: questions.json not found: "
            f"{QUESTIONS_FILE}"
        )

        QUESTION_DATA = {}

        return

    try:

        with QUESTIONS_FILE.open(
            "r",
            encoding="utf-8"
        ) as file:

            data = json.load(file)

        if not isinstance(data, dict):

            print(
                "ERROR: questions.json root "
                "must be an object."
            )

            QUESTION_DATA = {}

            return

        QUESTION_DATA = data

        print(
            "Questions loaded successfully."
        )

        print(
            "Categories:",
            list(QUESTION_DATA.keys())
        )

    except json.JSONDecodeError as error:

        print(
            "ERROR: questions.json invalid:",
            error
        )

        QUESTION_DATA = {}

    except Exception as error:

        print(
            "ERROR loading questions:",
            error
        )

        QUESTION_DATA = {}


load_questions()


# ============================================================
# DATABASE
# ============================================================

def get_db():

    connection = sqlite3.connect(
        DATABASE_FILE
    )

    connection.row_factory = sqlite3.Row

    return connection


def init_db():

    connection = get_db()

    cursor = connection.cursor()

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            best_score INTEGER DEFAULT 0,
            name TEXT DEFAULT '',
            email TEXT DEFAULT '',
            mobile TEXT DEFAULT ''
        )
        """
    )

    cursor.execute(
        "PRAGMA table_info(users)"
    )

    columns = [
        row["name"]
        for row in cursor.fetchall()
    ]

    if "name" not in columns:

        cursor.execute(
            """
            ALTER TABLE users
            ADD COLUMN name TEXT DEFAULT ''
            """
        )

    if "email" not in columns:

        cursor.execute(
            """
            ALTER TABLE users
            ADD COLUMN email TEXT DEFAULT ''
            """
        )

    if "mobile" not in columns:

        cursor.execute(
            """
            ALTER TABLE users
            ADD COLUMN mobile TEXT DEFAULT ''
            """
        )

    connection.commit()

    connection.close()

    print(
        "Database initialized successfully."
    )


init_db()


# ============================================================
# LOGIN REQUIRED
# ============================================================

def login_required(function):

    @wraps(function)
    def decorated_function(
        *args,
        **kwargs
    ):

        if not session.get("user_id"):

            return redirect(
                url_for("login")
            )

        return function(
            *args,
            **kwargs
        )

    return decorated_function


# ============================================================
# QUESTION HELPERS
# ============================================================

def normalize(value):

    return (
        str(value or "")
        .strip()
        .lower()
        .rstrip(".")
    )


def get_category_exams(category):

    category_data = QUESTION_DATA.get(
        category,
        {}
    )

    if not isinstance(
        category_data,
        dict
    ):

        return {}

    exams = category_data.get(
        "exams",
        {}
    )

    if not isinstance(
        exams,
        dict
    ):

        return {}

    return exams


def get_playable_questions(
    category,
    exam
):

    exams = get_category_exams(
        category
    )

    raw_questions = exams.get(
        exam,
        []
    )

    if not isinstance(
        raw_questions,
        list
    ):

        return []

    playable = []

    for item in raw_questions:

        if not isinstance(
            item,
            dict
        ):

            continue

        question_text = str(
            item.get(
                "q",
                ""
            )
        ).strip()

        answer = str(
            item.get(
                "answer",
                ""
            )
        ).strip()

        options = item.get(
            "options",
            []
        )

        if not question_text:
            continue

        if not answer:
            continue

        if not isinstance(
            options,
            list
        ):

            continue

        clean_options = [
            str(option).strip()
            for option in options
            if str(option).strip()
        ]

        if len(clean_options) < 2:
            continue

        correct_option = None

        for option in clean_options:

            if normalize(option) == normalize(answer):

                correct_option = option
                break

        if correct_option is None:

            for option in clean_options:

                if (
                    normalize(answer).startswith(
                        normalize(option)
                    )
                    or normalize(option).startswith(
                        normalize(answer)
                    )
                ):

                    correct_option = option
                    break

        if correct_option is None:
            continue

        playable.append(
            {
                "q": question_text,
                "options": clean_options,
                "answer": correct_option,
            }
        )

    return playable


def get_available_exams(category):

    exams = get_category_exams(
        category
    )

    available = {}

    for exam_name in exams:

        questions = get_playable_questions(
            category,
            exam_name
        )

        quiz_length = min(
            len(questions),
            QUIZ_LENGTH
        )

        if quiz_length > 0:

            available[exam_name] = (
                quiz_length
            )

    return available


# ============================================================
# SAVE BEST SCORE
# ============================================================

def save_best_score(score):

    user_id = session.get(
        "user_id"
    )

    if not user_id:
        return

    connection = get_db()

    cursor = connection.cursor()

    cursor.execute(
        """
        SELECT best_score
        FROM users
        WHERE id = ?
        """,
        (user_id,)
    )

    row = cursor.fetchone()

    if row:

        old_score = (
            row["best_score"]
            or 0
        )

        if score > old_score:

            cursor.execute(
                """
                UPDATE users
                SET best_score = ?
                WHERE id = ?
                """,
                (
                    score,
                    user_id
                )
            )

            connection.commit()

    connection.close()


# ============================================================
# HOME
# ============================================================

@app.route("/")
@login_required
def index():

    categories = {}

    for key in [
        "teaching",
        "music",
        "sports",
        "physical",
    ]:

        data = QUESTION_DATA.get(
            key,
            {}
        )

        if not get_available_exams(key):
            continue

        categories[key] = {
            "label": data.get(
                "label",
                CATEGORY_LABELS[key]
            ),
            "icon": CATEGORY_ICONS[key],
        }

    username = (
        session.get("name")
        or session.get("username")
        or "Player"
    )

    return render_template(
        "index.html",
        categories=categories,
        username=username
    )


# ============================================================
# EXAMS
# ============================================================

@app.route("/exams/<category>")
@login_required
def exams(category):

    if category not in CATEGORY_LABELS:

        abort(404)

    available_exams = (
        get_available_exams(
            category
        )
    )

    return render_template(
        "exams.html",
        category=category,
        category_label=(
            CATEGORY_LABELS[category]
        ),
        exams=available_exams
    )


# ============================================================
# REGISTER
# ============================================================

@app.route(
    "/register",
    methods=["GET", "POST"]
)
def register():

    if request.method == "POST":

        name = (
            request.form.get("name")
            or ""
        ).strip()

        username = (
            request.form.get("username")
            or ""
        ).strip()

        email = (
            request.form.get("email")
            or ""
        ).strip()

        mobile = (
            request.form.get("mobile")
            or ""
        ).strip()

        password = (
            request.form.get("password")
            or ""
        )

        confirm_password = (
            request.form.get(
                "confirm_password"
            )
            or ""
        )

        if (
            not name
            or not username
            or not email
            or not mobile
            or not password
            or not confirm_password
        ):

            return render_template(
                "register.html",
                error=(
                    "Please sabhi fields fill karein."
                ),
                name=name,
                username=username,
                email=email,
                mobile=mobile
            )

        if password != confirm_password:

            return render_template(
                "register.html",
                error=(
                    "Passwords match nahi kar rahe."
                ),
                name=name,
                username=username,
                email=email,
                mobile=mobile
            )

        if (
            not mobile.isdigit()
            or len(mobile) != 10
        ):

            return render_template(
                "register.html",
                error=(
                    "Mobile number 10 digits ka hona chahiye."
                ),
                name=name,
                username=username,
                email=email,
                mobile=mobile
            )

        if (
            "@" not in email
            or "." not in email
        ):

            return render_template(
                "register.html",
                error=(
                    "Valid email enter karein."
                ),
                name=name,
                username=username,
                email=email,
                mobile=mobile
            )

        connection = get_db()

        cursor = connection.cursor()

        cursor.execute(
            """
            SELECT id
            FROM users
            WHERE LOWER(username) = LOWER(?)
               OR LOWER(email) = LOWER(?)
            LIMIT 1
            """,
            (
                username,
                email
            )
        )

        existing = cursor.fetchone()

        if existing:

            connection.close()

            return render_template(
                "register.html",
                error=(
                    "Username ya email already registered hai."
                ),
                name=name,
                username=username,
                email=email,
                mobile=mobile
            )

        hashed_password = (
            generate_password_hash(
                password
            )
        )

        cursor.execute(
            """
            INSERT INTO users (
                username,
                password,
                best_score,
                name,
                email,
                mobile
            )
            VALUES (?, ?, 0, ?, ?, ?)
            """,
            (
                username,
                hashed_password,
                name,
                email,
                mobile
            )
        )

        connection.commit()

        connection.close()

        return redirect(
            url_for("login")
        )

    return render_template(
        "register.html"
    )


# ============================================================
# LOGIN
# ============================================================

@app.route(
    "/login",
    methods=["GET", "POST"]
)
def login():

    if session.get("user_id"):

        return redirect(
            url_for("index")
        )

    if request.method == "POST":

        username_or_email = (
            request.form.get(
                "username"
            )
            or ""
        ).strip()

        password = (
            request.form.get(
                "password"
            )
            or ""
        )

        connection = get_db()

        cursor = connection.cursor()

        cursor.execute(
            """
            SELECT *
            FROM users
            WHERE LOWER(username) = LOWER(?)
               OR LOWER(email) = LOWER(?)
            LIMIT 1
            """,
            (
                username_or_email,
                username_or_email
            )
        )

        user = cursor.fetchone()

        connection.close()

        if (
            user
            and check_password_hash(
                user["password"],
                password
            )
        ):

            session.clear()

            session["user_id"] = (
                user["id"]
            )

            session["username"] = (
                user["username"]
            )

            session["name"] = (
                user["name"]
            )

            return redirect(
                url_for("index")
            )

        return render_template(
            "login.html",
            error=(
                "Username/email ya password galat hai."
            )
        )

    return render_template(
        "login.html"
    )


# ============================================================
# LOGOUT
# ============================================================

@app.route("/logout")
def logout():

    session.clear()

    return redirect(
        url_for("login")
    )


# ============================================================
# NOTES
# ============================================================

@app.route("/notes")
@login_required
def notes():

    return render_template(
        "notes.html"
    )


# ============================================================
# LEADERBOARD
# ============================================================

@app.route("/leaderboard")
@login_required
def leaderboard():

    connection = get_db()

    cursor = connection.cursor()

    cursor.execute(
        """
        SELECT username, best_score
        FROM users
        ORDER BY
            best_score DESC,
            username ASC
        """
    )

    users = cursor.fetchall()

    connection.close()

    return render_template(
        "leaderboard.html",
        users=users
    )


# ============================================================
# START QUIZ
# ============================================================

@app.route(
    "/start",
    methods=["POST"]
)
@login_required
def start_quiz():

    category = (
        request.form.get(
            "category"
        )
        or ""
    ).strip()

    exam = (
        request.form.get(
            "exam"
        )
        or ""
    ).strip()

    questions = get_playable_questions(
        category,
        exam
    )

    if not questions:

        return redirect(
            url_for(
                "exams",
                category=category
            )
        )

    session["category"] = category

    session["exam"] = exam

    session["q_index"] = 0

    session["score"] = 0

    return redirect(
        url_for("question")
    )


# ============================================================
# QUESTION
# ============================================================

@app.route(
    "/question",
    methods=["GET", "POST"]
)
@login_required
def question():

    category = session.get(
        "category"
    )

    exam = session.get(
        "exam"
    )

    if not category or not exam:

        return redirect(
            url_for("index")
        )

    questions = get_playable_questions(
        category,
        exam
    )

    if not questions:

        return redirect(
            url_for(
                "exams",
                category=category
            )
        )

    quiz = questions[:QUIZ_LENGTH]

    quiz_length = len(quiz)

    q_index = int(
        session.get(
            "q_index",
            0
        )
    )

    # ========================================================
    # RESULT AFTER 10 QUESTIONS
    # ========================================================

    if q_index >= quiz_length:

        final_score = int(
            session.get(
                "score",
                0
            )
        )

        leaderboard_score = round(
            final_score
            * QUIZ_LENGTH
            / quiz_length
        )

        save_best_score(
            leaderboard_score
        )

        result_category = category

        result_exam = exam

        session.pop(
            "category",
            None
        )

        session.pop(
            "exam",
            None
        )

        session.pop(
            "q_index",
            None
        )

        session.pop(
            "score",
            None
        )

        return render_template(
            "result.html",
            score=final_score,
            total=quiz_length,
            category=result_category,
            exam=result_exam
        )

    current_question = quiz[
        q_index
    ]

    # ========================================================
    # ANSWER
    # ========================================================

    if request.method == "POST":

        selected = request.form.get(
            "option"
        )

        timed_out = (
            request.form.get(
                "timed_out"
            )
            == "1"
        )

        correct_answer = (
            current_question[
                "answer"
            ]
        )

        if (
            not timed_out
            and selected is not None
            and normalize(selected)
            == normalize(correct_answer)
        ):

            session["score"] = (
                int(
                    session.get(
                        "score",
                        0
                    )
                )
                + 1
            )

        session["q_index"] = (
            q_index + 1
        )

        return redirect(
            url_for("question")
        )

    return render_template(
        "question.html",
        question=current_question["q"],
        options=current_question["options"],
        q_number=q_index + 1,
        total=quiz_length,
        time_limit=TIME_PER_QUESTION,
        category_label=(
            CATEGORY_LABELS.get(
                category,
                category.title()
            )
        ),
        exam=exam
    )


# ============================================================
# RESULT DIRECT URL
# ============================================================

@app.route("/result")
@login_required
def result():

    return redirect(
        url_for("index")
    )


# ============================================================
# HEALTH CHECK FOR RENDER
# ============================================================

@app.route("/health")
def health():

    return {
        "status": "ok",
        "questions_file": (
            QUESTIONS_FILE.exists()
        ),
        "categories": list(
            QUESTION_DATA.keys()
        ),
    }, 200


# ============================================================
# RUN
# ============================================================

if __name__ == "__main__":

    port = int(
        os.environ.get(
            "PORT",
            10000
        )
    )

    app.run(
        host="0.0.0.0",
        port=port,
        debug=False
    )

