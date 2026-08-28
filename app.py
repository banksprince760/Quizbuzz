import os
import json
import gzip
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

COMPRESSED_QUESTIONS_FILE = BASE_DIR / "questions.json.gz"

DATABASE_FILE = BASE_DIR / "quizbuzz.db"


# ============================================================
# QUIZ SETTINGS
# ============================================================

QUIZ_LENGTH = 10


# ============================================================
# CATEGORIES
# ============================================================

CATEGORY_LABELS = {
    "civil-services-central": "Civil Services & Central Government",
    "state-civil-services": "State Civil Services",
    "banking-finance": "Banking, Insurance & Finance",
    "defence-paramilitary": "Defence & Paramilitary",
    "railway-recruitment": "Railway & Other Recruitment",
    "teaching": "Teaching & Research",
    "engineering": "Engineering",
    "medical": "Medical & Allied Sciences",
    "management": "Management",
    "law": "Law",
    "commerce-professional": "Commerce & Professional",
    "university-admission": "General University Admission",
    "physical": "Physical Education",
    "sports": "Sports",
    "music": "Music",
}

CATEGORY_ICONS = {
    "civil-services-central": "🏛️",
    "state-civil-services": "🗺️",
    "banking-finance": "🏦",
    "defence-paramilitary": "🛡️",
    "railway-recruitment": "🚆",
    "teaching": "📚",
    "engineering": "⚙️",
    "medical": "🩺",
    "management": "📊",
    "law": "⚖️",
    "commerce-professional": "💼",
    "university-admission": "🎓",
    "physical": "💪",
    "sports": "🏆",
    "music": "🎵",
}


# ============================================================
# QUESTIONS
# ============================================================

QUESTION_DATA = {}


def load_questions():

    global QUESTION_DATA

    if not QUESTIONS_FILE.exists() and not COMPRESSED_QUESTIONS_FILE.exists():

        print(
            f"WARNING: questions.json not found: "
            f"{QUESTIONS_FILE}"
        )

        QUESTION_DATA = {}

        return

    try:

        opener = gzip.open if COMPRESSED_QUESTIONS_FILE.exists() else open
        source_file = COMPRESSED_QUESTIONS_FILE if COMPRESSED_QUESTIONS_FILE.exists() else QUESTIONS_FILE

        with opener(source_file, "rt", encoding="utf-8") as file:

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

    for key in CATEGORY_LABELS:

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
# TEST INSTRUCTIONS
# ============================================================

@app.route("/instructions/<category>/<path:exam>")
@login_required
def instructions(category, exam):

    if category not in CATEGORY_LABELS:
        abort(404)

    if exam not in get_available_exams(category):
        abort(404)

    return render_template(
        "instructions.html",
        category=category,
        category_label=CATEGORY_LABELS[category],
        exam=exam,
        total=min(len(get_playable_questions(category, exam)), QUIZ_LENGTH),
    )


# ============================================================
# START TEST
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

    if request.form.get("agree") != "1":
        return redirect(url_for("instructions", category=category, exam=exam))

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

    session["answers"] = {}

    session["marked"] = []

    session.pop("last_result", None)

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

    if q_index >= quiz_length:
        q_index = quiz_length - 1
        session["q_index"] = q_index

    current_question = quiz[
        q_index
    ]

    # ========================================================
    # ANSWER
    # ========================================================

    if request.method == "POST":

        action = request.form.get("action", "save_next")
        selected = request.form.get("option")
        answers = dict(session.get("answers", {}))
        marked = set(session.get("marked", []))

        if selected:
            answers[str(q_index)] = selected
        elif action == "save_next":
            answers.pop(str(q_index), None)

        if action == "mark_review":
            marked.add(q_index)
        elif action == "save_next":
            marked.discard(q_index)

        session["answers"] = answers
        session["marked"] = sorted(marked)

        if action == "submit_test":
            return redirect(url_for("submit_test"))

        if action == "previous":
            session["q_index"] = max(0, q_index - 1)
        else:
            session["q_index"] = min(quiz_length - 1, q_index + 1)

        return redirect(url_for("question"))

    return render_template(
        "question.html",
        question=current_question["q"],
        options=current_question["options"],
        q_number=q_index + 1,
        total=quiz_length,
        selected=session.get("answers", {}).get(str(q_index)),
        marked=session.get("marked", []),
        answered_indices=[int(key) for key in session.get("answers", {})],
        category_label=(
            CATEGORY_LABELS.get(
                category,
                category.title()
            )
        ),
        exam=exam
    )


@app.route("/question/<int:index>")
@login_required
def question_at(index):
    category = session.get("category")
    exam = session.get("exam")
    total = min(len(get_playable_questions(category, exam)), QUIZ_LENGTH) if category and exam else 0
    if not 0 <= index < total:
        abort(404)
    session["q_index"] = index
    return redirect(url_for("question"))


@app.route("/submit-test", methods=["GET", "POST"])
@login_required
def submit_test():
    category = session.get("category")
    exam = session.get("exam")
    if not category or not exam:
        return redirect(url_for("index"))

    quiz = get_playable_questions(category, exam)[:QUIZ_LENGTH]
    answers = session.get("answers", {})
    details = []
    correct = wrong = 0
    for index, item in enumerate(quiz):
        selected = answers.get(str(index))
        is_correct = bool(selected and normalize(selected) == normalize(item["answer"]))
        correct += int(is_correct)
        wrong += int(bool(selected) and not is_correct)
        details.append({
            "number": index + 1,
            "question": item["q"],
            "options": item["options"],
            "selected": selected,
            "correct_answer": item["answer"],
            "is_correct": is_correct,
        })

    total = len(quiz)
    unattempted = total - correct - wrong
    save_best_score(round(correct * QUIZ_LENGTH / total) if total else 0)
    result_data = {
        "score": correct,
        "correct": correct,
        "wrong": wrong,
        "unattempted": unattempted,
        "total": total,
        "category": category,
        "exam": exam,
        "details": details,
    }
    session["last_result"] = result_data
    for key in ("category", "exam", "q_index", "score", "answers", "marked"):
        session.pop(key, None)
    return redirect(url_for("result"))


# ============================================================
# RESULT DIRECT URL
# ============================================================

@app.route("/result")
@login_required
def result():
    data = session.get("last_result")
    if not data:
        return redirect(url_for("index"))
    return render_template("result.html", **data)


@app.route("/solutions")
@login_required
def solutions():
    data = session.get("last_result")
    if not data:
        return redirect(url_for("index"))
    return render_template("solutions.html", **data)


# ============================================================
# HEALTH CHECK FOR RENDER
# ============================================================

@app.route("/health")
def health():

    return {
        "status": "ok",
        "questions_file": (
            QUESTIONS_FILE.exists() or COMPRESSED_QUESTIONS_FILE.exists()
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
