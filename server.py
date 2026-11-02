from datetime import datetime
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


# finds one student by exact ID, returns None when not found
def lookupStudent(studentId):
    for student in allStudents():
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


@app.route("/renew", methods=["GET", "POST"])
def renew():
    student = None
    okMessages = []
    errorMessages = []
    studentId = ""

    if request.method == "POST":
        studentId = request.form.get("id", "")
        monthsText = request.form.get("months", "")

        if monthsText == "":
            # step 1: only the ID was sent, so find the student first
            student = lookupStudent(studentId)

            if student is None:
                errorMessages = ["No student found with ID " + (studentId if studentId != "" else "(empty)")]
            elif student["status"] == "Cancelled":
                errorMessages = ["This pass is cancelled, cancelled passes cannot be renewed"]
                student = None
        else:
            # step 2: ID and months together
            out = runProgram("renew", studentId, monthsText)
            result = readOutput(out)

            if len(result["students"]) > 0:
                student = result["students"][0]
                okMessages = result["ok"]
            else:
                errorMessages = result["errors"]
                student = lookupStudent(studentId)
    else:
        # an admin row link lands here: /renew?id=STU1002
        studentId = request.args.get("id", "")

        if studentId != "":
            student = lookupStudent(studentId)

            if student is None:
                errorMessages = ["No student found with ID " + studentId]
            elif student["status"] == "Cancelled":
                errorMessages = ["This pass is cancelled, cancelled passes cannot be renewed"]
                student = None

    return render_template(
        "renew.html", student=student, ok=okMessages, errors=errorMessages, studentId=studentId
    )


@app.route("/cancel", methods=["GET", "POST"])
def cancel():
    student = None
    okMessages = []
    errorMessages = []
    studentId = ""

    if request.method == "POST":
        studentId = request.form.get("id", "")
        reason = request.form.get("reason", "")

        if reason == "":
            # step 1: only the ID was sent
            student = lookupStudent(studentId)

            if student is None:
                errorMessages = ["No student found with ID " + (studentId if studentId != "" else "(empty)")]
            elif student["status"] == "Cancelled":
                errorMessages = ["This pass is already cancelled"]
                student = None
        else:
            # step 2: ID and reason together
            out = runProgram("cancel", studentId, reason)
            result = readOutput(out)

            if len(result["students"]) > 0:
                student = result["students"][0]
                okMessages = result["ok"]
            else:
                errorMessages = result["errors"]
    else:
        # an admin row link lands here: /cancel?id=STU1002
        studentId = request.args.get("id", "")

        if studentId != "":
            student = lookupStudent(studentId)

            if student is None:
                errorMessages = ["No student found with ID " + studentId]
            elif student["status"] == "Cancelled":
                errorMessages = ["This pass is already cancelled"]
                student = None

    return render_template(
        "cancel.html", student=student, ok=okMessages, errors=errorMessages, studentId=studentId
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
    rows = students

    if status in ("Active", "Expired", "Cancelled"):
        rows = [student for student in students if student["displayStatus"] == status]

    return render_template(
        "admin.html", rows=rows, counts=countStudents(students), status=status
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
