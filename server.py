from datetime import datetime, timedelta
import csv
import io
import os
import subprocess

from flask import Flask, Response, redirect, render_template, request, session, url_for

app = Flask(__name__)
app.secret_key = "bus-pass-demo-secret-key-123"

folder = os.path.dirname(os.path.abspath(__file__))
program = os.path.join(folder, "buspass.exe")

# simple login for demo only, not for real use (password is in the code)
adminUser = "admin"
adminPass = "buspass123"

# must match FEE_PER_MONTH in buspass.c, used for the renew preview
FEE_PER_MONTH = 200


# runs the C program with the given arguments and returns its output
# the arguments go as a list, never as a shell string, so names with spaces work
def runProgram(*args):
    try:
        result = subprocess.run([program] + list(args), capture_output=True, text=True, cwd=folder, timeout=30)
    except Exception as e:
        return "ERROR: Could not run the bus pass program: " + str(e)

    out = result.stdout

    if out == "":
        out = result.stderr

    if out == "":
        out = "No output from program"

    return out


# changes "dd-mm-yyyy" into a date, returns None when the text is not a date
def dateValue(text):
    try:
        return datetime.strptime(text, "%d-%m-%Y").date()
    except ValueError:
        return None


# true for leap years, needed when a renewal passes through 29 February
def isLeap(year):
    return year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)


# adds months to "dd-mm-yyyy" text the same way the C addMonths does:
# a day that does not exist in the short month rolls into the next month
def addMonthsText(fromDate, months):
    day, month, year = [int(part) for part in fromDate.split("-")]
    pos = month - 1 + months
    year = year + pos // 12
    month = pos % 12
    daysIn = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]

    if month == 1 and isLeap(year):
        daysIn[1] = 29

    if day > daysIn[month]:
        day = day - daysIn[month]
        month = month + 1

    return "%02d-%02d-%04d" % (day, month + 1, year)


# the expiry a pass would get when renewed today, for the preview line
# same rule as the C program: an expired pass starts counting from today
def renewalPreview(student, months):
    expiry = dateValue(student["expiryDate"])

    if expiry is None:
        return ""

    today = datetime.now().date()

    if expiry < today:
        base = today.strftime("%d-%m-%Y")
    else:
        base = student["expiryDate"]

    return addMonthsText(base, months)


# passes that are still Active and expire within the next few days
def expiringSoon(students, days=7):
    soon = []
    today = datetime.now().date()

    for student in students:
        expiry = dateValue(student["expiryDate"])

        if expiry is not None and student["displayStatus"] == "Active" \
                and today <= expiry <= today + timedelta(days=days):
            soon.append(student)

    return soon


# decides what status the page should show
# a pass only looks Expired when it is Active but the expiry date is over
def passStatus(student):
    if student["status"] == "Cancelled":
        return "Cancelled"

    expiry = dateValue(student["expiryDate"])

    if student["status"] == "Active" and expiry is not None and expiry < datetime.now().date():
        return "Expired"

    return "Active"


# turns one | line from the exe output into a small dict for the templates
def oneStudent(parts):
    student = {
        "id": parts[0],
        "name": parts[1],
        "age": parts[2],
        "college": parts[3],
        "course": parts[4],
        "year": parts[5],
        "mobile": parts[6],
        "source": parts[7],
        "destination": parts[8],
        "status": parts[9],
        "issueDate": parts[10],
        "expiryDate": parts[11],
        "reason": parts[12] if len(parts) > 12 else "",
    }
    student["displayStatus"] = passStatus(student)
    return student


# reads the exe output: student lines joined by | and OK: or ERROR: messages
def readOutput(out):
    students = []
    okMessages = []
    errorMessages = []

    for line in out.splitlines():
        parts = line.split("|")

        if parts[0].startswith("STU") and len(parts) >= 12:
            students.append(oneStudent(parts))
        elif line.startswith("OK:"):
            okMessages.append(line[3:].strip())
        elif line.startswith("ERROR:"):
            errorMessages.append(line[6:].strip())

    return {"students": students, "ok": okMessages, "errors": errorMessages}


# every student in students.txt, with the shown status filled in
def allStudents():
    return readOutput(runProgram("list"))["students"]


# the exe messages are short, turn them into friendly sentences for pages
def friendlyErrors(errors):
    nice = []

    for message in errors:
        if message.startswith("Could not run the bus pass program"):
            nice.append("The bus pass program could not run. Is buspass.exe in the project folder?")
        else:
            nice.append(message)

    return nice


def friendlyOk(okMessages):
    nice = []

    for message in okMessages:
        if message.startswith("Cancelled "):
            nice.append("Pass cancelled (" + message[10:] + ").")
        else:
            nice.append(message)

    return nice


# finds one student by exact ID, returns None when not found
def lookupStudent(studentId, students=None):
    if students is None:
        students = allStudents()

    for student in students:
        if student["id"] == studentId:
            return student

    return None


# small counts used by the home page and the admin page
def countStudents(students):
    counts = {"total": len(students), "active": 0, "expired": 0, "cancelled": 0}

    for student in students:
        status = student["displayStatus"]

        if status == "Active":
            counts["active"] = counts["active"] + 1
        elif status == "Expired":
            counts["expired"] = counts["expired"] + 1
        elif status == "Cancelled":
            counts["cancelled"] = counts["cancelled"] + 1

    return counts


@app.route("/")
def home():
    students = allStudents()
    return render_template("home.html", counts=countStudents(students))


