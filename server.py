from datetime import date, datetime, timedelta
import csv
import io
import os
import subprocess

from flask import Flask, Response, redirect, render_template, request, session, url_for

app = Flask(__name__)
app.secret_key = "bus-pass-demo-secret-key-123"

folder = os.path.dirname(os.path.abspath(__file__))
program = os.path.join(folder, "buspass.exe")

# simple login for the demo only, the password sits in the code
adminUser = "admin"
adminPass = "buspass123"

# must match FEE_PER_MONTH in buspass.c
FEE_PER_MONTH = 200

# the fields of one pass, in the order buspass.c prints them, which is also
# the order of the columns in the CSV download
FIELDS = (
    "id", "name", "age", "college", "course", "year", "mobile",
    "source", "destination", "status", "issueDate", "expiryDate", "reason",
)


# ---------- talking to the C program ----------

# run buspass.exe with the given arguments and return what it printed.
# the arguments go as a list, never as one shell string, so names with
# spaces work and nothing can be injected into a command
def runProgram(*args):
    try:
        result = subprocess.run([program, *args], capture_output=True, text=True, cwd=folder, timeout=30)
    except Exception as e:
        return "ERROR: Could not run the bus pass program: " + str(e)

    return result.stdout or result.stderr or "No output from program"


# split the printed lines into students plus the OK and ERROR messages
def readOutput(out):
    students = []
    ok = []
    errors = []

    for line in out.splitlines():
        parts = line.split("|")

        if parts[0].startswith("STU") and len(parts) >= 12:
            students.append(oneStudent(parts))
        elif line.startswith("OK:"):
            ok.append(line[3:].strip())
        elif line.startswith("ERROR:"):
            errors.append(line[6:].strip())

    return {"students": students, "ok": ok, "errors": errors}


# one printed line as a dict the templates can use. the line has 12 fields
# and the reason is only there for cancelled passes, so the list is padded
def oneStudent(parts):
    parts = parts + [""] * (len(FIELDS) - len(parts))
    student = dict(zip(FIELDS, parts))
    student["displayStatus"] = passStatus(student)
    return student


# every student in students.txt
def allStudents():
    return readOutput(runProgram("list"))["students"]


# students matching a search field (id, name, course, source, destination)
def searchStudents(field, text):
    return readOutput(runProgram("search", field, text))["students"]


# the pass with this exact ID, or None
def lookupStudent(studentId, students=None):
    if students is None:
        students = allStudents()

    for student in students:
        if student["id"] == studentId:
            return student

    return None


# ---------- dates and status ----------

# "dd-mm-yyyy" text as a date, None when the text is not a date
def dateValue(text):
    try:
        return datetime.strptime(text, "%d-%m-%Y").date()
    except ValueError:
        return None


# the status the page shows. a pass only looks Expired when it is still
# Active and its expiry date is already over
def passStatus(student):
    if student["status"] == "Cancelled":
        return "Cancelled"

    expiry = dateValue(student["expiryDate"])

    if student["status"] == "Active" and expiry is not None and expiry < date.today():
        return "Expired"

    return "Active"