@app.route("/register", methods=["GET", "POST"])
def register():
    student = None
    errors = []

    if request.method == "POST":
        form = request.form
        out = runProgram(
            "register",
            form.get("name", ""),
            form.get("age", ""),
            form.get("college", ""),
            form.get("course", ""),
            form.get("year", ""),
            form.get("mobile", ""),
            form.get("source", ""),
            form.get("destination", ""),
        )
        result = readOutput(out)

        if len(result["students"]) > 0 and len(result["errors"]) == 0:
            student = result["students"][0]
        else:
            errors = result["errors"]

    return render_template("register.html", student=student, errors=errors, form=request.form)


@app.route("/search", methods=["GET", "POST"])
def search():
    results = []
    field = ""
    text = ""

    if request.method == "POST":
        field = request.form.get("field", "name")
        text = request.form.get("text", "")

        if text.strip() != "":
            results = readOutput(runProgram("search", field, text))["students"]

    return render_template("search.html", results=results, field=field, text=text)


# the renew page works in two steps:
# step 1: find the pass by ID, name or course
# step 2: choose months and renew. table row links jump straight to step 2
@app.route("/renew", methods=["GET", "POST"])
def renew():
    students = allStudents()
    okMessages = []
    errorMessages = []
    matches = []
    student = None
    field = "id"
    text = ""
    months = 1
    preview = ""

    if request.method == "POST" and request.form.get("months", "") != "":
        # step 2: renew the pass for the chosen months
        studentId = request.form.get("id", "")

        try:
            months = int(request.form.get("months", "1"))
        except ValueError:
            months = 1

        result = readOutput(runProgram("renew", studentId, str(months)))

        if len(result["students"]) > 0:
            student = result["students"][0]
            okMessages = friendlyOk(result["ok"])
        else:
            errorMessages = friendlyErrors(result["errors"])
            student = lookupStudent(studentId, students)
    elif request.method == "POST":
        # step 1: find by the chosen field
        field = request.form.get("field", "id")
        text = request.form.get("text", "")

        if text.strip() == "":
            errorMessages = ["Please type what to search for."]
        else:
            matches = readOutput(runProgram("search", field, text))["students"]

            if len(matches) == 1:
                # one match goes straight to the details step
                student = matches[0]
                matches = []

                if student["status"] == "Cancelled":
                    errorMessages = ["This pass is cancelled, cancelled passes cannot be renewed"]

            elif len(matches) == 0:
                errorMessages = ["No student found for those details."]
    else:
        # a table link lands here: /renew?id=STU1002
        studentId = request.args.get("id", "")

        if studentId != "":
            student = lookupStudent(studentId, students)

            if student is None:
                errorMessages = ["No student found with ID " + studentId]
            elif student["status"] == "Cancelled":
                errorMessages = ["This pass is cancelled, cancelled passes cannot be renewed"]

    # the details step shows the fee and the expiry preview for the chosen months
    if student is not None and len(okMessages) == 0 and student["status"] != "Cancelled":
        preview = renewalPreview(student, months)

    return render_template(
        "renew.html",
        student=student, ok=okMessages, errors=errorMessages, matches=matches,
        field=field, text=text, months=months, fee=FEE_PER_MONTH * months, preview=preview,
    )


# the cancel page works like the renew page: find the pass first,
# then confirm with a reason. the record is never deleted
@app.route("/cancel", methods=["GET", "POST"])
def cancel():
    students = allStudents()
    okMessages = []
    errorMessages = []
    matches = []
    student = None
    field = "id"
    text = ""

    if request.method == "POST" and request.form.get("reason", "") != "":
        # step 2: cancel the pass with the chosen reason
        studentId = request.form.get("id", "")
        reason = request.form.get("reason", "")

        if request.form.get("confirm", "") != "yes":
            errorMessages = ["Please tick the confirm box to cancel the pass."]
            student = lookupStudent(studentId, students)
        else:
            result = readOutput(runProgram("cancel", studentId, reason))

            if len(result["students"]) > 0:
                student = result["students"][0]
                okMessages = friendlyOk(result["ok"])
            else:
                errorMessages = friendlyErrors(result["errors"])
    elif request.method == "POST":
        # step 1: find by the chosen field
        field = request.form.get("field", "id")
        text = request.form.get("text", "")

        if text.strip() == "":
            errorMessages = ["Please type what to search for."]
        else:
            matches = readOutput(runProgram("search", field, text))["students"]

            if len(matches) == 1:
                # one match goes straight to the details step
                student = matches[0]
                matches = []

                if student["status"] == "Cancelled":
                    errorMessages = ["This pass is already cancelled"]

            elif len(matches) == 0:
                errorMessages = ["No student found for those details."]
    else:
        # a table link lands here: /cancel?id=STU1002
        studentId = request.args.get("id", "")

        if studentId != "":
            student = lookupStudent(studentId, students)

            if student is None:
                errorMessages = ["No student found with ID " + studentId]
            elif student["status"] == "Cancelled":
                errorMessages = ["This pass is already cancelled"]

    return render_template(
        "cancel.html",
        student=student, ok=okMessages, errors=errorMessages, matches=matches, field=field, text=text,
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
        rows = [student for student in students if student["displayStatus"] == status]

    # the text box filters by part of the name or the ID
    if q.strip() != "":
        lower = q.strip().lower()
        rows = [student for student in rows
                if lower in student["name"].lower() or lower in student["id"].lower()]

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
        writer.writerow(
            [student["id"], student["name"], student["age"], student["college"],
             student["course"], student["year"], student["mobile"], student["source"],
             student["destination"], student["status"], student["issueDate"],
             student["expiryDate"], student["reason"]]
        )

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