# the expiry a pass would get if it was renewed today, for the renew page.
# same rule as addMonths in buspass.c: an expired pass counts from today,
# and a month without that day rolls into the next month
def renewalPreview(student, months):
    expiry = dateValue(student["expiryDate"])

    if expiry is None:
        return ""

    base = date.today()

    if expiry > base:
        base = expiry

    month = base.month - 1 + months
    renewed = date(base.year + month // 12, month % 12 + 1, 1) + timedelta(days=base.day - 1)

    return renewed.strftime("%d-%m-%Y")


# passes that are Active and expire within the next few days
def expiringSoon(students, days=7):
    today = date.today()
    limit = today + timedelta(days=days)
    soon = []

    for student in students:
        expiry = dateValue(student["expiryDate"])

        if expiry is not None and student["displayStatus"] == "Active" and today <= expiry <= limit:
            soon.append(student)

    return soon


# how many passes are in each state, for the home and admin pages
def countStudents(students):
    counts = {"total": len(students), "active": 0, "expired": 0, "cancelled": 0}

    for student in students:
        counts[student["displayStatus"].lower()] += 1

    return counts


# ---------- step 1 of the renew and cancel pages ----------

# find the pass to work on. it returns the student, or a list of matches to
# pick from, or an error. one single match goes straight to the details step
def findPass(studentId, field, text):
    if studentId != "":
        student = lookupStudent(studentId)

        if student is None:
            return None, [], ["No student found with ID " + studentId]
    elif text.strip() == "":
        return None, [], ["Please type what to search for."]
    else:
        matches = searchStudents(field, text)

        if len(matches) == 0:
            return None, [], ["No student found for those details."]

        if len(matches) > 1:
            return None, matches, []

        student = matches[0]

    if student["status"] == "Cancelled":
        return student, [], ["This pass is already cancelled"]

    return student, [], []


# ---------- pages ----------

@app.route("/")
def home():
    students = allStudents()
    return render_template("home.html", counts=countStudents(students))


# the register form fields, in the order the C program wants them
REGISTER_FIELDS = ("name", "age", "college", "course", "year", "mobile", "source", "destination")


@app.route("/register", methods=["GET", "POST"])
def register():
    student = None
    errors = []

    if request.method == "POST":
        values = [request.form.get(name, "") for name in REGISTER_FIELDS]
        result = readOutput(runProgram("register", *values))

        if result["students"] and not result["errors"]:
            student = result["students"][0]
        else:
            errors = result["errors"]

    return render_template("register.html", student=student, errors=errors, form=request.form)


@app.route("/search", methods=["GET", "POST"])
def search():
    results = []
    field = "id"
    text = ""

    if request.method == "POST":
        field = request.form.get("field", "id")
        text = request.form.get("text", "")

        if text.strip() != "":
            results = searchStudents(field, text)

    return render_template("search.html", results=results, field=field, text=text)


# renew works in two steps: find the pass, then choose the months.
# a table link lands on step 2 directly with /renew?id=STU1002
@app.route("/renew", methods=["GET", "POST"])
def renew():
    students = allStudents()
    student = None
    matches = []
    ok = []
    errors = []
    field = "id"
    text = ""
    months = 1

    if request.method == "POST" and request.form.get("months", "") != "":
        # step 2: renew the pass
        studentId = request.form.get("id", "")

        try:
            months = int(request.form.get("months", "1"))
        except ValueError:
            months = 1

        result = readOutput(runProgram("renew", studentId, str(months)))

        if result["students"]:
            student = result["students"][0]
            ok = result["ok"]
        else:
            errors = result["errors"]
            student = lookupStudent(studentId, students)
    elif request.method == "POST":
        # step 1: find the pass
        field = request.form.get("field", "id")
        text = request.form.get("text", "")
        student, matches, errors = findPass("", field, text)
    elif request.args.get("id", "") != "":
        student, matches, errors = findPass(request.args.get("id", ""), field, text)

    # the details step shows the fee and the new expiry for the chosen months
    preview = ""

    if student is not None and not ok and student["status"] != "Cancelled":
        preview = renewalPreview(student, months)

    return render_template(
        "renew.html",
        student=student, ok=ok, errors=errors, matches=matches,
        field=field, text=text, months=months, fee=FEE_PER_MONTH * months, preview=preview,
    )


# cancel works in the same two steps. the record is never deleted, only the
# status and the reason change
@app.route("/cancel", methods=["GET", "POST"])
def cancel():
    students = allStudents()
    student = None
    matches = []
    ok = []
    errors = []
    field = "id"
    text = ""

    if request.method == "POST" and request.form.get("reason", "") != "":
        # step 2: cancel the pass
        studentId = request.form.get("id", "")

        if request.form.get("confirm", "") != "yes":
            errors = ["Please tick the confirm box to cancel the pass."]
            student = lookupStudent(studentId, students)
        else:
            result = readOutput(runProgram("cancel", studentId, request.form.get("reason", "")))

            if result["students"]:
                student = result["students"][0]
                ok = result["ok"]
            else:
                errors = result["errors"]
    elif request.method == "POST":
        # step 1: find the pass
        field = request.form.get("field", "id")
        text = request.form.get("text", "")
        student, matches, errors = findPass("", field, text)
    elif request.args.get("id", "") != "":
        student, matches, errors = findPass(request.args.get("id", ""), field, text)

    return render_template(
        "cancel.html",
        student=student, ok=ok, errors=errors, matches=matches, field=field, text=text,
    )


@app.route("/admin-login", methods=["GET", "POST"])
def adminLogin():
    errors = []

    if request.method == "POST":
        username = request.form.get("username", "")
        password = request.form.get("password", "")

        if username == adminUser and password == adminPass:
            session["admin"] = True
            return redirect(url_for("admin"))

        errors = ["Wrong username or password"]

    return render_template("admin_login.html", errors=errors)


@app.route("/admin")
def admin():
    if "admin" not in session:
        return redirect(url_for("adminLogin"))

    students = allStudents()
    status = request.args.get("status", "All")
    q = request.args.get("q", "")
    rows = students

    if status in ("Active", "Expired", "Cancelled"):
        rows = [student for student in rows if student["displayStatus"] == status]

    # the text box looks for part of the name or the ID
    text = q.strip().lower()

    if text != "":
        rows = [student for student in rows if text in student["name"].lower() or text in student["id"].lower()]

    return render_template(
        "admin.html", rows=rows, counts=countStudents(students), status=status, q=q,
        expiring=expiringSoon(students),
    )


@app.route("/admin-download")
def adminDownload():
    if "admin" not in session:
        return redirect(url_for("adminLogin"))

    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(
        ["ID", "Name", "Age", "College", "Course", "Year", "Mobile",
         "Source", "Destination", "Status", "Issue Date", "Expiry Date", "Reason"]
    )

    for student in allStudents():
        writer.writerow([student[field] for field in FIELDS])

    return Response(
        buffer.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=students.csv"},
    )


@app.route("/logout")
def logout():
    session.pop("admin", None)
    return redirect(url_for("home"))


if __name__ == "__main__":
    app.run(debug=True)
